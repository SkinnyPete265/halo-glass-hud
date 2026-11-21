"""Poll GitHub for owner-approved releases and build them on the local PC."""

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPOSITORY = "SkinnyPete265/halo-glass-hud"
OWNER = REPOSITORY.split("/")[0]
BRANCH = "main"
REMOTE = f"https://github.com/{REPOSITORY}.git"
WORKFLOW = "local-release.yml"
ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "local" / "release-worker"
SHA = re.compile(r"[0-9a-f]{40}")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TITLE = re.compile(r"Halo local release ([0-9a-f]{40}) (package|install|install-and-smoke)")
INPUTS = (
    Path("project.local.json"),
    Path("native/reference/native-controls.erpk"),
    Path("native/reference/drs-template.bin"),
)


def now():
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def enrolled_job(run):
    match = TITLE.fullmatch(run.get("display_title", ""))
    publisher = run.get("head_repository") or {}
    if (
        match
        and run.get("event") == "workflow_dispatch"
        and run.get("head_branch") == BRANCH
        and publisher.get("full_name", "").casefold() == REPOSITORY.casefold()
        and (run.get("actor") or {}).get("login", "").casefold() == OWNER.casefold()
        and (run.get("triggering_actor") or {}).get("login", "").casefold() == OWNER.casefold()
        and SHA.fullmatch(run.get("head_sha", ""))
        and type(run.get("id")) is int
    ):
        return {
            "run": run["id"],
            "workflow_commit": run["head_sha"],
            "commit": match[1],
            "mode": match[2],
        }
    return None


def remote_runs(since):
    base = f"https://api.github.com/repos/{REPOSITORY}/actions/workflows/{WORKFLOW}/runs"
    parameters = {
        "branch": BRANCH, "event": "workflow_dispatch", "actor": OWNER,
        "created": f">={since}", "per_page": 100,
    }
    runs = []
    for page in range(1, 11):
        request = Request(
            f"{base}?{urlencode(dict(parameters, page=page))}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "Halo-HUD-release-worker"},
        )
        with urlopen(request, timeout=20) as response:
            batch = json.load(response)["workflow_runs"]
        runs.extend(batch)
        if len(batch) < 100:
            return sorted(runs, key=lambda run: (run["created_at"], run["id"]))
    raise RuntimeError("Too many workflow runs since enrollment. Review the queue before resetting it.")


def git(checkout, *args):
    subprocess.run(["git", "-C", str(checkout), *args], check=True, creationflags=NO_WINDOW)


def prepare(checkout, job):
    if not (checkout / ".git").is_dir():
        subprocess.run(
            ["git", "clone", "--no-checkout", REMOTE, str(checkout)],
            check=True, creationflags=NO_WINDOW,
        )
    git(checkout, "fetch", "--no-tags", REMOTE, f"refs/heads/{BRANCH}")
    git(checkout, "merge-base", "--is-ancestor", job["workflow_commit"], "FETCH_HEAD")
    git(checkout, "fetch", "--no-tags", REMOTE, job["commit"])
    git(checkout, "switch", "--detach", job["commit"])
    changes = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain"], text=True, creationflags=NO_WINDOW,
    )
    if changes:
        raise ValueError("The release checkout has uncommitted changes.")
    for relative in INPUTS:
        tracked = subprocess.check_output(
            ["git", "-C", str(checkout), "ls-files", "--", relative.as_posix()],
            text=True, creationflags=NO_WINDOW,
        )
        if tracked:
            raise ValueError(f"The requested commit tracks local input {relative}.")
        target = checkout / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def execute(home, job, state, status_path):
    checkout = home / "checkout"
    run_path = home / "jobs" / str(job["run"])
    run_path.mkdir(exist_ok=True)
    result_path = run_path / "result.json"
    if state == "waiting_for_game_close":
        query = subprocess.run(
            ["tasklist.exe", "/FI", "IMAGENAME eq F1_25.exe", "/FO", "CSV", "/NH"],
            check=True, capture_output=True, text=True, creationflags=NO_WINDOW,
        )
        if '"f1_25.exe"' in query.stdout.casefold():
            return
    result_path.unlink(missing_ok=True)
    write(status_path, dict(job, status="running", updated=now()))
    try:
        prepare(checkout, job)
        command = [
            str(Path(sys.executable).with_name("python.exe")), "-B",
            "tools/project.py", "release", "--native",
            "--result", str(result_path),
        ]
        if job["mode"] != "package":
            command.append("--install")
        if job["mode"] == "install-and-smoke":
            command.append("--smoke")
        with (run_path / "release.log").open("ab") as log:
            result = subprocess.run(
                command, cwd=checkout, stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW,
            )
        release = read(result_path) if result_path.is_file() else {}
        status = release.get("status", "failed")
        if result.returncode and status not in ("waiting_for_game_close", "smoke_failed"):
            status = "failed"
        write(status_path, dict(job, status=status, updated=now(), release=release))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        write(status_path, dict(job, status="failed", updated=now(), error=str(error)))


def process(home, runs):
    for run in runs:
        job = enrolled_job(run)
        if job is None:
            continue
        path = home / "jobs" / f"{job['run']}.json"
        saved = read(path) if path.is_file() else {}
        state = saved.get("status")
        if state == "running":
            write(path, dict(saved, status="interrupted", updated=now()))
            continue
        if state not in (None, "waiting_for_game_close"):
            continue
        if run["status"] != "completed":
            return
        if run["conclusion"] == "success":
            execute(home, job, state, path)
            return


def poll(home):
    import msvcrt

    with (home / "worker.lock").open("a+b") as lock:
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return
        try:
            runs = remote_runs(read(home / "enrollment.json")["since"])
            process(home, runs)
            write(home / "poll.json", {"updated": now(), "status": "ok"})
        except (OSError, ValueError, RuntimeError) as error:
            status = "workflow_not_found" if isinstance(error, HTTPError) and error.code == 404 else "failed"
            write(home / "poll.json", {"updated": now(), "status": status, "error": str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("setup", "poll", "status"))
    args = parser.parse_args()
    if args.action == "setup":
        for relative in INPUTS:
            if not (ROOT / relative).is_file():
                parser.error(f"Missing local input {relative}")
        (HOME / "jobs").mkdir(parents=True, exist_ok=True)
        enrollment = HOME / "enrollment.json"
        if not enrollment.exists():
            write(enrollment, {"since": now()})
        print(HOME)
    elif args.action == "poll":
        poll(HOME)
    else:
        paths = [HOME / "poll.json", *sorted((HOME / "jobs").glob("*.json"))]
        print(json.dumps([read(path) for path in paths if path.is_file()], indent=2))


if __name__ == "__main__":
    main()
