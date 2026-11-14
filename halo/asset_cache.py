"""Content-checked asset caching for changes to declared shared style settings."""

import hashlib
import json
import math
import tempfile
from PIL import Image
from pathlib import Path


class AssetCache:
    def __init__(self, root, source, settings):
        self.root = root
        self.path = root / "build/asset-cache.json"
        self.source = source
        self.settings = settings
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            loaded = {}
        self.entries = loaded.get("entries", {}) if isinstance(loaded, dict) else {}
        if not isinstance(self.entries, dict):
            self.entries = {}
        self.next = {}
        self.generated = []
        self.reused = []

    def get(self, name, keys, create):
        encoded = json.dumps(
            {
                "source": self.source,
                "name": name,
                "settings": {key: self.settings[key] for key in keys},
            },
            sort_keys=True,
        ).encode()
        key = hashlib.sha256(encoded).hexdigest()
        old = self.entries.get(name, {})
        if isinstance(old, dict) and old.get("key") == key:
            metadata = old.get("sprite", {})
            if not isinstance(metadata, dict):
                metadata = {}
            png = metadata.get("png", "")
            if not isinstance(png, str):
                png = ""
            path = (self.root / png).resolve()
            if path.is_relative_to((self.root / "art").resolve()) and path.is_file():
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                bounds = metadata.get("bounds")
                valid_bounds = (
                    isinstance(bounds, list)
                    and len(bounds) == 4
                    and all(
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and math.isfinite(value)
                        for value in bounds
                    )
                )
                if digest == old.get("sha256") and valid_bounds:
                    self.next[name] = old
                    self.reused.append(name)
                    return metadata
        metadata = create()
        digest = hashlib.sha256((self.root / metadata["png"]).read_bytes()).hexdigest()
        self.next[name] = {"key": key, "sha256": digest, "sprite": metadata}
        self.generated.append(name)
        return metadata

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_suffix(".tmp")
        pending.write_text(
            json.dumps({"entries": self.next}, indent=2) + "\n", encoding="utf-8"
        )
        pending.replace(self.path)
        print(
            f"Artwork assets generated {len(self.generated)}, reused {len(self.reused)}."
        )


def cached_layer(root, name, key, producer):
    """Persist an expensive fixed raster separately from a small live caption."""
    identity = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    folder = root / "build/render-layers"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name + "-" + identity + ".png")
    checksum = path.with_suffix(".sha256")
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() == checksum.read_text():
            with Image.open(path) as image:
                return image.convert("RGBA")
    except (OSError, ValueError):
        pass
    image = producer()
    with tempfile.NamedTemporaryFile(dir=folder, suffix=".png", delete=False) as output:
        pending = Path(output.name)
    try:
        image.save(pending)
        digest = hashlib.sha256(pending.read_bytes()).hexdigest()
        pending.replace(path)
        with tempfile.NamedTemporaryFile(dir=folder, mode="w", delete=False) as output:
            output.write(digest)
            marker = Path(output.name)
        marker.replace(checksum)
    finally:
        pending.unlink(missing_ok=True)
    return image
