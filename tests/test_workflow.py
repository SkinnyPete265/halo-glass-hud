"""Focused regression checks for artwork reuse and package publication."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest import mock
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT)]

import build as workflow
import build_inputs
import compatibility
import package as packaging
import project_config
import fetch_sdk

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'build').mkdir(parents=True,exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='workflow-test-', dir=ROOT/'build')
        self.root = Path(temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to((ROOT/'build').resolve()))
        self.addCleanup(temporary.cleanup)
        for module in (workflow, build_inputs, packaging, project_config):
            self.enterContext(mock.patch.object(module, 'ROOT', self.root))
        self.enterContext(
            mock.patch.object(
                compatibility,
                'build_environment_fingerprint',
                return_value='fixture-game-and-launcher',
            )
        )
        for folder in ('halo', 'tools/formats', 'native/reference', 'assets/fonts/Saira',
                       'registry', 'runtime', 'art', 'dist', 'build'):
            (self.root/folder).mkdir(parents=True, exist_ok=True)
        self.record = {'sprites': {'meter': {'png': 'art/meter.png'}}}
        self.registry = {'hud.element': {'glass_dial': self.record}}
        (self.root/'registry/hud.json').write_text(json.dumps(self.registry))
        for name in ('halo/dial.py', 'tools/build_inputs.py', 'tools/native_interop.py',
                     'tools/prepare_runtime.py', 'tools/f126_interop.py', 'tools/asset_only.py', 'assets/fonts/Saira/Saira.ttf',
                     'LICENSE', 'README.md', 'requirements.txt'):
            (self.root/name).write_text('fixture')
        self.manifest = {'id': 'local.workflow-fixture', 'version': '0.0.0',
                         'operations': {'native': []}}
        (self.root/'swofty.json').write_text(json.dumps(self.manifest))
        (self.root/'CHANGELOG.md').write_text('# Changelog\n\n## 0.0.0\n\n- Fixture release\n')
        (self.root/'runtime/hud_scene.erp').write_bytes(b'scene')
        (self.root/'runtime/hud_template.erp').write_bytes(b'template')
        (self.root/'runtime/overlays.json').write_text('{"ops":[]}')
        self.generate()
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def generate(self):
        Image.new('RGBA', (4, 4), (100, 200, 240, 255)).save(self.root/'art/meter.png')
        (self.root/'registry/hud.json').write_text(json.dumps(self.registry))
        return self.record

    def validation(self):
        record = {'hud_registry_sha256': build_inputs.file_hash(self.root/'registry/hud.json'),
                  'source_inputs_sha256': compatibility.runtime_inputs_fingerprint(),
                  'runtime_archives': {name: build_inputs.file_hash(self.root/'runtime'/name)
                                       for name in ('hud_scene.erp', 'hud_template.erp')}}
        (self.root/'runtime/validation.json').write_text(json.dumps(record))

    def test_artwork_tracks_assets_from_the_second_dial(self):
        self.registry['hud.element']['glass_dial_26'] = {
            'sprites': {'extra': {'png': 'art/extra.png'}}}
        extra=self.root/'art/extra.png'
        Image.new('RGBA',(4,4),(10,20,30,255)).save(extra)
        with mock.patch.object(workflow.composition,'write',side_effect=self.generate) as generate:
            workflow.artwork()
            workflow.artwork()
            self.assertEqual(generate.call_count,1)
            Image.new('RGBA',(4,4),(30,20,10,255)).save(extra)
            workflow.artwork()
            self.assertEqual(generate.call_count,2)

    def test_artwork_reuses_and_invalidates(self):
        with mock.patch.object(workflow.composition, 'write', side_effect=self.generate) as generate:
            workflow.artwork()
            workflow.artwork()
            self.assertEqual(generate.call_count, 1)
            (self.root/'halo/dial.py').write_text('changed source')
            workflow.artwork()
            self.assertEqual(generate.call_count, 2)
            (self.root/'art/meter.png').write_bytes(b'changed output')
            workflow.artwork()
            self.assertEqual(generate.call_count, 3)
            (self.root/'art/meter.png').unlink()
            workflow.artwork()
            self.assertEqual(generate.call_count, 4)

    def test_artwork_recovers_corrupt_cache(self):
        for content in ('{', '[]'):
            with self.subTest(content=content):
                (self.root/'build/artwork-cache.json').write_text(content)
                with mock.patch.object(workflow.composition, 'write', side_effect=self.generate) as generate:
                    workflow.artwork()
                    self.assertEqual(generate.call_count, 1)

    def test_runtime_fingerprint_covers_relevant_inputs(self):
        previous = build_inputs.runtime_inputs_fingerprint()
        for name in ('art/meter.png', 'assets/fonts/Saira/Saira.ttf', 'tools/native_interop.py'):
            path = self.root/name
            path.write_bytes(path.read_bytes()+b'changed')
            current = build_inputs.runtime_inputs_fingerprint()
            self.assertNotEqual(previous, current, name)
            previous = current

    def test_local_configuration_and_launcher_arguments(self):
        self.assertEqual(project_config.local_settings(), {})
        self.assertEqual(project_config.launcher_command('swofty'), ['swofty'])
        settings = {'launcher': 'D:/example/swofty.exe', 'data_dir': 'D:/example/data'}
        (self.root/'project.local.json').write_text(json.dumps(settings))
        self.assertEqual(project_config.local_settings(), settings)
        self.assertEqual(project_config.launcher_command(settings['launcher'], settings['data_dir']),
                         ['D:/example/swofty.exe', '--data-dir', 'D:/example/data'])
        (self.root/'project.local.json').write_text('[]')
        with self.assertRaisesRegex(ValueError, 'Expected an object'):
            project_config.local_settings()

    def test_install_checks_survive_optimized_python(self):
        result = subprocess.run([sys.executable, '-B', '-O', '-c',
                                 "from verify_install import require; require(False, 'verification sentinel')"],
                                cwd=ROOT/'tools', capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('verification sentinel', result.stderr)

    def test_sdk_fetch_records_package_license(self):
        license_data = b'MIT License fixture'
        requests = []
        def response(url, timeout):
            requests.append(url)
            return io.BytesIO(license_data if url.endswith('packages/sdk/LICENSE') else b'// header fixture')
        destination = self.root/'native/include'
        with mock.patch.object(fetch_sdk, 'DEST', destination), \
             mock.patch.object(fetch_sdk, 'HEADERS', ['swofty_api.h']), \
             mock.patch.object(fetch_sdk, 'urlopen', side_effect=response):
            fetch_sdk.main()
        self.assertIn(fetch_sdk.BASE+'packages/sdk/LICENSE', requests)
        self.assertEqual((destination/'LICENSE').read_bytes(), license_data)
        record = json.loads((destination/'source.json').read_text())
        self.assertEqual(record['license']['url'], fetch_sdk.BASE+'packages/sdk/LICENSE')
        self.assertEqual(record['license']['sha256'], build_inputs.file_hash(destination/'LICENSE'))

    def test_public_docs_and_local_configuration_selection(self):
        (self.root/'THIRD_PARTY_NOTICES.md').write_text('fixture notice')
        (self.root/'docs').mkdir()
        (self.root/'docs/DEVELOPMENT.md').write_text('fixture development guide')
        (self.root/'project.local.example.json').write_text('{"launcher":"example"}')
        (self.root/'project.local.json').write_text('{"launcher":"private-local-path"}')
        self.validation()
        packaging.package()
        with zipfile.ZipFile(self.root/'dist/local.workflow-fixture.swoftyaddon') as archive:
            self.assertIn('THIRD_PARTY_NOTICES.md', archive.namelist())
            self.assertIn('docs/DEVELOPMENT.md', archive.namelist())
            self.assertIn('source/docs/DEVELOPMENT.md', archive.namelist())
            self.assertIn('source/project.local.example.json', archive.namelist())
            self.assertNotIn('source/project.local.json', archive.namelist())
            self.assertNotIn('project.local.json', archive.namelist())

    def test_package_rejects_stale_inputs(self):
        self.validation()
        (self.root/'tools/native_interop.py').write_text('changed source')
        with self.assertRaisesRegex(ValueError, 'Runtime inputs changed'):
            packaging.package()

    def test_unchanged_package_reuses_verified_output(self):
        self.validation()
        output = packaging.package()
        original = output.read_bytes()
        with mock.patch.object(zipfile.ZipFile, "writestr", side_effect=AssertionError("Repacked unchanged files")):
            self.assertEqual(packaging.package(), output)
        self.assertEqual(output.read_bytes(), original)

    def test_package_cache_detects_damage_and_source_only_changes(self):
        self.validation()
        output = packaging.package()
        output.write_bytes(b"damaged")
        packaging.package()
        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
        (self.root / "README.md").write_text("updated documentation")
        packaging.package()
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(archive.read("README.md"), b"updated documentation")

    def test_failed_package_preserves_previous(self):
        self.validation()
        output = self.root/'dist/local.workflow-fixture.swoftyaddon'
        output.write_bytes(b'previous package')
        with mock.patch.object(zipfile.ZipFile, 'testzip', return_value='broken entry'):
            with self.assertRaisesRegex(ValueError, 'CRC'):
                packaging.package()
        self.assertEqual(output.read_bytes(), b'previous package')
        self.assertEqual(list(output.parent.glob('*.tmp')), [])

    def test_successful_package_publishes_verified_archive(self):
        self.registry["hud.element"]["glass_dial_26"] = {
            "sprites": {"extra": {"png": "art/extra.png"}}
        }
        (self.root / "registry/hud.json").write_text(json.dumps(self.registry))
        (self.root / "art/extra.png").write_bytes(b"26 sprite")
        (self.root / "art/scratch.png").write_bytes(b"local art")
        (self.root / "tools/scratch.py").write_text("local script")
        self.validation()
        packaging.package()
        output = self.root/'dist/local.workflow-fixture.swoftyaddon'
        with zipfile.ZipFile(output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(json.loads(archive.read('swofty.json'))['version'], '0.0.0')
            self.assertEqual(archive.read("CHANGELOG.md"), archive.read("source/CHANGELOG.md"))
            self.assertEqual(archive.read("source/art/extra.png"), b"26 sprite")
            self.assertNotIn("source/art/scratch.png", archive.namelist())
            self.assertNotIn("source/tools/scratch.py", archive.namelist())
        self.assertEqual(list(output.parent.glob('*.tmp')), [])

    def test_package_requires_unique_release_notes_for_manifest_version(self):
        self.validation()
        changelog = self.root / "CHANGELOG.md"
        for headings in ("## 0.0.1\n\n- Other version\n",
                         "## 0.0.0\n\n- First\n\n## 0.0.0\n\n- Second\n"):
            changelog.write_text(headings)
            with self.assertRaisesRegex(ValueError, "CHANGELOG.md"):
                packaging.package()

    def test_beta_notes_keep_subheadings_and_exclude_other_versions(self):
        changelog = "# Changelog\n\n## 0.15.0-beta.1\n\n### Development\n\n- SDK update\n\n## 0.14.2\n\n- Older release\n"
        self.assertEqual(packaging.release_notes(changelog, "0.15.0-beta.1"),
                         "### Development\n\n- SDK update")


if __name__ == '__main__':
    unittest.main()
