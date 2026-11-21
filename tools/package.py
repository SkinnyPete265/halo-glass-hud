"""Package validated, precomposed HUD overlays plus complete authoring sources."""
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile
import tempfile
from compatibility import runtime_inputs_fingerprint

ROOT = Path(__file__).resolve().parents[1]

SOURCE_FILES = (
    "AGENTS.md", "project.local.example.json", "style.json",
    "assets/fonts/Saira/OFL.txt", "assets/fonts/Saira/Saira.ttf",
    "native/include/LICENSE", "native/include/source.json",
    "native/reference/drs-template.bin", "native/reference/native-controls.erpk",
    "native/reference/native-controls-source.json", "native/reference/sector_reader.cpp",
    "tests/test_compatibility.py", "tests/test_composition_crop.py", "tests/test_devtools.py",
    "tests/test_drs_battery.py", "tests/test_local_release.py", "tests/test_wing_edge_stitch.py",
    "tests/test_workflow.py",
    "tools/asset_only.py", "tools/build.py", "tools/build_inputs.py", "tools/check_time_trial.py",
    "tools/compatibility.py", "tools/extract_native_reference.py", "tools/f126_interop.py",
    "tools/fetch_sdk.py", "tools/local_release.py", "tools/log_summary.py", "tools/native_interop.py",
    "tools/package.py", "tools/prepare_runtime.py", "tools/project.py",
    "tools/project_config.py", "tools/Register-HaloReleaseWorker.ps1", "tools/release_state.py",
    "tools/stage_timing.py",
    "tools/validate_registry.py", "tools/verify_install.py", "tools/formats/SWOFTY-LICENSE",
)
SOURCE_PATTERNS = (
    "halo/*.py", "native/src/*.cpp", "native/src/*.hpp", "native/test/*.cpp",
    "native/include/**/*.h", "native/include/**/*.hpp", "tools/formats/*.py",
)


def authored_sources(registry):
    paths = {name for name in SOURCE_FILES if (ROOT / name).is_file()}
    for pattern in SOURCE_PATTERNS:
        paths.update(path.relative_to(ROOT).as_posix() for path in ROOT.glob(pattern)
                     if path.is_file())
    paths.add("registry/hud.json")
    for dial in registry["hud.element"].values():
        for sprite in dial["sprites"].values():
            name = sprite["png"]
            path = PurePosixPath(name)
            if path.parent != PurePosixPath("art") or path.suffix != ".png" or "\\" in name:
                raise ValueError(f"Invalid packaged HUD sprite path: {name}")
            paths.add(path.as_posix())
    return paths


def release_notes(changelog, version):
    """Select one release section without its version heading."""
    sections = re.split(r"^##[ \t]+([^\n]+)\n", changelog, flags=re.MULTILINE)
    matches = [body.strip() for heading, body in zip(sections[1::2], sections[2::2])
               if heading.strip() == version]
    if len(matches) != 1 or not matches[0]:
        raise ValueError(f"CHANGELOG.md needs one nonempty section headed '## {version}'")
    return matches[0]


def package():
    source_manifest = json.loads((ROOT / "swofty.json").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    release_notes(changelog, source_manifest["version"])
    validation = json.loads((ROOT / "runtime/validation.json").read_text())
    registry = (ROOT / "registry/hud.json").read_bytes()
    registry_hash = hashlib.sha256(registry).hexdigest()
    if validation["hud_registry_sha256"] != registry_hash:
        raise ValueError("Regenerate the composer output before packaging")
    prepared_inputs = validation.get("source_inputs_sha256")
    if prepared_inputs is not None and prepared_inputs != runtime_inputs_fingerprint():
        raise ValueError("Runtime inputs changed after validation. Run tools/build.py --compose.")
    for name, expected in validation["runtime_archives"].items():
        if hashlib.sha256((ROOT / "runtime" / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Prepared overlay changed after validation")

    runtime_manifest = copy.deepcopy(source_manifest)
    runtime_manifest["kind"] = ["erp", "native"]
    runtime_manifest["operations"] = {
        "erp": ["runtime/overlays.json"],
        "native": source_manifest["operations"]["native"],
    }
    entries = {
        "swofty.json": (json.dumps(runtime_manifest, indent=2) + "\n").encode(),
        "CHANGELOG.md": changelog.encode("utf-8"),
    }
    for name in ("LICENSE", "README.md", "runtime/hud_scene.erp",
                 "runtime/hud_template.erp", "runtime/overlays.json",
                 "runtime/validation.json"):
        entries[name] = (ROOT / name).read_bytes()
    for item in source_manifest["operations"]["native"]:
        entries[item["dll"]] = (ROOT / item["dll"]).read_bytes()

    source_paths = {"swofty.json", "LICENSE", "README.md", "requirements.txt"}
    entries["source/CHANGELOG.md"] = entries["CHANGELOG.md"]
    for name in ("THIRD_PARTY_NOTICES.md", "docs/DEVELOPMENT.md", "docs/REPOSITORY.md"):
        path = ROOT / name
        if path.is_file():
            entries[name] = path.read_bytes()
            source_paths.add(name)
    source_paths.update(authored_sources(json.loads(registry)))
    for name in source_paths:
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT):
            raise ValueError(f"Packaged source points outside the workspace: {name}")
        entries["source/" + name] = registry if name == "registry/hud.json" else path.read_bytes()

    output = ROOT / "dist" / (source_manifest["id"] + ".swoftyaddon")
    identity = hashlib.sha256()
    for name, data in sorted(entries.items()):
        identity.update(name.encode("utf-8") + b"\0")
        identity.update(hashlib.sha256(data).digest())
    inputs = identity.hexdigest()
    cache_path = ROOT / "build/package-cache.json"
    try:
        previous = json.loads(cache_path.read_text())
        if (previous.get("inputs") == inputs
                and previous.get("output") == hashlib.sha256(output.read_bytes()).hexdigest()):
            print(f"Reused verified package {output}")
            return output
    except (OSError, ValueError, AttributeError):
        pass

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=output.name+'.',
                                     suffix='.tmp', delete=False) as pending:
        temporary = Path(pending.name)
    try:
        with zipfile.ZipFile(temporary, "w") as archive:
            for name, data in sorted(entries.items()):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o644 << 16
                archive.writestr(entry, data)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise ValueError("Package failed its CRC check")
            if any(archive.read(name) != data for name, data in entries.items()):
                raise ValueError("Package differs from validated inputs")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pending_cache = cache_path.with_suffix(".tmp")
    pending_cache.write_text(json.dumps({
        "inputs": inputs,
        "output": hashlib.sha256(output.read_bytes()).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")
    pending_cache.replace(cache_path)
    print(f"Packaged {output} with {len(entries)} verified files")
    return output

if __name__ == "__main__":
    package()
