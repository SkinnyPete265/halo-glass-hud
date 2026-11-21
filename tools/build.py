"""Generate shared art quickly. Native and composer validation are opt-in."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo import composition
from build_inputs import artwork_inputs_fingerprint, file_hash
from compatibility import runtime_inputs_fingerprint
from project_config import local_settings, launcher_command, require_active_game
from validate_registry import validate_registry

def run(command, **options):
    subprocess.run(command, cwd=ROOT, check=True, **options)

def native(zig_command="zig", *, tests_only=False):
    build = ROOT / "build" / "native"
    build.mkdir(parents=True, exist_ok=True)
    zig = shutil.which(zig_command)
    if not zig:
        raise RuntimeError(f"Zig executable not found: {zig_command}")
    # WinGet exposes Zig through a symlink. Zig needs the real executable path
    # to locate its adjacent lib directory, so resolve the shim before invoking it.
    zig = str(Path(zig).resolve())
    environment = os.environ.copy()
    environment["ZIG_GLOBAL_CACHE_DIR"] = str(ROOT / "build/zig-cache/global")
    environment["ZIG_LOCAL_CACHE_DIR"] = str(ROOT / "build/zig-cache/local")
    common = [zig, "c++", "-target", "x86_64-windows-gnu", "-std=c++23", "-O2",
              "-Wall", "-Wextra", "-Wno-nullability-completeness",
              "-I" + str(ROOT / "native/include")]
    if not tests_only:
        for source, destination in (("addon.cpp", "halo_hud_v2.dll"),
                                    ("sector_times.cpp", "sector_times.dll")):
            run(common + ["-shared", "-o", str(ROOT / "native" / destination),
                          str(ROOT / "native/src" / source)], env=environment)
    for name in ("dial_test", "sector_test"):
        test = build / (name + ".exe")
        run(common + ["-UNDEBUG", "-o", str(test), str(ROOT / "native/test" / (name + ".cpp"))],
            env=environment)
        run([str(test)])


def artwork():
    """Reuse generated assets only when their inputs and recorded outputs match."""
    for name in ('art','registry'):
        (ROOT/name).mkdir(parents=True,exist_ok=True)
    fingerprint = artwork_inputs_fingerprint()
    cache_path = ROOT/'build/artwork-cache.json'
    try:
        cache = json.loads(cache_path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    if (cache.get('inputs_sha256') == fingerprint and cache.get('outputs_sha256')
            and all((ROOT/name).is_file() and file_hash(ROOT/name) == expected
                    for name, expected in cache['outputs_sha256'].items())):
        print('Reused generated artwork after content checks.')
        return json.loads((ROOT/'registry/hud.json').read_text())['hud.element']['glass_dial']
    record = composition.write()
    if artwork_inputs_fingerprint()!=fingerprint:
        raise RuntimeError('Source inputs changed during artwork generation. Retry the build.')
    outputs = {'registry/hud.json'}
    records=json.loads((ROOT/'registry/hud.json').read_text())['hud.element'].values()
    outputs.update(sprite['png'] for item in records for sprite in item['sprites'].values())
    cache = {'inputs_sha256': fingerprint,
             'outputs_sha256': {name: file_hash(ROOT/name) for name in sorted(outputs)}}
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2)+'\n', encoding='utf-8')
    print('Regenerated artwork and recorded its content hashes.')
    return record


def main():
    settings = local_settings()
    parser = argparse.ArgumentParser()
    native_mode = parser.add_mutually_exclusive_group()
    native_mode.add_argument("--native", action="store_true")
    native_mode.add_argument("--native-tests", action="store_true",
                             help="Run native fixtures without generating artwork or DLLs")
    parser.add_argument("--compose", action="store_true")
    parser.add_argument("--launcher", default=settings.get("launcher", "swofty"))
    parser.add_argument("--data-dir", default=settings.get("data_dir"))
    parser.add_argument("--zig", default=settings.get("zig", "zig"),
                        help="Zig executable for native builds and tests")
    args = parser.parse_args()
    if args.native_tests:
        if args.compose:
            parser.error("--native-tests runs independently of --compose")
        native(args.zig, tests_only=True)
        return
    if args.compose:
        settings = {**settings, "launcher": args.launcher}
        launcher = launcher_command(args.launcher, args.data_dir) + [
            "--profile", settings.get("profile", "default"),
        ]
        require_active_game(launcher, settings.get("game"))
    authoring=artwork_inputs_fingerprint()
    from stage_timing import Timings
    timings = Timings(ROOT / "build/build-timings.json")
    with timings.stage("artwork"):
        record = artwork()
    if artwork_inputs_fingerprint()!=authoring:
        raise RuntimeError('Style changed during generation. Retry the build.')
    from PIL import Image
    for sprite in record["sprites"].values():
        with Image.open(ROOT / sprite["png"]) as image:
            if image.width % 4 or image.height % 4:
                raise ValueError(f"Non-aligned texture {sprite['png']}")
    if args.native:
        with timings.stage("native DLLs and tests"):
            native(args.zig)
    if args.compose:
        addon = json.loads((ROOT/'swofty.json').read_text(encoding='utf-8'))['id']
        from asset_only import try_refresh, try_reuse, record as record_composition
        validate_registry(addon)
        expected_inputs = runtime_inputs_fingerprint(settings)
        with timings.stage("native composition"):
            if not try_reuse(expected_inputs, settings) and not try_refresh(launcher, addon, expected_inputs, settings):
                run(launcher + ['dev','check',str(ROOT)])
                run(launcher + ['hud','check'])
                run(launcher + ['hud','compose',str(ROOT),'registry/hud.json',
                                '--id',addon,'--out',str(ROOT/'build/composed')])
                from prepare_runtime import prepare
                prepare(expected_inputs, settings)
                record_composition(expected_inputs, settings)
    print("Shared-layout artwork and composition are ready.")

if __name__ == "__main__":
    main()
