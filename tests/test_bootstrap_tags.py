"""Direct-stock bootstrap guards plus optional tests against owned tag inputs."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bootstrap_tags as bootstrap
from workspace_config import ProjectConfig


class FakeTag:
    def __init__(self, data):
        self.data = data

    def write_to_bytes(self):
        return self.data

    def recompute_checksum(self):
        pass


class FakeBinding:
    class TagFile:
        @staticmethod
        def read(path):
            return FakeTag(path.read_bytes())

        @staticmethod
        def read_from_bytes(data):
            return FakeTag(data)


class BootstrapGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = ProjectConfig(workspace=self.root)

    def inputs(self):
        for name in bootstrap.BOOTSTRAP_INPUTS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('owned:' + name).encode())

    def files(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def render(self, **kwargs):
        with patch.object(bootstrap.importlib, 'import_module', return_value=FakeBinding), \
                patch.object(bootstrap, '_author', return_value={'test_template': True}):
            return bootstrap.build_bootstrap(self.config, **kwargs)

    def test_import_does_not_need_binding_or_touch_workspace(self):
        code = """import sys
class RejectBinding:
    def find_spec(self, fullname, *args):
        if fullname == 'blam_tags':
            raise RuntimeError('native binding imported during module import')
sys.meta_path.insert(0, RejectBinding())
sys.path.insert(0, sys.argv[1])
import bootstrap_tags
assert 'blam_tags' not in sys.modules
"""
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT)],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.files(), {})

    def test_missing_input_fails_before_binding_import_or_output_creation(self):
        self.inputs()
        (self.root / bootstrap.BOOTSTRAP_INPUTS[-1]).unlink()
        before = self.files()
        with patch.object(bootstrap.importlib, 'import_module') as load:
            with self.assertRaisesRegex(bootstrap.BootstrapError, 'Missing owned stock'):
                bootstrap.build_bootstrap(self.config)
        load.assert_not_called()
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / 'native-tags').exists())

    def test_output_parent_file_and_output_directory_rejected_before_import(self):
        self.inputs()
        for relative, directory in [('native-tags', False), (bootstrap.MANIFEST_PATH, True)]:
            with self.subTest(relative=relative):
                path = self.root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir() if directory else path.write_bytes(b'preserve')
                with patch.object(bootstrap.importlib, 'import_module') as load:
                    with self.assertRaises(bootstrap.BootstrapError):
                        bootstrap.build_bootstrap(self.config)
                load.assert_not_called()
                path.rmdir() if directory else path.unlink()

    def test_linked_output_is_rejected_and_external_bytes_preserved(self):
        self.inputs()
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'external.scenario'
            external.write_bytes(b'preserve')
            target = self.root / bootstrap.BOOTSTRAP_OUTPUTS[0]
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest('This host cannot create test symlinks')
            with patch.object(bootstrap.importlib, 'import_module') as load:
                with self.assertRaisesRegex(bootstrap.BootstrapError, 'Redirected'):
                    bootstrap.build_bootstrap(self.config)
            load.assert_not_called()
            self.assertEqual(external.read_bytes(), b'preserve')

    def test_authoring_error_leaves_all_old_output_bytes_untouched(self):
        self.inputs()
        output = self.root / bootstrap.BOOTSTRAP_OUTPUTS[0]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b'existing candidate')
        before = self.files()
        with patch.object(bootstrap.importlib, 'import_module', return_value=FakeBinding), \
                patch.object(bootstrap, '_author', side_effect=bootstrap.BootstrapError('bad template')):
            with self.assertRaisesRegex(bootstrap.BootstrapError, 'bad template'):
                bootstrap.build_bootstrap(self.config)
        self.assertEqual(self.files(), before)

    def test_input_roundtrip_mismatch_rejected_before_authoring(self):
        self.inputs()
        with patch.object(bootstrap.importlib, 'import_module', return_value=FakeBinding), \
                patch.object(FakeBinding.TagFile, 'read', return_value=FakeTag(b'changed')), \
                patch.object(bootstrap, '_author') as author:
            with self.assertRaisesRegex(bootstrap.BootstrapError, 'does not preserve'):
                bootstrap.build_bootstrap(self.config)
        author.assert_not_called()
        self.assertFalse((self.root / 'native-tags').exists())

    def test_authored_roundtrip_mismatch_leaves_no_partial_outputs(self):
        self.inputs()
        before = self.files()
        with patch.object(FakeBinding.TagFile, 'read_from_bytes', return_value=FakeTag(b'bad')):
            with self.assertRaisesRegex(bootstrap.BootstrapError, 'does not round-trip'):
                self.render()
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / 'native-tags').exists())

    def test_check_renders_same_manifest_without_creating_any_output(self):
        self.inputs()
        before = self.files()
        checked = self.render(check=True)
        self.assertEqual(self.files(), before)
        self.assertFalse((self.root / 'native-tags').exists())
        written = self.render()
        self.assertEqual(checked, written)

    def test_late_ui_or_manifest_publish_error_restores_every_previous_file(self):
        self.inputs()
        names = bootstrap.BOOTSTRAP_OUTPUTS + (bootstrap.MANIFEST_PATH,)
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('previous:' + name).encode())
        before = self.files()
        real_replace = bootstrap.os.replace
        for failing_index in (2, 3):
            def fail_late(source, target):
                if Path(source).name == f'new-{failing_index}':
                    raise OSError('simulated late publication failure')
                return real_replace(source, target)
            with self.subTest(output=names[failing_index]), \
                    patch.object(bootstrap.os, 'replace', side_effect=fail_late), \
                    self.assertRaisesRegex(OSError, 'late publication failure'):
                self.render()
            self.assertEqual(self.files(), before)
            self.assertFalse(list(self.root.glob('.last-stand-bootstrap-*')))

    def test_ui_stage_write_error_does_not_replace_prior_outputs(self):
        self.inputs()
        self.render()
        before = self.files()
        real_write = Path.write_bytes
        def fail_stage(path, data):
            if path.name == 'new-2':
                raise OSError('simulated staging disk error')
            return real_write(path, data)
        with patch.object(Path, 'write_bytes', fail_stage), \
                self.assertRaisesRegex(OSError, 'staging disk error'):
            self.render()
        self.assertEqual(self.files(), before)
        self.assertFalse(list(self.root.glob('.last-stand-bootstrap-*')))

    def test_new_outputs_are_removed_when_manifest_publication_fails(self):
        self.inputs()
        before = self.files()
        real_replace = bootstrap.os.replace
        def fail_manifest(source, target):
            if Path(source).name == 'new-3':
                raise OSError('simulated manifest error')
            return real_replace(source, target)
        with patch.object(bootstrap.os, 'replace', side_effect=fail_manifest), \
                self.assertRaisesRegex(OSError, 'manifest error'):
            self.render()
        self.assertEqual(self.files(), before)
        self.assertFalse(list(self.root.glob('.last-stand-bootstrap-*')))

    def test_rollback_failure_keeps_previous_bytes_for_recovery(self):
        self.inputs()
        names = bootstrap.BOOTSTRAP_OUTPUTS + (bootstrap.MANIFEST_PATH,)
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('previous:' + name).encode())
        before = self.files()
        real_replace = bootstrap.os.replace
        def fail_twice(source, target):
            if Path(source).name in ('new-2', 'old-1'):
                raise OSError('simulated persistent disk error')
            return real_replace(source, target)
        with patch.object(bootstrap.os, 'replace', side_effect=fail_twice), \
                self.assertRaisesRegex(bootstrap.BootstrapRecoveryError, 'recovery files retained'):
            self.render()
        recovery = list(self.root.glob('.last-stand-bootstrap-*'))
        self.assertEqual(len(recovery), 1)
        for index, name in enumerate(names):
            self.assertEqual((recovery[0] / f'old-{index}').read_bytes(), before[name])
        for name in bootstrap.BOOTSTRAP_INPUTS:
            self.assertEqual((self.root / name).read_bytes(), before[name])

    def test_rollback_does_not_overwrite_an_external_edit_after_publication(self):
        self.inputs()
        self.render()
        before = self.files()
        first, second = bootstrap.BOOTSTRAP_OUTPUTS[:2]
        real_replace = bootstrap.os.replace
        def edit_then_fail(source, target):
            if Path(source).name == 'new-1':
                (self.root / first).write_bytes(b'external edit after first publication')
                raise OSError('second replacement failed')
            return real_replace(source, target)
        with patch.object(bootstrap.os, 'replace', side_effect=edit_then_fail), \
                self.assertRaisesRegex(bootstrap.BootstrapRecoveryError, 'Rollback destination changed'):
            self.render()
        self.assertEqual((self.root / first).read_bytes(), b'external edit after first publication')
        self.assertEqual((self.root / second).read_bytes(), before[second])
        recovery = list(self.root.glob('.last-stand-bootstrap-*'))
        self.assertEqual(len(recovery), 1)
        self.assertEqual((recovery[0] / 'old-0').read_bytes(), before[first])

    def test_changed_preimage_is_preserved_and_earlier_publication_rolled_back(self):
        self.inputs()
        self.render()
        before = self.files()
        first, second = bootstrap.BOOTSTRAP_OUTPUTS[:2]
        real_replace = bootstrap.os.replace
        def edit_next(source, target):
            result = real_replace(source, target)
            if Path(source).name == 'new-0':
                (self.root / second).write_bytes(b'external edit before second publication')
            return result
        with patch.object(bootstrap.os, 'replace', side_effect=edit_next), \
                self.assertRaisesRegex(bootstrap.BootstrapRecoveryError, 'changed since preflight'):
            self.render()
        self.assertEqual((self.root / first).read_bytes(), before[first])
        self.assertEqual((self.root / second).read_bytes(), b'external edit before second publication')
        recovery = list(self.root.glob('.last-stand-bootstrap-*'))
        self.assertEqual(len(recovery), 1)
        self.assertEqual((recovery[0] / 'old-1').read_bytes(), before[second])

    def test_only_exact_outputs_written_and_every_hash_matches_actual_bytes(self):
        self.inputs()
        stale = self.root / 'native-tags/levels/survivors/last_stand/birdbase.scenario'
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_bytes(b'historical baseline must not select inputs')
        unrelated = self.root / 'native-tags/objects/survivors/needler_1.weapon'
        unrelated.parent.mkdir(parents=True, exist_ok=True)
        unrelated.write_bytes(b'unrelated old tag')
        before = self.files()
        report = self.render()
        self.assertEqual(set(self.files()) - set(before),
                         set(bootstrap.BOOTSTRAP_OUTPUTS) | {bootstrap.MANIFEST_PATH})
        for name, data in before.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        for record in report['inputs'] + report['outputs']:
            payload = (self.root / record['path']).read_bytes()
            self.assertEqual(record['size'], len(payload))
            self.assertEqual(record['sha256'], hashlib.sha256(payload).hexdigest())
        self.assertEqual(json.loads((self.root / bootstrap.MANIFEST_PATH).read_text()), report)
        after = self.files()
        self.assertEqual(self.render(), report)
        self.assertEqual(self.files(), after)

    def test_cli_config_root_and_check_reach_builder(self):
        config_path = self.root / 'settings.json'
        config_path.write_text('{"schema_version":1,"remote":{"host":"test-kit"}}')
        with patch.object(bootstrap, 'build_bootstrap', return_value={'ok': True}) as build, \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(bootstrap.main(['--config', str(config_path), '--root',
                                             str(self.root), '--check']), 0)
        config = build.call_args.args[0]
        self.assertEqual(config.workspace, self.root)
        self.assertEqual(config.remote_host, 'test-kit')
        self.assertEqual(build.call_args.kwargs, {'check': True})
        self.assertEqual(json.loads(output.getvalue()), {'ok': True})


def owned_available():
    if not all((ROOT / name).is_file() for name in bootstrap.BOOTSTRAP_INPUTS):
        return False
    try:
        __import__('blam_tags')
    except ImportError:
        return False
    return True


def raw_tree(row):
    """Raw rows include unknown data; descend blocks whose payload is separate."""
    children = []
    for name in row.field_names():
        field = row.field(name)
        if field.type_name == 'block':
            children.append((name, tuple(raw_tree(child) for child in field.as_block())))
        elif field.type_name == 'struct':
            children.append((name, raw_tree(field.as_struct())))
    return row.raw, tuple(children)


@unittest.skipUnless(owned_available(), 'Canonical owned bootstrap inputs and binding are unavailable')
class OwnedBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import blam_tags
        cls.binding = blam_tags
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name).resolve()
        for name in bootstrap.BOOTSTRAP_INPUTS:
            path = cls.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, path)
        cls.config = ProjectConfig(workspace=cls.root)
        cls.report = bootstrap.build_bootstrap(cls.config)
        cls.stock = cls.binding.TagFile.read(cls.root / bootstrap.BOOTSTRAP_INPUTS[0])
        cls.original = cls.binding.TagFile.read(cls.root / bootstrap.BOOTSTRAP_INPUTS[1])
        cls.result = cls.binding.TagFile.read(cls.root / bootstrap.BOOTSTRAP_OUTPUTS[0])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_owned_output_is_deterministic_and_parser_roundtrips(self):
        before = {name: (self.root / name).read_bytes()
                  for name in bootstrap.BOOTSTRAP_OUTPUTS + (bootstrap.MANIFEST_PATH,)}
        self.assertEqual(bootstrap.build_bootstrap(self.config), self.report)
        self.assertEqual(before, {name: (self.root / name).read_bytes() for name in before})
        self.assertEqual(self.result.write_to_bytes(), before[bootstrap.BOOTSTRAP_OUTPUTS[0]])

    def test_all_stock_navigation_geometry_lighting_and_placements_preserved(self):
        # Full raw nested navigation rows are compared, not just positions. This
        # deliberately leaves the historical compiled-navigation delta unproven.
        for name in ('zones', 'ai pathfinding data', 'ai user hint data', 'structure bsps',
                     'zone set pvs', 'zone set audibility',
                     'lighting zone sets', 'scenery', 'scenery palette', 'machines',
                     'machine palette', 'reference frames'):
            with self.subTest(block=name):
                original = bootstrap.block(self.original.root(), name)
                result = bootstrap.block(self.result.root(), name)
                self.assertEqual(tuple(raw_tree(row) for row in result),
                                 tuple(raw_tree(row) for row in original))
        self.assertEqual(self.result.root().field('structure seams').value,
                         self.original.root().field('structure seams').value)

    def test_single_ar_profile_no_inherited_needler_or_beacons(self):
        root = self.result.root()
        profiles = bootstrap.block(root, 'player starting profile')
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].field('name').value, 'sv_start')
        self.assertEqual(profiles[0].field('primary weapon').value,
                         (0x77656170, bootstrap.ASSAULT_RIFLE))
        self.assertIsNone(profiles[0].field('secondary weapon').value)
        self.assertNotIn(b'objects\\survivors\\needler_', self.result.write_to_bytes())
        self.assertNotIn(b'sv_marker_', self.result.write_to_bytes())
        self.assertEqual(len(bootstrap.block(root, 'player starting locations')), 1)
        self.assertEqual(bootstrap.block(root, 'player starting locations')[0]
                         .field('campaign player type').value, 'masterchief')

    def test_template_palette_indices_and_outdoor_bindings(self):
        root = self.result.root()
        bootstrap._validate_palettes(self.stock.root())
        for name, field in (('character palette', 'reference'), ('weapon palette', 'name')):
            original = bootstrap.block(self.stock.root(), name)
            result = bootstrap.block(root, name)
            self.assertEqual([result[i].field(field).value for i in range(len(original))],
                             [row.field(field).value for row in original])
        self.assertEqual(bootstrap.block(root, 'character palette')[21].field('reference').value,
                         (0x63686172, bootstrap.FLOOD_CHARACTER))
        zone = bootstrap.block(root, 'zone sets')[0]
        self.assertEqual(zone.field('name').value, 'sv_outdoors')
        self.assertEqual(zone.field('bsp zone flags').value, 1)
        self.assertEqual(zone.field('flags').value, [])
        self.assertEqual(zone.field('pvs index').value, self.report['template']['pvs_index'])
        for name in bootstrap.CLEAR_BLOCKS:
            self.assertEqual(len(bootstrap.block(root, name)), 0, name)
        self.assertEqual(len(bootstrap.block(root, 'squads')), 1)
        objective = bootstrap.block(root, 'ai objectives')[0]
        task = bootstrap.block(objective, 'tasks')[0]
        self.assertEqual(len(bootstrap.block(task, 'direction')), 0)
        self.assertEqual(task.field('parent').value, -1)
        area = bootstrap.block(task, 'areas')[0]
        self.assertEqual(area.field('area').value, self.report['template']['area_index'])

    def test_changed_stock_identity_fails_without_outputs(self):
        tag = self.binding.TagFile.read(self.root / bootstrap.BOOTSTRAP_INPUTS[0])
        bootstrap.put(bootstrap.block(tag.root(), 'character palette')[3], 'reference',
                      (0x63686172, r'objects\characters\brute\ai\brute'))
        outdoor = self.binding.TagFile.read(self.root / bootstrap.BOOTSTRAP_INPUTS[1])
        strings = self.binding.TagFile.read(self.root / bootstrap.BOOTSTRAP_INPUTS[2])
        with self.assertRaisesRegex(bootstrap.BootstrapError, 'identity at 3'):
            bootstrap._author(self.binding, tag, outdoor, strings)

    def test_zone_selection_uses_identity_and_rejects_wrong_bsp_mask(self):
        outdoor = self.binding.TagFile.read(self.root / bootstrap.BOOTSTRAP_INPUTS[1])
        zones = bootstrap.block(outdoor.root(), 'zone sets')
        index = next(i for i, row in enumerate(zones) if row.field('name').value == 'bsp_000')
        zones.swap(index, 3)
        selected, pvs = bootstrap._select_zone(outdoor.root())
        self.assertEqual(selected, 3)
        self.assertEqual(pvs, self.report['template']['pvs_index'])
        self.assertEqual(zones[0].field('name').value, 'sv_outdoors')
        outdoor = self.binding.TagFile.read(self.root / bootstrap.BOOTSTRAP_INPUTS[1])
        row = next(row for row in bootstrap.block(outdoor.root(), 'zone sets')
                   if row.field('name').value == 'bsp_000')
        bootstrap.put(row, 'bsp zone flags', 2)
        with self.assertRaisesRegex(bootstrap.BootstrapError, 'bsp zone flags'):
            bootstrap._select_zone(outdoor.root())


if __name__ == '__main__':
    unittest.main()
