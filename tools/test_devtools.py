"""Regression checks for asset invalidation, safe tuning and release diagnostics."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from halo.asset_cache import AssetCache, cached_layer
from halo import tuning
from log_summary import save_summary, summarize
from tune_server import apply_settings, digest
from release_state import update


class DeveloperToolsTests(unittest.TestCase):
    def setUp(self):
        (ROOT / "build").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "build", prefix="devtools-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "art").mkdir()
        self.settings = json.loads((ROOT / "style.json").read_text())

    def create(self, name, value=100):
        Image.new("RGBA", (4, 4), (value, 20, 30, 255)).save(
            self.root / "art" / (name + ".png")
        )
        return {"png": "art/" + name + ".png", "bounds": [0, 0, 4, 4]}

    def test_asset_invalidation_is_scoped_to_declared_style(self):
        cache = AssetCache(self.root, "source", self.settings)
        cache.get("base", ("gears_weight",), lambda: self.create("base"))
        cache.get("battery", ("battery_width",), lambda: self.create("battery"))
        cache.save()
        changed = dict(self.settings, gears_weight=710)
        cache = AssetCache(self.root, "source", changed)
        cache.get("base", ("gears_weight",), lambda: self.create("base", 110))
        cache.get(
            "battery",
            ("battery_width",),
            lambda: self.fail("Unchanged battery regenerated"),
        )
        self.assertEqual(cache.generated, ["base"])
        self.assertEqual(cache.reused, ["battery"])

    def test_corrupt_asset_and_source_change_regenerate(self):
        cache = AssetCache(self.root, "source", self.settings)
        cache.get("base", (), lambda: self.create("base"))
        cache.save()
        (self.root / "art/base.png").write_bytes(b"corrupt")
        cache = AssetCache(self.root, "source", self.settings)
        cache.get("base", (), lambda: self.create("base"))
        cache.save()
        self.assertEqual(cache.generated, ["base"])
        cache = AssetCache(self.root, "new source", self.settings)
        cache.get("base", (), lambda: self.create("base"))
        self.assertEqual(cache.generated, ["base"])

    def test_corrupt_metadata_regenerates(self):
        folder = self.root / "build"
        folder.mkdir()
        (folder / "asset-cache.json").write_text(
            '{"entries":{"base":{"key":"bad","sprite":3}}}'
        )
        cache = AssetCache(self.root, "source", self.settings)
        cache.get("base", (), lambda: self.create("base"))
        self.assertEqual(cache.generated, ["base"])

    def test_fixed_layer_cache_checks_content(self):
        calls = []

        def draw():
            calls.append(1)
            return Image.new("RGBA", (8, 8), (20, 30, 40, 255))

        cached_layer(self.root, "backing", {"a": 1}, draw)
        cached_layer(self.root, "backing", {"a": 1}, draw)
        self.assertEqual(len(calls), 1)
        next((self.root / "build/render-layers").glob("*.png")).write_bytes(b"damaged")
        cached_layer(self.root, "backing", {"a": 1}, draw)
        self.assertEqual(len(calls), 2)

    def test_settings_validation_rejects_unsupported_values(self):
        for values in (
            dict(self.settings, gears_weight=float("nan")),
            dict(self.settings, battery_width=5000),
            dict(self.settings, gears_colour="red"),
            dict(self.settings, extra=1),
            dict(self.settings, speed_y=True),
        ):
            with self.assertRaises(ValueError):
                tuning.validate(values)

    def test_apply_is_explicit_and_rejects_stale_source(self):
        path = self.root / "style.json"
        path.write_text(json.dumps(self.settings))
        original = digest(path)
        updated = dict(self.settings, gears_weight=710)
        report = apply_settings(path, updated, original)
        self.assertEqual(report["changed"], ["gears_weight"])
        self.assertEqual(report["build"], "texture-only candidate")
        with self.assertRaises(ValueError):
            apply_settings(path, self.settings, original)
        self.assertEqual(json.loads(path.read_text())["gears_weight"], 710)

    def test_unchanged_apply_preserves_source_bytes(self):
        path = self.root / "style.json"
        original = json.dumps(self.settings, separators=(",", ":"))
        path.write_text(original)
        result = apply_settings(path, self.settings, digest(path))
        self.assertEqual(result["changed"], [])
        self.assertEqual(path.read_text(), original)

    def test_native_setting_requests_composition(self):
        path = self.root / "style.json"
        path.write_text(json.dumps(self.settings))
        report = apply_settings(path, dict(self.settings, battery_y=150), digest(path))
        self.assertEqual(report["build"], "native composition")

    def test_log_delta_preserves_errors_and_finds_new_warnings(self):
        path = self.root / "build.log"
        baseline = self.root / "baseline.json"
        path.write_text("[catalogue] known warning\nwarning: old\n")
        save_summary(path, baseline, accept=True)
        path.write_text(
            "[catalogue] known warning\nwarning: old\nwarning: new\nValueError: broken field\n"
        )
        result = summarize(path, baseline, 1)
        self.assertEqual(result["new_warning_count"], 1)
        self.assertEqual(result["new_warnings"][0]["text"], "warning: new")
        self.assertIn("broken field", result["errors"][0])
        self.assertEqual(result["warning_counts"]["catalogue"], 1)

    def test_state_update_preserves_notes_and_matching_install_version(self):
        (self.root / "swofty.json").write_text('{"id":"test.hud","version":"2.0"}')
        notes = "# State\n\n## Owner notes\nKeep the approved design.\n"
        (self.root / "PROJECT_STATE.md").write_text(notes)
        store = self.root / "store"
        (store / "addons/test.hud").mkdir(parents=True)
        (store / "addons/test.hud/swofty.json").write_text('{"version":"1.0"}')
        (self.root / "build").mkdir()
        (self.root / "build/install-report-v1.0.json").write_text(
            '{"version":"1.0","in_game_test":"Pending"}'
        )
        first = update(self.root, {"data_dir": str(store)})
        update(self.root, {"data_dir": str(store)})
        result = (self.root / "PROJECT_STATE.md").read_text()
        self.assertIn("Keep the approved design.", result)
        self.assertEqual(result.count("BEGIN GENERATED RELEASE STATE"), 1)
        self.assertEqual(first["installed_version"], "1.0")
        self.assertEqual(first["source_version"], "2.0")


if __name__ == "__main__":
    unittest.main()
