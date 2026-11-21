"""Validate the generated dial registry with SWOFTY's pinned HUD schema."""

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
REVISION = "70b94d885189e776e899852a4f86dc20067f2b4c"  # SWOFTY v1.10.21
UPSTREAM = "https://raw.githubusercontent.com/Swofty-Developments/SwoftyLauncher/"
FILES = {
    "tools/std/validate.py": "7296895177b2f671b9494959da6c30508ca17e78d7b96c91380049a61215b736",
    "tools/std/stdschema.py": "2f017e5ba460c723b805e719f7d22278034207f3a3a6f972b2d37a5dd5c378dc",
    "packages/sdk/std/registries/hud.element/1.4.json": "e544f6fb6391217437718eaa4943856542dced21ee99ff14f40598ff8935fbb5",
}


def validate_registry(addon):
    cache = ROOT / "build/sdk-validation" / REVISION
    for relative, checksum in FILES.items():
        path = cache / relative
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == checksum:
            continue
        with urlopen(f"{UPSTREAM}{REVISION}/{relative}", timeout=15) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != checksum:
            raise ValueError(f"Unexpected SDK validation file checksum: {relative}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        try:
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as temp:
        # The SDK pins an individual schema version through the validation filename.
        registry = Path(temp) / "hud@1.4.json"
        registry.write_bytes((ROOT / "registry/hud.json").read_bytes())
        subprocess.run(
            [sys.executable, "-B", str(cache / "tools/std/validate.py"),
             "--repo", str(cache), "--data", "--addon", addon, str(registry)],
            cwd=ROOT, check=True,
        )
