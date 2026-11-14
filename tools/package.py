"""Package validated, precomposed HUD overlays plus complete authoring sources."""
import copy
import hashlib
import json
from pathlib import Path
import zipfile
import tempfile
from build_inputs import runtime_inputs_fingerprint

ROOT = Path(__file__).resolve().parents[1]

def package():
    source_manifest = json.loads((ROOT / "swofty.json").read_text(encoding="utf-8"))
    validation = json.loads((ROOT / "runtime/validation.json").read_text())
    registry_hash = hashlib.sha256((ROOT / "registry/hud.json").read_bytes()).hexdigest()
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
    }
    for name in ("LICENSE", "README.md", "runtime/hud_scene.erp",
                 "runtime/hud_template.erp", "runtime/overlays.json",
                 "runtime/validation.json"):
        entries[name] = (ROOT / name).read_bytes()
    for item in source_manifest["operations"]["native"]:
        entries[item["dll"]] = (ROOT / item["dll"]).read_bytes()

    source_paths = {"swofty.json", "LICENSE", "README.md", "requirements.txt"}
    documentation = [ROOT/"THIRD_PARTY_NOTICES.md"]
    documentation.extend((ROOT/"docs").rglob("*.md"))
    for path in documentation:
        if path.is_file():
            name = path.relative_to(ROOT).as_posix()
            entries[name] = path.read_bytes()
            source_paths.add(name)
    for name in ('project.local.example.json','style.json'):
        if (ROOT/name).is_file():
            source_paths.add(name)
    for folder in ("halo", "native/src", "native/include", "native/test",
                   "native/reference", "assets/fonts/Saira", "tools", "registry", "art"):
        source_paths.update(
            path.relative_to(ROOT).as_posix() for path in (ROOT / folder).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts)
    for name in source_paths:
        entries["source/" + name] = (ROOT / name).read_bytes()

    output = ROOT / "dist" / (source_manifest["id"] + ".swoftyaddon")
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
    print(f"Packaged {output} with {len(entries)} verified files")

if __name__ == "__main__":
    package()
