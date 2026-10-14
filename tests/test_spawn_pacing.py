"""LS-09 source tests: encounter schedule consistency and spawn pacing.

Pins, in the HSC VM, the pacing behavior the director relies on:

- the layout's per-stage schedule stays consistent with the catalog's
  stage introductions (families accumulate; carried families keep
  their cohort count and unlock second in every later stage);
- a cohort whose spawn flags are too close to the player does not
  place, while other eligible cohorts in the same stage still do;
- a blocked cohort retries on later spawn cycles and places once its
  flags are clear (no permanent suppression, no partial placement);
- placement is all-or-nothing against the 36-actor cap;
- the infection cohort obeys the same clearance rule as every other
  family (acceptance calls infection forms out explicitly).

Ordinary-run pacing proof remains native work; see LS09_PACING.md.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_progression_native import ProgressionVM
import progression_catalog


class ScheduleConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.v = ProgressionVM()
        self.v.boot()

    def test_layout_schedule_matches_catalog_introductions(self):
        expected = {}
        for stage_def, stage in zip(progression_catalog.STAGES,
                                    self.v.layout['stages']):
            self.assertEqual(stage['number'], stage_def['number'])
            for family in stage_def['new_enemy_types']:
                self.assertNotIn(family, expected)
                expected[family] = None
            squads = {sq['enemy']: sq for sq in stage['squads']}
            self.assertEqual(set(squads), set(expected))
            for family, sq in squads.items():
                signature = (sq['count'], sq['unlock_seconds'])
                if expected[family] is None:
                    expected[family] = signature
                else:
                    # Carried families never change shape between stages.
                    self.assertEqual(signature, expected[family],
                                     f'{family} changed in stage '
                                     f"{stage['number']}")

    def test_stage_rosters_grow_and_stage_four_exceeds_cap_on_paper(self):
        totals = [sum(sq['count'] for sq in stage['squads'])
                  for stage in self.v.layout['stages']]
        self.assertEqual(totals, sorted(totals))
        # 38 roster vs the 36 cap: late cohorts place only as room
        # frees. The pacing doc records this; the cap tests below pin
        # that the runtime honors it.
        self.assertGreater(totals[-1], 36)


class SpawnPacingTests(unittest.TestCase):
    def setUp(self):
        self.v = ProgressionVM()
        self.v.boot()
        self.v.run('sv_close_menu')

    def enter_stage(self, number, seconds=250):
        v = self.v
        v.run('sv_clear_enemies')
        for name in list(v.living):
            v.living[name] = 0
        v.globals['sv_stage'] = number
        v.globals['sv_stage_seconds'] = seconds
        v.globals['sv_total'] = 0

    def block(self, squad):
        stage = next(s for s in self.v.layout['stages']
                     if any(sq['name'] == squad for sq in s['squads']))
        flags = next(sq['spawn_flags'] for sq in stage['squads']
                     if sq['name'] == squad)
        for flag in flags:
            self.v.camera_distances[flag] = 1.0

    def unblock(self, squad):
        stage = next(s for s in self.v.layout['stages']
                     if any(sq['name'] == squad for sq in s['squads']))
        flags = next(sq['spawn_flags'] for sq in stage['squads']
                     if sq['name'] == squad)
        for flag in flags:
            self.v.camera_distances[flag] = 10.0

    def test_blocked_cohort_waits_while_eligible_cohorts_spawn(self):
        v = self.v
        self.enter_stage(1)
        self.block('sv_s1_grunts')
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s1_grunts'], 0)
        self.assertEqual(v.living['sv_s1_jackals'], 4)
        self.assertEqual(v.living['sv_s1_brutes'], 3)

    def test_blocked_cohort_retries_and_places_once_clear(self):
        v = self.v
        self.enter_stage(1)
        self.block('sv_s1_grunts')
        v.run('sv_spawn')
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s1_grunts'], 0)
        self.unblock('sv_s1_grunts')
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s1_grunts'], 6)
        self.assertEqual(v.globals['sv_s1_grunts_prev'], 6)

    def test_placement_is_all_or_nothing_against_the_cap(self):
        v = self.v
        self.enter_stage(1)
        # 33 already alive elsewhere: the 6-count and 4-count cohorts
        # cannot fit, but the 3-count brutes exactly can, and do.
        v.living['sv_s2_grunts'] = 33  # filler outside the stage roster
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s1_grunts'], 0)
        self.assertEqual(v.living['sv_s1_jackals'], 0)
        self.assertEqual(v.living['sv_s1_brutes'], 3)
        # Cohorts evaluate in reverse roster order, so freeing six
        # slots lets the 4-count jackals take four of them first.
        v.living['sv_s2_grunts'] = 27
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s1_jackals'], 4)
        self.assertEqual(v.living['sv_s1_grunts'], 0)
        # Free six more: the grunts cohort now places whole.
        v.living['sv_s2_grunts'] = 21
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s1_grunts'], 6)

    def test_infection_cohort_obeys_the_same_clearance(self):
        v = self.v
        self.enter_stage(3)
        self.block('sv_s3_infection')
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s3_infection'], 0)
        self.assertEqual(v.living['sv_s3_floodcombat'], 6)
        self.unblock('sv_s3_infection')
        v.run('sv_spawn')
        self.assertEqual(v.living['sv_s3_infection'], 10)


if __name__ == '__main__':
    unittest.main()
