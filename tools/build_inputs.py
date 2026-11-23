"""Content fingerprints for generated artwork and prepared UI inputs."""
import hashlib
from pathlib import Path
import sys
from PIL import __version__ as pillow_version

ROOT = Path(__file__).resolve().parents[1]


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_fingerprint(paths, root=None):
    root = ROOT if root is None else root
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(b'\0')
        digest.update(file_hash(path).encode('ascii'))
        digest.update(b'\0')
    return digest.hexdigest()


def artwork_source_fingerprint():
    paths = list((ROOT/'halo').glob('*.py'))
    paths.extend(path for path in (ROOT/'assets/fonts/Saira').rglob('*') if path.is_file())
    paths.append(ROOT/'tools/build_inputs.py')
    versions = str(sys.version_info[:3]) + pillow_version
    return hashlib.sha256((files_fingerprint(paths) + versions).encode('utf-8')).hexdigest()


def artwork_inputs_fingerprint():
    source=artwork_source_fingerprint()
    style=ROOT/'style.json'
    if style.exists():
        source+=file_hash(style)
    return hashlib.sha256(source.encode('ascii')).hexdigest()


def runtime_inputs_fingerprint():
    paths = list((ROOT/'art').glob('*.png'))
    paths.extend((ROOT/'tools/formats').glob('*.py'))
    paths.extend(path for path in (ROOT/'native/reference').rglob('*') if path.is_file())
    paths.extend(ROOT/name for name in ('swofty.json', 'registry/hud.json',
                 'tools/build_inputs.py', 'tools/native_interop.py', 'tools/f126_interop.py', 'tools/prepare_runtime.py', 'tools/asset_only.py'))
    combined = artwork_inputs_fingerprint() + files_fingerprint(paths)
    return hashlib.sha256(combined.encode('ascii')).hexdigest()
