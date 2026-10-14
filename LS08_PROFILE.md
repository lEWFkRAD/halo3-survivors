# LS-08 design: permanent progression between new runs

Status: profile module implemented in source (Kip, 2026-10-14); the
engine bridge and launcher integration are native/follow-on work.
Acceptance lives in [PLAN.md](PLAN.md#ls-08-permanent-progression-between-new-runs),
issue #9. Nothing here is native evidence.

## Separation of state

Three kinds of state stay separate:

- **Run state:** ranks, XP, tokens and stage progress inside one run
  (HSC globals, carried by the Armory checkpoint core).
- **Native checkpoint state:** the opaque, exact-build-bound cores the
  launcher stores in immutable generations. Never parsed, never
  edited by the profile system.
- **Permanent state:** unlocks and salvage that survive across runs,
  owned by `permanent_profile.py` in a versioned JSON profile with
  atomic saves, a preserved backup and an applied-outcome ledger.

## Economy proposal (numbers are proposals, not tuning)

- **First permanent unlock:** weapon availability. Winning a run with
  a weapon unlocked earns that weapon's permanent availability: on
  later New Runs it starts unlocked without spending run tokens. The
  unlock namespace is the catalog's availability-scope node IDs
  (`<weapon>.unlock`), enforced by the module, so permanent unlocks
  track stable catalog IDs as the catalog evolves.
- **Permanent currency:** salvage. Proposal: a victory awards 25, a
  defeat that reaches stage 3 or later awards 10 (amounts to tune
  after the first integrated run). Salvage is spent on permanent
  unlocks directly once more than availability persistence exists;
  the module provides guarded earn/spend primitives only.
- **Run outcomes are identified, not amounts:** every reward flows
  through `apply_outcome` with a unique outcome ID (for example
  `run-<date>-victory-<n>` from the session record). Replaying an
  outcome, by crash recovery or duplicate submission, awards nothing
  the second time.

## New Run and Continue semantics

- **New Run** resets run state. Before launch, the launcher reads the
  permanent profile and seeds exactly the permanent benefits (weapon
  availability globals set, nothing else). Seeding happens once, at
  run creation.
- **Continue** restores the checkpoint core as today and never
  reapplies starting bonuses: the checkpoint already contains the
  run state those bonuses produced. The profile is not consulted on
  the Continue path except to record a newly finished run's outcome.
- **QA isolation:** QA sessions use a `qa`-kind profile under the QA
  root; loading with an expected kind refuses mismatches, so QA
  rewards cannot land in the production profile.

## Bridge candidates for the native spike

The issue rules out parsing opaque cores and assuming SDK hooks work
in retail. Candidates, in test order:

1. **Launcher-seeded init at New Run:** the launcher already manages
   `init.txt` for the session. If the engine executes init commands
   before `sv_boot` reads globals, the launcher can set the
   availability globals for permanently unlocked weapons (and a
   profile-seeded flag the HSC can record). Must prove: ordering
   against `sv_boot`, that a checkpoint Continue ignores the seed,
   and behavior when init is absent (profile missing = no bonuses,
   never a crash).
2. **Console/log outcome channel:** run outcomes (victory, stage
   reached) are already observable in the SDK session through the
   LS-03 assertion path; the launcher-side watcher would call
   `apply_outcome` once per observed outcome ID. Must prove the same
   channel story that LS-03 requires, and mark retail unsupported
   until an equivalent is shown there.
3. **HSC-written marker file:** if any supported HSC file/log write
   exists on the target, the run can emit an outcome marker the
   launcher consumes. Unproven; do not design around it until the
   spike shows it exists.

## Retail caveat

Retail architecture depends on LS-02. Until a bridge candidate is
proved on retail, permanent progression is an SDK-side feature and
must be reported that way; a silent SDK-only assumption in the
release path is exactly what the issue forbids.

## Module guarantees (source-proven)

`tests/test_permanent_profile.py` proves: save/load round-trips,
validation rejections (unknown or run-scope unlock IDs, negative or
mistyped amounts, extra fields, duplicate ledger entries), anti-
replay by outcome ID, spend guards, backup preservation and explicit
recovery, failed-save atomicity (original intact, no temp litter),
linked-output refusal, v0 migration and future-version rejection,
and kind isolation.
