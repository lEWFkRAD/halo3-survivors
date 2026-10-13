"""Behavioral targeting checks for the factored native actor scan."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hsc_vm import VM, parse
from generate_progression import normalized_catalog
from progression_hsc import HSC, combat


class TargetingVM(VM):
    def __init__(self):
        super().__init__()
        catalog = normalized_catalog()
        hsc = HSC()
        combat(hsc, catalog['weapons'], catalog['nodes'])
        self.globals, self.scripts = {}, {}
        for form in parse(hsc.render()):
            if form[0] == 'global':
                self.globals[form[2]] = form[3]
            else:
                self.scripts[form[3]] = form[4:]
        self.globals.update(sv_players=['player'], sv_actor_list=[], sv_range=10)
        self.hit_slots = sorted(name for name in self.globals if name.startswith('sv_hit'))
        self.lookups, self.distance_queries = [], []

    def eval(self, expression):
        if isinstance(expression, list):
            if expression[0] == 'list_get':
                self.lookups.append(self.eval(expression[2]))
            elif expression[0] == 'objects_distance_to_object':
                self.distance_queries.append(self.eval(expression[2]))
            elif expression[0] == 'damage_object_effect':
                path, target = [self.eval(value) for value in expression[1:]]
                self.actor_health[target] -= int(path.rsplit('_d', 1)[1])
                self.calls.append(('damage_object_effect', [path, target]))
                return None
        return super().eval(expression)

    def find(self):
        self.lookups.clear()
        self.distance_queries.clear()
        self.run('sv_find_target')
        return self.globals['sv_target']


class TargetScanningTests(unittest.TestCase):
    def setUp(self):
        self.vm = TargetingVM()

    def full_actor_list(self):
        v = self.vm
        actors = [f'actor_{index}' for index in range(65)]
        actors[0] = None
        v.globals['sv_actor_list'] = actors
        v.actor_health = {actor: 1000 for actor in actors if actor is not None}
        v.actor_health[actors[1]] = 0
        v.distances = {actor: 20 for actor in actors if actor is not None}
        for index, distance in ((1, .01), (2, -1), (3, .1), (5, 2), (12, 2),
                                (62, 10), (63, 1), (64, 0)):
            v.distances[actors[index]] = distance
        return actors

    def test_all_64_slots_preserve_nearest_ties_hit_exclusions_and_bounds(self):
        v = self.vm
        actors = self.full_actor_list()
        v.run('sv_clear_hits')
        # The final hit slot must exclude an otherwise nearest actor too.
        v.globals[v.hit_slots[-1]] = actors[3]
        for target, distance, hit_slot in ((actors[63], 1, 0),
                                          (actors[5], 2, 1),
                                          (actors[12], 2, 2)):
            self.assertEqual(v.find(), target)
            self.assertEqual(v.lookups, list(range(64)))
            self.assertEqual(v.globals['sv_nearest'], distance)
            self.assertNotIn(None, v.distance_queries)
            self.assertNotIn(actors[1], v.distance_queries)
            self.assertNotIn(actors[3], v.distance_queries)
            self.assertNotIn(actors[64], v.distance_queries)
            v.globals[f'sv_hit{hit_slot}'] = target
        self.assertEqual(v.find(), 'none')
        self.assertEqual(v.globals['sv_nearest'], 10)
        self.assertEqual(v.lookups, list(range(64)))

    def test_empty_short_and_playerless_lists_do_not_select_invalid_objects(self):
        v = self.vm
        self.assertEqual(v.find(), 'none')
        self.assertEqual(v.lookups, list(range(64)))
        self.assertEqual(v.distance_queries, [])
        v.globals['sv_actor_list'] = [None, 'dead', 'live']
        v.actor_health.update(dead=-1, live=1)
        v.distances.update(dead=0, live=0)
        self.assertEqual(v.find(), 'live')
        self.assertEqual(v.lookups, list(range(64)))
        self.assertEqual(v.distance_queries, ['live'])
        v.globals['sv_players'] = []
        self.assertEqual(v.find(), 'none')
        self.assertEqual(v.globals['sv_nearest'], 10)

    def test_multiple_weapon_hits_keep_order_and_never_repeat_a_live_target(self):
        v = self.vm
        actors = self.full_actor_list()
        # Firing clears prior hits, so remove the already-hit actor from range.
        v.distances[actors[3]] = 30
        v.globals.update(sv_w_needler_range=10, sv_w_needler_targets=len(v.hit_slots))
        v.run('sv_w_needler_fire')
        hits = [args[1] for op, args in v.calls if op == 'damage_object_effect']
        self.assertEqual(hits, [actors[63], actors[5], actors[12]])
        self.assertEqual(v.globals['sv_shots'], 3)
        self.assertTrue(all(v.actor_health[actor] > 0 for actor in hits))
        self.assertEqual(v.lookups, list(range(64)) * len(v.hit_slots))
        self.assertEqual(v.actor_health[actors[64]], 1000)


if __name__ == '__main__':
    unittest.main()
