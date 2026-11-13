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

ROOT = Path(__file__).resolve().parents[1]


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def main():
    settings = local_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument('--same-dlls-as', type=Path)
    parser.add_argument('--launcher', default=settings.get('launcher', 'swofty'))
    parser.add_argument('--data-dir', type=Path, default=settings.get('data_dir'))
    parser.add_argument('--profile', default=settings.get('profile', 'default'))
    parser.add_argument('--cache', type=Path, help='Verify this exact cache folder')
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
    for item in manifest['operations']['native']:
        name = item['dll']
        route = 'swofty/addons/'+addon+'/'+name
        require(Path(plan['loader'][route]).read_bytes() == (ROOT/name).read_bytes(), ('DLL route', route))

    snapshot = ROOT/'build'/f'profile-before-{args.profile}-v{version}.json'
    if not snapshot.exists():
        snapshot = ROOT/'build'/f'profile-before-v{version}.json'
    before = json.loads(snapshot.read_text())
    after = json.loads((store/'profiles'/(args.profile+'.json')).read_text())
    next(item for item in before['addons'] if item['id'] == addon)['enabled'] = True
    require(after == before, 'Profile settings changed')
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
    report = {'version':version,'launcher':launcher,'installed_files':len(files),'cache':str(cache),
              'verified_resource_copies':verified,'native_loader_routes_verified':True,
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
