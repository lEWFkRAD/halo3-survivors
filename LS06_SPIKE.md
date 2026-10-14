# LS-06 spike design: projectile and melee combat

Status: source preparation (Kip, 2026-10-14). The spike itself is native
work and needs a slot reservation in the coordination issue plus a session
handoff; nothing here is native evidence. Acceptance for LS-06 lives in
[PLAN.md](PLAN.md#ls-06-projectile-and-melee-combat) and issue #7.

## Current damage architecture (verified against source)

- Target selection (`progression_hsc.combat`): a 64-slot actor scan picks
  the nearest living hostile inside the weapon's range. The test is
  distance only; there is no line-of-sight or obstruction check. Per-slot
  `sv_hit<i>` exclusions stop one fire event from hitting the same actor
  through two target slots.
- On a hit, the fire script plays `impact_<weapon>` on the target. That
  effect is cosmetic by construction: `progression_tags.cosmetic_impact`
  strips gameplay parts at authoring time.
- Damage is applied instantly by HSC: each weapon has exactly one
  `<weapon>_apply_damage` dispatch whose chunked cases call
  `damage_object_effect` with a radius-0, zero-AOE `<weapon>_d<value>`
  tag (exact lower/upper bounds, authored by `author_damage`). The
  dispatch case set is exactly the contract damage values.
- Cadence is per weapon and independent: a clock decrements 3 per fast
  tick and refires on `cadence_ticks`. Unlock globals gate firing.
- `tests/test_combat_damage_paths.py` pins this baseline structurally:
  one dispatch per weapon, no duplicate cases, no damage calls outside
  the dispatches, hit recorded before the cosmetic effect and the apply,
  one shot counted per application.

Weapon table (base values from `progression_catalog`):

| Weapon | Damage | Cadence ticks | Range | Targets | Spike role |
| --- | ---: | ---: | ---: | ---: | --- |
| Assault Rifle | 7 | 6 | 14 | 1 | ranged projectile spike |
| Energy Sword | 45 | 24 | 3 | 3 | close-range spike |
| Needler | 12 | 12 | 12 | 1 | conversion candidate |
| Plasma Rifle | 10 | 9 | 12 | 1 | conversion candidate |
| Shotgun | 28 | 30 | 6 | 3 | conversion candidate |
| Rocket Launcher | 70 | 60 | 16 | 3 | conversion candidate |

## Spike picks and rationale

- **Assault Rifle (ranged):** fastest cadence and a mid range make
  travel time, obstruction and cleanup measurable within one stage,
  and single-target fire keeps attribution unambiguous.
- **Energy Sword (close range):** range 3 with 3 targets is the melee
  profile. The spike decides whether close-range damage should ride a
  short-lived projectile/arc object or stay instant with an arc test;
  either outcome is a documented decision, not a default.

## Conversion rule

Replacement, never addition. A converted weapon's damage comes only
from projectile contact (or the proven melee mechanism); its
`_apply_damage` dispatch and `<weapon>_d<value>` cases are removed in
the same change, and `tests/test_combat_damage_paths.py` is updated in
that change to describe the new single path. Two live damage paths for
one weapon is the failure this rule exists to prevent (issue
acceptance: no double damage or duplicate hit rewards).

## What the native spike must measure

For each spike weapon, in an isolated QA profile with a reserved slot:

1. **Launch:** spawn position and direction relative to the player and
   the auto-target; behavior when the target moves or dies in flight.
2. **Ownership/team:** projectiles damage hostiles only; record what
   happens on contact with the player, scenery and other actors.
3. **Collision/obstruction:** a wall or rock between player and target
   blocks the shot (today it cannot); record the impact point and that
   no damage passes through.
4. **Attribution:** damage value equals the catalog value for the
   current ranks; XP and shot counters advance once per hit, never per
   launch plus per hit.
5. **Cleanup:** live projectiles at Armory open, stage transition,
   ending (win and lose) and checkpoint reload: none may damage after
   the transition, and object counts return to zero.
6. **Budget:** maximum concurrent projectile objects at the fastest
   cadence (derive from cadence and measured lifetime; state the cap
   in the spike report) and the actor/object counts during a full
   stage at the 36-enemy cap.

Suggested observation cases for `qa_assertions.py` once the transport
exists: target-in-open takes damage after travel delay; target-behind-
rock takes none; dead-target projectile expires harmlessly; Armory
open with rounds in flight applies no further damage; stage transition
leaves zero live projectiles. Each case reports through `native_qa`
with the candidate identity bound, per LS-03.

## Conversion order after a proven spike

1. Plasma Rifle and Needler (same single-target ranged profile).
2. Shotgun (multi-target becomes spread or per-pellet accounting; the
   spike report must state which, with cadence/damage re-measured).
3. Rocket Launcher (radius damage is a deliberate design change from
   today's radius-0 tags; needs its own acceptance note).
4. Energy Sword per the close-range spike decision.

Any weapon that keeps instant damage keeps it intentionally, with the
reason recorded here and in the PR. Balance numbers after conversion
are measured, not assumed from the instant-damage table above.
