"""Verify a packaged release against SWOFTY's installed files and prepared cache."""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import zipfile
from PIL import Image
import prepare_runtime
from formats import erpw
from project_config import local_settings
from halo import material

ROOT = Path(__file__).resolve().parents[1]


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def verify_profile_change(before, after, addon):
    original = next((item for item in before['addons'] if item['id'] == addon), None)
    if original is None:
        added = [item for item in after['addons'] if item['id'] == addon]
        require(len(added) == 1 and added[0].get('enabled') is True,
                'Addon was not added and enabled in the target profile')
        after = {**after, 'addons': [item for item in after['addons'] if item['id'] != addon]}
    else:
        original['enabled'] = True
    require(after == before, 'Profile settings changed')


def main():
    settings = local_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument('--same-dlls-as', type=Path)
    parser.add_argument('--launcher', default=settings.get('launcher', 'swofty'))
    parser.add_argument('--data-dir', type=Path, default=settings.get('data_dir'))
    parser.add_argument('--profile', default=settings.get('profile', 'default'))
    parser.add_argument('--cache', type=Path, help='Verify this exact cache folder')
    parser.add_argument('--profile-snapshot', type=Path, help='Verify against this pre-install profile')
    args = parser.parse_args()
    if args.data_dir is None:
        parser.error('Supply --data-dir or set data_dir in project.local.json.')
    store = args.data_dir
    manifest = json.loads((ROOT/'swofty.json').read_text(encoding='utf-8'))
    version, addon = manifest['version'], manifest['id']
    package = ROOT/'dist'/(addon+'.swoftyaddon')
    installed = store/'addons'/addon
    with zipfile.ZipFile(package) as archive:
        require(archive.testzip() is None, 'Package CRC')
        files = [name for name in archive.namelist() if not name.endswith('/')]
        for name in files:
            require((installed/name).read_bytes() == archive.read(name), ('Installed file', name))
        require(json.loads(archive.read('swofty.json'))['version'] == version, 'Installed version')
        if args.same_dlls_as:
            previous_package = ROOT/args.same_dlls_as/'dist'/package.name
            with zipfile.ZipFile(previous_package) as previous:
                for item in manifest['operations']['native']:
                    require(archive.read(item['dll']) == previous.read(item['dll']), ('DLL changed', item['dll']))

    cache = args.cache
    if cache is None:
        plans = sorted((store/'cache/overlay'/args.profile).glob('*/plan.json'),
                       key=lambda path: path.stat().st_mtime, reverse=True)
        require(plans, 'No built cache was found for profile '+args.profile)
        cache = plans[0].parent
    plan = json.loads((cache/'plan.json').read_text())
    require(plan.get('profile') == args.profile, ('Cache belongs to another profile', plan.get('profile')))
    operations = json.loads((ROOT/'runtime/overlays.json').read_text())['ops']
    verified = 0
    for operation in operations:
        source = erpw.Erp(ROOT/operation['source'])
        for target in operation['erps']:
            cached = erpw.Erp(Path(plan['replace'][target]))
            for resource in source.res:
                actual = cached.find(resource.name)
                require(len(actual.frags) == len(resource.frags), ('Fragment count', target, resource.name))
                for index in range(len(resource.frags)):
                    require(cached.frag_data(actual,index) == source.frag_data(resource,index), (target,resource.name,index))
                verified += 1
    persistent_target = "2025_asset_groups/ui_package/persistent.erp"
    require(persistent_target in plan.get("replace", {}), "Fresh overlay has no persistent.erp replacement")
    cached_persistent = erpw.Erp(Path(plan["replace"][persistent_target]))
    stock_persistent_path = Path(settings["game"]) / persistent_target
    stock_persistent = erpw.Erp(stock_persistent_path)
    animated_library_name = (
        "eaid://ui_package/art/materials/animated_material_library.idf"
        "?context=animstringtable&file=0"
    )
    stock_library = stock_persistent.find(animated_library_name)
    overlay_library = cached_persistent.find(animated_library_name)
    require(len(stock_library.frags) == len(overlay_library.frags), "Updated stock animated material library is missing from cached persistent.erp")
    require(
        all(
            stock_persistent.frag_data(stock_library, index)
            == cached_persistent.frag_data(overlay_library, index)
            for index in range(len(stock_library.frags))
        ),
        "Cached persistent.erp does not contain the current game's animated material library",
    )

    scene_source = erpw.Erp(ROOT / "runtime/hud_scene.erp")
    registry = json.loads((ROOT / "registry/hud.json").read_text(encoding="utf-8"))
    base_textures = {}
    for dial_key in ("glass_dial", "glass_dial_26"):
        record = registry["hud.element"][dial_key]
        require("base" in record["sprites"], ("Missing base sprite", dial_key))
        resource_name = (
            "eaid://ui_package/art/osd/textures/hud/"
            + record["prefix"]
            + "_base.tif.image"
        )
        source = scene_source.find(resource_name)
        cached = cached_persistent.find(resource_name)
        require(len(source.frags) == len(cached.frags), ("Candidate base texture missing", dial_key))
        for index in range(len(source.frags)):
            require(
                scene_source.frag_data(source, index)
                == cached_persistent.frag_data(cached, index),
                ("Candidate base texture differs in fresh overlay", dial_key, index),
            )
        base_textures[dial_key] = resource_name

    for item in manifest['operations']['native']:
        name = item['dll']
        route = 'swofty/addons/'+addon+'/'+name
        require(Path(plan['loader'][route]).read_bytes() == (ROOT/name).read_bytes(), ('DLL route', route))

    snapshot = args.profile_snapshot or ROOT/'build'/f'profile-before-{args.profile}-v{version}.json'
    if args.profile_snapshot is None and not snapshot.exists():
        snapshot = ROOT/'build'/f'profile-before-v{version}.json'
    before = json.loads(snapshot.read_text())
    after = json.loads((store/'profiles'/(args.profile+'.json')).read_text())
    verify_profile_change(before, after, addon)
    runtime = erpw.Erp(ROOT/'runtime/hud_scene.erp')
    name = 'eaid://ui_package/art/osd/textures/hud/halo_v2_rpm_fill_mask.tif.image'
    resource = runtime.find(name)
    width,height = struct.unpack_from('<II',runtime.frag_data(resource,0),12)
    decoded = Image.frombytes('RGBA',(width,height),runtime.frag_data(resource,1),'bcn',7,'BC7').getchannel('A')
    source = Image.open(ROOT/'art/rpm_fill_mask.png').getchannel('A')
    require((width,height) == source.size, 'RPM mask dimensions')
    error = math.sqrt(sum((a-b)**2 for a,b in zip(source.getdata(),decoded.getdata()))/(width*height))
    require(error < 2, ('RPM mask compression error', error))
    # BC7 endpoints can differ by one alpha level after compression.
    require(decoded.getpixel((0,height//2)) >= 254 and decoded.getpixel((width-1,height//2)) <= 1, 'RPM mask endpoints')

    built = json.loads((cache/'built.json').read_text())
    warnings = built.get('warnings',[])
    other = [warning for warning in warnings if '[catalogue]' not in warning]
    launcher = subprocess.check_output([str(args.launcher),'--version'],text=True).strip()
    report = {'version':version,'launcher':launcher,'profile':args.profile,
              'installed_files':len(files),'cache':str(cache),
              'verified_resource_copies':verified,'native_loader_routes_verified':True,
              'native_loader_routes':["swofty/addons/"+addon+"/"+item['dll'] for item in manifest['operations']['native']],
              'stock_animated_material_library_verified':True,
              'candidate_base_textures_verified':base_textures,
              'race_edge_variant':material.DEFAULT_RACE_EDGE_VARIANT,
              'profile_settings_verified':True,'rpm_soft_mask_alpha_rms_error':error,
              'warning_count':len(warnings),'non_catalogue_warnings':other,
              'in_game_test':f'Pending for v{version}'}
    if args.same_dlls_as:
        report['dlls_match_previous_release'] = True
        report['rollback'] = args.same_dlls_as.as_posix()
    output = ROOT/'build'/f'install-report-v{version}.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
