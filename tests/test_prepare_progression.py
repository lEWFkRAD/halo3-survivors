"""Preparation must finish its prerequisite/import phase before any writes."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import preflight
import prepare_progression
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
        for name in preflight.AUTHORING_SOURCES + preflight.AUTHORING_INPUTS:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture')
        (self.root / 'source').mkdir()

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() if path.is_file() else None
                for path in self.root.rglob('*')}

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
        modules = {
            'progression_catalog': SimpleNamespace(),
            'progression_tags': SimpleNamespace(main=lambda: events.append('tags'), author_damage=lambda: events.append('damage')),
            'generate_progression': SimpleNamespace(main=lambda: events.append('scripts')),
            'author_progression_ui': SimpleNamespace(main=lambda: events.append('ui')),
        }
        def load(name):
            events.append('import ' + name)
            return modules[name]
        def archive_open(*args):
            events.append('archive')
            class Archive:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def add(self, *args, **kwargs):
                    pass
            return Archive()
        with patch.object(prepare_progression.importlib, 'import_module', side_effect=load), patch.object(prepare_progression.tarfile, 'open', side_effect=archive_open), redirect_stdout(io.StringIO()):
            self.assertEqual(prepare_progression.main([]), 0)
        self.assertEqual(set(events[:4]), {'import progression_catalog', 'import progression_tags', 'import generate_progression', 'import author_progression_ui'})
        self.assertEqual(events[4:], ['tags', 'scripts', 'damage', 'ui', 'archive'])

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
