"""Build identity fingerprints for prepared HUD compositions.

Artwork cache keys intentionally do not include the game or SWOFTY build. A
new game or launcher can change the stock resources and composition behavior,
so native-composition reuse and texture-only refresh use this stricter key.
"""

import hashlib
import json
from pathlib import Path
import re
import shutil
import struct

from build_inputs import runtime_inputs_fingerprint as _source_runtime_inputs_fingerprint
from project_config import local_settings


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pe_identity(path):
    path = Path(path).resolve()
    with path.open("rb") as source:
        dos = source.read(64)
        if len(dos) != 64 or dos[:2] != b"MZ":
            raise ValueError(f"Not a PE executable: {path}")
        pe_offset = struct.unpack_from("<I", dos, 0x3C)[0]
        if pe_offset < 64 or pe_offset > 1024 * 1024:
            raise ValueError(f"Invalid PE header offset in {path}")
        source.seek(pe_offset)
        header = source.read(24)
        if len(header) != 24 or header[:4] != b"PE\0\0":
            raise ValueError(f"Invalid PE signature in {path}")
        machine, _, timestamp, _, _, optional_size, _ = struct.unpack_from(
            "<HHIIIHH", header, 4
        )
        optional = source.read(optional_size)
        if len(optional) < 60 or struct.unpack_from("<H", optional)[0] != 0x20B:
            raise ValueError(f"Expected a PE32+ executable: {path}")
        image_size = struct.unpack_from("<I", optional, 56)[0]
    return {
        "path": str(path),
        "file_size": path.stat().st_size,
        "machine": machine,
        "pe_timestamp": timestamp,
        "size_of_image": image_size,
    }


def _steam_build_id(game_root):
    game_root = Path(game_root).resolve()
    if game_root.is_file():
        game_root = game_root.parent
    manifest = None
    for parent in (game_root, *game_root.parents):
        if parent.name.lower() == "steamapps":
            manifest = parent / "appmanifest_3059520.acf"
            break
        if parent.name.lower() == "common":
            manifest = parent.parent / "appmanifest_3059520.acf"
            break
    if manifest is None or not manifest.is_file():
        raise FileNotFoundError(
            f"Could not locate Steam appmanifest_3059520.acf for {game_root}"
        )
    text = manifest.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'^\s*"buildid"\s*"(\d+)"\s*$', text, re.MULTILINE)
    if not match:
        raise ValueError(f"Steam build ID missing from {manifest}")
    return match.group(1)


def build_environment_identity(settings=None):
    """Return the concrete Steam game and SWOFTY executable identities."""
    settings = local_settings() if settings is None else settings
    game_value = settings.get("game")
    launcher_value = settings.get("launcher")
    if not game_value or not launcher_value:
        raise ValueError("Game and launcher paths are required for composition reuse")

    game_root = Path(game_value).resolve()
    game_exe = game_root if game_root.is_file() else game_root / "F1_25.exe"
    if not game_exe.is_file():
        raise FileNotFoundError(f"F1 25 executable not found: {game_exe}")
    game = _pe_identity(game_exe)
    game["steam_build_id"] = _steam_build_id(game_root)

    launcher_value = str(launcher_value)
    launcher_path = Path(launcher_value)
    if not launcher_path.is_file():
        located = shutil.which(launcher_value)
        if not located:
            raise FileNotFoundError(f"SWOFTY launcher not found: {launcher_value}")
        launcher_path = Path(located)
    launcher_path = launcher_path.resolve()
    launcher = {
        "path": str(launcher_path),
        "file_size": launcher_path.stat().st_size,
        "sha256": _sha256(launcher_path),
    }
    return {"schema": 1, "game": game, "launcher": launcher}


def build_environment_fingerprint(settings=None):
    encoded = json.dumps(
        build_environment_identity(settings), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def runtime_inputs_fingerprint(settings=None):
    """Fingerprint source inputs plus the exact stock/launcher environment."""
    identity = {
        "source_inputs": _source_runtime_inputs_fingerprint(),
        "environment": build_environment_fingerprint(settings),
        "compatibility_code": _sha256(Path(__file__)),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()
