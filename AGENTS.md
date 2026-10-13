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
existing deployment details. The supported configurable build route is documented
in [BOOTSTRAP.md](BOOTSTRAP.md), with isolated stock rebuild evidence in
[native-validation-ls01.json](native-validation-ls01.json). Do not change unrelated
host, fleet, inference or service settings to work on this game.

## Source and generated files

- Edit `progression_catalog.py`, `generate_progression.py`, `progression_hsc.py`
  and tag/UI authoring sources as appropriate. Do not patch generated
  `source/progression.hsc` as the lasting implementation.
- Coordinate shared generator/catalog/scenario changes. Regenerate outputs from
  the integrated sources, review the diff and record native compatibility changes.
- Use `fetch_progression_inputs.py`, `bootstrap_tags.py`, `prepare_progression.py`
  and `native_workspace.py` for the supported configured build path. Preserve
  their exact manifests and reject undeclared/stale tag outputs. Native save,
  compilation and cache building remain explicit operator steps.
- Several historical remote/QA scripts perform work at top level and retain
  machine paths. They are not the supported fresh-build route. Read them before
  running or importing them; use import-safe modules for new reusable helpers.
- `native_workspace.py` never stops a session or launches a compiler. Its process
  snapshots do not replace the native slot/session handoff, and its readback
  receipts never establish successful compilation. Replacement requires backups;
  inspect the resulting native evidence before consuming a readback as a baseline.
- `.gitattributes` preserves exact bytes because native receipts bind content
  hashes. Avoid broad line-ending/formatting rewrites during gameplay changes.
- Keep source bundling's explicit allowlist current for authored deliverables.
  Never commit owned tags, native tools, maps, saves, credentials or local media.

## Native behavior that must not regress

- Chunk native dispatch and scans; the interpreter has a shallow expression
  stack. Do not introduce giant expressions or unbounded recursive scans.
- Current generation guards are fewer than 1,024 scripts, fewer than 512 globals,
  at most 128 title definitions and at most 9,500 authored script/global
  references. Keep the reference guard: the SDK compiler has a separate bounded
  reference bookkeeping table, and definition/syntax counts did not prevent
  earlier live-Armory compiler crashes. Source counts omit engine-injected
  material; do not equate them with native counts or compilation success.
  The compiled live Armory candidate recorded 495 scripts, 180 globals, 51,074
  syntax datums and 127 titles, including the final black-panel presentation.
  Recheck these after subsequent source or tag changes.
  Historical v0.4 contained 400 scripts, 175 globals and 121 titles; the static
  LS-05 prototype had 402 scripts, 178 globals and 128 titles. These authoring
  guards are not universal engine-limit claims.
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
- The live Armory has nine pages covering all 50 nodes, with current ranks and
  available/locked/owned/maxed markers. Selected details, wallet, next-price and
  purchase feedback remain separate. Keep the one-second refresh limit through
  rapid navigation and close/reopen. Process Resume before a due refresh and
  disable training text outside the Armory; wallet/price titles expire within
  one second. Preserve release latches, the shared actor-consideration helper
  and bounded inline graph keys that keep compiler reference pressure low.
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

For current Armory work, read [ARMORY_LIVE.md](ARMORY_LIVE.md) and
[its evidence](native-validation-ls05-live.json). The authored final presentation
uses an opaque black panel and white wallet text. Bounded native checks cover
readability, Resume/reopen and Continue; refresh gaps and wider acceptance remain.
The [earlier HUD probe](ARMORY_NATIVE_PROBE.md) and
[probe evidence](native-validation-ls05-ui-probe.json) established four concurrent
title slots and the private training-string route. They remain historical:
128 definitions do not permit one simultaneous title per skill. Production
preparation now explicitly includes the live HUD outputs; the separate probe
outputs remain outside that allowlist and must not be promoted. LS-05 stays open.

Run the appropriate source checks, normally
`python -B -m unittest discover -s tests -v`. The LS-01 source suite passes
331 tests with six skipped entries in the owner checkout, and 326 tests with
seven skipped entries in a clean export. Separately, all 22 bootstrap tests
(including six owned-input checks) and all five geometry tests pass using the
fresh owned inputs/compiled baseline. Do not describe those separate checks as
a full fresh-owned-input suite run. Historical LS-05 counts were 217 owner tests
and 212 clean-export passes, with one skipped five-test geometry module.

The stock rebuild at implementation `dc4d80e58111ad026b0a722899130ce4e5caa2b2`
uses an isolated extracted kit without historical private scenario templates.
[native-validation-ls01.json](native-validation-ls01.json) records baseline
save/readback, final 402-script/178-global/43,180-datum/128-title compilation,
a 702,328,832-byte cache with a success marker, and 19 short SDK assertions.
The cache log retains 25 stock-asset error diagnostic lines; native tool exit
was not captured. Stage one was ordinary uncheated play; stages two through
four were seeded/deathless checks. Complete runs, exhaustive reachability,
retail support and LS-11 release evidence remain unfinished. All 20 prior
production profile files are unchanged, two normal session files were added,
and the original Continue/Armory was restored. The installed package is unchanged.

The current live Armory candidate uses 601 graph snapshots plus a fallback over
nine pages. The selected objective supplies effects, prerequisite ranks and stage
gates, while separate notices show wallet and next price. Source model/VM checks
do not establish native readability, input behavior or recovery. Keep the final
candidate's checks and limits in [native-validation-ls05-live.json](native-validation-ls05-live.json).
The [seven-page static prototype](native-validation-ls05.json) retains its own
historical input/purchase/restart evidence and 402-script/178-global/128-title
readback; those results do not validate the live HUD.

The live candidate changes script, scenario and private-asset fingerprints,
including the canonical CHUD globals dependency. Use its isolated QA profile,
preserve the production build/checkpoint, and never load a production core into
this candidate or promote the QA profile. Missing or changed live HUD dependencies
must reject Continue. The installed v0.4 package and launcher remain unchanged;
no full ordinary run, retail validation or release promotion is claimed.
A fresh cache has native exit 0 and a success marker, with 25 retained stock-asset
error diagnostic lines; its gameplay has not been tested. The bounded final
presentation checks pass; LS-05 is not complete.

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

Use [NATIVE_QA.md](NATIVE_QA.md) for fresh assertion nonces, pre-dispatch log
cursors and explicit passed/failed/unresolved observations. Verify process,
profile and candidate fingerprints independently of the supplied report labels.
The LS-03 evidence reader adds 28 source regressions, and launcher shutdown
adds five profile-cleanup regressions; the LS-03 milestone's combined owner
suite passed 250 tests. Existing native receipts retain their original test counts.

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
