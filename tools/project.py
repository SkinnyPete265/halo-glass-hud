"""Reusable project status, checks and release orchestration."""

import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
from build_inputs import file_hash
from compatibility import build_environment_identity
from log_summary import save_summary
from release_state import read_json, update as update_state
from project_config import local_settings, launcher_command
from stage_timing import Timings

ROOT = Path(__file__).resolve().parents[1]


def run(command, log=None):
    if log:
        with log.open("w", encoding="utf-8") as output:
            result = subprocess.run(
                command, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT
            )
        baseline = ROOT / "build/log-baselines" / (log.stem.split("-v")[0] + ".json")
        print(json.dumps(save_summary(log, baseline, result.returncode), indent=2))
        if result.returncode:
            raise RuntimeError("Command failed. See " + str(log))
    else:
        subprocess.run(command, cwd=ROOT, check=True)


def game_running():
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-Process -Name F1_25 -ErrorAction SilentlyContinue).Count",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip() not in ("", "0")


def preserve_installed(settings, manifest):
    installed = Path(settings["data_dir"]) / "addons" / manifest["id"]
    if not (installed / "swofty.json").exists():
        return None
    version = json.loads((installed / "swofty.json").read_text(encoding="utf-8"))[
        "version"
    ]
    archive_root = ROOT / "local/archive/rollbacks"
    backup = archive_root / ("rollback-v" + version)
    target = backup / "dist" / (manifest["id"] + ".swoftyaddon")
    if target.exists() and not installed_matches(target, installed):
        digest = hashlib.sha256()
        for path in sorted(item for item in installed.rglob("*") if item.is_file()):
            digest.update(path.relative_to(installed).as_posix().encode("utf-8"))
            digest.update(b"\0")
            with path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            digest.update(b"\0")
        backup = archive_root / ("rollback-v" + version + "-" + digest.hexdigest()[:12])
        target = backup / "dist" / (manifest["id"] + ".swoftyaddon")
        if target.exists() and not installed_matches(target, installed):
            raise RuntimeError("Existing rollback snapshot does not match the installed addon")
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        pending = target.with_suffix(".tmp")
        try:
            with zipfile.ZipFile(pending, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(installed.rglob("*")):
                    if path.is_file():
                        archive.write(path, path.relative_to(installed).as_posix())
            with zipfile.ZipFile(pending) as archive:
                if archive.testzip():
                    raise RuntimeError("Rollback archive CRC failed")
            if not installed_matches(pending, installed):
                raise RuntimeError("Rollback archive does not match the installed addon")
            pending.replace(target)
        finally:
            pending.unlink(missing_ok=True)
    return backup


def installed_matches(package, installed):
    """Compare the installed tree with the package already verified by packaging."""
    try:
        with zipfile.ZipFile(package) as archive:
            names = {name for name in archive.namelist() if not name.endswith("/")}
            actual = {
                path.relative_to(installed).as_posix()
                for path in installed.rglob("*")
                if path.is_file()
            }
            return names == actual and all(
                (installed / name).read_bytes() == archive.read(name) for name in names
            )
    except (OSError, ValueError, zipfile.BadZipFile):
        return False


def profile_enabled(path, addon):
    profile = json.loads(path.read_text(encoding="utf-8"))
    return any(
        item["id"] == addon and item.get("enabled", False)
        for item in profile.get("addons", [])
    )


def release(settings, manifest, args, *, result_path=None):
    runs = ROOT / "build/releases"
    runs.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="v" + manifest["version"] + "-", dir=runs))
    timings = Timings(folder / "release-timings.json")
    record = {
        "version": manifest["version"],
        "profile": settings.get("profile", "default"),
        "status": "failed",
    }
    try:
        if args.install and settings.get("data_dir"):
            profile = record["profile"]
            profile_file = Path(settings["data_dir"]) / "profiles" / f"{profile}.json"
            if profile_file.is_file() and profile_enabled(profile_file, "nick.f1-2026-halo"):
                warning = (
                    f"Project Halo (nick.f1-2026-halo) is enabled in profile {profile!r} "
                    "and can override Halo Glass dial resources. Disable it in SWOFTY "
                    "if exact-cache verification reports a conflict."
                )
                record["profile_warning"] = warning
                print(f"Warning: {warning}", file=sys.stderr, flush=True)
        prepare_release(settings, manifest, args, folder, timings, record)
        record["status"] = "cache_verified" if args.install else "packaged"
    except Exception as error:
        record["error"] = str(error)
        raise
    finally:
        record["evidence"] = str(folder)
        result = json.dumps(record, indent=2) + "\n"
        (folder / "release.json").write_text(result, encoding="utf-8")
        if result_path:
            pending = result_path.with_suffix(".tmp")
            pending.write_text(result, encoding="utf-8")
            pending.replace(result_path)
        if timings.path.exists():
            shutil.copy2(timings.path, ROOT / "build/release-timings.json")
        print(f"Release evidence: {folder}")


def prepare_release(settings, manifest, args, folder, timings, record):
    version = manifest["version"]
    addon = manifest["id"]
    command = [sys.executable, "-B", "tools/build.py", "--compose"]
    if args.native:
        command.append("--native")
    compose_log = folder / ("compose-v" + version + ".log")
    with timings.stage("artwork and composition"):
        run(command, compose_log)
    for name in ("build/build-timings.json", "runtime/validation.json"):
        path = ROOT / name
        if path.exists():
            shutil.copy2(path, folder / path.name)
    record["source_inputs_sha256"] = read_json(folder / "validation.json").get("source_inputs_sha256")
    identity = build_environment_identity(settings)
    record["game"] = identity["game"]
    record["launcher"] = identity["launcher"]
    record["launcher"]["version"] = subprocess.check_output(
        [identity["launcher"]["path"], "--version"], cwd=ROOT, text=True
    ).strip()
    package = ROOT / "dist" / (addon + ".swoftyaddon")
    with timings.stage("packaging"):
        run([sys.executable, "-B", "tools/package.py"])
    record["package_sha256"] = file_hash(package)
    artifact = folder / f"{addon}-{version}.swoftyaddon"
    shutil.copy2(package, artifact)
    if file_hash(artifact) != record["package_sha256"]:
        raise RuntimeError("The versioned package differs from the verified package.")
    record["package"] = str(artifact)
    composition_reused = (
        "Reused native composition and validation"
        in compose_log.read_text(encoding="utf-8")
    )
    save_summary(
        compose_log,
        ROOT / "build/log-baselines/compose.json",
        accept=not composition_reused,
    )
    if not args.install:
        return
    if game_running():
        record["status"] = "waiting_for_game_close"
        raise RuntimeError(
            "Package ready. Close F1 25 normally, then repeat release --install. Verified outputs will be reused."
        )
    profile = record["profile"]
    store = Path(settings["data_dir"])
    profile_path = store / "profiles" / (profile + ".json")
    snapshot = folder / "profile-before.json"
    shutil.copy2(profile_path, snapshot)
    cli = launcher_command(settings["launcher"], settings["data_dir"]) + [
        "--profile",
        profile,
    ]
    rollback = None
    with timings.stage("installation"):
        # Keep a byte-exact rollback snapshot even when SWOFTY already has the
        # requested package. Same-version prior snapshots may contain different art.
        rollback = preserve_installed(settings, manifest)
        record["rollback"] = str(rollback) if rollback else None
        if installed_matches(package, store / "addons" / addon):
            print("Reused matching installed addon files.")
        else:
            run(cli + ["addons", "install", str(package)])
        if profile_enabled(profile_path, addon):
            print("Addon is already enabled in the selected profile.")
        else:
            run(cli + ["addons", "enable", addon])
    log = folder / ("swofty-build-v" + version + ".log")
    with timings.stage("SWOFTY cache"):
        run(cli + ["build", "--game", settings["game"]], log)
    matches = re.findall(
        r"^overlay [0-9a-f]+: (.+)$",
        log.read_text(encoding="utf-8", errors="replace"),
        re.MULTILINE,
    )
    if not matches:
        raise RuntimeError("Build completed. Inspect the cache path in " + str(log))
    cache = Path(matches[-1].strip())
    record["cache"] = str(cache)
    try:
        with timings.stage("installation verification"):
            run(
                [
                    sys.executable,
                    "-B",
                    "tools/verify_install.py",
                    "--cache",
                    str(cache),
                    "--launcher",
                    settings["launcher"],
                    "--data-dir",
                    str(store),
                    "--profile",
                    profile,
                    "--profile-snapshot",
                    str(snapshot),
                ]
            )
    except (subprocess.CalledProcessError, RuntimeError):
        conflict_log = folder / "conflicts.log"
        try:
            run(cli + ["conflicts"], conflict_log)
        except (OSError, RuntimeError):
            pass  # Keep the original verification failure if diagnostics also fail.
        record["conflict_log"] = str(conflict_log)
        print(f"SWOFTY profile conflict report: {conflict_log}", file=sys.stderr)
        raise
    save_summary(log, ROOT / "build/log-baselines/swofty-build.json", accept=True)
    report = ROOT / "build" / f"install-report-v{version}.json"
    shutil.copy2(report, folder / report.name)
    print(
        json.dumps(
            {
                "version": version,
                "cache": str(cache),
                "rollback": str(rollback),
                "timings": str(timings.path),
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("status", "check", "release", "state", "logs", "notes")
    )
    parser.add_argument(
        "path", nargs="?", type=Path, help="Log file for the logs action"
    )
    parser.add_argument(
        "--install", action="store_true", help="Install and verify a requested release"
    )
    parser.add_argument(
        "--native", action="store_true", help="Rebuild DLLs and run native tests"
    )
    parser.add_argument("--result", type=Path, help="Also write the release record to this path")
    args = parser.parse_args()
    if args.action != "release" and (args.install or args.native or args.result):
        parser.error("--install, --native and --result apply to release")
    if args.path and args.action != "logs":
        parser.error("A file path applies to logs")
    if args.action == "state":
        print(json.dumps(update_state(), indent=2))
        return
    if args.action == "notes":
        from package import release_notes

        manifest = read_json(ROOT / "swofty.json")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        print(release_notes(changelog, manifest["version"]))
        return
    if args.action == "logs":
        if args.path is None:
            parser.error("Supply the log file")
        baseline = (
            ROOT / "build/log-baselines" / (args.path.stem.split("-v")[0] + ".json")
        )
        print(json.dumps(save_summary(args.path, baseline), indent=2))
        return
    if args.action == "status":
        settings = local_settings()
        manifest = json.loads((ROOT / "swofty.json").read_text(encoding="utf-8"))
        inputs = [
            "native/reference/native-controls.erpk",
            "native/reference/drs-template.bin",
        ]
        print(
            json.dumps(
                {
                    "root": str(ROOT),
                    "version": manifest["version"],
                    "profile": settings.get("profile", "default"),
                    "local_configuration": (ROOT / "project.local.json").exists(),
                    "native_inputs": {name: (ROOT / name).exists() for name in inputs},
                    "game_running": game_running(),
                },
                indent=2,
            )
        )
        return
    if args.action == "check":
        (ROOT / "build").mkdir(exist_ok=True)
        run([sys.executable, "-B", "tests/test_workflow.py"])
        run([sys.executable, "-B", "tests/test_compatibility.py"])
        run([sys.executable, "-B", "tests/test_local_release.py"])
        if not (ROOT / "registry/hud.json").exists():
            run([sys.executable, "-B", "tools/build.py"])
        from validate_registry import validate_registry

        validate_registry(read_json(ROOT / "swofty.json")["id"])
        run([sys.executable, "-B", "tests/test_composition_crop.py"])
        run([sys.executable, "-B", "tests/test_wing_edge_stitch.py"])
        run([sys.executable, "-B", "tests/test_drs_battery.py"])
        run([sys.executable, "-B", "tests/test_devtools.py"])
        return
    settings = local_settings()
    manifest = json.loads((ROOT / "swofty.json").read_text(encoding="utf-8"))
    required = ("launcher", "data_dir", "game")
    if args.install and any(not settings.get(key) for key in required):
        parser.error("Configure launcher, data_dir and game in project.local.json")
    (ROOT / "build").mkdir(exist_ok=True)
    release(settings, manifest, args, result_path=args.result)


if __name__ == "__main__":
    try:
        main()
    finally:
        if sys.argv[1:2] == ["release"]:
            try:
                update_state()
            except Exception as error:
                print("Release state update failed. " + str(error), file=sys.stderr)
