"""Owned-input fetching is explicit, bounded and preserves previous data on failure."""
from dataclasses import replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import shlex
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import fetch_progression_inputs as fetch
from workspace_config import ProjectConfig


class FetchInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'Source Workspace'
        self.root.mkdir()
        self.kit = self.base / "Owned Kit's Directory"
        self.config = ProjectConfig(self.root, editing_kit=self.kit,
                                    remote_host='owned-test-host',
                                    remote_editing_kit="/home/owner/Owned Kit's $(literal)/H3EK",
                                    remote_python='/opt/Python Tools/python3',
                                    ssh=str(self.base / 'SSH Tools/ssh.exe'))
        self.blobs = {}
        for name, relative in fetch.INPUTS.items():
            # Tiny original fixtures have a stock-format header, not Halo data.
            blob = bytearray(80)
            blob[48:52] = fetch.TAG_GROUPS[Path(name).suffix]
            blob[60:68] = b'MALB!gat'
            self.blobs[name] = bytes(blob) + relative.encode('ascii')
            source = self.kit / 'tags' / relative
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(self.blobs[name])
        self.real_run = subprocess.run

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def seed_outputs(self):
        for name in fetch.OUTPUTS:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(('previous:' + name).encode())
        unrelated = self.root / 'private-inputs/v3/keep-me.txt'
        unrelated.write_text('User data must survive.', encoding='utf-8')
        return self.snapshot()

    def remote_emulator(self, command, **kwargs):
        """Execute the actual stdin program locally; no SSH/network is used."""
        self.assertEqual(command[:9], [self.config.ssh, '-o', 'BatchMode=yes', '-o',
                                     'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
                                     '--', self.config.remote_host])
        self.assertEqual(shlex.split(command[9]), [self.config.remote_python, '-c', fetch.REMOTE_PROGRAM])
        self.assertNotIn('shell', kwargs)
        self.assertNotIn(self.config.remote_editing_kit, command[9])
        request = json.loads(kwargs['input'])
        self.assertEqual(request['kit'], self.config.remote_editing_kit)
        self.assertEqual(request['inputs'], fetch.INPUTS)
        request['kit'] = str(self.kit)
        kwargs['input'] = json.dumps(request).encode()
        result = self.real_run([sys.executable, '-B', '-c', fetch.REMOTE_PROGRAM], **kwargs)
        if request['action'] == 'check' and result.returncode == 0:
            report = json.loads(result.stdout)
            for item, relative in zip(report['checks'], fetch.INPUTS.values()):
                item['path'] = str(PurePosixPath(self.config.remote_editing_kit) / 'tags' / relative)
            result.stdout = json.dumps(report).encode()
        return result

    def make_tar(self, *, edit_manifest=None, omit=None, extra=None, corrupt=None, linked=None):
        stream = io.BytesIO()
        records = {name: {'source': fetch.INPUTS[name], 'size': len(blob),
                          'sha256': hashlib.sha256(blob).hexdigest()}
                   for name, blob in self.blobs.items()}
        manifest = {'schema_version': 1, 'files': records}
        if edit_manifest:
            edit_manifest(manifest)
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for name, blob in self.blobs.items():
                if name == omit:
                    continue
                if name == corrupt:
                    blob = blob[:-1] + bytes([blob[-1] ^ 1])
                item = tarfile.TarInfo(name)
                if name == linked:
                    item.type = tarfile.SYMTYPE
                    item.linkname = '../../../outside.tag'
                    archive.addfile(item)
                    continue
                item.size = len(blob)
                archive.addfile(item, io.BytesIO(blob))
            payload = json.dumps(manifest).encode()
            item = tarfile.TarInfo('transfer.json')
            item.size = len(payload)
            archive.addfile(item, io.BytesIO(payload))
            if extra:
                item = tarfile.TarInfo(extra)
                item.size = 3
                archive.addfile(item, io.BytesIO(b'bad'))
        return stream.getvalue()

    def test_import_never_imports_binding_reads_inputs_writes_or_connects(self):
        spec = importlib.util.spec_from_file_location('fetch_import_check', fetch.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'blam_tags': None}), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('mkdir on import')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('read on import')), \
                patch.object(Path, 'write_bytes', side_effect=AssertionError('write on import')), \
                patch.object(subprocess, 'run', side_effect=AssertionError('process on import')):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.fetch_inputs))

    def test_canonical_bootstrap_sword_and_support_provenance(self):
        self.assertEqual(fetch.INPUTS['private-inputs/bootstrap/020_base.scenario'], 'levels/solo/020_base/020_base.scenario')
        self.assertEqual(fetch.INPUTS['private-inputs/bootstrap/070_waste.scenario'], 'levels/solo/070_waste/070_waste.scenario')
        self.assertEqual(fetch.INPUTS['private-inputs/bootstrap/020_base.multilingual_unicode_string_list'], 'ui/chapter_titles/020_base.multilingual_unicode_string_list')
        self.assertEqual(fetch.DAMAGE['energy_sword'], 'objects/weapons/damage_effects/dash_melee.damage_effect')
        self.assertEqual(fetch.INPUTS['private-inputs/v3/energy_blade.weapon'], 'objects/weapons/melee/energy_blade/energy_blade.weapon')
        self.assertEqual(len(fetch.ARMORY), 5)
        for name, path in fetch.ARMORY.items():
            self.assertEqual(fetch.INPUTS['private-inputs/armory/' + name], path)

    def test_local_spaces_exact_files_hashes_and_compatible_metadata(self):
        old = self.seed_outputs()
        with patch.object(subprocess, 'run', side_effect=AssertionError('unexpected remote call')):
            result = fetch.fetch_inputs(self.config)
        self.assertTrue(result['published'])
        self.assertEqual(set(result['files']), set(fetch.INPUTS))
        self.assertEqual(self.snapshot()['private-inputs/v3/keep-me.txt'], old['private-inputs/v3/keep-me.txt'])
        self.assertEqual(set(self.snapshot()), set(fetch.OUTPUTS) | {'private-inputs/v3/keep-me.txt'})
        for name, blob in self.blobs.items():
            self.assertEqual((self.root / name).read_bytes(), blob)
            self.assertEqual(result['files'][name]['sha256'], hashlib.sha256(blob).hexdigest())
        for area in ('bootstrap', 'armory', 'v3'):
            manifest = json.loads((self.root / f'private-inputs/{area}/sources.json').read_text())
            self.assertEqual(manifest['source'], {'mode': 'local', 'editing_kit': str(self.kit)})
            expected = {name: record for name, record in result['files'].items()
                        if name.startswith(f'private-inputs/{area}/')}
            self.assertEqual(manifest['files'], expected)
        self.assertEqual(manifest['damage'], fetch.DAMAGE)
        self.assertEqual(manifest['support'], fetch.SUPPORT)
        characters = json.loads((self.root / 'private-inputs/v3/character-paths.json').read_text())
        self.assertEqual(characters, {k: v.replace('/', '\\') for k, v in fetch.CHARACTERS.items()})

    def test_check_is_stat_only_and_creates_no_outputs_or_temporary_files(self):
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('tag read')), \
                patch.object(Path, 'open', side_effect=AssertionError('tag open')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('mkdir')), \
                patch.object(tempfile, 'mkdtemp', side_effect=AssertionError('temporary write')):
            report = fetch.fetch_inputs(self.config, check=True)
        self.assertTrue(report['ready'])
        self.assertFalse(report['published'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_missing_final_input_blocks_before_any_write(self):
        before = self.seed_outputs()
        final = list(fetch.INPUTS.values())[-1]
        (self.kit / 'tags' / final).unlink()
        with patch.object(tempfile, 'mkdtemp', side_effect=AssertionError('temporary write')):
            result = fetch.fetch_inputs(self.config)
        self.assertFalse(result['ready'])
        self.assertEqual(result['inputs'][-1]['status'], 'missing')
        self.assertEqual(self.snapshot(), before)

    def test_default_does_not_implicitly_contact_onyx(self):
        with patch.object(subprocess, 'run', side_effect=AssertionError('implicit remote')):
            result = fetch.fetch_inputs(replace(self.config, editing_kit=None))
        self.assertFalse(result['ready'])
        self.assertEqual(result['inputs'][0]['path'], 'editing_kit')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_undersized_oversized_and_wrong_type_sources_fail_before_staging(self):
        name = list(fetch.INPUTS.values())[-1]
        source = self.kit / 'tags' / name
        source.write_bytes(b'too short')
        with patch.object(tempfile, 'mkdtemp', side_effect=AssertionError('write')):
            self.assertEqual(fetch.fetch_inputs(self.config)['inputs'][-1]['status'], 'invalid_size')
        source.unlink()
        source.mkdir()
        self.assertEqual(fetch.fetch_inputs(self.config)['inputs'][-1]['status'], 'wrong_type')
        source.rmdir()
        source.write_bytes(self.blobs[list(fetch.INPUTS)[-1]])
        with patch.object(fetch, 'MAX_TOTAL', 1), \
                patch.object(tempfile, 'mkdtemp', side_effect=AssertionError('write')):
            self.assertFalse(fetch.fetch_inputs(self.config)['ready'])
        with patch.object(fetch, 'MAX_FILE', 80):
            self.assertFalse(fetch.fetch_inputs(self.config)['ready'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_output_parent_file_blocks_before_input_read(self):
        (self.root / 'private-inputs').write_text('Do not replace me.')
        with patch.object(tempfile, 'mkdtemp', side_effect=AssertionError('temporary write')):
            result = fetch.fetch_inputs(self.config)
        self.assertFalse(result['ready'])
        self.assertTrue(all(item['status'] == 'unsafe' for item in result['outputs']))
        self.assertEqual((self.root / 'private-inputs').read_text(), 'Do not replace me.')

    def test_symlink_output_file_and_parent_are_rejected(self):
        outside = self.base / 'Outside'
        outside.mkdir()
        (outside / 'keep.txt').write_text('untouched')
        target = self.root / 'private-inputs'
        try:
            target.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'Symlinks unavailable: {error}')
        self.assertFalse(fetch.fetch_inputs(self.config)['ready'])
        self.assertEqual(sorted(p.name for p in outside.iterdir()), ['keep.txt'])
        target.unlink()
        target.mkdir()
        name = next(iter(fetch.INPUTS))
        linked = self.root / name
        linked.parent.mkdir(parents=True)
        linked.symlink_to(outside / 'keep.txt')
        self.assertFalse(fetch.fetch_inputs(self.config)['ready'])
        self.assertEqual((outside / 'keep.txt').read_text(), 'untouched')

    def test_directory_in_place_of_declared_output_is_rejected(self):
        (self.root / fetch.METADATA[-1]).mkdir(parents=True)
        self.assertFalse(fetch.fetch_inputs(self.config)['ready'])

    def test_wrong_kind_and_corrupt_late_input_preserve_all_old_outputs(self):
        before = self.seed_outputs()
        name = list(fetch.INPUTS)[-1]
        path = self.kit / 'tags' / fetch.INPUTS[name]
        good = path.read_bytes()
        for contents in (bytes(len(good)), good[:48] + b'rncs' + good[52:]):
            with self.subTest(contents=contents[48:52]):
                path.write_bytes(contents)
                with self.assertRaisesRegex(fetch.FetchError, 'header'):
                    fetch.fetch_inputs(self.config)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse(list(self.root.glob('.fetch-inputs-*')))

    def test_disappearing_late_input_after_preflight_preserves_previous_files(self):
        before = self.seed_outputs()
        real_stage = fetch._stage_local
        def stage(config, staging, checks):
            (self.kit / 'tags' / list(fetch.INPUTS.values())[-1]).unlink()
            return real_stage(config, staging, checks)
        with patch.object(fetch, '_stage_local', side_effect=stage), \
                self.assertRaises(fetch.FetchError):
            fetch.fetch_inputs(self.config)
        self.assertEqual(self.snapshot(), before)

    def test_publication_failure_rolls_back_already_replaced_files(self):
        before = self.seed_outputs()
        real_replace = fetch.os.replace
        calls = 0
        def replace_one(source, destination):
            nonlocal calls
            calls += 1
            if calls == 5:
                raise OSError('simulated publish failure')
            return real_replace(source, destination)
        with patch.object(fetch.os, 'replace', side_effect=replace_one), \
                self.assertRaisesRegex(fetch.FetchError, 'simulated publish failure'):
            fetch.fetch_inputs(self.config)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(list(self.root.glob('.fetch-inputs-*')))

    def test_failure_rolls_back_new_outputs_and_preserves_recovery_on_rollback_failure(self):
        real_replace = fetch.os.replace
        calls = 0
        def replace_one(source, destination):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('simulated publish failure')
            return real_replace(source, destination)
        with patch.object(fetch.os, 'replace', side_effect=replace_one), \
                self.assertRaises(fetch.FetchError):
            fetch.fetch_inputs(self.config)
        self.assertEqual(self.snapshot(), {})
        self.assertFalse(list(self.root.glob('.fetch-inputs-*')))
        before = self.seed_outputs()
        calls = 0
        def fail_after_first(source, destination):
            nonlocal calls
            calls += 1
            if calls >= 2:
                raise OSError('simulated persistent disk error')
            return real_replace(source, destination)
        with patch.object(fetch.os, 'replace', side_effect=fail_after_first), \
                self.assertRaisesRegex(fetch.RecoveryError, 'recovery files retained'):
            fetch.fetch_inputs(self.config)
        recovery = list(self.root.glob('.fetch-inputs-*'))
        self.assertEqual(len(recovery), 1)
        first = next(iter(fetch.INPUTS))
        self.assertEqual((recovery[0] / 'previous' / first).read_bytes(), before[first])

    def test_rollback_preserves_external_edit_to_an_already_published_output(self):
        before = self.seed_outputs()
        first, second = list(fetch.OUTPUTS)[:2]
        real_replace = fetch.os.replace
        def edit_then_fail(source, destination):
            if Path(destination) == self.root / second:
                (self.root / first).write_bytes(b'external edit after first publication')
                raise OSError('second replacement failed')
            return real_replace(source, destination)
        with patch.object(fetch.os, 'replace', side_effect=edit_then_fail), \
                self.assertRaisesRegex(fetch.RecoveryError, 'Rollback destination changed'):
            fetch.fetch_inputs(self.config)
        self.assertEqual((self.root / first).read_bytes(), b'external edit after first publication')
        for name in fetch.OUTPUTS[1:]:
            self.assertEqual((self.root / name).read_bytes(), before[name])
        recovery = list(self.root.glob('.fetch-inputs-*'))
        self.assertEqual(len(recovery), 1)
        self.assertEqual((recovery[0] / 'previous' / first).read_bytes(), before[first])

    def test_changed_unpublished_preimage_is_preserved_and_prior_publication_reverted(self):
        before = self.seed_outputs()
        first, second = list(fetch.OUTPUTS)[:2]
        real_replace = fetch.os.replace
        def edit_next(source, destination):
            result = real_replace(source, destination)
            if Path(source).as_posix().endswith('/files/' + first):
                (self.root / second).write_bytes(b'external edit before second publication')
            return result
        with patch.object(fetch.os, 'replace', side_effect=edit_next), \
                self.assertRaisesRegex(fetch.RecoveryError, 'changed since preflight'):
            fetch.fetch_inputs(self.config)
        self.assertEqual((self.root / first).read_bytes(), before[first])
        self.assertEqual((self.root / second).read_bytes(), b'external edit before second publication')
        recovery = list(self.root.glob('.fetch-inputs-*'))
        self.assertEqual(len(recovery), 1)
        self.assertEqual((recovery[0] / 'previous' / second).read_bytes(), before[second])

    def test_remote_program_check_reads_no_tag_bytes(self):
        request = json.loads(fetch._remote_request(self.config, 'check'))
        request['kit'] = str(self.kit)
        prefix = "from pathlib import Path\nPath.open=lambda *a,**k: (_ for _ in ()).throw(AssertionError('read tag'))\n"
        result = self.real_run([sys.executable, '-B', '-c', prefix + fetch.REMOTE_PROGRAM],
                               input=json.dumps(request).encode(), capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['ready'])

    def test_remote_argv_quoting_and_roundtrip_keep_paths_literal(self):
        with patch.object(subprocess, 'run', side_effect=self.remote_emulator) as run:
            result = fetch.fetch_inputs(self.config, remote=True)
        self.assertEqual(run.call_count, 2)
        self.assertTrue(result['published'])
        for name, blob in self.blobs.items():
            self.assertEqual((self.root / name).read_bytes(), blob)
        manifest = json.loads((self.root / 'private-inputs/v3/sources.json').read_text())
        self.assertEqual(manifest['source'], {'mode': 'remote', 'host': self.config.remote_host,
                                              'editing_kit': self.config.remote_editing_kit})

    def test_remote_check_never_stages_and_reports_missing(self):
        (self.kit / 'tags' / list(fetch.INPUTS.values())[-1]).unlink()
        with patch.object(subprocess, 'run', side_effect=self.remote_emulator) as run, \
                patch.object(tempfile, 'mkdtemp', side_effect=AssertionError('write')):
            result = fetch.fetch_inputs(self.config, remote=True, check=True)
        self.assertFalse(result['ready'])
        self.assertEqual(run.call_count, 1)

    def test_failed_remote_fetch_leaves_previous_outputs_intact(self):
        before = self.seed_outputs()
        def broken(command, **kwargs):
            if json.loads(kwargs['input'])['action'] == 'check':
                return self.remote_emulator(command, **kwargs)
            kwargs['stdout'].write(b'partial transport')
            return subprocess.CompletedProcess(command, 1, stderr=b'input missing')
        with patch.object(subprocess, 'run', side_effect=broken), \
                self.assertRaisesRegex(fetch.FetchError, 'input missing'):
            fetch.fetch_inputs(self.config, remote=True)
        self.assertEqual(self.snapshot(), before)

    def test_remote_missing_changed_extra_and_duplicate_entries_fail_closed(self):
        before = self.seed_outputs()
        first = next(iter(fetch.INPUTS))
        variants = {
            'corrupt content': self.make_tar(corrupt=first),
            'missing last': self.make_tar(omit=list(fetch.INPUTS)[-1]),
            'outside path': self.make_tar(extra='../outside.tag'),
            'extra tag': self.make_tar(extra='private-inputs/v3/stale.effect'),
            'duplicate': self.make_tar(extra=first),
            'symlink member': self.make_tar(linked=first),
            'bad manifest': self.make_tar(edit_manifest=lambda m: m['files'][first].update(sha256='0' * 64)),
            'truncated archive': b'broken tar data',
        }
        for label, payload in variants.items():
            def remote(command, **kwargs):
                if json.loads(kwargs['input'])['action'] == 'check':
                    return self.remote_emulator(command, **kwargs)
                kwargs['stdout'].write(payload)
                return subprocess.CompletedProcess(command, 0, stderr=b'')
            with self.subTest(label=label), patch.object(subprocess, 'run', side_effect=remote), \
                    self.assertRaises(fetch.FetchError):
                fetch.fetch_inputs(self.config, remote=True)
            self.assertEqual(self.snapshot(), before)
            self.assertFalse(list(self.root.glob('.fetch-inputs-*')))

    def test_remote_timeout_and_invalid_stat_report_fail_without_writes(self):
        for result in (subprocess.TimeoutExpired('ssh', 30),
                       subprocess.CompletedProcess('ssh', 0, stdout=b'{}', stderr=b'')):
            with self.subTest(result=result):
                kwargs = {'side_effect': result} if isinstance(result, Exception) else {'return_value': result}
                with patch.object(subprocess, 'run', **kwargs), self.assertRaises(fetch.FetchError):
                    fetch.fetch_inputs(self.config, remote=True)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_remote_stat_report_cannot_lie_about_missing_input_or_origin(self):
        for change in ('readiness', 'path', 'count', 'size'):
            def corrupt(command, **kwargs):
                result = self.remote_emulator(command, **kwargs)
                report = json.loads(result.stdout)
                if change == 'readiness':
                    report['checks'][-1]['status'] = 'missing'
                elif change == 'path':
                    report['checks'][-1]['path'] = '/other/kit/tag'
                elif change == 'count':
                    report['checks'].pop()
                else:
                    report['checks'][-1]['size'] = True
                result.stdout = json.dumps(report).encode()
                return result
            with self.subTest(change=change), patch.object(subprocess, 'run', side_effect=corrupt), \
                    self.assertRaises(fetch.FetchError):
                fetch.fetch_inputs(self.config, remote=True)
            self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_config_root_check_and_invalid_selection(self):
        config = self.base / 'local.json'
        config.write_text(json.dumps({'schema_version': 1, 'editing_kit': str(self.kit)}))
        output = io.StringIO()
        with patch('sys.stdout', output):
            status = fetch.main(['--config', str(config), '--root', str(self.root), '--check', '--json'])
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(output.getvalue())['ready'])
        self.assertEqual(list(self.root.iterdir()), [])
        output = io.StringIO()
        with patch('sys.stdout', output):
            status = fetch.main(['--config', str(self.base / 'missing.json'), '--root', str(self.root), '--json'])
        self.assertEqual(status, 2)
        self.assertFalse(json.loads(output.getvalue())['published'])


if __name__ == '__main__':
    unittest.main()
