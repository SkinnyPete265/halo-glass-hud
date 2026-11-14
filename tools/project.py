"""Reusable project status, checks and release orchestration."""

import argparse
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from log_summary import save_summary
from release_state import update as update_state
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
        ["tasklist", "/FI", "IMAGENAME eq F1_25.exe", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=True,
    )
    return "f1_25.exe" in result.stdout.lower()


def preserve_installed(settings, manifest):
    installed = Path(settings["data_dir"]) / "addons" / manifest["id"]
    if not (installed / "swofty.json").exists():
        return None
    version = json.loads((installed / "swofty.json").read_text(encoding="utf-8"))[
        "version"
    ]
    backup = ROOT / "build" / ("rollback-v" + version)
    target = backup / "dist" / (manifest["id"] + ".swoftyaddon")
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


def release(settings, manifest, args):
    timings = Timings(ROOT / "build/release-timings.json")
    version = manifest["version"]
    command = [sys.executable, "-B", "tools/build.py", "--compose", "--skip-preview"]
    if args.native:
        command.append("--native")
    compose_log = ROOT / "build" / ("compose-v" + version + ".log")
    with timings.stage("artwork and composition"):
        run(command, compose_log)
    with timings.stage("packaging"):
        run([sys.executable, "-B", "tools/package.py"])
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
        raise RuntimeError(
            "Package ready. Close F1 25 normally, then repeat release --install. Verified outputs will be reused."
        )
    profile = settings.get("profile", "default")
    addon = manifest["id"]
    store = Path(settings["data_dir"])
    profile_path = store / "profiles" / (profile + ".json")
    snapshot = ROOT / "build" / f"profile-before-{profile}-v{version}.json"
    shutil.copy2(profile_path, snapshot)
    cli = launcher_command(settings["launcher"], settings["data_dir"]) + [
        "--profile",
        profile,
    ]
    package = ROOT / "dist" / (addon + ".swoftyaddon")
    rollback = None
    with timings.stage("installation"):
        if installed_matches(package, store / "addons" / addon):
            print("Reused matching installed addon files.")
        else:
            rollback = preserve_installed(settings, manifest)
            run(cli + ["addons", "install", str(package)])
        if profile_enabled(profile_path, addon):
            print("Addon is already enabled in the selected profile.")
        else:
            run(cli + ["addons", "enable", addon])
    log = ROOT / "build" / ("swofty-build-v" + version + ".log")
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
            ]
        )
    save_summary(log, ROOT / "build/log-baselines/swofty-build.json", accept=True)
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
        "action", choices=("status", "check", "release", "state", "logs", "tune")
    )
    parser.add_argument(
        "path", nargs="?", type=Path, help="Log file for the logs action"
    )
    parser.add_argument("--port", type=int, default=8766, help="Local tuning port")
    parser.add_argument(
        "--install", action="store_true", help="Install and verify a requested release"
    )
    parser.add_argument(
        "--native", action="store_true", help="Rebuild DLLs and run native tests"
    )
    args = parser.parse_args()
    if args.action != "release" and (args.install or args.native):
        parser.error("--install and --native apply to release")
    if args.path and args.action != "logs":
        parser.error("A file path applies to logs")
    if args.action == "tune":
        from tune_server import serve

        serve(port=args.port)
        return
    if args.action == "state":
        print(json.dumps(update_state(), indent=2))
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
        run([sys.executable, "-B", "tools/test_workflow.py"])
        if not (ROOT / "registry/hud.json").exists():
            run([sys.executable, "-B", "tools/build.py", "--skip-preview"])
        run([sys.executable, "-B", "tools/test_drs_battery.py"])
        run([sys.executable, "-B", "tools/test_devtools.py"])
        return
    settings = local_settings()
    manifest = json.loads((ROOT / "swofty.json").read_text(encoding="utf-8"))
    required = ("launcher", "data_dir", "game")
    if args.install and any(not settings.get(key) for key in required):
        parser.error("Configure launcher, data_dir and game in project.local.json")
    (ROOT / "build").mkdir(exist_ok=True)
    release(settings, manifest, args)


if __name__ == "__main__":
    try:
        main()
    finally:
        if sys.argv[1:2] == ["release"]:
            try:
                update_state()
            except Exception as error:
                print("Release state update failed. " + str(error), file=sys.stderr)
