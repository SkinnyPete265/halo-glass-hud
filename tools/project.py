"""Reusable project status, checks and release orchestration."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from project_config import local_settings, launcher_command

ROOT=Path(__file__).resolve().parents[1]


def run(command,log=None):
    if log:
        with log.open('w',encoding='utf-8') as output:
            result=subprocess.run(command,cwd=ROOT,stdout=output,stderr=subprocess.STDOUT)
        if result.returncode:
            print(log.read_text(encoding='utf-8',errors='replace')[-6000:])
            raise RuntimeError('Command failed. See '+str(log))
    else:
        subprocess.run(command,cwd=ROOT,check=True)


def game_running():
    result=subprocess.run(['tasklist','/FI','IMAGENAME eq F1_25.exe','/FO','CSV','/NH'],
                          capture_output=True,text=True,check=True)
    return 'f1_25.exe' in result.stdout.lower()


def preserve_installed(settings,manifest):
    installed=Path(settings['data_dir'])/'addons'/manifest['id']
    if not (installed/'swofty.json').exists():
        return None
    version=json.loads((installed/'swofty.json').read_text(encoding='utf-8'))['version']
    backup=ROOT/'build'/('rollback-v'+version)
    target=backup/'dist'/(manifest['id']+'.swoftyaddon')
    if not target.exists():
        target.parent.mkdir(parents=True,exist_ok=True)
        pending=target.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(pending,'w',zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(installed.rglob('*')):
                    if path.is_file():
                        archive.write(path,path.relative_to(installed).as_posix())
            with zipfile.ZipFile(pending) as archive:
                if archive.testzip():
                    raise RuntimeError('Rollback archive CRC failed')
            pending.replace(target)
        finally:
            pending.unlink(missing_ok=True)
    return backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('status','check','release'))
    parser.add_argument('--install',action='store_true',help='Install and verify a requested release')
    parser.add_argument('--native',action='store_true',help='Rebuild DLLs and run native tests')
    args=parser.parse_args()
    if args.action!='release' and (args.install or args.native):
        parser.error('--install and --native apply to release')
    settings=local_settings()
    manifest=json.loads((ROOT/'swofty.json').read_text(encoding='utf-8'))
    if args.action=='status':
        inputs=['native/reference/native-controls.erpk','native/reference/drs-template.bin']
        print(json.dumps({'root':str(ROOT),'version':manifest['version'],
            'profile':settings.get('profile','default'),
            'local_configuration':(ROOT/'project.local.json').exists(),
            'native_inputs':{name:(ROOT/name).exists() for name in inputs},
            'game_running':game_running()},indent=2))
        return
    if args.action=='check':
        run([sys.executable,'-B','tools/test_workflow.py'])
        if not (ROOT/'registry/hud.json').exists():
            run([sys.executable,'-B','tools/build.py','--skip-preview'])
        run([sys.executable,'-B','tools/test_drs_battery.py'])
        return
    required=('launcher','data_dir','game')
    if args.install and any(not settings.get(key) for key in required):
        parser.error('Configure launcher, data_dir and game in project.local.json')
    (ROOT/'build').mkdir(exist_ok=True)
    rollback=preserve_installed(settings,manifest) if args.install else None
    version=manifest['version']
    command=[sys.executable,'-B','tools/build.py','--compose','--skip-preview']
    if args.native:
        command.append('--native')
    run(command,ROOT/'build'/('compose-v'+version+'.log'))
    run([sys.executable,'-B','tools/package.py'])
    if not args.install:
        return
    if game_running():
        raise RuntimeError('Package ready. Close F1 25 normally before running release --install again.')
    profile=settings.get('profile','default')
    snapshot=ROOT/'build'/f'profile-before-{profile}-v{version}.json'
    shutil.copy2(Path(settings['data_dir'])/'profiles'/(profile+'.json'),snapshot)
    cli=launcher_command(settings['launcher'],settings['data_dir'])+['--profile',profile]
    package=ROOT/'dist'/(manifest['id']+'.swoftyaddon')
    run(cli+['addons','install',str(package)])
    run(cli+['addons','enable',manifest['id']])
    run(cli+['build','--game',settings['game']],ROOT/'build'/('swofty-build-v'+version+'.log'))
    plans=list((Path(settings['data_dir'])/'cache/overlay'/profile).glob('*/plan.json'))
    cache=max(plans,key=lambda path:path.stat().st_mtime).parent
    run([sys.executable,'-B','tools/verify_install.py','--cache',str(cache)])
    print(json.dumps({'version':version,'cache':str(cache),'rollback':str(rollback)},indent=2))

if __name__=='__main__':
    main()
