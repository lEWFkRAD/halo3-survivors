"""LS-06 baseline: exactly one damage path per weapon in generated HSC.

Today every weapon deals instant point damage: HSC selects a target,
plays a cosmetic impact effect on it, and applies damage through a
single per-weapon dispatch (chunked damage_object_effect cases with
radius-0 tags). LS-06 converts attacks to projectiles/melee by
REPLACEMENT: a converted weapon must lose its direct dispatch in the
same change, or it would deal damage twice. These structural tests pin
the pre-spike baseline so a conversion is a deliberate, review-visible
edit of this file, and so double damage cannot arrive by accident.

They walk the parsed HSC from generate_progression.build (the same
forms the HSC-VM tests execute); they prove nothing about native
projectile behavior. See LS06_SPIKE.md.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from hsc_vm import parse
from generate_progression import build, normalized_catalog

# Weapon key -> HSC code, mirroring the rename in generate_progression.build.
CODES = {'assault_rifle': 'ar', 'rocket_launcher': 'rl', 'energy_sword': 'es',
         'plasma_rifle': 'pr', 'shotgun': 'sg', 'needler': 'nl'}


def walk(form):
    yield form
    if isinstance(form, list):
        for item in form:
            yield from walk(item)


class CombatDamagePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = normalized_catalog()
        layout = json.loads((ROOT / 'progression-layout.json').read_text())
        source, _, cls.damage_values = build(cls.data, layout)
        cls.scripts = {}
        for form in parse(source):
            if isinstance(form, list) and len(form) > 3 and form[0] == 'script':
                name = str(form[3])
                assert name not in cls.scripts, name
                cls.scripts[name] = form[4:]
        # Slot count from the same formula progression_hsc.combat uses.
        nodes = cls.data['nodes']
        cls.slots = max(
            int(w['base']['targets'] + sum(
                max(0, e['per_rank']) * n['max_rank']
                for n in nodes if n['weapon'] == key
                for e in n['effects'] if e['stat'] == 'targets'))
            for key, w in cls.data['weapons'].items())

    def damage_cases(self, code):
        """(guard value, tag key, tag value) per case in the dispatch chunks."""
        cases = []
        for call in self.scripts[f'sv_w_{code}_apply_damage']:
            chunk = self.scripts[call[0]]
            for form in chunk:
                self.assertEqual(form[0], 'if')
                guard = form[1]
                self.assertEqual(guard[:2], ['=', f'sv_w_{code}_damage'])
                effect = form[2]
                self.assertEqual(effect[0], 'damage_object_effect')
                self.assertEqual(effect[2], 'sv_target')
                tag = effect[1].rsplit('\\', 1)[-1]
                tag_key, _, tag_value = tag.rpartition('_d')
                cases.append((guard[2], tag_key, int(tag_value)))
        return cases

    def test_exactly_one_apply_damage_dispatch_per_weapon(self):
        for key, code in CODES.items():
            with self.subTest(weapon=key):
                self.assertIn(f'sv_w_{code}_apply_damage', self.scripts)
                callers = [name for name, body in self.scripts.items()
                           if any(form == [f'sv_w_{code}_apply_damage']
                                  for form in walk(body))]
                self.assertEqual(callers, [f'sv_w_{code}_fire'])

    def test_dispatch_cases_are_exactly_the_contract_damage_values(self):
        for key, code in CODES.items():
            with self.subTest(weapon=key):
                cases = self.damage_cases(code)
                self.assertTrue(cases)
                for guard, tag_key, tag_value in cases:
                    self.assertEqual(tag_key, key)
                    # The tag applied is the value the guard selected.
                    self.assertEqual(guard, tag_value)
                values = [tag_value for _, _, tag_value in cases]
                self.assertEqual(len(values), len(set(values)))
                self.assertEqual(sorted(values),
                                 sorted(self.damage_values[key]))

    def test_no_damage_outside_the_dispatches(self):
        total = sum(1 for body in self.scripts.values()
                    for form in walk(body)
                    if isinstance(form, list) and form
                    and form[0] == 'damage_object_effect')
        expected = sum(len(v) for v in self.damage_values.values())
        self.assertEqual(total, expected)

    def test_fire_records_hit_then_applies_once_per_slot(self):
        for key, code in CODES.items():
            with self.subTest(weapon=key):
                body = self.scripts[f'sv_w_{code}_fire']
                slots = [form for form in body
                         if isinstance(form, list) and form
                         and form[0] == 'if']
                self.assertEqual(len(slots), self.slots)
                for index, slot in enumerate(slots):
                    self.assertEqual(slot[1],
                                     ['>', f'sv_w_{code}_targets', index])
                    sequence = [form for form in walk(slot)
                                if isinstance(form, list) and form]
                    hits = [f for f in sequence
                            if f[:2] == ['set', f'sv_hit{index}']]
                    effects = [f for f in sequence
                               if f[0] == 'effect_new_on_object_marker']
                    applies = [f for f in sequence
                               if f == [f'sv_w_{code}_apply_damage']]
                    shots = [f for f in sequence
                             if f[:2] == ['set', 'sv_shots']]
                    self.assertEqual(len(hits), 1)
                    self.assertEqual(len(applies), 1)
                    self.assertEqual(len(shots), 1)
                    self.assertEqual(len(effects), 1)
                    self.assertTrue(effects[0][1].endswith(
                        f'\\impact_{key}'))
                    order = [sequence.index(hits[0]),
                             sequence.index(effects[0]),
                             sequence.index(applies[0]),
                             sequence.index(shots[0])]
                    self.assertEqual(order, sorted(order))


if __name__ == '__main__':
    unittest.main()
