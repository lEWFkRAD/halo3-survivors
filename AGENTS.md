# Last Stand agent handoff

## Start here

Read [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md),
[PLAN.md](PLAN.md), [TASKS.md](TASKS.md) and
[DEVELOPMENT.md](DEVELOPMENT.md). This repository is the shared source and plan
for the native Halo 3 mod. The project is a v0.4 prototype, not a finished retail
release. Preserve overhead play, auto attacks, outdoor stages and stage-carried
upgrades. Vehicles are a later extension; multiplayer is outside current scope.

Before editing, inspect Git status, the latest remote branch, the task issue and
open PRs. Preserve existing work. Use a separate branch/worktree for each bounded
task. Do not turn a documentation task into an unrequested gameplay rewrite.

## Claim and coordinate work

GitHub issues linked from TASKS.md are the live ownership/status record. Search
the issue and open PRs before claiming. Record your agent identity, branch/base
commit, files/area, intended acceptance criteria and whether native time is
needed. Existing active claims take precedence; resolve overlap with the
coordinating agent. Do not assign another person or send unsolicited messages.

For work with a task ID, keep it in the branch and PR title, for example `ls-01-portable-paths`
and `[LS-01] Configure authoring paths`. Do not mark work complete merely because
code exists. Link the result and evidence, and identify anything still blocked.
Leave a handoff and release the claim when stopping. Check stale claims with the
coordinator before taking over, especially claims involving a running process.
Small standalone fixes can go directly to a focused PR without a new task issue,
as described in CONTRIBUTING.md; still check for overlapping work first.

## One native operator at a time

Onyx-Linux's active Halo/Sapien window, private Wine prefix, staged tags,
compiler/cache output, `init.txt`, launcher, saves and installed package are
shared resources. Reserve the native integration slot in the [coordination issue](https://github.com/lEWFkRAD/halo3-survivors/issues/1)
before controlling or changing them. Only the current operator may stage,
compile, drive input, run native QA, replace launchers or promote a package.

The reservation records operator, branch/commit, purpose, QA profile and last
update. A stale timestamp alone does not authorize killing a process or taking
over the display. Verify handoff with the coordinator. Source-only work in an
isolated branch can continue while another agent owns the native slot.

A slot claim does not authorize replacing the user's active game. Before a
native mutation, inspect and record the current process/prefix, launcher owner,
active profile and staged candidate. Arrange a handoff with the session owner
and preserve its checkpoint before stopping a process or replacing live tags,
HSC, `init.txt`, launcher or package. Do not stage a new build while a production
launcher is saving against the old fingerprints. If ownership is unclear, keep
source work separate and resolve it with the coordinator before native mutation.

The current development root is
`C:\Users\Administrator\Projects\halo3-survivors` on the Windows coordinator.
The current native workspace is
`/home/jeffrey-watts/Documents/Games/Halo3Survivors` on Onyx-Linux. These are
existing deployment details, not a portable setup guarantee. Do not change
unrelated host, fleet, inference or service settings to work on this game.

## Source and generated files

- Edit `progression_catalog.py`, `generate_progression.py`, `progression_hsc.py`
  and tag/UI authoring sources as appropriate. Do not patch generated
  `source/progression.hsc` as the lasting implementation.
- Coordinate shared generator/catalog/scenario changes. Regenerate outputs from
  the integrated sources, review the diff and record native compatibility changes.
- Several remote/QA scripts perform work at top level. Read them before running
  or importing them; use import-safe modules for new reusable helpers.
- `.gitattributes` preserves exact bytes because native receipts bind content
  hashes. Avoid broad line-ending/formatting rewrites during gameplay changes.
- Keep source bundling's explicit allowlist current for authored deliverables.
  Never commit owned tags, native tools, maps, saves, credentials or local media.

## Native behavior that must not regress

- Chunk native dispatch and scans; the interpreter has a shallow expression
  stack. Do not introduce giant expressions or unbounded recursive scans.
- Current generation guards are fewer than 1,024 scripts, fewer than 512 globals
  and at most 128 titles. Historical v0.4 native readback contained 400 scripts,
  175 globals and 121 titles. Native counts include engine-injected definitions;
  do not compare them directly with source declaration counts.
  These are current authoring guards, not universal engine-limit claims.
- The enemy cap is 36, the actor scan covers 64 slots, and selected targets are
  bounded at 12. Audit related budgets before changing any one of these.
- Spawn positions use valid navigation/BSP bindings. Guard every cohort slot
  against near-player placement. Infection multiplicity and carrier death
  children must not bypass the actor cap.
- `ai_erase` is deferred until an AI update. Stopping AI too early leaves frozen
  actors. Preserve the final-victory cleanup regression and verify zero actors
  after a simulation update.
- Input action priming and release latches are intentional. A held click buys
  one rank; navigation/category chords must not cause accidental purchases.
- Current impacts are cosmetic and HSC applies direct damage. Projectile/melee
  work must prevent damage from being applied through both paths.
- Native cores are opaque and exact-build-bound. Camera/controller state needs
  repair after Continue, but repair must not reset ranks, actors or cooldowns.
  The LS-04 candidate retains the camera anchor during periodic repair so it
  does not bypass the movement switching margin.
- Preserve immutable save generations, atomic CURRENT updates, old-save archives
  and launch ownership through the actual native child process. QA profiles must
  stay under the QA root and never become the player's profile.

## Verification and handoff

Run the appropriate source checks, normally
`python -B -m unittest discover -s tests -v`. Current LS-04 candidate: 183
passing source-only tests plus one skipped module containing five native
geometry tests; all 188 passed in the owner workspace with the required
binding/assets. The historical v0.4 native release baseline was 109 tests.

This slice covers camera switching/repair and non-node cinematic title contrast.
Bounded native checks and their limits are recorded in
[native-validation-ls04.json](native-validation-ls04.json); candidate readback is
400 scripts, 177 globals and 121 titles. The original production staged build
and checkpoint were restored afterward. Do not treat this candidate as a
promoted package or LS-04 as complete. CHUD skill descriptions retain their
existing styling and need separate native work.

Source tests do not prove native compilation, UI, AI/navigation, retail behavior
or balance. For relevant changes, queue a bounded native experiment through the
operator, with the exact commit, setup, expected result and cleanup instructions.
Temporary QA mutations/cheats belong only to the isolated QA session/profile.

Historical release receipts remain historical. New gameplay candidates need new
evidence and cache receipts. Inspect observed assertions; a screenshot created
successfully is not proof the assertion was true. Record final-fix scope honestly.

LS-10 and LS-11 are repeatable release gates. Later milestones need fresh linked
validation issues/checklists for their own integrated candidate; a closed beta
checklist does not validate a subsequent combat or vehicle build.

A PR/handoff should state the problem and resulting behavior, task ID, changed
areas, tests and native evidence, save compatibility, remaining limits and any
next native action. Keep source-only work marked native-pending until it is
tested. The integration owner reviews overlapping changes and owns the final
build/promotion sequence; no agent should independently deploy its branch over
another agent's native session.

On SHATNER, also follow the user's shared wiki coordination instructions. GitHub
is the shared plan available to other agents; local wiki paths are not a
prerequisite for working from a clone.
