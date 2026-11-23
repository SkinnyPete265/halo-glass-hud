"""Build native publishers and verify their source and binary fingerprints."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_inputs import file_hash, files_fingerprint

PUBLISHERS = {
    'addon.cpp': 'native/halo_hud_v2.dll',
    'sector_times.cpp': 'native/sector_times.dll',
}
STAMP = 'build/native/validation.json'


def native_inputs(root):
    inputs = [root / 'tools/native_build.py']
    for directory in ('src', 'include', 'test'):
        inputs.extend(path for path in (root / 'native' / directory).rglob('*')
                      if path.is_file())
    return files_fingerprint(inputs, root)


def verified_dlls(root, names):
    """Return the exact bytes validated by the latest successful native build."""
    if not names:
        return {}
    try:
        record = json.loads((root / STAMP).read_text(encoding='utf-8'))
        if record['inputs_sha256'] != native_inputs(root):
            raise ValueError('Native sources changed')
        binaries = {name: (root / name).read_bytes() for name in names}
        if any(hashlib.sha256(data).hexdigest() != record['dll_sha256'][name]
               for name, data in binaries.items()):
            raise ValueError('Native DLL content changed')
        return binaries
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError('Native DLLs need validation. Run python -B tools/build.py --native '
                           'or use tools/project.py release to rebuild them automatically.') from error


def build_native(root, zig_command, *, tests_only=False):
    output = root / 'build/native'
    output.mkdir(parents=True, exist_ok=True)
    zig = shutil.which(zig_command)
    if not zig:
        raise RuntimeError(f'Zig executable not found: {zig_command}')
    # Resolve the WinGet shim so Zig can locate its adjacent lib directory.
    zig = str(Path(zig).resolve())
    environment = os.environ.copy()
    environment['ZIG_GLOBAL_CACHE_DIR'] = str(root / 'build/zig-cache/global')
    environment['ZIG_LOCAL_CACHE_DIR'] = str(root / 'build/zig-cache/local')
    common = [zig, 'c++', '-target', 'x86_64-windows-gnu', '-std=c++23', '-O2',
              '-Wall', '-Wextra', '-Wno-nullability-completeness',
              '-I' + str(root / 'native/include')]
    if not tests_only:
        stamp = root / STAMP
        stamp.unlink(missing_ok=True)
        fingerprint = native_inputs(root)
        for source, destination in PUBLISHERS.items():
            subprocess.run(common + ['-shared', '-o', str(root / destination),
                                     str(root / 'native/src' / source)],
                           cwd=root, env=environment, check=True)
    for name in ('dial_test', 'sector_test'):
        test = output / (name + '.exe')
        subprocess.run(common + ['-UNDEBUG', '-o', str(test), str(root / 'native/test' / (name + '.cpp'))],
                       cwd=root, env=environment, check=True)
        subprocess.run([str(test)], cwd=root, check=True)
    if tests_only:
        return
    if native_inputs(root) != fingerprint:
        raise RuntimeError('Native inputs changed during compilation. Retry the build.')
    record = {'inputs_sha256': fingerprint,
              'dll_sha256': {name: file_hash(root / name) for name in PUBLISHERS.values()}}
    pending = tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output, delete=False)
    temporary = Path(pending.name)
    try:
        with pending:
            pending.write(json.dumps(record, indent=2) + '\n')
        temporary.replace(stamp)
    finally:
        temporary.unlink(missing_ok=True)
