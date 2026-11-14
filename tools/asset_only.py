"""Conservative texture-only composition with a full-build fallback."""

import hashlib
import json
from pathlib import Path
import subprocess
from build_inputs import (
    artwork_source_fingerprint,
    files_fingerprint,
    file_hash,
    runtime_inputs_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]


def structure_fingerprint():
    paths = list((ROOT / "tools/formats").glob("*.py"))
    paths.extend(
        path for path in (ROOT / "native/reference").rglob("*") if path.is_file()
    )
    paths.extend(path for path in (ROOT / "native/src").rglob("*") if path.is_file())
    paths.extend(
        ROOT / name
        for name in (
            "swofty.json",
            "tools/native_interop.py",
            "tools/f126_interop.py",
            "tools/prepare_runtime.py",
            "tools/asset_only.py",
        )
    )
    return hashlib.sha256(
        (artwork_source_fingerprint() + files_fingerprint(paths)).encode()
    ).hexdigest()


def state():
    records = json.loads((ROOT / "registry/hud.json").read_text())["hud.element"]
    paths = {
        item["png"]
        for record in records.values()
        for item in record["sprites"].values()
    }
    return {
        "structure": structure_fingerprint(),
        "registry": file_hash(ROOT / "registry/hud.json"),
        "style": json.loads((ROOT / "style.json").read_text()),
        "assets": {name: file_hash(ROOT / name) for name in sorted(paths)},
        "archives": {
            str(path.relative_to(ROOT)): file_hash(path)
            for directory in ("runtime", "build/composed")
            for path in (ROOT / directory).glob("*.erp")
        },
    }


def record(expected_inputs=None):
    path = ROOT / "build/composition-cache.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    captured = state()
    if expected_inputs and runtime_inputs_fingerprint() != expected_inputs:
        raise ValueError("Source changed while recording composition state")
    path.write_text(json.dumps(captured, indent=2) + "\n", encoding="utf-8")


def try_refresh(launcher, addon, expected_inputs=None):
    expected_inputs = expected_inputs or runtime_inputs_fingerprint()
    from halo.tuning import ART_ONLY_KEYS
    from prepare_runtime import validate, validate_f126
    from formats import erpw

    try:
        old = json.loads((ROOT / "build/composition-cache.json").read_text())
        current = state()
    except (OSError, ValueError, KeyError):
        return False
    if not isinstance(old, dict) or any(
        not isinstance(old.get(key), dict) for key in ("assets", "archives", "style")
    ):
        return False
    if (
        old.get("structure") != current["structure"]
        or old.get("registry") != current["registry"]
    ):
        return False
    if old.get("archives") != current["archives"] or len(current["archives"]) != 4:
        return False
    changed_style = {
        key
        for key in current["style"]
        if current["style"][key] != old.get("style", {}).get(key)
    }
    if changed_style - ART_ONLY_KEYS:
        return False
    changed = {
        name
        for name, digest in current["assets"].items()
        if digest != old.get("assets", {}).get(name)
    }
    if not changed:
        return False
    registry = json.loads((ROOT / "registry/hud.json").read_text())
    selections = {}
    for key, record_value in registry["hud.element"].items():
        sprites = {
            name: value
            for name, value in record_value["sprites"].items()
            if value["png"] in changed
        }
        if sprites:
            selections[key] = {
                "prefix": record_value["prefix"],
                "dial": record_value["dial"],
                "stock": "hide",
                "spectator": False,
                "box": record_value["box"],
                "sprites": sprites,
                "elements": [
                    {"kind": "sprite", "id": name, "sprite": name, "layer": 20}
                    for name in sprites
                ],
            }
    subset = ROOT / "build/texture-subset.json"
    subset.write_text(json.dumps({"hud.element": selections}), encoding="utf-8")
    out = ROOT / "build/texture-composed"
    try:
        subprocess.run(
            launcher
            + [
                "hud",
                "compose",
                str(ROOT),
                str(subset),
                "--id",
                addon,
                "--out",
                str(out),
            ],
            cwd=ROOT,
            check=True,
        )
        fresh = erpw.Erp(out / "hud_scene.erp")
        compiled = erpw.Erp(ROOT / "build/composed/hud_scene.erp")
        runtime = erpw.Erp(ROOT / "runtime/hud_scene.erp")
        images = []
        for selected in selections.values():
            for name in selected["sprites"]:
                texture = (
                    "eaid://ui_package/art/osd/textures/hud/"
                    + selected["prefix"]
                    + "_"
                    + name
                    + ".tif"
                )
                # Metadata equality keeps the existing material, dimensions and bindings intact.
                for archive in (compiled, runtime):
                    for resource_name in (texture, texture + ".image"):
                        before = archive.find(resource_name)
                        after = fresh.find(resource_name)
                        if len(before.frags) != len(after.frags):
                            return False
                        for index in range(len(before.frags)):
                            if resource_name.endswith(".image") and index == 1:
                                continue
                            if archive.frag_data(before, index) != fresh.frag_data(
                                after, index
                            ):
                                return False
                images.append(texture + ".image")
        for archive in (compiled, runtime):
            for name in images:
                archive.set_frag(
                    archive.find(name), 1, fresh.frag_data(fresh.find(name), 1)
                )
        template = erpw.Erp(ROOT / "runtime/hud_template.erp")
        validate(runtime, template)
        validate_f126(runtime, template)
        if runtime_inputs_fingerprint() != expected_inputs:
            raise ValueError("Style changed during texture generation")
        # All compatibility checks finish before the existing outputs are replaced.
        for archive, path in (
            (compiled, ROOT / "build/composed/hud_scene.erp"),
            (runtime, ROOT / "runtime/hud_scene.erp"),
        ):
            pending = path.with_suffix(".pending.erp")
            archive.to_file(pending, reframe=False)
            pending.replace(path)
        path = ROOT / "runtime/validation.json"
        report = json.loads(path.read_text())
        report["source_inputs_sha256"] = expected_inputs
        report["runtime_archives"] = {
            name: file_hash(ROOT / "runtime" / name)
            for name in report["runtime_archives"]
        }
        report["texture_refresh"] = {"images": images, "native_layout_reused": True}
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        record(expected_inputs)
        print(
            f"Refreshed {len(images)} texture resources using the validated native layout."
        )
        return True
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print("Texture refresh requires full composition. " + str(error))
        return False
