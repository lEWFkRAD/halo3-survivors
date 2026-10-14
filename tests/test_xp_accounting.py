"""LS-07 baseline: count-derived XP accounting in generated progression.

XP today is inferred, not collected: each squad keeps a _prev living
counter and sv_observe awards (prev - now) * squad xp * sv_xp_scale
when the count drops. LS-07 replaces this with physical drops once a
native death-location mechanism is proved; when pickups become
authoritative, this direct credit must be disabled in the same change
(the LS-06 replacement rule). These tests pin the current accounting
directly so that change is deliberate and review-visible:

- exact awards for single- and multi-squad kills inside one tick;
- exactly-once credit across repeated observes;
- the XP scale multiplier applies to the award;
- count increases never award, and _prev follows the count;
- clearing enemies (transition/victory) awards nothing;
- a respawn baseline is respected (placed actors are not deaths).

HSC-VM behavior tests only; nothing here proves native drop behavior.
See LS07_DROPS.md.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_progression_native import ProgressionVM


class XpAccountingTests(unittest.TestCase):
    def setUp(self):
        self.v = ProgressionVM()
        self.v.boot()
        self.v.run('sv_close_menu')

    def field(self, squad, living):
        self.v.living[squad] = living
        self.v.globals[squad + '_prev'] = living

    def test_single_squad_kills_award_exactly_once(self):
        v = self.v
        self.field('sv_s1_grunts', 6)
        v.living['sv_s1_grunts'] = 4
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 20)  # 2 kills * 10 xp
        v.run('sv_observe')
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 20)
        self.assertEqual(v.globals['sv_s1_grunts_prev'], 4)

    def test_multi_squad_kills_in_one_tick_award_the_sum(self):
        v = self.v
        self.field('sv_s1_grunts', 6)
        self.field('sv_s1_jackals', 4)
        self.field('sv_s1_brutes', 3)
        v.living['sv_s1_grunts'] = 5   # 1 * 10
        v.living['sv_s1_jackals'] = 2  # 2 * 20
        v.living['sv_s1_brutes'] = 3   # 0
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 50)

    def test_xp_scale_multiplies_the_award(self):
        v = self.v
        v.globals['sv_xp_scale'] = 1.5
        self.field('sv_s1_brutes', 3)
        v.living['sv_s1_brutes'] = 2
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 45)  # 1 * 30 * 1.5

    def test_count_increase_never_awards_and_prev_follows(self):
        v = self.v
        self.field('sv_s1_grunts', 4)
        v.living['sv_s1_grunts'] = 6  # infection children, not deaths
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 0)
        self.assertEqual(v.globals['sv_s1_grunts_prev'], 6)
        # The raised baseline is real: the children are combatants, so
        # killing them pays like any other kill (2 * 10 xp). A drop
        # design must decide the same question per child; see
        # LS07_DROPS.md.
        v.living['sv_s1_grunts'] = 4
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 20)

    def test_clear_enemies_awards_nothing(self):
        v = self.v
        self.field('sv_s1_grunts', 6)
        self.field('sv_s1_jackals', 4)
        v.run('sv_clear_enemies')
        # ai_erase is deferred in the engine; the VM applies it through
        # its own path, so zero the living counts as the update would.
        for squad in ('sv_s1_grunts', 'sv_s1_jackals'):
            v.living[squad] = 0
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 0)

    def test_respawn_baseline_is_not_a_death(self):
        v = self.v
        self.field('sv_s1_grunts', 0)
        # Spawn path: ai_place then _prev is set to the placed count.
        v.living['sv_s1_grunts'] = 6
        v.globals['sv_s1_grunts_prev'] = 6
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 0)
        v.living['sv_s1_grunts'] = 5
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 10)

    def test_observe_only_counts_the_current_stage(self):
        v = self.v
        # A stage-2 squad's counter moves while stage 1 is active:
        # sv_observe dispatches to the current stage only.
        self.field('sv_s2_grunts', 6)
        v.living['sv_s2_grunts'] = 0
        v.run('sv_observe')
        self.assertEqual(v.globals['sv_xp'], 0)
        self.assertEqual(v.globals['sv_s2_grunts_prev'], 6)


if __name__ == '__main__':
    unittest.main()
