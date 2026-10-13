"""Live HUD authoring guards; real owned-tag readback is explicitly opt-in."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import author_armory_hud as hud
from preflight import ARMORY_INPUTS, ARMORY_OUTPUTS


class ArmoryAuthorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.originals = {}
        for role, name in hud.INPUTS.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            self.originals[role] = ('owned ' + role).encode()
            path.write_bytes(self.originals[role])
        self.payloads = {role: ('authored ' + role).encode() for role in hud.DESTINATIONS}

    def run_author(self):
        with patch.object(hud.importlib, 'import_module', return_value=SimpleNamespace(
                messages=lambda: {'sv_g0_0': 'A0\r\nB1'})), \
                patch.object(hud, 'build_payloads', return_value=(self.payloads, {})), \
                redirect_stdout(io.StringIO()):
            return hud.main(self.root)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def test_declarations_match_supported_prepare_contract(self):
        self.assertEqual(set(hud.INPUTS.values()) - {hud.SCENARIO}, set(ARMORY_INPUTS))
        self.assertEqual(set(hud.ADDITIONAL_OUTPUTS), set(ARMORY_OUTPUTS))
        self.assertEqual(len(hud.ADDITIONAL_OUTPUTS), 4)

    def test_explicit_messages_reject_oversized_nonascii_nul_and_ambiguous_line_breaks(self):
        hud.validate_messages({'sv_g0_0': 'Owned1\r\nLocked0'})
        hud.validate_messages({'sv_g0_0': 'A' * 110})
        for messages in ({}, {'foreign': 'A'}, {'sv_g0_0': ''}, {'sv_g0_0': 'A' * 111},
                         {'sv_g0_0': '\u03a9'}, {'sv_g0_0': 'A\0B'},
                         {'sv_g0_0': 'A\nB'}, {'sv_g0_0': 'A\rB'}):
            with self.subTest(messages=messages), self.assertRaises(hud.ArmoryAuthorError):
                hud.validate_messages(messages)

    def test_main_updates_only_declared_scenario_and_four_new_tags(self):
        returned = self.run_author()
        self.assertEqual(set(returned), {self.root / name for name in ARMORY_OUTPUTS})
        for role, name in hud.DESTINATIONS.items():
            self.assertEqual((self.root / name).read_bytes(), self.payloads[role])
        for role, name in hud.INPUTS.items():
            if role != 'scenario':
                self.assertEqual((self.root / name).read_bytes(), self.originals[role])
        self.assertEqual(set(self.snapshot()), set(hud.INPUTS.values()) | set(ARMORY_OUTPUTS))
        self.assertFalse(list(self.root.glob('.armory-hud-*')))

    def test_invalid_templates_cannot_overwrite_existing_outputs(self):
        self.run_author()
        before = self.snapshot()
        with patch.object(hud.importlib, 'import_module', return_value=SimpleNamespace(
                messages=lambda: {'sv_g0_0': 'A'})), \
                patch.object(hud, 'build_payloads', side_effect=hud.ArmoryAuthorError('bad template')), \
                self.assertRaisesRegex(hud.ArmoryAuthorError, 'bad template'):
            hud.main(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_missing_owned_input_blocks_before_binding_import(self):
        (self.root / hud.INPUTS['chud']).unlink()
        before = self.snapshot()
        with patch.object(hud.importlib, 'import_module') as importer, \
                self.assertRaises(hud.ArmoryAuthorError):
            hud.main(self.root)
        importer.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_linked_output_is_rejected(self):
        target = self.root / hud.DESTINATIONS['biped']
        target.parent.mkdir(parents=True)
        outside = self.root / 'keep'
        outside.write_bytes(b'keep')
        try:
            target.symlink_to(outside)
        except OSError as error:
            self.skipTest(str(error))
        with patch.object(hud.importlib, 'import_module') as importer, \
                self.assertRaisesRegex(hud.ArmoryAuthorError, 'Linked'):
            hud.main(self.root)
        importer.assert_not_called()
        self.assertEqual(outside.read_bytes(), b'keep')

    def test_output_hardlink_to_owned_tag_is_rejected(self):
        target = self.root / hud.DESTINATIONS['biped']
        target.parent.mkdir(parents=True)
        try:
            os.link(self.root / hud.INPUTS['biped'], target)
        except OSError as error:
            self.skipTest(str(error))
        with patch.object(hud.importlib, 'import_module') as importer, \
                self.assertRaisesRegex(hud.ArmoryAuthorError, 'aliases'):
            hud.main(self.root)
        importer.assert_not_called()
        self.assertEqual(target.read_bytes(), self.originals['biped'])

    def test_import_never_loads_binding_live_catalog_or_writes(self):
        root = Path(hud.__file__).parent
        code = """import importlib.abc,sys,pathlib
class Refuse(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in ('blam_tags','armory_live'): raise AssertionError('eager import')
sys.meta_path.insert(0,Refuse())
sys.path.insert(0,sys.argv[1])
import author_armory_hud
assert not list(pathlib.Path.cwd().iterdir())
"""
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, '-B', '-c', code, str(root)],
                                    cwd=temporary, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')


@unittest.skipUnless(os.environ.get('LAST_STAND_ARMORY_INPUTS'),
                     'Set LAST_STAND_ARMORY_INPUTS to an owned input-path JSON map')
class OwnedArmoryAuthorTests(unittest.TestCase):
    def setUp(self):
        config = json.loads(Path(os.environ['LAST_STAND_ARMORY_INPUTS']).read_text())
        binding_dir = config.pop('binding_dir', None)
        if binding_dir is not None:
            sys.path.insert(0, binding_dir)
            self.addCleanup(sys.path.remove, binding_dir)
        self.b = __import__('blam_tags')
        self.assertEqual(set(config), set(hud.INPUTS))
        self.originals = {role: Path(path).read_bytes() for role, path in config.items()}

    def test_real_catalog_preserves_stock_strings_and_roundtrips_every_output(self):
        from armory_live import messages
        texts = messages()
        outputs, audit = hud.build_payloads(self.originals, self.b, texts)
        self.assertTrue(audit['scenario_inverse_audit'])
        self.assertTrue(audit['biped_normalized_inverse_audit'])
        source = self.b.TagFile.read_from_bytes(self.originals['hud_messages']).root()
        authored = self.b.TagFile.read_from_bytes(outputs['hud_messages']).root()
        source_data = source.field('string data utf8').value
        data = authored.field('string data utf8').value
        self.assertEqual(data[:len(source_data)], source_data)
        original_refs = source.field('string references').as_block()
        refs = authored.field('string references').as_block()
        self.assertEqual(len(refs), len(original_refs) + len(texts))
        for i in range(len(original_refs)):
            self.assertEqual(hud._snapshot(refs[i]), hud._snapshot(original_refs[i]))
        for i, (name, text) in enumerate(texts.items(), len(original_refs)):
            row = refs[i]
            self.assertEqual(row.field('string id').value, name)
            for field in row.field_names():
                if field.endswith(' offset'):
                    offset = row.field(field).value
                    self.assertEqual(data[offset:data.index(b'\0', offset)].decode(), text)
        for data in outputs.values():
            self.assertEqual(self.b.TagFile.read_from_bytes(data).write_to_bytes(), data)
        scenario = self.b.TagFile.read_from_bytes(outputs['scenario']).root()
        self.assertIn('override globals', scenario.field('flags').value)
        row = scenario.field('override player representations').as_block()[0]
        self.assertEqual(row.field('third person unit').value, (0x62697064, r'objects\survivors\armory'))
        biped = self.b.TagFile.read_from_bytes(outputs['biped']).root()
        reference = biped.field('unit').as_struct().field('NEW HUD INTERFACES').as_block()[0].field('chud interface').value
        self.assertEqual(reference, (0x63686474, r'ui\survivors\armory'))
        globals = self.b.TagFile.read_from_bytes(outputs['chud_globals']).root()
        for skin in globals.field('skins').as_block():
            self.assertEqual(skin.field('chud text').value, (0x756e6963, r'ui\survivors\armory_messages'))

    def test_wrong_owned_roles_existing_override_and_duplicate_ids_fail_before_writes(self):
        cases = []
        wrong = dict(self.originals)
        wrong['biped'] = wrong['chud']
        cases.append((wrong, {'sv_g0_0': 'A'}))
        prior, _ = hud.build_payloads(self.originals, self.b, {'sv_g0_0': 'A'})
        cases.append(({**self.originals, 'scenario': prior['scenario']}, {'sv_g0_0': 'A'}))
        cases.append(({**self.originals, 'hud_messages': prior['hud_messages']}, {'sv_g0_0': 'A'}))
        for inputs, messages in cases:
            with self.assertRaises(hud.ArmoryAuthorError):
                hud.build_payloads(inputs, self.b, messages)


if __name__ == '__main__':
    unittest.main()
