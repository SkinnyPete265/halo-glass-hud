"""Refresh generated release facts while preserving the owner's working notes."""

import argparse
import json
from pathlib import Path
import subprocess
from project_config import local_settings

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- BEGIN GENERATED RELEASE STATE -->"
END = "<!-- END GENERATED RELEASE STATE -->"


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def source_checkout(root):
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root, capture_output=True, text=True,
        )
    except FileNotFoundError:
        return {"source_commit": None, "tracked_edits": None}
    return {
        "source_commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "tracked_edits": len(dirty.stdout.splitlines()) if dirty.returncode == 0 else None,
    }


def facts(root, settings):
    source = read_json(root / "swofty.json")
    profile = settings.get("profile", "default")
    installed = {}
    if settings.get("data_dir") and source.get("id"):
        installed = read_json(
            Path(settings["data_dir"]) / "addons" / source["id"] / "swofty.json"
        )
    version = installed.get("version")
    report = (
        read_json(root / "build" / f"install-report-v{version}.json") if version else {}
    )
    report_profile = report.get("profile")
    if not report_profile and report.get("cache"):
        report_profile = Path(report["cache"]).parent.name
    if report.get("version") != version or (report_profile and report_profile != profile):
        report = {}
    validation = read_json(root / "runtime/validation.json")
    checkout = source_checkout(root)
    return {
        **checkout,
        "source_version": source.get("version"),
        "installed_version": version,
        "profile": profile,
        "commit": checkout["source_commit"][:7] if checkout["source_commit"] else "unavailable",
        "last_install_verification": report,
        "prepared_runtime": bool(validation),
        "report_path": f"build/install-report-v{version}.json" if report else None,
    }


def update(root=ROOT, settings=None):
    settings = local_settings() if settings is None else settings
    value = facts(root, settings)
    report = value["last_install_verification"]
    lines = [
        BEGIN,
        "## Generated release facts",
        "",
        "- Source version " + str(value["source_version"]),
        "- Installed version " + str(value["installed_version"] or "unavailable"),
        "- SWOFTY profile " + value["profile"],
        "- Source commit " + value["commit"],
        "- Pending tracked source edits "
        + (str(value["tracked_edits"]) if value["tracked_edits"] is not None else "unavailable"),
        "- Last recorded in-game status "
        + str(report.get("in_game_test", "unverified")),
    ]
    if report:
        lines.extend(
            [
                "- Last verified cache " + str(report.get("cache")),
                "- Last installation check "
                + str(report.get("installed_files"))
                + " files and "
                + str(report.get("verified_resource_copies"))
                + " cached resource copies",
                "- Verification report " + value["report_path"],
            ]
        )
    lines.extend(
        [
            "",
            "These facts describe saved verification reports. New source edits require their own release checks.",
            END,
        ]
    )
    block = "\n".join(lines)
    target = root / "PROJECT_STATE.md"
    existing = (
        target.read_text(encoding="utf-8") if target.exists() else "# Project state\n"
    )
    if BEGIN in existing and END in existing:
        before, remainder = existing.split(BEGIN, 1)
        _, after = remainder.split(END, 1)
        result = before + block + after
    else:
        result = existing.rstrip() + "\n\n" + block + "\n"
    pending = target.with_suffix(".tmp")
    pending.write_text(result, encoding="utf-8")
    pending.replace(target)
    output = root / "build/release-state.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return value


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(update(), indent=2))
