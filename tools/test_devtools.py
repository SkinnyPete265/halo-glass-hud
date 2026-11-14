"""Regression checks for asset invalidation, safe tuning and release diagnostics."""

import hashlib
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
import zipfile
import asset_only
import project
from stage_timing import Timings
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
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
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
            "[catalogue] known warning\nwarning: old\nwarning: new\n0 errors, 3 warnings\nValueError: broken field\n"
        )
        result = summarize(path, baseline, 1)
        self.assertEqual(result["new_warning_count"], 1)
        self.assertEqual(result["new_warnings"][0]["text"], "warning: new")
        self.assertIn("broken field", result["errors"][0])
        self.assertEqual(result["warning_counts"]["catalogue"], 1)

    def test_native_reuse_checks_saved_state_report_and_outputs(self):
        (self.root / "build").mkdir()
        (self.root / "runtime").mkdir()
        report = {"source_inputs_sha256": "source", "runtime_archives": {}}
        for name in ("hud_scene.erp", "hud_template.erp"):
            path = self.root / "runtime" / name
            path.write_bytes(name.encode())
            report["runtime_archives"][name] = digest(path)
        (self.root / "runtime/validation.json").write_text(json.dumps(report))
        (self.root / "build/composition-cache.json").write_text('{"identity":"saved"}')
        with mock.patch.object(asset_only, "ROOT", self.root), mock.patch.object(
            asset_only, "state", return_value={"identity": "saved"}
        ):
            self.assertTrue(asset_only.try_reuse("source"))
            self.assertFalse(asset_only.try_reuse("different source"))
            (self.root / "runtime/hud_scene.erp").write_bytes(b"damaged")
            self.assertFalse(asset_only.try_reuse("source"))
        with mock.patch.object(asset_only, "ROOT", self.root), mock.patch.object(
            asset_only, "state", return_value={"identity": "changed"}
        ):
            self.assertFalse(asset_only.try_reuse("source"))

    def test_timing_records_failed_stage(self):
        path = self.root / "timings.json"
        timings = Timings(path)
        with self.assertRaisesRegex(ValueError, "failure"):
            with timings.stage("fixture"):
                raise ValueError("failure")
        result = json.loads(path.read_text())["stages"][0]
        self.assertEqual(result["status"], "failed")
        self.assertGreaterEqual(result["seconds"], 0)

    def test_installed_match_detects_changed_and_extra_files(self):
        package = self.root / "addon.zip"
        installed = self.root / "installed"
        installed.mkdir()
        (installed / "file").write_bytes(b"approved")
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("file", b"approved")
        self.assertTrue(project.installed_matches(package, installed))
        (installed / "extra").write_bytes(b"old file")
        self.assertFalse(project.installed_matches(package, installed))
        (installed / "extra").unlink()
        (installed / "file").write_bytes(b"changed")
        self.assertFalse(project.installed_matches(package, installed))

    def test_release_retry_skips_matching_install_and_enable(self):
        store = self.root / "store"
        (store / "profiles").mkdir(parents=True)
        (store / "profiles/default.json").write_text(
            '{"addons":[{"id":"test.hud","enabled":true}]}'
        )
        settings = {"data_dir": str(store), "launcher": "swofty", "game": "game"}
        commands = []

        def run(command, log=None):
            commands.append(command)
            if log:
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text("overlay abcd: fixture-cache\n")

        with mock.patch.object(project, "ROOT", self.root), mock.patch.object(
            project, "run", side_effect=run
        ), mock.patch.object(
            project, "game_running", return_value=False
        ), mock.patch.object(
            project, "installed_matches", return_value=True
        ), mock.patch.object(
            project, "preserve_installed"
        ) as backup:
            project.release(
                settings,
                {"id": "test.hud", "version": "1"},
                SimpleNamespace(native=False, install=True),
            )
            backup.assert_not_called()
        self.assertFalse(
            any("install" in command or "enable" in command for command in commands)
        )
        self.assertTrue(
            any("verify_install.py" in " ".join(command) for command in commands)
        )
        self.assertEqual(
            len(
                json.loads((self.root / "build/release-timings.json").read_text())[
                    "stages"
                ]
            ),
            5,
        )

    def test_running_game_defers_install_after_preparing_package(self):
        commands = []

        def run(command, log=None):
            commands.append(command)
            if log:
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text("")

        with mock.patch.object(project, "ROOT", self.root), mock.patch.object(
            project, "run", side_effect=run
        ), mock.patch.object(
            project, "game_running", return_value=True
        ), mock.patch.object(
            project, "preserve_installed"
        ) as backup:
            with self.assertRaisesRegex(RuntimeError, "Package ready"):
                project.release(
                    {},
                    {"id": "test.hud", "version": "1"},
                    SimpleNamespace(native=False, install=True),
                )
            backup.assert_not_called()
        self.assertEqual(len(commands), 2)

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
