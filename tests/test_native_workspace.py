"""Portable staging tests use fake kits/process probes; no SDK process runs."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bootstrap_tags
import native_workspace as native
from preflight import AUTHORING_INPUTS
from prepare_progression import FIXED_OUTPUTS, UI_OUTPUT
from workspace_config import ProjectConfig


IDLE = {'status': 'idle', 'processes': []}


class NativeWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name).resolve()
        self.root = base / 'source with spaces'
        self.kit = base / 'owned H3EK'
        self.root.mkdir()
        self.kit.mkdir()
        for name in ('tool.exe', 'sapien.exe', 'halo3_tag_test.exe'):
            (self.kit / name).write_bytes(b'fake owned executable; never run')
        (self.kit / 'tags').mkdir()
        (self.kit / 'data').mkdir()
        self.config = ProjectConfig(workspace=self.root, editing_kit=self.kit)
        self.probe = lambda config: IDLE

    def write(self, name, data=b'fixture', root=None):
        path = (root or self.root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return native._record(data)

    def snapshot(self, root=None):
        root = root or self.root
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob('*') if p.is_file()}

    def bootstrap(self):
        result = {'schema_version': 1, 'stage': 'direct-stock-bootstrap',
                  'native_validation': 'required'}
        for key, names in (('inputs', bootstrap_tags.BOOTSTRAP_INPUTS),
                           ('outputs', bootstrap_tags.BOOTSTRAP_OUTPUTS)):
            result[key] = [{'path': name, **self.write(name, name.encode())} for name in names]
        self.write(bootstrap_tags.MANIFEST_PATH, json.dumps(result).encode())
        return result

    def archive(self, members, *, extra=None, linked=False):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            for name, data in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            if extra is not None:
                info = tarfile.TarInfo(extra)
                if linked:
                    info.type = tarfile.SYMTYPE
                    info.linkname = '../../outside'
                    tar.addfile(info)
                else:
                    info.size = 5
                    tar.addfile(info, io.BytesIO(b'extra'))
        return stream.getvalue()

    def progression(self):
        outputs = set(FIXED_OUTPUTS) | {'native-tags/objects/survivors/v3/needler_d12.damage_effect'}
        result = {'schema_version': 1, 'stage': 'authored', 'native_compilation_required': True,
                  'inputs': {name: self.write(name, name.encode()) for name in AUTHORING_INPUTS},
                  'sources': {'prepare_progression.py': self.write('prepare_progression.py', b'authored source')},
                  'outputs': {name: self.write(name, name.encode()) for name in sorted(outputs)}}
        members = {name.removeprefix('native-tags/'): (self.root / name).read_bytes()
                   for name in outputs if '/objects/' in name or name == UI_OUTPUT}
        result['archive'] = {'path': 'v3-native.tar', 'members': sorted(members),
                             **self.write('v3-native.tar', self.archive(members))}
        self.write('progression-build.json', json.dumps(result).encode())
        return result, members

    def stage(self, kind='bootstrap', **kwargs):
        return native.stage(self.config, kind, process_probe=self.probe, **kwargs)

    def test_import_never_inspects_processes_or_imports_native_binding(self):
        code = """import sys,subprocess
class RejectNative:
    def find_spec(self, fullname, *args):
        if fullname == 'blam_tags': raise RuntimeError('native import')
sys.meta_path.insert(0, RejectNative())
subprocess.run=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('process call'))
sys.path.insert(0,sys.argv[1])
import native_workspace
"""
        result = subprocess.run([sys.executable, '-B', '-c', code, str(Path(native.__file__).parent)],
                                cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), {})

    def test_full_check_leaves_workspace_and_kit_byte_identical(self):
        self.bootstrap()
        before, kit_before = self.snapshot(), self.snapshot(self.kit)
        report = self.stage(check=True)
        self.assertEqual(report['status'], 'preflight-passed')
        self.assertFalse(report['native_compilation_verified'])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.snapshot(self.kit), kit_before)

    def test_bootstrap_stages_exact_three_files_and_never_mutates_production_paths(self):
        self.bootstrap()
        self.write('init.txt', b'keep init', self.kit)
        self.write('maps/keep.map', b'keep map', self.kit)
        self.write('saves/CURRENT', b'keep save', self.kit)
        before = self.snapshot(self.kit)
        report = self.stage()
        expected = {native.SCENARIO, native.HSC,
                    'tags/ui/survivors/last_stand.multilingual_unicode_string_list'}
        self.assertEqual(set(self.snapshot(self.kit)) - set(before), expected)
        self.assertEqual(set(report['files']), expected)
        self.assertEqual(report['backups'], {})
        self.assertEqual(report['status'], 'copied-unverified')
        self.assertFalse(report['native_compilation_verified'])
        for name, data in before.items():
            self.assertEqual((self.kit / name).read_bytes(), data)
        self.assertEqual(json.loads((self.root / report['receipt']).read_text()), report)

    def test_existing_destination_requires_replace_and_backups_hold_exact_old_bytes(self):
        self.bootstrap()
        self.write(native.SCENARIO, b'prior scenario', self.kit)
        self.write(native.HSC, b'prior script', self.kit)
        before, kit_before = self.snapshot(), self.snapshot(self.kit)
        with self.assertRaisesRegex(native.WorkspaceError, '--replace'):
            self.stage()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.snapshot(self.kit), kit_before)
        report = self.stage(replace=True)
        self.assertEqual(set(report['backups']), {native.SCENARIO, native.HSC})
        for name, backup in report['backups'].items():
            self.assertEqual((self.root / backup).read_bytes(), kit_before[name])

    def test_unknown_busy_and_inconsistent_process_reports_fail_before_writes(self):
        self.bootstrap()
        before, kit_before = self.snapshot(), self.snapshot(self.kit)
        for report in ({'status': 'unresolved', 'processes': []},
                       {'status': 'busy', 'processes': [{'pid': 1}]},
                       {'status': 'idle', 'processes': [{'pid': 1}]}, None):
            with self.subTest(report=report), self.assertRaisesRegex(native.WorkspaceError, 'confirmed idle'):
                native.stage(self.config, 'bootstrap', process_probe=lambda config: report)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.snapshot(self.kit), kit_before)

    def test_process_recheck_catches_new_session_before_backup_or_copy(self):
        self.bootstrap()
        before = self.snapshot()
        with patch.object(native, 'probe_processes', side_effect=[IDLE, {'status': 'busy', 'processes': [1]}]):
            with self.assertRaises(native.WorkspaceError):
                native.stage(self.config, 'bootstrap')
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.kit / native.SCENARIO).exists())

    def test_missing_or_changed_input_fails_even_when_outputs_match(self):
        self.bootstrap()
        self.write(bootstrap_tags.BOOTSTRAP_INPUTS[0], b'changed stock')
        before = self.snapshot(self.kit)
        with self.assertRaisesRegex(native.WorkspaceError, 'hash mismatch'):
            self.stage()
        self.assertEqual(self.snapshot(self.kit), before)

    def test_bootstrap_duplicate_and_undeclared_manifest_paths_rejected(self):
        manifest = self.bootstrap()
        for entry in ({**manifest['outputs'][0]},
                      {'path': '../outside.scenario', 'size': 0, 'sha256': '0' * 64}):
            with self.subTest(entry=entry):
                altered = {**manifest, 'outputs': manifest['outputs'] + [entry]}
                self.write(bootstrap_tags.MANIFEST_PATH, json.dumps(altered).encode())
                with self.assertRaises(native.WorkspaceError):
                    self.stage()
        self.assertFalse((self.kit / native.SCENARIO).exists())

    def test_progression_archive_and_files_are_exact_stale_tags_stay_unstaged(self):
        manifest, members = self.progression()
        self.write('native-tags/objects/survivors/v3/stale.effect', b'stale')
        report = self.stage('progression')
        self.assertEqual(set(report['files']), {native.SCENARIO, native.HSC} | {'tags/' + n for n in members})
        self.assertFalse((self.kit / 'tags/objects/survivors/v3/stale.effect').exists())
        self.assertEqual((self.kit / native.SCENARIO).read_bytes(),
                         (self.root / 'native-tags/levels/survivors/last_stand/progression-ui.scenario').read_bytes())

    def test_progression_archive_rejects_extra_duplicate_link_and_traversal_members(self):
        manifest, members = self.progression()
        for extra, linked in [('objects/survivors/v3/undeclared.effect', False),
                              (next(iter(members)), False), ('../../outside', False),
                              ('objects/survivors/v3/link.effect', True)]:
            with self.subTest(extra=extra, linked=linked):
                raw = self.archive(members, extra=extra, linked=linked)
                manifest['archive'].update(self.write('v3-native.tar', raw))
                self.write('progression-build.json', json.dumps(manifest).encode())
                with self.assertRaises(native.WorkspaceError):
                    self.stage('progression')
        self.assertFalse((self.kit / native.SCENARIO).exists())

    def test_archive_payload_mismatch_rejected_with_valid_container_hash(self):
        manifest, members = self.progression()
        first = next(iter(members))
        members[first] = b'x' * len(members[first])
        manifest['archive'].update(self.write('v3-native.tar', self.archive(members)))
        self.write('progression-build.json', json.dumps(manifest).encode())
        with self.assertRaisesRegex(native.WorkspaceError, 'Archive bytes differ'):
            self.stage('progression')

    def test_undeclared_progression_output_rejected_even_with_a_valid_hash(self):
        manifest, _ = self.progression()
        manifest['outputs']['init.txt'] = self.write('init.txt', b'bad target')
        self.write('progression-build.json', json.dumps(manifest).encode())
        with self.assertRaisesRegex(native.WorkspaceError, 'undeclared artifacts'):
            self.stage('progression')

    def test_linked_source_destination_and_backup_parent_rejected(self):
        self.bootstrap()
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / 'keep'
            target.write_bytes(b'preserve')
            for root, relative in [(self.root, bootstrap_tags.BOOTSTRAP_INPUTS[0]),
                                   (self.kit, native.SCENARIO), (self.root, 'backups')]:
                with self.subTest(relative=relative):
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    original = path.read_bytes() if path.is_file() else None
                    path.unlink(missing_ok=True)
                    try:
                        path.symlink_to(Path(outside) if relative == 'backups' else target,
                                        target_is_directory=relative == 'backups')
                    except (OSError, NotImplementedError):
                        self.skipTest('Host cannot create test symlinks')
                    try:
                        with self.assertRaises(native.WorkspaceError):
                            self.stage(replace=True)
                        self.assertEqual(target.read_bytes(), b'preserve')
                    finally:
                        path.unlink()
                        if original is not None:
                            path.write_bytes(original)

    def test_late_copy_failure_restores_existing_and_removes_new_files(self):
        self.bootstrap()
        self.write(native.SCENARIO, b'old scenario', self.kit)
        before = self.snapshot(self.kit)
        real_write = native._write_atomic
        def fail(path, data):
            if path == self.kit / 'tags/ui/survivors/last_stand.multilingual_unicode_string_list':
                raise OSError('simulated disk failure')
            return real_write(path, data)
        with patch.object(native, '_write_atomic', side_effect=fail):
            with self.assertRaisesRegex(native.WorkspaceError, 'prior destinations restored'):
                self.stage(replace=True)
        self.assertEqual(self.snapshot(self.kit), before)
        self.assertTrue(list((self.root / 'backups').rglob('last_stand.scenario')))

    def test_readback_copies_bytes_but_cannot_claim_compilation_success(self):
        self.write(native.SCENARIO, b'possibly uncompiled scenario', self.kit)
        before = self.snapshot(self.kit)
        for kind in native.READBACK:
            with self.subTest(kind=kind):
                report = native.readback(self.config, kind, process_probe=self.probe)
                self.assertEqual((self.root / native.READBACK[kind]).read_bytes(), b'possibly uncompiled scenario')
                self.assertFalse(report['native_compilation_verified'])
                self.assertEqual(report['status'], 'copied-unverified')
                self.assertEqual(report['source']['sha256'], report['files'][native.READBACK[kind]]['sha256'])
                with self.assertRaisesRegex(native.WorkspaceError, '--replace'):
                    native.readback(self.config, kind, process_probe=self.probe)
        self.assertEqual(self.snapshot(self.kit), before)

    def test_cli_config_root_kind_and_check_are_forwarded(self):
        settings = self.root / 'settings.json'
        settings.write_text(json.dumps({'schema_version': 1, 'editing_kit': str(self.kit)}))
        with patch.object(native, 'readback', return_value={'native_compilation_verified': False}) as read, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(native.main(['--config', str(settings), '--root', str(self.root),
                                          '--check', 'readback', '--kind', 'bootstrap']), 0)
        self.assertEqual(read.call_args.args[0].editing_kit, self.kit)
        self.assertEqual(read.call_args.args[1], 'bootstrap')
        self.assertTrue(read.call_args.kwargs['check'])
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            native.main(['readback'])


class ProcessProbeTests(unittest.TestCase):
    def test_windows_tasklist_failure_and_matching_process(self):
        config = ProjectConfig(Path('C:/workspace'), Path('C:/H3EK'))
        for output, expected in [('"python.exe","123","Console","1","1 K"\n', 'idle'),
                                 ('"sapien.exe","5","Console","1","1 K"\n', 'busy'),
                                 ('ERROR unavailable', 'unresolved')]:
            with self.subTest(output=output), patch.object(native.sys, 'platform', 'win32'), \
                    patch.object(native.subprocess, 'run', return_value=SimpleNamespace(stdout=output)):
                self.assertEqual(native.probe_processes(config)['status'], expected)
        with patch.object(native.sys, 'platform', 'win32'), \
                patch.object(native.subprocess, 'run', side_effect=OSError('missing tasklist')):
            self.assertEqual(native.probe_processes(config)['status'], 'unresolved')

    def test_linux_wine_main_thread_detected_from_executable_argument(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Path(td)
            process = proc / '123'
            process.mkdir()
            (process / 'comm').write_text('MAIN_THREAD\n')
            (process / 'cmdline').write_bytes(b'Z:\\owned kit\\halo3_tag_test.exe\0')
            with patch.object(native.sys, 'platform', 'linux'), patch.object(native, 'Path', return_value=proc):
                result = native.probe_processes(ProjectConfig(Path('/workspace'), Path('/kit')))
            self.assertEqual(result, {'status': 'busy', 'processes': [{'pid': 123, 'name': 'halo3_tag_test.exe'}]})

    def test_unsupported_platform_is_unresolved(self):
        with patch.object(native.sys, 'platform', 'unsupported'):
            self.assertEqual(native.probe_processes(ProjectConfig(Path('/workspace')))['status'], 'unresolved')

    def test_unreadable_linux_process_cannot_produce_idle_result(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Path(td)
            process = proc / '123'
            process.mkdir()
            (process / 'comm').write_text('MAIN_THREAD\n')
            (process / 'cmdline').mkdir()  # Reading this path as bytes fails.
            with patch.object(native.sys, 'platform', 'linux'), patch.object(native, 'Path', return_value=proc):
                result = native.probe_processes(ProjectConfig(Path('/workspace'), Path('/kit')))
            self.assertEqual(result['status'], 'unresolved')

    def test_relative_or_different_root_launcher_blocks_before_native_child_exists(self):
        with tempfile.TemporaryDirectory() as td:
            proc = Path(td)
            process = proc / '123'
            process.mkdir()
            (process / 'comm').write_text('python3\n')
            for argument in ('launch.py', 'launch_v04.py', '/other/production/launch.py'):
                with self.subTest(argument=argument):
                    (process / 'cmdline').write_bytes(('python3\0' + argument + '\0').encode())
                    with patch.object(native.sys, 'platform', 'linux'), patch.object(native, 'Path', return_value=proc):
                        result = native.probe_processes(ProjectConfig(Path('/workspace'), Path('/kit')))
                    self.assertEqual(result['status'], 'busy')


if __name__ == '__main__':
    unittest.main()
