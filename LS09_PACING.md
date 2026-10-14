# LS-09: enemy director and stage pacing record

Status: source record (Kip, 2026-10-14), generated from the tracked
catalog and layout and checked by `tests/test_spawn_pacing.py`.
Ordinary-run pacing proof and final balance approval remain native
work under LS-09/LS-10. Acceptance: issue #10.

## Encounter schedule (acceptance item 1)

Families are introduced per stage and carried into every later stage
with identical cohort count and unlock second (the consistency test
fails if a carried family changes shape). Unlock is seconds into the
stage; XP is the per-kill value from the layout.

| Stage | Family | Cohort | Unlock | XP |
| --- | --- | ---: | ---: | ---: |
| 1 Landing | grunts | 6 | 0s | 10 |
| 1 Landing | jackals | 4 | 30s | 20 |
| 1 Landing | brutes | 3 | 90s | 30 |
| 2 Incursion | captains | 2 | 45s | 50 |
| 2 Incursion | snipers | 2 | 90s | 35 |
| 3 Outbreak | floodcombat | 6 | 0s | 20 |
| 3 Outbreak | infection | 10 | 45s | 3 |
| 3 Outbreak | carrier | 2 | 90s | 40 |
| 4 Last Stand | hunters | 2 | 0s | 100 |
| 4 Last Stand | chieftain | 1 | 120s | 150 |

Carried rosters: stage 1 fields 13 actors, stage 2 fields 17,
stage 3 fields 35, stage 4 fields 38 on paper.

## Director mechanics (verified in source)

- **Respawn model:** a cohort respawns as a whole once its living
  count reaches zero, its unlock second has passed, and the cap
  check passes. There is no trickle replacement.
- **Cap interaction:** the actor cap is 36. Stage 4's roster (38)
  exceeds it, so late cohorts place only as kills free room.
  Placement is all-or-nothing per cohort: `sv_total + count <= 36`
  or the cohort waits for the next cycle.
- **Evaluation order:** cohorts evaluate in reverse roster order
  inside a spawn cycle, so newer families claim freed cap room
  before older ones in the same cycle. Any pacing retune must take
  this into account; it is pinned by test.
- **Player clearance:** before placing, a cohort checks every one of
  its spawn flags: if the player is within 2 units of any flag, the
  cohort waits. Placement points themselves come from the family's
  spawn profile ring (5.5-8 units from stage center for most, 7.5-9
  for heavies, 8-10 for snipers; see `progression_tags.spawn_profile`
  and the LS-04 arena audit). The rule is identical for infection
  forms; carrier death children are not placements and remain
  governed by the authoring that disables unbudgeted child spawns.
- **Retry:** a blocked or capped cohort is re-evaluated every spawn
  cycle (once per stage second via `sv_step`); nothing is permanently
  suppressed.
- **No accidental rewards:** clearing actors at transitions or
  victory awards no XP (pinned under LS-07); kill attribution is the
  count-derived mechanism documented in LS07_DROPS.md.

## Open native items

- **Stuck/offscreen enemies:** squads use the `surround` AI objective
  (follow the player, follow radius 1.5, run movement). Whether
  actors stall on arena geometry or leave the camera's useful area in
  real play needs observed runs; no source change is proposed until
  an observation exists.
- **Pacing proof:** at least one ordinary run demonstrating the
  intended pressure curve per stage, then LS-10's broader
  measurement, before final balance approval. Cohort cadence or
  unlock retunes should cite those observations, not this table.
