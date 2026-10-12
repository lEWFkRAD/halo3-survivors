"""Prerequisite checks must report gaps without authoring or contacting a game."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import bundle_source
import preflight
from workspace_config import ProjectConfig


REPO = Path(__file__).resolve().parents[1]


def write_fixture(root, names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'owned fixture: ' + name.encode())


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
            for path in root.rglob('*')}


class LocalPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.config = ProjectConfig(workspace=self.root)

    def authoring(self):
        return preflight.inspect_workspace(self.config, 'authoring', binding_probe=lambda: True)

    def prepare_inputs(self):
        write_fixture(self.root, preflight.AUTHORING_SOURCES + preflight.AUTHORING_INPUTS)
        (self.root / 'source').mkdir()

    def test_authoring_lists_every_missing_input_without_creating_outputs(self):
        before = snapshot(self.root)
        report = self.authoring()
        missing = {item['path'] for item in report['checks'] if item['status'] == 'missing'}
        self.assertFalse(report['ready'])
        self.assertTrue({str(self.root / name) for name in preflight.AUTHORING_INPUTS} <= missing)
        self.assertEqual(snapshot(self.root), before)
        self.assertTrue(all(not (self.root / name).exists() for name in preflight.AUTHORING_OUTPUTS))

    def test_all_six_effects_are_mandatory_and_reported_together(self):
        self.prepare_inputs()
        effects = [self.root / f'private-inputs/v3/{weapon}.effect' for weapon in preflight.WEAPONS]
        self.assertEqual(len(effects), 6)
        for path in effects:
            path.unlink()
        report = self.authoring()
        failures = {item['path'] for item in report['checks'] if item['status'] != 'ok'}
        self.assertFalse(report['ready'])
        self.assertEqual(failures, {str(path) for path in effects})

    def test_complete_direct_inputs_do_not_require_generated_outputs(self):
        self.prepare_inputs()
        before = snapshot(self.root)
        report = self.authoring()
        self.assertTrue(report['ready'], report)
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse((self.root / 'progression-contract.json').exists())
        self.assertFalse((self.root / 'progression-layout.json').exists())
        self.assertTrue(any('dependency closure' in value for value in report['limitations']))

    def test_input_directory_is_not_accepted_as_a_tag_file(self):
        self.prepare_inputs()
        target = self.root / preflight.AUTHORING_INPUTS[0]
        target.unlink()
        target.mkdir()
        report = self.authoring()
        self.assertFalse(report['ready'])
        self.assertEqual(next(item['status'] for item in report['checks'] if item['path'] == str(target)), 'wrong_type')

    def test_missing_binding_blocks_authoring_without_importing_it(self):
        self.prepare_inputs()
        with patch.object(preflight.importlib.util, 'find_spec', return_value=None) as find:
            report = preflight.inspect_workspace(self.config, 'authoring')
        find.assert_called_once_with('blam_tags')
        self.assertFalse(report['ready'])
        self.assertEqual([item['path'] for item in report['checks'] if item['status'] != 'ok'], ['blam_tags'])

    def test_broken_binding_discovery_is_missing_instead_of_crashing(self):
        for error in (ImportError('unavailable'), ValueError('missing module spec')):
            with self.subTest(error=error), patch.object(preflight.importlib.util, 'find_spec', side_effect=error):
                self.assertFalse(preflight.binding_available())

    def test_output_with_file_as_parent_is_rejected_without_mutation(self):
        (self.root / 'source').write_bytes(b'keep this file')
        report = preflight.output_safety(self.root, 'source/progression.hsc')
        self.assertEqual(report['status'], 'unsafe')
        self.assertEqual((self.root / 'source').read_bytes(), b'keep this file')

    def test_output_of_wrong_type_is_rejected(self):
        (self.root / 'progression-layout.json').mkdir()
        self.assertEqual(preflight.output_safety(self.root, 'progression-layout.json')['status'], 'unsafe')
        path = self.root / 'native-tags/objects/survivors/v3'
        path.parent.mkdir(parents=True)
        path.write_bytes(b'not a directory')
        self.assertEqual(preflight.output_safety(self.root, 'native-tags/objects/survivors/v3')['status'], 'unsafe')

    def test_missing_source_directory_blocks_before_authors_can_write(self):
        self.prepare_inputs()
        (self.root / 'source').rmdir()
        before = snapshot(self.root)
        report = self.authoring()
        self.assertFalse(report['ready'])
        self.assertEqual(next(item['status'] for item in report['checks'] if item['path'] == str(self.root / 'source/progression.hsc')), 'unsafe')
        self.assertEqual(snapshot(self.root), before)

    def symlink(self, path, target, *, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'Symlink creation unavailable: {error}')

    def test_output_symlink_and_symlinked_parent_are_rejected(self):
        target = self.root / 'target'
        target.mkdir()
        self.symlink(self.root / 'source', target, directory=True)
        self.assertEqual(preflight.output_safety(self.root, 'source/progression.hsc')['status'], 'unsafe')
        file_target = self.root / 'target.json'
        file_target.write_bytes(b'preserve')
        self.symlink(self.root / 'progression-layout.json', file_target)
        self.assertEqual(preflight.output_safety(self.root, 'progression-layout.json')['status'], 'unsafe')
        self.assertEqual(file_target.read_bytes(), b'preserve')

    def test_output_directory_rejects_linked_descendants(self):
        directory = self.root / 'native-tags/objects/survivors/v3'
        nested = directory / 'nested'
        nested.mkdir(parents=True)
        target = self.root / 'protected.effect'
        target.write_bytes(b'preserve')
        self.symlink(nested / 'impact.effect', target)
        self.assertEqual(preflight.output_safety(self.root, 'native-tags/objects/survivors/v3')['status'], 'unsafe')
        self.assertEqual(target.read_bytes(), b'preserve')

    def test_native_stage_requires_configuration_and_checks_file_types(self):
        report = preflight.inspect_workspace(self.config, 'native')
        self.assertFalse(report['ready'])
        self.assertEqual(report['checks'][-1]['path'], 'editing_kit')
        kit = self.root / 'Owned H3EK'
        for name, kind in preflight.NATIVE_REQUIREMENTS:
            path = kit / name
            if kind == 'directory':
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
        config = replace(self.config, editing_kit=kit)
        self.assertTrue(preflight.inspect_workspace(config, 'native')['ready'])
        (kit / 'tool.exe').unlink()
        (kit / 'tool.exe').mkdir()
        report = preflight.inspect_workspace(config, 'native')
        self.assertFalse(report['ready'])
        self.assertEqual(next(item['status'] for item in report['checks'] if item['path'] == str(kit / 'tool.exe')), 'wrong_type')

    def test_tools_cli_selects_native_and_uses_override(self):
        output = io.StringIO()
        with patch.object(preflight, 'load_config', return_value=self.config), redirect_stdout(output):
            code = preflight.main(['--tools', str(self.root / 'Other Kit'), '--json'])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(report['stage'], 'native')
        self.assertIn(str(self.root / 'Other Kit' / 'tool.exe'), [item['path'] for item in report['checks']])

    def test_remote_cli_rejects_local_tools_or_non_native_stage(self):
        for args in (['--remote', '--tools', str(self.root)], ['--remote', '--stage', 'source']):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                preflight.main(args)
            self.assertEqual(error.exception.code, 2)

    def test_source_export_runs_preflight_without_owned_inputs(self):
        output = self.root / 'source.zip'
        bundle_source.build_bundle(REPO, output)
        export = self.root / 'export'
        with zipfile.ZipFile(output) as archive:
            archive.extractall(export)
        before = snapshot(export)
        for stage, expected_code in (('source', 0), ('authoring', 2)):
            result = subprocess.run(
                [sys.executable, '-B', str(export / 'preflight.py'), '--stage', stage, '--json'],
                cwd=export, text=True, capture_output=True, timeout=30,
                env={key: value for key, value in os.environ.items() if key != 'LAST_STAND_CONFIG'},
            )
            self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report['stage'], stage)
            self.assertEqual(report['ready'], expected_code == 0)
            if stage == 'authoring':
                self.assertTrue(all(str(export / name) in {item['path'] for item in report['checks'] if item['status'] == 'missing'} for name in preflight.AUTHORING_INPUTS))
        self.assertEqual(snapshot(export), before)
        self.assertFalse((export / 'private-inputs').exists())


class RemotePreflightTests(unittest.TestCase):
    def setUp(self):
        self.config = ProjectConfig(
            workspace=REPO, remote_host='test@host',
            remote_workspace="/owned/Workspace with spaces and 'quotes' $(touch marker)",
            remote_editing_kit='/owned/SDK with spaces; touch marker',
            remote_python='/tools/Python Runtime/python3', ssh='custom-ssh',
        )

    @staticmethod
    def valid_report(request):
        return dict(schema_version=1, stage='native', workspace=request['workspace'], ready=True,
                    checks=[dict(item, status='ok') for item in request['paths']],
                    limitations=request['limitations'])

    def probe(self, transform=None):
        def run(command, **kwargs):
            report = self.valid_report(json.loads(kwargs['input']))
            if transform is not None:
                report = transform(report)
            return subprocess.CompletedProcess(command, 0, json.dumps(report), '')
        with patch.object(preflight.shutil, 'which', return_value='custom-ssh'), patch.object(preflight.subprocess, 'run', side_effect=run):
            return preflight.inspect_remote(self.config)

    def test_ssh_uses_argument_array_and_paths_are_json_data_only(self):
        captured = {}
        def run(command, **kwargs):
            captured.update(command=command, **kwargs)
            report = self.valid_report(json.loads(kwargs['input']))
            return subprocess.CompletedProcess(command, 0, json.dumps(report), '')
        with patch.object(preflight.shutil, 'which', return_value='custom-ssh'), patch.object(preflight.subprocess, 'run', side_effect=run):
            self.assertTrue(preflight.inspect_remote(self.config)['ready'])
        command = captured['command']
        self.assertEqual(command[0], 'custom-ssh')
        self.assertEqual(command[-2], self.config.remote_host)
        self.assertEqual(command[-3], '--')
        self.assertIn('StrictHostKeyChecking=yes', command)
        self.assertIn('BatchMode=yes', command)
        self.assertEqual(shlex.split(command[-1]), [self.config.remote_python, '-c', preflight.REMOTE_PROBE])
        self.assertNotIn(self.config.remote_workspace, command[-1])
        self.assertNotIn(self.config.remote_editing_kit, command[-1])
        self.assertNotIn('shell', captured)
        self.assertEqual(captured['timeout'], 30)
        request = json.loads(captured['input'])
        self.assertEqual(request['workspace'], self.config.remote_workspace)
        self.assertEqual(request['paths'][1]['path'], self.config.remote_editing_kit + '/tool.exe')

    def test_probe_program_performs_real_read_only_stat_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / 'tag file.effect'
            existing.write_bytes(b'owned content')
            missing = root / 'not-created.effect'
            request = dict(workspace=str(root), limitations=list(preflight.LIMITATIONS), paths=[
                dict(path=str(root), expected='directory', hint='workspace'),
                dict(path=str(existing), expected='file', hint='owned tag'),
                dict(path=str(existing), expected='directory', hint='wrong type'),
                dict(path=str(missing), expected='file', hint='missing tag'),
            ])
            before = snapshot(root)
            result = subprocess.run([sys.executable, '-B', '-c', preflight.REMOTE_PROBE], input=json.dumps(request), text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual([item['status'] for item in report['checks']], ['ok', 'ok', 'wrong_type', 'missing'])
            self.assertFalse(report['ready'])
            self.assertEqual(snapshot(root), before)

    def test_missing_ssh_never_attempts_a_connection(self):
        with patch.object(preflight.shutil, 'which', return_value=None), patch.object(preflight.subprocess, 'run') as run:
            with self.assertRaisesRegex(preflight.ProbeError, 'SSH executable'):
                preflight.inspect_remote(self.config)
        run.assert_not_called()

    def test_connection_error_timeout_and_nonzero_exit_are_reported(self):
        for error in (OSError('unavailable'), subprocess.TimeoutExpired('ssh', 30)):
            with self.subTest(error=error), patch.object(preflight.shutil, 'which', return_value='ssh'), patch.object(preflight.subprocess, 'run', side_effect=error):
                with self.assertRaisesRegex(preflight.ProbeError, 'did not complete'):
                    preflight.inspect_remote(self.config)
        result = subprocess.CompletedProcess([], 255, '', 'Host key verification failed.')
        with patch.object(preflight.shutil, 'which', return_value='ssh'), patch.object(preflight.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(preflight.ProbeError, '255.*Host key'):
                preflight.inspect_remote(self.config)

    def test_missing_native_files_return_a_valid_blocked_report(self):
        def mark_missing(report):
            report['checks'][-1]['status'] = 'missing'
            report['ready'] = False
            return report
        report = self.probe(mark_missing)
        self.assertFalse(report['ready'])
        self.assertEqual(report['checks'][-1]['status'], 'missing')

    def test_invalid_or_noisy_json_is_rejected(self):
        for output in ('', 'not JSON', 'login banner\n{}', '[]', 'null'):
            result = subprocess.CompletedProcess([], 0, output, '')
            with self.subTest(output=output), patch.object(preflight.shutil, 'which', return_value='ssh'), patch.object(preflight.subprocess, 'run', return_value=result):
                with self.assertRaisesRegex(preflight.ProbeError, 'invalid report'):
                    preflight.inspect_remote(self.config)

    def test_report_cannot_forge_success_or_change_requested_paths(self):
        def altered(key, value):
            return lambda report: dict(report, **{key: value})
        def change_check(report, key, value):
            report['checks'][0][key] = value
            return report
        cases = [
            altered('schema_version', True), altered('schema_version', 1.0),
            altered('schema_version', 2), altered('stage', 'source'),
            altered('workspace', '/unexpected'), altered('checks', []),
            altered('checks', None), altered('ready', 1), altered('ready', False),
            altered('limitations', []), altered('limitations', 'not a list'),
            lambda report: change_check(report, 'path', '/unexpected'),
            lambda report: change_check(report, 'expected', 'file'),
            lambda report: change_check(report, 'hint', 'untrusted replacement'),
            lambda report: change_check(report, 'status', 'unchecked'),
            lambda report: change_check(report, 'status', 'missing'),
            lambda report: dict(report, checks=[None] * len(report['checks'])),
        ]
        for index, transform in enumerate(cases):
            with self.subTest(case=index), self.assertRaisesRegex(preflight.ProbeError, 'invalid report'):
                self.probe(transform)

    def test_validation_still_runs_when_python_assertions_are_disabled(self):
        code = '''import json, subprocess
from pathlib import Path
from unittest.mock import patch
import preflight
from workspace_config import ProjectConfig
config=ProjectConfig(Path.cwd())
def run(command, **kwargs):
    request=json.loads(kwargs['input'])
    # Complete response with valid paths but an invalid version and success bit.
    report=dict(schema_version=2, stage='native', workspace=request['workspace'],
                ready=False, limitations=request['limitations'],
                checks=[dict(item, status='ok') for item in request['paths']])
    return subprocess.CompletedProcess(command, 0, json.dumps(report), '')
with patch.object(preflight.shutil, 'which', return_value='ssh'), patch.object(preflight.subprocess, 'run', side_effect=run):
    try:
        preflight.inspect_remote(config)
    except preflight.ProbeError:
        pass
    else:
        raise RuntimeError('Invalid remote report accepted under -O')
'''
        result = subprocess.run([sys.executable, '-B', '-O', '-c', code], cwd=REPO, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_json_connection_failure_is_machine_readable(self):
        output = io.StringIO()
        with patch.object(preflight, 'load_config', return_value=self.config), patch.object(preflight, 'inspect_remote', side_effect=preflight.ProbeError('unavailable')), redirect_stdout(output):
            code = preflight.main(['--remote', '--json'])
        self.assertEqual(code, 2)
        report = json.loads(output.getvalue())
        self.assertFalse(report['ready'])
        self.assertEqual(report['error'], 'unavailable')


if __name__ == '__main__':
    unittest.main()
