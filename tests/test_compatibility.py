"""Regression checks for build-aware composition caches and rollback snapshots."""

import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import asset_only
import compatibility
import project
import project_config
from check_time_trial import complete_laps


def write_pe(path, timestamp, image_size):
    data = bytearray(0x200)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 3, timestamp, 0, 0, 0xF0, 0x22)
    struct.pack_into("<H", data, 0x98, 0x20B)
    struct.pack_into("<I", data, 0x98 + 56, image_size)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class CompatibilityTests(unittest.TestCase):
    def test_stock_game_must_match_launcher_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "F1 25 Steam"
            other = root / "F1 25 EA"
            listing = f"* Steam   1.0.145.2472   {game}\n  EA App   1.0.145.2472   {other}\n"
            with mock.patch.object(project_config.subprocess, "check_output",
                                   return_value=listing) as run:
                command = ["swofty", "--profile", "test"]
                project_config.require_active_game(command, game)
                run.assert_called_once_with(command + ["game", "list"], text=True)
                with self.assertRaisesRegex(RuntimeError, "active game"):
                    project_config.require_active_game(command, other)

    def test_time_trial_reports_live_split_order_and_restart(self):
        prefix = "[halo-v2-sectors] "
        selected = prefix + "generation=7 player=0 provider=live.car_detail"
        lap = [prefix + f"accepted lap=1 S{i}=20000 ms" for i in range(1, 4)]
        reset = prefix + "player lap counter or clock rewound; rebaselined"
        self.assertEqual(complete_laps("\n".join([selected, *lap, reset, *lap])), [[1], [1]])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            complete_laps("\n".join([selected, *lap, lap[-1]]))
        with self.assertRaisesRegex(ValueError, "without the Live v6 provider"):
            complete_laps("\n".join([selected.replace("live.car_detail", "verified split reader"), *lap]))

    def make_environment(self, root):
        steamapps = root / "steamapps"
        game = steamapps / "common" / "F1 25"
        write_pe(game / "F1_25.exe", 1794312636, 0x18434000)
        (steamapps / "appmanifest_3059520.acf").write_text(
            '"AppState" {\n  "buildid" "26566308"\n}\n', encoding="utf-8"
        )
        launcher = root / "swofty.exe"
        launcher.write_bytes(b"SWOFTY launcher build A")
        return {"game": str(game), "launcher": str(launcher)}, game, launcher

    def test_environment_identity_tracks_game_and_launcher_builds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            settings, game, launcher = self.make_environment(root)
            original = compatibility.build_environment_identity(settings)
            self.assertEqual(original["game"]["steam_build_id"], "26566308")
            self.assertEqual(original["game"]["pe_timestamp"], 1794312636)
            self.assertEqual(original["game"]["size_of_image"], 0x18434000)
            original_fingerprint = compatibility.build_environment_fingerprint(settings)

            manifest = root / "steamapps" / "appmanifest_3059520.acf"
            manifest.write_text('"buildid" "26566309"\n', encoding="utf-8")
            self.assertNotEqual(
                original_fingerprint,
                compatibility.build_environment_fingerprint(settings),
            )
            manifest.write_text('"buildid" "26566308"\n', encoding="utf-8")
            launcher.write_bytes(b"SWOFTY launcher build B")
            self.assertNotEqual(
                original_fingerprint,
                compatibility.build_environment_fingerprint(settings),
            )

    @mock.patch.object(compatibility, "_source_runtime_inputs_fingerprint", return_value="source")
    def test_runtime_fingerprint_tracks_launcher_and_game_changes(self, _source):
        with tempfile.TemporaryDirectory() as temporary:
            settings, game, launcher = self.make_environment(Path(temporary))
            first = compatibility.runtime_inputs_fingerprint(settings)
            launcher.write_bytes(b"SWOFTY launcher build B")
            second = compatibility.runtime_inputs_fingerprint(settings)
            self.assertNotEqual(first, second)

            first = second
            write_pe(game / "F1_25.exe", 1794312637, 0x18434000)
            second = compatibility.runtime_inputs_fingerprint(settings)
            self.assertNotEqual(first, second)

    def test_structure_fingerprint_tracks_environment(self):
        with mock.patch.object(asset_only, "artwork_source_fingerprint", return_value="art"), \
             mock.patch.object(asset_only, "files_fingerprint", return_value="composition"), \
             mock.patch.object(asset_only, "build_environment_fingerprint", side_effect=("old-build", "new-build")):
            self.assertNotEqual(
                asset_only.structure_fingerprint(), asset_only.structure_fingerprint()
            )

    def test_reuse_and_texture_refresh_reject_different_environment(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            root = Path(temporary)
            (root / "build").mkdir()
            previous = {
                "structure": "game-and-launcher-A",
                "registry": "same-registry",
                "assets": {},
                "archives": {},
                "style": {},
            }
            current = {**previous, "structure": "game-and-launcher-B"}
            (root / "build/composition-cache.json").write_text(
                json.dumps(previous), encoding="utf-8"
            )
            with mock.patch.object(asset_only, "ROOT", root), mock.patch.object(
                asset_only, "state", return_value=current
            ):
                self.assertFalse(asset_only.try_reuse("current-inputs"))
                self.assertFalse(asset_only.try_refresh([], "candidate", "current-inputs"))

    def test_rollback_snapshot_uses_exact_installed_files_when_version_repeats(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temporary:
            root = Path(temporary)
            installed = root / "swofty-data/addons/local.halo-hud-v2"
            installed.mkdir(parents=True)
            (installed / "swofty.json").write_text(
                '{"version":"0.14.1"}', encoding="utf-8"
            )
            (installed / "candidate.bin").write_bytes(b"currently installed")
            (installed / ".swofty-files.json").write_text("{}", encoding="utf-8")

            archive_root = root / "local/archive/rollbacks"
            old_backup = archive_root / "rollback-v0.14.1"
            old_target = old_backup / "dist/local.halo-hud-v2.swoftyaddon"
            old_target.parent.mkdir(parents=True)
            with zipfile.ZipFile(old_target, "w") as archive:
                archive.writestr("swofty.json", '{"version":"0.14.1"}')
                archive.writestr("candidate.bin", b"older same-version package")

            with mock.patch.object(project, "ROOT", root):
                backup = project.preserve_installed(
                    {"data_dir": str(root / "swofty-data")},
                    {"id": "local.halo-hud-v2"},
                )
            snapshot = backup / "dist/local.halo-hud-v2.swoftyaddon"
            self.assertTrue(snapshot.is_file())
            self.assertEqual(backup.parent, archive_root)
            self.assertNotEqual(backup, old_backup)
            self.assertTrue(project.installed_matches(snapshot, installed))
            with zipfile.ZipFile(snapshot) as archive:
                self.assertNotIn(".swofty-files.json", archive.namelist())
            (installed / "unexpected.bin").write_bytes(b"unpackaged file")
            self.assertFalse(project.installed_matches(snapshot, installed))


if __name__ == "__main__":
    unittest.main()
