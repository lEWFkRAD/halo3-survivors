"""Preparation must finish its prerequisite/import phase before any writes."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import preflight
import prepare_progression
import workspace_config
from workspace_config import ConfigError, ProjectConfig


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = ProjectConfig(workspace=self.root)
        for patcher in (
            patch.object(prepare_progression, 'ROOT', self.root),
            patch.object(prepare_progression, 'load_config', return_value=self.config),
            patch.object(preflight, 'binding_available', return_value=True),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def inputs(self):
        names = preflight.AUTHORING_SOURCES + preflight.AUTHORING_INPUTS + (
            'workspace_config.py', 'preflight.py', 'armory_presentation.py')
        for name in names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        (self.root / 'source').mkdir()

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() if path.is_file() else None
                for path in self.root.rglob('*')}

    def fake_authors(self, events=None):
        events = events if events is not None else []
        def writer(label, names):
            def run(*, root):
                self.assertNotEqual(root, self.root)
                self.assertEqual(root.parent, self.root)
                events.append(label)
                result = []
                for name in names:
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(('authored: ' + name).encode())
                    result.append(path)
                return tuple(result)
            return run
        objects = 'native-tags/objects/survivors/v3/'
        scenario = 'native-tags/levels/survivors/last_stand/'
        modules = {
            name: SimpleNamespace(__file__=str(self.root / (name + '.py')))
            for name in ('progression_tags', 'generate_progression', 'author_progression_ui',
                         'progression_catalog', 'progression_hsc', 'armory_presentation',
                         'author_armory_hud', 'armory_live', 'armory_graph_budget',
                         'workspace_config', 'preflight')
        }
        modules['progression_tags'].main = writer('tags', (
            scenario + 'progression.scenario', 'progression-layout.json',
            *(objects + name for name in ('carrier.biped', 'carrier.character',
                                         'watchtower_gravlift.light', 'watchtower_base.device_machine'))))
        modules['generate_progression'].main = writer('scripts', (
            'source/progression.hsc', 'progression-contract.json'))
        modules['progression_tags'].author_damage = writer('damage', (
            objects + 'needler_d7.damage_effect', objects + 'impact_needler.effect'))
        modules['author_progression_ui'].main = writer('ui', (
            scenario + 'progression-ui.scenario', prepare_progression.UI_OUTPUT))
        hud_writer = writer('hud', preflight.ARMORY_OUTPUTS)
        def hud(*, root):
            path = root / scenario / 'progression-ui.scenario'
            path.write_bytes(path.read_bytes() + b' with HUD override')
            return hud_writer(root=root)
        modules['author_armory_hud'].main = hud
        return modules

    def run_authors(self, modules, args=(), events=None):
        def load(name):
            if events is not None:
                events.append('import ' + name)
            return modules[name]
        with patch.object(prepare_progression.importlib, 'import_module', side_effect=load), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return prepare_progression.main(list(args))

    def test_missing_prerequisites_block_before_imports_or_tar_writes(self):
        before = self.snapshot()
        with patch.object(prepare_progression.importlib, 'import_module') as author_import, patch.object(prepare_progression.tarfile, 'open') as archive, redirect_stdout(io.StringIO()):
            self.assertEqual(prepare_progression.main([]), 2)
        author_import.assert_not_called()
        archive.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_missing_effect_blocks_preparation_despite_other_valid_inputs(self):
        self.inputs()
        (self.root / 'private-inputs/v3/energy_sword.effect').unlink()
        before = self.snapshot()
        with patch.object(prepare_progression.importlib, 'import_module') as author_import, patch.object(prepare_progression.tarfile, 'open') as archive, redirect_stdout(io.StringIO()):
            self.assertEqual(prepare_progression.main([]), 2)
        author_import.assert_not_called()
        archive.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_missing_armory_template_blocks_before_any_author_import(self):
        self.inputs()
        (self.root / preflight.ARMORY_INPUTS[-1]).unlink()
        before = self.snapshot()
        with patch.object(prepare_progression.importlib, 'import_module') as author_import, redirect_stdout(io.StringIO()):
            self.assertEqual(prepare_progression.main([]), 2)
        author_import.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_successful_check_does_not_import_authors_or_modify_files(self):
        self.inputs()
        before = self.snapshot()
        output = io.StringIO()
        with patch.object(prepare_progression.importlib, 'import_module') as author_import, patch.object(prepare_progression.tarfile, 'open') as archive, redirect_stdout(output):
            self.assertEqual(prepare_progression.main(['--check', '--json']), 0)
        author_import.assert_not_called()
        archive.assert_not_called()
        report = json.loads(output.getvalue())
        self.assertTrue(report['ready'])
        self.assertEqual(report['stage'], 'authoring')
        self.assertEqual(self.snapshot(), before)

    def test_failed_check_is_structured_and_read_only(self):
        output = io.StringIO()
        with patch.object(prepare_progression.importlib, 'import_module') as author_import, redirect_stdout(output):
            self.assertEqual(prepare_progression.main(['--check', '--json']), 2)
        author_import.assert_not_called()
        self.assertFalse(json.loads(output.getvalue())['ready'])
        self.assertEqual(self.snapshot(), {})

    def test_late_module_import_failure_happens_before_any_author_calls(self):
        self.inputs()
        events = []
        tags = SimpleNamespace(main=lambda: events.append('write tags'), author_damage=lambda: events.append('write damage'))
        generator = SimpleNamespace(main=lambda: events.append('write scripts'))
        def load(name):
            events.append('import ' + name)
            if name == 'author_progression_ui':
                raise ImportError('native binding failed to load')
            return {'progression_tags': tags, 'generate_progression': generator, 'progression_catalog': SimpleNamespace()}[name]
        before = self.snapshot()
        with patch.object(prepare_progression.importlib, 'import_module', side_effect=load), patch.object(prepare_progression.tarfile, 'open') as archive, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(prepare_progression.main([]), 2)
        self.assertTrue(events)
        self.assertTrue(all(event.startswith('import ') for event in events), events)
        self.assertEqual(events[-1], 'import author_progression_ui')
        archive.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_catalog_import_failure_blocks_before_any_author_calls(self):
        self.inputs()
        events = []
        modules = {
            'progression_tags': SimpleNamespace(main=lambda: events.append('write tags'), author_damage=lambda: events.append('write damage')),
            'generate_progression': SimpleNamespace(main=lambda: events.append('write scripts')),
            'author_progression_ui': SimpleNamespace(main=lambda: events.append('write ui')),
        }
        def load(name):
            events.append('import ' + name)
            if name == 'progression_catalog':
                raise SyntaxError('broken catalog')
            return modules[name]
        before = self.snapshot()
        with patch.object(prepare_progression.importlib, 'import_module', side_effect=load), patch.object(prepare_progression.tarfile, 'open') as archive, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(prepare_progression.main([]), 2)
        self.assertTrue(all(event.startswith('import ') for event in events), events)
        self.assertEqual(events[-1], 'import progression_catalog')
        archive.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_missing_source_directory_blocks_before_author_imports(self):
        self.inputs()
        (self.root / 'source').rmdir()
        before = self.snapshot()
        with patch.object(prepare_progression.importlib, 'import_module') as author_import, patch.object(prepare_progression.tarfile, 'open') as archive, redirect_stdout(io.StringIO()):
            self.assertEqual(prepare_progression.main([]), 2)
        author_import.assert_not_called()
        archive.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_all_modules_load_before_authors_run_and_archive_is_last(self):
        self.inputs()
        events = []
        modules = self.fake_authors(events)
        actual_open = tarfile.open
        def archive_open(*args, **kwargs):
            events.append('archive')
            return actual_open(*args, **kwargs)
        with patch.object(prepare_progression.tarfile, 'open', side_effect=archive_open):
            self.assertEqual(self.run_authors(modules, events=events), 0)
        self.assertEqual(set(events[:11]), {'import ' + name for name in modules})
        self.assertEqual(events[11:], ['tags', 'scripts', 'damage', 'ui', 'hud', 'archive'])

    def test_declared_archive_excludes_stale_files_and_manifest_matches_bytes(self):
        self.inputs()
        stale = self.root / 'native-tags/objects/survivors/v3/stale.damage_effect'
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b'old private tag')
        optional = self.root / prepare_progression.OPTIONAL_INPUTS[0]
        optional.write_text('{"infection":"owned-path"}')
        before_inputs = {name: (self.root / name).read_bytes()
                         for name in (*preflight.AUTHORING_INPUTS, *prepare_progression.OPTIONAL_INPUTS)}
        self.assertEqual(self.run_authors(self.fake_authors()), 0)
        manifest = json.loads((self.root / 'progression-build.json').read_text())
        self.assertTrue(manifest['native_compilation_required'])
        self.assertEqual(manifest['stage'], 'authored')
        self.assertNotIn(stale.relative_to(self.root).as_posix(), manifest['outputs'])
        self.assertEqual(stale.read_bytes(), b'old private tag')
        for name, content in before_inputs.items():
            self.assertEqual(manifest['inputs'][name], {
                'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content)})
        for name, expected in manifest['outputs'].items():
            content = (self.root / name).read_bytes()
            self.assertEqual(expected, {'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content)})
        archive_bytes = (self.root / manifest['archive']['path']).read_bytes()
        self.assertEqual(manifest['archive']['sha256'], hashlib.sha256(archive_bytes).hexdigest())
        self.assertEqual(manifest['archive']['size'], len(archive_bytes))
        with tarfile.open(self.root / 'v3-native.tar') as archive:
            self.assertEqual(archive.getnames(), manifest['archive']['members'])
            self.assertEqual(len(archive.getmembers()), 11)
            for member in archive.getmembers():
                self.assertTrue(member.isfile())
                self.assertIn('native-tags/' + member.name, manifest['outputs'])
                self.assertEqual(archive.extractfile(member).read(), (self.root / 'native-tags' / member.name).read_bytes())
        self.assertFalse(any(path.name.startswith('.last-stand-prepare-') for path in self.root.iterdir()))

    def test_archive_bytes_are_deterministic_and_only_manifest_is_last(self):
        self.inputs()
        modules = self.fake_authors()
        self.assertEqual(self.run_authors(modules), 0)
        first_archive = (self.root / 'v3-native.tar').read_bytes()
        first_manifest = (self.root / 'progression-build.json').read_bytes()
        replaces = []
        original_replace = prepare_progression.os.replace
        def replace(source, destination):
            replaces.append(destination.name)
            return original_replace(source, destination)
        with patch.object(prepare_progression.os, 'replace', side_effect=replace):
            self.assertEqual(self.run_authors(modules), 0)
        self.assertEqual(replaces[-2:], ['v3-native.tar', 'progression-build.json'])
        self.assertEqual((self.root / 'v3-native.tar').read_bytes(), first_archive)
        self.assertEqual((self.root / 'progression-build.json').read_bytes(), first_manifest)

    def test_late_author_failure_preserves_every_existing_output(self):
        self.inputs()
        self.assertEqual(self.run_authors(self.fake_authors()), 0)
        before = self.snapshot()
        modules = self.fake_authors()
        ui = modules['author_progression_ui'].main
        def fail(*, root):
            ui(root=root)
            raise ValueError('bad native string table')
        modules['author_progression_ui'].main = fail
        self.assertEqual(self.run_authors(modules), 2)
        self.assertEqual(self.snapshot(), before)

    def test_archive_failure_preserves_every_existing_output(self):
        self.inputs()
        self.assertEqual(self.run_authors(self.fake_authors()), 0)
        before = self.snapshot()
        with patch.object(prepare_progression.tarfile, 'open', side_effect=OSError('archive failed')):
            self.assertEqual(self.run_authors(self.fake_authors()), 2)
        self.assertEqual(self.snapshot(), before)

    def test_hud_failure_after_scenario_rewrite_preserves_all_published_outputs(self):
        self.inputs()
        self.assertEqual(self.run_authors(self.fake_authors()), 0)
        before = self.snapshot()
        modules = self.fake_authors()
        author = modules['author_armory_hud'].main
        def fail(*, root):
            author(root=root)
            raise ValueError('HUD validation failed')
        modules['author_armory_hud'].main = fail
        self.assertEqual(self.run_authors(modules), 2)
        self.assertEqual(self.snapshot(), before)

    def test_undeclared_or_invalid_output_never_reaches_publication(self):
        self.inputs()
        for invalid in ('undeclared', 'outside', 'directory', 'duplicate', 'missing'):
            with self.subTest(invalid=invalid):
                before = self.snapshot()
                modules = self.fake_authors()
                ui = modules['author_progression_ui'].main
                def wrong(*, root):
                    paths = ui(root=root)
                    if invalid == 'outside':
                        return (*paths, self.root / 'outside.effect')
                    if invalid == 'duplicate':
                        return (*paths, paths[0])
                    if invalid == 'missing':
                        paths[0].unlink()
                        return paths
                    path = root / 'native-tags/objects/survivors/v3/forgotten.effect'
                    if invalid == 'directory':
                        path.mkdir()
                        return (*paths, path)
                    path.write_bytes(b'undeclared')
                    return paths
                modules['author_progression_ui'].main = wrong
                self.assertEqual(self.run_authors(modules), 2)
                self.assertEqual(self.snapshot(), before)

    def test_author_cannot_rewrite_its_owned_input_snapshot(self):
        self.inputs()
        before = self.snapshot()
        modules = self.fake_authors()
        ui = modules['author_progression_ui'].main
        def mutate(*, root):
            paths = ui(root=root)
            (root / preflight.AUTHORING_INPUTS[0]).write_bytes(b'modified input')
            return paths
        modules['author_progression_ui'].main = mutate
        self.assertEqual(self.run_authors(modules), 2)
        self.assertEqual(self.snapshot(), before)

    def test_root_argument_controls_inputs_and_outputs_independently_of_checkout(self):
        self.inputs()
        with tempfile.TemporaryDirectory() as other:
            checkout = Path(other).resolve()
            with patch.object(prepare_progression, 'ROOT', checkout), patch.object(prepare_progression, 'load_config', wraps=workspace_config.load_config) as load:
                self.assertEqual(self.run_authors(self.fake_authors(), ['--root', str(self.root)]), 0)
            load.assert_called_once_with(None, workspace=self.root)
            self.assertEqual(list(checkout.iterdir()), [])
        self.assertTrue((self.root / 'progression-build.json').is_file())

    def test_real_generator_writes_only_configured_workspace(self):
        import generate_progression
        repo = Path(generate_progression.__file__).parent
        shutil.copyfile(repo / 'progression-layout.json', self.root / 'progression-layout.json')
        (self.root / 'source').mkdir()
        original = (repo / 'source/progression.hsc').read_bytes()
        with redirect_stdout(io.StringIO()):
            written = generate_progression.main(root=self.root)
        self.assertEqual(set(written), {self.root / 'source/progression.hsc', self.root / 'progression-contract.json'})
        self.assertEqual((repo / 'source/progression.hsc').read_bytes(), original)
        contract = json.loads((self.root / 'progression-contract.json').read_text())
        self.assertEqual(len(contract['titles']), 127)
        self.assertEqual(len(contract['catalog']['nodes']), 50)

    def test_json_requires_check_to_prevent_implicit_mutation(self):
        with patch.object(prepare_progression.importlib, 'import_module') as author_import, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            prepare_progression.main(['--json'])
        self.assertEqual(error.exception.code, 2)
        author_import.assert_not_called()

    def test_configuration_error_in_json_check_is_machine_readable(self):
        output = io.StringIO()
        with patch.object(prepare_progression, 'load_config', side_effect=ConfigError('invalid settings')), redirect_stdout(output), redirect_stderr(io.StringIO()):
            self.assertEqual(prepare_progression.main(['--check', '--json']), 2)
        report = json.loads(output.getvalue())
        self.assertFalse(report['ready'])
        self.assertEqual(report['error'], 'invalid settings')

    def test_importing_preparation_does_not_load_authors_or_create_files(self):
        spec = importlib.util.spec_from_file_location('preparation_import_check', prepare_progression.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.object(prepare_progression.importlib, 'import_module', side_effect=AssertionError('author import during import')), patch.object(Path, 'mkdir', side_effect=AssertionError('write during import')), patch.object(Path, 'write_text', side_effect=AssertionError('write during import')), patch.object(prepare_progression.tarfile, 'open', side_effect=AssertionError('archive during import')):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.main))


if __name__ == '__main__':
    unittest.main()
