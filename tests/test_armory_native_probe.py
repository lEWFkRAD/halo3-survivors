"""Publication guards run without owned tags; optional real-input readback is explicit."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import armory_native_probe as probe


class ProbePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = {}
        for name in probe.INPUT_GROUPS:
            path = self.root / (name + '.input')
            path.write_bytes(('original ' + name).encode())
            self.inputs[name] = path
        self.output = self.root / 'candidate'
        self.originals = {k: p.read_bytes() for k, p in self.inputs.items()}
        self.payloads = {name: ('authored ' + name).encode() for name in probe.DESTINATIONS}
        self.binding = patch.object(probe, '_binding', return_value=object()).start()
        self.addCleanup(patch.stopall)
        self.author = patch.object(probe, '_build_payloads',
                                  return_value=(self.payloads, {'test_fixture': True})).start()

    def run_author(self, **kwargs):
        return probe.author_probe(**self.inputs, output_dir=self.output, **kwargs)

    def assert_inputs_unchanged(self):
        self.assertEqual({k: p.read_bytes() for k, p in self.inputs.items()}, self.originals)

    def assert_no_staging(self):
        self.assertFalse(list(self.root.glob('.armory-probe-*')))

    def test_exact_files_and_manifest_match_payloads(self):
        receipt = self.run_author(override_globals=True)
        expected = set(probe.DESTINATIONS.values()) | {probe.MANIFEST}
        actual = {p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(actual, expected)
        self.assertEqual(json.loads((self.output / probe.MANIFEST).read_text()), receipt)
        self.assertEqual(receipt['native_status'], 'not_run')
        for name, data in self.payloads.items():
            destination = probe.DESTINATIONS[name]
            self.assertEqual((self.output / destination).read_bytes(), data)
            self.assertEqual(receipt['outputs'][destination], {
                'native_destination': destination, 'bytes': len(data),
                'sha256': hashlib.sha256(data).hexdigest()})
        self.assertTrue(self.author.call_args.args[2])
        self.assert_inputs_unchanged()
        self.assert_no_staging()

    def test_existing_empty_directory_is_supported(self):
        self.output.mkdir()
        self.run_author()
        self.assertTrue((self.output / probe.MANIFEST).is_file())

    def test_nonempty_output_is_preserved_before_import(self):
        self.output.mkdir()
        sentinel = self.output / 'sentinel'
        sentinel.write_bytes(b'external')
        with self.assertRaisesRegex(probe.ProbeError, 'new or empty'):
            self.run_author()
        self.assertEqual(sentinel.read_bytes(), b'external')
        self.binding.assert_not_called()
        self.assert_inputs_unchanged()

    def test_input_directory_cannot_be_output(self):
        self.output = self.root
        with self.assertRaises(probe.ProbeError):
            self.run_author()
        self.binding.assert_not_called()
        self.assert_inputs_unchanged()

    def test_missing_input_fails_before_import_or_output(self):
        self.inputs['chud'] = self.root / 'absent'
        with self.assertRaises(FileNotFoundError):
            self.run_author()
        self.binding.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_input_path_alias_is_rejected(self):
        self.inputs['ui'] = self.inputs['scenario']
        with self.assertRaisesRegex(probe.ProbeError, 'distinct'):
            self.run_author()
        self.binding.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_hard_link_input_alias_is_rejected(self):
        alias = self.root / 'alias'
        try:
            os.link(self.inputs['scenario'], alias)
        except OSError as error:
            self.skipTest(str(error))
        self.inputs['ui'] = alias
        with self.assertRaisesRegex(probe.ProbeError, 'distinct'):
            self.run_author()
        self.binding.assert_not_called()

    def test_linked_output_is_rejected_without_touching_target(self):
        target = self.root / 'real'
        target.mkdir()
        try:
            self.output.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaisesRegex(probe.ProbeError, 'Linked path'):
            self.run_author()
        self.assertEqual(list(target.iterdir()), [])
        self.binding.assert_not_called()

    def test_failed_author_preserves_existing_empty_output(self):
        self.output.mkdir()
        self.author.side_effect = RuntimeError('tag schema rejected')
        with self.assertRaisesRegex(RuntimeError, 'tag schema'):
            self.run_author()
        self.assertEqual(list(self.output.iterdir()), [])
        self.assert_inputs_unchanged()
        self.assert_no_staging()

    def test_failed_binding_does_not_create_output(self):
        self.binding.side_effect = ImportError('binding missing')
        with self.assertRaisesRegex(ImportError, 'binding missing'):
            self.run_author()
        self.author.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_undeclared_outputs_are_rejected(self):
        self.author.return_value = ({**self.payloads, '../escape': b'bad'}, {})
        with self.assertRaisesRegex(probe.ProbeError, 'undeclared'):
            self.run_author()
        self.assertFalse(self.output.exists())
        self.assert_no_staging()

    def test_input_changed_during_authoring_prevents_publication(self):
        def changing_author(*args):
            self.inputs['scenario'].write_bytes(b'external edit')
            return self.payloads, {}
        self.author.side_effect = changing_author
        with self.assertRaisesRegex(probe.ProbeError, 'input changed'):
            self.run_author()
        self.assertEqual(self.inputs['scenario'].read_bytes(), b'external edit')
        self.assertFalse(self.output.exists())
        self.assert_no_staging()

    def test_concurrent_output_file_is_preserved(self):
        def changing_author(*args):
            self.output.mkdir()
            (self.output / 'external').write_bytes(b'keep')
            return self.payloads, {}
        self.author.side_effect = changing_author
        with self.assertRaisesRegex(probe.ProbeError, 'new or empty'):
            self.run_author()
        self.assertEqual((self.output / 'external').read_bytes(), b'keep')
        self.assertEqual(len(list(self.output.iterdir())), 1)
        self.assert_no_staging()

    def test_publication_failure_restores_empty_output_without_partial_manifest(self):
        self.output.mkdir()
        with patch.object(probe.os, 'rename', side_effect=OSError('rename blocked')):
            with self.assertRaisesRegex(OSError, 'rename blocked'):
                self.run_author()
        self.assertEqual(list(self.output.iterdir()), [])
        self.assert_inputs_unchanged()
        self.assert_no_staging()

    def test_cli_passes_explicit_paths_and_override(self):
        argv = [arg for key, path in self.inputs.items()
                for arg in ('--' + key.replace('_', '-'), str(path))]
        argv += ['--output-dir', str(self.output), '--override-globals']
        with patch('builtins.print'):
            self.assertEqual(probe.main(argv), 0)
        self.assertTrue(self.author.call_args.args[2])
        self.assertTrue((self.output / probe.MANIFEST).exists())


class ProbeMessageTests(unittest.TestCase):
    def test_catalog_and_seeded_examples_remain_distinct(self):
        from armory_presentation import native_page_titles
        messages, seeded = probe.make_messages()
        self.assertEqual(messages['sv_armory_probe'],
                         native_page_titles()['sv_tree_0'].replace('\n', '\r\n')
                         + '\r\nEND ARMORY PROBE')
        self.assertEqual({n['state'] for n in seeded['nodes']},
                         {'maxed', 'purchased', 'available', 'locked'})
        self.assertIn('SEEDED DISPLAY PROBE', messages['sv_armory_owned'])
        self.assertIn('Read-only sample: stage 2 | points 3', messages['sv_armory_owned'])
        self.assertEqual(messages['sv_armory_wallet'], 'ARMORY / 3 UPGRADE POINTS')
        self.assertLessEqual(len(messages['sv_armory_compact']), 110)
        self.assertIn('SEEDED', messages['sv_armory_compact'])
        for state in ('MAX', 'OWN', 'BUY', 'LOCK'):
            self.assertIn(state, messages['sv_armory_compact'])
        ruler = messages['sv_armory_ruler']
        self.assertEqual(len(ruler), 320)
        for offset in range(0, 320, 10):
            self.assertEqual(ruler[offset:offset+10], f'{offset:03d}......|')
        self.assertTrue(all('\n' not in value.replace('\r\n', '') for value in messages.values()))

    def test_import_and_help_do_not_load_binding_or_write_files(self):
        root = Path(probe.__file__).resolve().parent
        with tempfile.TemporaryDirectory() as temporary:
            code = '''
import importlib.abc, pathlib, sys
class RefuseBinding(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == 'blam_tags':
            raise AssertionError('native binding imported')
sys.meta_path.insert(0, RefuseBinding())
sys.path.insert(0, sys.argv[1])
import armory_native_probe
try:
    armory_native_probe.main(['--help'])
except SystemExit as error:
    assert error.code == 0
assert 'blam_tags' not in sys.modules
assert not list(pathlib.Path.cwd().iterdir())
'''
            process = subprocess.run([sys.executable, '-S', '-B', '-c', code, str(root)],
                                     cwd=temporary, capture_output=True, text=True)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertIn('--output-dir', process.stdout)
            self.assertEqual(list(Path(temporary).iterdir()), [])


@unittest.skipUnless(os.environ.get('LAST_STAND_PROBE_INPUTS'),
                     'Set LAST_STAND_PROBE_INPUTS to a private JSON input-path map for owned readback')
class OwnedProbeTests(unittest.TestCase):
    def test_owned_templates_preserve_strings_inputs_and_declared_roundtrips(self):
        config = json.loads(Path(os.environ['LAST_STAND_PROBE_INPUTS']).read_text())
        binding = probe._binding(config.pop('binding_dir', None))
        self.assertEqual(set(config), set(probe.INPUT_GROUPS))
        originals = {k: Path(p).read_bytes() for k, p in config.items()}
        with tempfile.TemporaryDirectory() as temporary:
            for override in (False, True):
                output = Path(temporary) / str(override)
                receipt = probe.author_probe(**config, output_dir=output, override_globals=override)
                self.assertEqual(receipt['audit']['override_globals'], override)
                self.assertEqual({k: Path(p).read_bytes() for k, p in config.items()}, originals)
                self.assertEqual((output / probe.DESTINATIONS['ui']).read_bytes(), originals['ui'])
                original_strings = binding.TagFile.read_from_bytes(originals['hud_messages']).root()
                authored = binding.TagFile.read(output / probe.DESTINATIONS['hud_messages']).root()
                old_data = original_strings.field('string data utf8').value
                data = authored.field('string data utf8').value
                self.assertEqual(data[:len(old_data)], old_data)
                refs = authored.field('string references').as_block()
                old_refs = original_strings.field('string references').as_block()
                self.assertEqual(len(refs), len(old_refs) + len(probe.make_messages()[0]))
                for i in range(len(old_refs)):
                    self.assertEqual(probe._snapshot(refs[i]), probe._snapshot(old_refs[i]))
                for message in receipt['audit']['appended_messages']:
                    row = refs[message['index']]
                    for name in row.field_names():
                        if name.endswith(' offset'):
                            offset = row.field(name).value
                            self.assertEqual(data[offset:data.index(b'\0', offset)].decode(), message['text'])
                scenario = binding.TagFile.read(output / probe.DESTINATIONS['scenario'])
                self.assertEqual('override globals' in scenario.root().field('flags').value, override)
                for path in receipt['outputs']:
                    data = (output / path).read_bytes()
                    self.assertEqual(binding.TagFile.read_from_bytes(data).write_to_bytes(), data)


if __name__ == '__main__':
    unittest.main()
