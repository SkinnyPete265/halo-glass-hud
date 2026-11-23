"""Regression checks for asset invalidation, style validation and release diagnostics."""

import hashlib
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]

import asset_only
import project
from stage_timing import Timings

from halo.asset_cache import AssetCache, cached_layer
from halo import tuning
from log_summary import save_summary, summarize
from build_inputs import file_hash
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
        changed_weight = 710 if self.settings["gears_weight"] != 710 else 720
        changed = dict(self.settings, gears_weight=changed_weight)
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
            report["runtime_archives"][name] = file_hash(path)
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

    def test_release_retry_preserves_rollback_and_skips_matching_install(self):
        self.stub_release_evidence()
        store = self.root / "store"
        (store / "profiles").mkdir(parents=True)
        (store / "profiles/default.json").write_text(
            '{"addons":[{"id":"test.hud","enabled":true},'
            '{"id":"nick.f1-2026-halo","enabled":true}]}'
        )
        settings = {"data_dir": str(store), "launcher": "swofty", "game": "game"}
        commands = []
        verify_error = None
        diagnostics = io.StringIO()

        def run(command, log=None):
            commands.append(command)
            if log:
                log.parent.mkdir(parents=True, exist_ok=True)
                log.write_text("overlay abcd: fixture-cache\n")
            if "tools/verify_install.py" in command:
                if verify_error:
                    raise verify_error
                (self.root / "build/install-report-v1.json").write_text("{}")

        with mock.patch.object(project, "ROOT", self.root), mock.patch.object(
            project, "run", side_effect=run
        ), mock.patch.object(
            project, "game_running", return_value=False
        ), mock.patch.object(
            project, "installed_matches", return_value=True
        ), mock.patch.object(
            project, "preserve_installed"
        ) as backup, contextlib.redirect_stderr(diagnostics):
            project.release(
                settings,
                {"id": "test.hud", "version": "1"},
                SimpleNamespace(native=False, install=True),
            )
            backup.assert_called_once_with(settings, {"id": "test.hud", "version": "1"})
            verify_error = subprocess.CalledProcessError(1, "verify_install.py")
            with self.assertRaises(subprocess.CalledProcessError) as raised:
                project.release(settings, {"id": "test.hud", "version": "1"},
                                SimpleNamespace(native=False, install=True))
            self.assertIs(raised.exception, verify_error)
        self.assertFalse(
            any("install" in command or "enable" in command for command in commands)
        )
        self.assertTrue(
            any("verify_install.py" in " ".join(command) for command in commands)
        )
        records = [json.loads(path.read_text())
                   for path in (self.root / "build/releases").glob("*/release.json")]
        failed = next(item for item in records if item["status"] == "failed")
        self.assertTrue(Path(failed["conflict_log"]).is_file())
        evidence = next(path.parent for path in (self.root / "build/releases").glob("*/install-report-v1.json"))
        record = json.loads((evidence / "release.json").read_text())
        self.assertEqual(record["status"], "cache_verified")
        self.assertEqual(record["cache"], "fixture-cache")
        self.assertEqual(Path(record["package"]).name, "test.hud-1.swoftyaddon")
        self.assertEqual(Path(record["package"]).read_bytes(),
                         (self.root / "dist/test.hud.swoftyaddon").read_bytes())
        self.assertIn("nick.f1-2026-halo", record["profile_warning"])
        self.assertIn(record["profile_warning"], diagnostics.getvalue())
        self.assertIn("SWOFTY profile conflict report:", diagnostics.getvalue())
        self.assertTrue(project.profile_enabled(store / "profiles/default.json", "nick.f1-2026-halo"))
        self.assertTrue((evidence / "profile-before.json").is_file())
        self.assertTrue((evidence / "install-report-v1.json").is_file())
        self.assertEqual(
            len(
                json.loads((self.root / "build/release-timings.json").read_text())[
                    "stages"
                ]
            ),
            5,
        )

    def test_running_game_defers_install_after_preparing_package(self):
        self.stub_release_evidence()
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
        record = next((self.root / "build/releases").glob("*/release.json"))
        self.assertEqual(json.loads(record.read_text())["status"], "waiting_for_game_close")

    def stub_release_evidence(self):
        (self.root / "dist").mkdir()
        (self.root / "dist/test.hud.swoftyaddon").write_bytes(b"test addon")
        self.enterContext(mock.patch.object(project, "build_environment_identity", return_value={
            "game": {"steam_build_id": "1"}, "launcher": {"path": "swofty"},
        }))
        self.enterContext(mock.patch.object(
            project.subprocess, "check_output", return_value="swofty 1.10.21\n",
        ))

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
