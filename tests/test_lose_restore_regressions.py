"""LS-03 source regressions: post-lose quiescence and Continue repair cadence.

These are HSC-VM behavior tests (like test_progression_native); they are not
native evidence. They pin two recovery invariants from the LS-03 audit:
after sv_lose the run must stay frozen (no saves, no combat, no clock), and
the Continue control-repair loop must fire on its 30-tick cadence without
resetting run state.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_progression_native import ProgressionVM


class LoseQuiescenceTests(unittest.TestCase):
    def setUp(self):
        self.v = ProgressionVM()
        self.v.boot()

    def test_lose_freezes_run_and_blocks_save_and_combat_paths(self):
        v = self.v
        v.run('sv_close_menu')
        v.globals.update(sv_seconds=12, sv_stage_seconds=12, sv_shots=5,
                         sv_xp=40, sv_tokens=7)
        v.calls.clear()
        v.run('sv_lose')
        self.assertFalse(v.globals['sv_running'])
        self.assertTrue(v.globals['sv_finished'])
        self.assertIn(('cinematic_set_chud_objective', ['sv_loss']), v.calls)
        self.assertFalse(v.training_enabled)
        snapshot = {k: v.globals[k] for k in
                    ('sv_seconds', 'sv_stage_seconds', 'sv_shots', 'sv_xp',
                     'sv_tokens')}
        v.calls.clear()
        # Combat loop, stage clock and menu machinery all stay inert.
        v.fast_frames(30)
        v.run('sv_clock')
        v.run('sv_clock')
        self.assertEqual({k: v.globals[k] for k in snapshot}, snapshot)
        self.assertFalse(any(op == 'core_save_name' for op, _ in v.calls))
        self.assertFalse(any(op == 'damage_object_effect' for op, _ in v.calls))
        self.assertFalse(v.globals['sv_menu_open'])
        # Even a direct checkpoint attempt after the ending cannot save.
        v.run('sv_checkpoint')
        self.assertFalse(any(op == 'core_save_name' for op, _ in v.calls))

    def test_boot_after_lose_starts_fresh_instead_of_reviving_the_run(self):
        v = self.v
        v.run('sv_close_menu')
        v.run('sv_lose')
        self.assertTrue(v.globals['sv_finished'])
        # A fresh boot (the Continue/New Run relaunch path) re-enters stage
        # one through sv_boot rather than un-finishing the lost run in place.
        v2 = ProgressionVM()
        v2.boot()
        self.assertTrue(v2.globals['sv_running'])
        self.assertFalse(v2.globals['sv_finished'])
        self.assertEqual(v2.globals['sv_stage'], 1)


class RestoreCadenceTests(unittest.TestCase):
    def setUp(self):
        self.v = ProgressionVM()
        self.v.boot()

    def test_repair_fires_on_the_tenth_fast_tick_not_before(self):
        v = self.v
        v.globals.update(sv_restore_clock=0, sv_xp=80, sv_seconds=40,
                         sv_shots=67, sv_ar_u=1)
        v.calls.clear()
        for _ in range(9):
            v.run('sv_restore_controls')
        self.assertEqual(v.globals['sv_restore_clock'], 27)
        self.assertFalse(any(op == 'camera_set' for op, _ in v.calls))
        v.run('sv_restore_controls')
        self.assertEqual(v.globals['sv_restore_clock'], 0)
        self.assertTrue(any(op == 'camera_set' for op, _ in v.calls))
        # The repair preserves run state while re-applying the view.
        self.assertEqual([v.globals[k] for k in
                          ('sv_xp', 'sv_seconds', 'sv_shots', 'sv_ar_u')],
                         [80, 40, 67, 1])

    def test_repair_restores_training_state_from_menu(self):
        v = self.v
        v.run('sv_close_menu')
        v.globals['sv_restore_clock'] = 27
        v.run('sv_restore_controls')
        self.assertFalse(v.training_enabled)
        v.run('sv_open_menu')
        v.globals['sv_restore_clock'] = 27
        v.run('sv_restore_controls')
        self.assertTrue(v.training_enabled)


if __name__ == '__main__':
    unittest.main()
