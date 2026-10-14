"""LS-04 arena layout audit: hermetic invariants over the tracked layout.

Acceptance item 4 requires navigation and spawn-clearance behavior to stay
valid after scenery changes. The owner-checkout geometry test proves that
against the native scenario, but it skips without owned tags. The tracked
progression-layout.json (the generator's own input) carries the same facts,
so this module checks them in any clone:

- spawn rings, spacing, vertical clearance and counts for every squad;
- camera anchors contained by the arena and inside the boundary-return
  threshold, at exactly camera_height above their anchor points;
- a framed stage center (boundary returns and stage entry land on an
  anchor) and framed spawns (an anchor within 2.5 units of every spawn);
- inner-arena anchor coverage within the audited per-stage bounds.

Coverage audit (2026-10-14, Kip, on the tracked layout): anchors are
authored from scenario firing positions, so coverage is uneven by sector.
Worst distance to an anchor inside r<=10 of each center measures
{1: 10.00, 2: 6.60, 3: 10.00, 4: 3.55}; stages 1 and 3 have sectors with no
firing positions, where the center anchor is the nearest one. The bounds
below record that state with headroom: a scenery or layout change that
degrades coverage fails here. Closing the gaps needs new firing positions
in the owned scenario (native authoring), and before/after captures plus
real-movement checks remain native-gated under LS-04.
"""
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = json.loads((ROOT / 'progression-layout.json').read_text())

BOUNDARY_RETURN_DISTANCE = 21  # generate_progression sv_boundary_check
SPAWN_FRAME_DISTANCE = 2.5     # audited worst spawn-to-anchor: 2.10
INNER_DISC = 10
INNER_COVERAGE_BOUNDS = {1: 10.5, 2: 7.5, 3: 10.5, 4: 4.5}


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class ArenaLayoutTests(unittest.TestCase):
    def test_layout_shape(self):
        self.assertEqual(len(LAYOUT['stages']), 4)
        self.assertEqual(LAYOUT['camera_height'], 12)
        for stage in LAYOUT['stages']:
            self.assertEqual(stage['radius'], 20)
            self.assertTrue(stage['cameras'])
            self.assertTrue(stage['squads'])

    def test_camera_anchors_contained_and_at_camera_height(self):
        height = LAYOUT['camera_height']
        for stage in LAYOUT['stages']:
            center = stage['center']
            for camera in stage['cameras']:
                with self.subTest(stage=stage['number'], camera=camera['name']):
                    self.assertLessEqual(dist(camera['position'], center),
                                         stage['radius'])
                    # The camera never anchors somewhere the boundary
                    # check would teleport the player away from.
                    self.assertLess(dist(camera['position'], center),
                                    BOUNDARY_RETURN_DISTANCE)
                    point = camera['camera_position']
                    self.assertEqual(point[:2], camera['position'][:2])
                    self.assertAlmostEqual(point[2] - camera['position'][2],
                                           height)

    def test_stage_centers_and_spawns_are_framed(self):
        for stage in LAYOUT['stages']:
            center = stage['center']
            anchors = [camera['position'] for camera in stage['cameras']]
            with self.subTest(stage=stage['number'], point='center'):
                self.assertLessEqual(min(dist(center, a) for a in anchors),
                                     0.01)
            for squad in stage['squads']:
                for position in squad['spawn_positions']:
                    with self.subTest(stage=stage['number'],
                                      squad=squad['name']):
                        self.assertLessEqual(
                            min(dist(position, a) for a in anchors),
                            SPAWN_FRAME_DISTANCE)

    def test_spawn_rings_spacing_and_vertical_clearance(self):
        for stage in LAYOUT['stages']:
            center = stage['center']
            for squad in stage['squads']:
                low, high = squad['spawn_radius']
                positions = squad['spawn_positions']
                with self.subTest(stage=stage['number'], squad=squad['name']):
                    self.assertEqual(len(positions), squad['count'])
                    self.assertEqual(len(squad['spawn_flags']), squad['count'])
                for i, position in enumerate(positions):
                    self.assertGreaterEqual(dist(position, center), low)
                    self.assertLessEqual(dist(position, center), high)
                    self.assertLessEqual(abs(position[2] - center[2]), 3)
                    for other in positions[i + 1:]:
                        self.assertGreaterEqual(
                            dist(position, other),
                            squad['minimum_spawn_spacing'])

    def test_inner_arena_anchor_coverage_within_audited_bounds(self):
        for stage in LAYOUT['stages']:
            center = stage['center']
            anchors = [camera['position'] for camera in stage['cameras']]
            worst = 0.0
            steps = int(INNER_DISC / 0.5)
            for ix in range(-steps, steps + 1):
                for iy in range(-steps, steps + 1):
                    x, y = ix * 0.5, iy * 0.5
                    if math.hypot(x, y) > INNER_DISC:
                        continue
                    point = (center[0] + x, center[1] + y)
                    worst = max(worst, min(dist(point, a) for a in anchors))
            with self.subTest(stage=stage['number']):
                self.assertLessEqual(worst,
                                     INNER_COVERAGE_BOUNDS[stage['number']])

    def test_disabled_occluder_matches_authoring_rule(self):
        occluders = LAYOUT['disabled_occluders']
        self.assertEqual(len(occluders), 1)
        occluder = occluders[0]
        self.assertTrue(occluder['path'].endswith('bfg_stand'))
        # disable_arena_occluders drops stands within 25 units of the
        # stage 3 or 4 centers; the recorded entry must satisfy that rule.
        centers = [s['center'] for s in LAYOUT['stages']
                   if s['number'] in (3, 4)]
        self.assertTrue(any(dist(occluder['position'], c) <= 25
                            for c in centers))


if __name__ == '__main__':
    unittest.main()
