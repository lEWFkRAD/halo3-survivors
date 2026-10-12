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
  175 globals and 121 titles. The LS-05 prototype has 402 scripts, 178 globals
  and 128 titles, leaving no spare title rows. Native counts include
  engine-injected definitions; do not compare them directly with source
  declaration counts.
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
- Armory branch pages are static catalog references; current selected-skill
  details and purchase feedback remain separate. Keep the one-second page
  refresh limit through rapid navigation and close/reopen. Process Resume
  before a due refresh, and let expired pages disappear outside the Armory.
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
`python -B -m unittest discover -s tests -v`. The current LS-05 prototype passes
217 tests in the owner workspace with the required binding/assets. Its clean
source-export test has not yet been run; record that result separately rather
than deriving it from the owner count.

The LS-05 prototype adds seven static branch-reference pages, covering all 50
nodes alongside the existing selected-skill CHUD detail. All seven pages fit
in the inspected native captures. Bounded native evidence and limits belong in
[native-validation-ls05.json](native-validation-ls05.json); native readback is
402 scripts, 178 globals, 43,180 syntax datums and 128 titles. Dynamic graphical
states for every node and stronger contrast remain unfinished. This is an
interim presentation, not completion of LS-05 or an installed-package promotion.
Its additional scheduler global and changed script/scenario fingerprints make
older-build cores incompatible. Use an isolated LS-05 QA profile and preserve
the production build and checkpoint; never load a production core into this
candidate or promote the QA profile.

Historical LS-04 validation passed 188 owner tests and 183 source-export tests,
with one skipped module containing five native geometry tests. That slice
covered camera switching/repair and non-node cinematic title contrast; its
400-script, 177-global, 121-title native readback and restoration evidence remain
in [native-validation-ls04.json](native-validation-ls04.json). It was not a
promoted package or completion of LS-04. CHUD skill descriptions retain their
existing styling. The historical installed v0.4 release baseline was 109 tests.

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
