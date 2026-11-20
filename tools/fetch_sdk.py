"""Fetch the project's SWOFTY SDK headers at the recorded upstream revision."""
import hashlib
import json
import re
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "native" / "include"
TAG = "v1.10.11"
REVISION = "c7fc9dffeff94fc65339b5584171bd5b5bd0071a"
BASE = f"https://raw.githubusercontent.com/Swofty-Developments/SwoftyLauncher/{REVISION}/"
HEADERS = ["swofty/events.hpp", "swofty/mixin.hpp", "swofty/hud_leaves.hpp",
           "swofty/live.hpp", "swofty/fake_hud.hpp", "swofty/fake_live.hpp"]

def main():
    pending = list(HEADERS)
    fetched = {}
    while pending:
        name = pending.pop()
        if name in fetched:
            continue
        url = BASE + "packages/sdk/include/" + name
        with urlopen(url, timeout=30) as response:
            data = response.read()
        target = DEST / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        fetched[name] = hashlib.sha256(data).hexdigest()
        includes = re.findall(r'#include\s*[<"]([^>"]+)[>"]', data.decode("utf-8"))
        pending.extend(name for name in includes
                       if name.startswith("swofty/") or name == "swofty_api.h")
    license_url = BASE + "packages/sdk/LICENSE"
    with urlopen(license_url, timeout=30) as response:
        license_data = response.read()
    (DEST / "LICENSE").write_bytes(license_data)
    (DEST / "source.json").write_text(json.dumps({
        "repository": "Swofty-Developments/SwoftyLauncher",
        "tag": TAG, "revision": REVISION, "sha256": dict(sorted(fetched.items())),
        "license": {"path": "LICENSE", "url": license_url,
                    "sha256": hashlib.sha256(license_data).hexdigest()}
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Fetched {len(fetched)} pinned SDK headers.")

if __name__ == "__main__":
    main()
