# LS-07 design: physical XP drops and collection

Status: source preparation (Kip, 2026-10-14). LS-07 depends on a proved
native death/drop mechanism; this document is the design and audit that
proof must satisfy. Nothing here is native evidence. Acceptance lives
in [PLAN.md](PLAN.md#ls-07-physical-xp-drops-and-collection), issue #8.

## Current XP accounting (verified against source)

XP is inferred from squad living counts (`progression_hsc.enemies`):

- Each squad has a `<squad>_prev` counter. `sv_observe` runs for the
  current stage inside `sv_step` and, per squad, awards
  `(prev - now) * squad xp * sv_xp_scale` when the count dropped, then
  sets `prev = now`.
- Squad XP values come from the layout (stage 1: grunts 10, jackals 20,
  brutes 30). `sv_xp_scale` is driven by the Battlefield Insight /
  Combat Scholar support ranks.
- Count increases never award directly, but `_prev` follows the count,
  so actors added by infection multiplicity pay XP when killed later:
  they are combatants, and total XP stays bounded by actors killed.
- `sv_clear_enemies` zeroes every `_prev` after `ai_erase`, so clearing
  actors at a transition or victory pays nothing.
- Spawning sets `_prev` to the placed count, so a fresh cohort is a
  baseline, never a windfall or a debt.
- Level-up is batched and separate: `sv_level_up` converts XP to
  levels/tokens when the Armory opens and preserves the remainder
  (covered by the progression tests).

`tests/test_xp_accounting.py` pins each property above. The mechanism's
one structural gap is the reason LS-07 exists: **a count delta carries
no death location**, so nothing physical can be dropped yet.

## What the native proof must establish

A drop needs a location and a single attribution at the moment of
death. Candidate mechanisms, in the order to test them:

1. **Actor polling:** the autofire scan already walks the 64-slot
   actor list. A per-fast-tick health snapshot per slot could detect an
   alive-to-dead transition and read the actor's position before the
   corpse is erased. Must prove: position is readable at that moment,
   the slot is not reused inside the same tick, `ai_erase` deferral
   does not hide the transition, and 64-slot polling stays inside the
   script/reference budgets.
2. **Damage-side attribution:** HSC applies all player damage today,
   so the killing blow is known at apply time except for damage over
   time and multi-weapon same-tick kills. Must prove: the target's
   position is readable in the apply path and death is registered
   exactly once even when two weapons land in the same tick.
3. **Engine death effects:** a tag-side death effect that spawns the
   drop object. Must prove: it fires for HSC-applied damage, carries
   the right denomination per squad, and does not fire for
   `ai_erase` clears.

Whichever mechanism proves out, the acceptance evidence needs: a real
kill creates the intended drop at a valid location; clearing actors
creates none; and attribution survives the 36-enemy cap with infection
multiplicity (children are kills with locations too, or an explicit
documented exception).

## Drop economy parameters (to fix at proof time)

- **Denomination:** one drop per kill, valued at the squad's XP.
  Aggregation (merging nearby drops into one object of summed value)
  is allowed only if collection still awards the exact sum once.
- **Collection:** radius and feedback are presentation decisions, but
  collection must award through the same `sv_xp` path so batched
  level-up behavior is unchanged.
- **Lifetime:** drops expire or persist per an explicit rule; the rule
  for stage change, player death and Continue must be written before
  implementation (recommended: drops are run state, cleared without
  award on stage change and death, restored only if the checkpoint
  itself was written while they lay uncollected — matching how the
  checkpoint treats other run state).
- **Bound:** maximum live drops must be capped independently of the
  enemy cap (a long fight at the cap generates a drop per kill); the
  cap behavior (oldest expires, merges, or stops spawning) is part of
  the design record, with object counts measured in the proof.

## Switch-over rule

When drops become authoritative, the count-derived credit in
`sv_observe` is disabled in the same change (the LS-06 replacement
rule: never two XP paths for one kill), and
`tests/test_xp_accounting.py` is replaced in that change by drop
accounting tests. Until then the count mechanism remains the single
source of XP and these baseline tests guard it.
