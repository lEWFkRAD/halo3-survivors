"""Camera behavior in generated progression; native movement still needs QA."""
import unittest

from test_progression_native import ProgressionVM
from progression_hsc import CAMERA_SWITCH_MARGIN


class ProgressionCameraTests(unittest.TestCase):
    def setUp(self):
        self.v = ProgressionVM()
        self.v.boot()
        self.anchors = {
            stage['number']: [camera['name'] for camera in stage['cameras']]
            for stage in self.v.layout['stages']
        }
        self.v.camera_distances.update({
            name: 100.0 for names in self.anchors.values() for name in names
        })
        self.a, self.b = self.anchors[1][:2]
        self.v.globals.update(sv_view_current=-1, sv_restore_clock=0)
        self.v.calls.clear()

    def pans(self):
        return [args for op, args in self.v.calls if op == 'camera_set']

    def select_first(self):
        self.v.camera_distances.update({self.a: 5.0, self.b: 6.0})
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [[self.a, 6]])
        self.v.calls.clear()

    def invalidate_stage(self, stage=1):
        self.v.camera_distances.update({name: -1 for name in self.anchors[stage]})

    def test_initial_view_selects_nearest_valid_anchor(self):
        self.v.camera_distances.update({self.a: -1, self.b: 2.0})
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [[self.b, 6]])
        self.assertEqual(self.v.globals['sv_view_current'], 1001)

    def test_small_distance_alternation_does_not_reverse_pan(self):
        self.select_first()
        for frame in range(100):
            self.v.camera_distances.update({
                self.a: 4.99 if frame % 2 else 5.0,
                self.b: 5.0 if frame % 2 else 4.99,
            })
            self.v.run('sv_follow')
        self.assertEqual(self.pans(), [])
        self.assertEqual(self.v.globals['sv_view_current'], 1000)

    def test_equal_distances_keep_current_even_if_other_anchor_scans_first(self):
        self.v.camera_distances.update({self.a: 6.0, self.b: 5.0})
        self.v.run('sv_follow')
        self.v.calls.clear()
        self.v.camera_distances[self.a] = 5.0
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [])
        self.assertEqual(self.v.globals['sv_view_current'], 1001)

    def test_margin_boundary_holds_then_meaningful_movement_switches(self):
        self.select_first()
        self.v.camera_distances[self.b] = 5.0 - CAMERA_SWITCH_MARGIN
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [])
        self.v.camera_distances[self.b] -= 0.01
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [[self.b, 6]])
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [[self.b, 6]])

    def test_invalid_current_anchor_switches_immediately(self):
        self.select_first()
        self.v.camera_distances[self.a] = -1
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [[self.b, 6]])

    def test_each_stage_switches_without_comparing_previous_stage_distance(self):
        self.select_first()
        for stage in range(2, 5):
            with self.subTest(stage=stage):
                target = self.anchors[stage][1]
                self.v.globals['sv_stage'] = stage
                self.v.camera_distances[target] = 99.99
                self.v.run('sv_follow')
                self.assertEqual(self.pans()[-1], [target, 6])
                self.assertEqual(self.v.globals['sv_view_current'], stage * 1000 + 1)
        self.assertEqual(len(self.pans()), 3)

    def test_no_valid_anchor_does_not_pan_or_forget_current(self):
        self.select_first()
        self.invalidate_stage()
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [])
        self.assertEqual(self.v.globals['sv_view_current'], 1000)

    def test_missing_player_never_pans_and_follow_recovers_when_player_returns(self):
        self.select_first()
        self.v.player_count = 0
        self.v.camera_distances[self.b] = 1.0
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [])
        self.v.player_count = 1
        self.v.run('sv_follow')
        self.assertEqual(self.pans(), [[self.b, 6]])

    def test_periodic_repair_reapplies_retained_anchor_through_jitter(self):
        self.select_first()
        for frame in range(100):
            self.v.camera_distances.update({
                self.a: 4.99 if frame % 2 else 5.0,
                self.b: 5.0 if frame % 2 else 4.99,
            })
            self.v.run('sv_fast_clock')
        self.assertEqual(self.pans(), [[self.a, 6]] * 10)
        self.assertFalse(self.v.globals['sv_view_refresh'])

    def test_periodic_repair_and_real_movement_emit_one_pan(self):
        self.select_first()
        self.v.camera_distances[self.b] = 1.0
        self.v.globals['sv_restore_clock'] = 27
        self.v.run('sv_fast_clock')
        self.assertEqual(self.pans(), [[self.b, 6]])

    def test_repair_without_valid_anchor_consumes_request_without_pan(self):
        self.select_first()
        for missing_player in (False, True):
            with self.subTest(missing_player=missing_player):
                if missing_player:
                    self.v.player_count = 0
                    self.v.camera_distances[self.a] = 5.0
                else:
                    self.invalidate_stage()
                self.v.globals['sv_restore_clock'] = 27
                self.v.run('sv_restore_controls')
                self.assertEqual(self.pans(), [])
                self.assertFalse(self.v.globals['sv_view_refresh'])

    def test_repair_preserves_live_run_and_input_state(self):
        self.select_first()
        self.v.setrank('needler.damage', 2)
        self.v.setrank('assault_rifle.unlock', 1)
        state = {
            'sv_seconds': 430, 'sv_stage_seconds': 130, 'sv_xp': 81.25,
            'sv_tokens': 7, 'sv_shots': 123, 'sv_selection': 8,
            'sv_menu_latched': True, 'sv_menu_open': True,
        }
        cooldowns = {
            key: 9 for key in self.v.globals
            if key.startswith('sv_w_') and key.endswith('_clock')
        }
        self.assertTrue(cooldowns)
        self.v.globals.update(state | cooldowns)
        squad = next(iter(self.v.living))
        self.v.living[squad] = 2
        self.v.actors[squad] = ['grunt-a', 'grunt-b']
        self.v.actor_health.update({'grunt-a': 30, 'grunt-b': 12})
        self.v.health, self.v.shield = 0.75, 0.5
        self.v.held_input = {'primary_trigger'}
        self.v.ai_enabled = True
        self.v.globals['sv_restore_clock'] = 27
        self.v.run('sv_restore_controls')
        self.assertEqual(self.pans(), [[self.a, 6]])
        self.assertEqual({key: self.v.globals[key] for key in state | cooldowns}, state | cooldowns)
        self.assertEqual(self.v.rank('needler.damage'), 2)
        self.assertEqual(self.v.rank('assault_rifle.unlock'), 1)
        self.assertEqual(self.v.living[squad], 2)
        self.assertEqual(self.v.actors[squad], ['grunt-a', 'grunt-b'])
        self.assertEqual(self.v.actor_health, {'grunt-a': 30, 'grunt-b': 12})
        self.assertEqual((self.v.health, self.v.shield), (0.75, 0.5))
        self.assertEqual(self.v.held_input, {'primary_trigger'})
        self.assertFalse(self.v.ai_enabled)

    def test_finished_run_does_not_repair_or_pan(self):
        self.select_first()
        self.v.globals.update(sv_finished=True, sv_restore_clock=27)
        self.v.camera_distances[self.b] = 1.0
        self.v.run('sv_fast_clock')
        self.assertEqual(self.pans(), [])


if __name__ == '__main__':
    unittest.main()
