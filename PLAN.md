# Last Stand implementation plan

Last Stand is a native Halo MCC Halo 3 survival mod with an overhead camera,
automatic attacks and branching upgrades. This plan takes the playable v0.4
prototype through retail verification, presentation and balance work, then
optional gameplay expansions and vehicles. Other agents can take a bounded
task from [TASKS.md](TASKS.md) and follow [AGENTS.md](AGENTS.md).

Baseline date: 2026-10-12. The first GitHub snapshot is commit
`74101a27c33542d6b7cfa4e5cdd2c69bc1d106e5`. No completion dates are promised;
native feasibility and observed playtests determine the sequence.

## Product requirements and scope

| Requirement | Current behavior | Remaining work |
| --- | --- | --- |
| Native MCC Halo 3 mod | Native scenario, scripts, tags and compiled package exist; playable in the owned SDK engine | Verify the actual retail MCC mod-menu path and supported features |
| Bird's-eye view | Overhead follow camera across four outdoor Ark arenas | Improve contrast, occlusion, terrain edges and recovery |
| Automatic firing | Six independently timed weapons select targets automatically | Improve weapon feel and collision behavior where native mechanisms permit |
| Full branching skill tree | 50 nodes: seven per weapon plus eight support nodes | Clear graphical presentation, usability and balance |
| Upgrades carried to the next levels | Ranks, weapons, XP and points persist between the four stages | Preserve this behavior through all changes |
| Enemies introduced at different stages | Timed Covenant and Flood families; 36-enemy cap | Full-run pacing, spawn fairness and performance tuning |
| Vehicles eventually | Not implemented | Isolated feasibility prototype, then a later integrated feature |

Permanent unlocks across entirely new runs, physical XP pickups and travelling
projectiles are planned expansions. They were not the same requirement as
carrying upgrades between stages. Current stage carry already works. A New Run
currently starts fresh; Continue resumes an exact-build Armory checkpoint.

Keep the native Halo engine, outdoor spaces, overhead view and automatic attack
loop. The current target is solo. Multiplayer, public Workshop distribution,
monetization and replacing the native game are outside this plan.

## Verified baseline

- Four stages last five active minutes each; the Armory pauses the survival
  clock and automatic attacks. Movement remains possible while protected.
- Needler, Assault Rifle, Shotgun, Plasma Rifle, Rocket Launcher and Energy
  Sword have damage/cadence upgrades, exclusive specializations and capstones.
- Kills award XP directly. Multiple affordable levels are awarded in one
  Armory visit. The point wallet caps at 50.
- Automatic weapons currently apply immediate damage with separate visual
  effects. Projectile travel, physical melee and pickup objects are absent.
- Armory visits and purchases request native checkpoints. The SDK launcher
  offers Continue/New Run, retains earlier generations and checks exact
  engine/scenario/script/private-asset compatibility.
- 109 deterministic tests passed in the owner workspace. A source-only export
  passed 104 tests and skipped the module containing five native geometry
  tests. These counts describe the v0.4 baseline, not all future commits.
- Native checks cover menu input, six weapons, stage carry/rosters/cap, camera,
  clock, spawn clearance, batched XP, full-process Continue and final victory.
  The broader checks preceded a final one-line victory correction; the exact
  scope is recorded in [native-validation-v04.json](native-validation-v04.json).
- Retail MCC loading and retail persistence are unverified. Fresh-clone native
  builds still require the prepared private scenario and local tool setup.

## Proposed delivery sequence

| Milestone | Work | Completion gate |
| --- | --- | --- |
| Reproducible native baseline | LS-01, LS-02, LS-03 | A prepared owned installation can build a candidate; retail capabilities and limitations are recorded; QA reports actual outcomes |
| Playable beta | LS-04, LS-05, LS-09, LS-10, LS-11 | Readable controls/tree, complete ordinary runs, stable recovery and a verified retail installation/update path |
| Expanded combat and progression | LS-06, LS-07, LS-08, then LS-10/LS-11 again | Only mechanisms proved in the intended engine ship; new systems retain correct damage, XP and save behavior |
| Vehicles | LS-12, LS-13, then LS-10/LS-11 again | One proven vehicle loop expands without breaking infantry play, camera, saves or encounter budgets |

Source preparation, UI design and deterministic test work can run in parallel.
Onyx compilation, active-window control, staging, native QA and promotion must
run through one integration owner at a time. A dependency blocks completion of
the dependent feature, not preliminary read-only research or isolated design.

## Architecture and ownership map

| Area | Main sources | Notes |
| --- | --- | --- |
| Node IDs, branches, costs, effects | `progression_catalog.py` | Stable IDs should drive UI and any future permanent profile |
| Run state, menu, stages, checkpoint hooks | `generate_progression.py` | Shared integration hotspot; coordinate changes |
| Camera, enemy observation/spawn, auto attacks | `progression_hsc.py` | Shared hotspot; emits bounded native functions |
| Scenario, placement, private damage tags | `progression_tags.py`, `author_effects.py`, `outdoors.py`, `birds_eye.py`, `author_hangar.py` | Requires owned native assets and `blam_tags` |
| Native titles and Armory presentation | `author_progression_ui.py` | Current title guard has little spare capacity |
| SDK launch and saves | `launch_v04.py`, `install_launcher_v04.py` | Opaque exact-build native cores; production and QA profiles separated |
| Native orchestration | `prepare_progression.py`, `fetch_progression_inputs.py`, `onyx_progression.py`, `progression_remote.py`, `remote_build.py` | Several entry points act at import/top level; inspect before running |
| Validation and promotion | `qa_progression.py`, `qa_v03_final.py`, `qa_v04.py`, `promote_v03.py` | Historical filenames do not necessarily identify the current target version |
| Source tests and distribution | `tests/`, `bundle_source.py` | Source VM is not the native compiler; archive uses an explicit allowlist |
| Generated outputs | `source/progression.hsc`, `progression-contract.json`, `progression-layout.json` | Edit authoring sources, then regenerate deliberately |

The initial map, its exact build receipt, promotion record and launcher receipt
are linked from [README.md](README.md). Preserve those historical records.
New candidates need their own evidence; changing a receipt does not validate
changed code.

## Work packages

### LS-01 Portable configuration and native bootstrap

Priority: P0. Can start now. Owner area: helper/configuration and authoring setup.

Replace embedded machine paths, SSH assumptions and tool locations with a small
documented configuration layer while preserving current defaults. Inventory the
owned inputs required by the existing authoring chain, including
`outdoor-compiled.scenario`, UI inputs, character tags and private effects.
Document the pinned `blam_tags` source and toolchain from DEVELOPMENT.md.

Deliver a preflight that reports missing prerequisites before any mutation,
plus an ordered bootstrap recipe from a clean source checkout and an owned H3EK
installation. Reuse the existing authoring scripts where possible. Record which
steps still require native compilation instead of treating old local outputs as
fresh inputs. Keep gameplay changes out of this task.

Acceptance:

- [ ] A source-only checkout runs the applicable tests with explicit skips.
- [ ] Configured paths work with spaces and fail clearly when tools are missing.
- [ ] An isolated prepared installation can author and compile a candidate using
  the documented sequence without reading an undeclared development artifact.
- [ ] A second run preserves user data and does not silently replace saves or
  install into unrelated game folders.
- [ ] Owned assets, executables, credentials and local profiles stay untracked.

### LS-02 Retail MCC compatibility and save capability

Priority: P0. Owner Xbox/Microsoft sign-in is needed for retail execution.
Owner area: retail integration, package metadata and native evidence.

Use the existing installed package first. Record game/tool versions, exact map
hash and mod registration, then load it through retail MCC's mod menu. Verify
overhead movement, real Armory input, automatic attacks, stage transition,
death/restart and victory. Identify which script/debug functions are SDK-only
and whether they affect retail compilation, loading or runtime behavior.

Evaluate saving separately. Native `core_save_name` / `core_load_game_name`
success in the SDK does not prove retail support. Record a capability matrix
for retail and SDK, with each feature supported, unsupported or unresolved.
If a feature needs a different retail implementation, produce a bounded design
before replacing the working SDK path. The owner performs account sign-in.

Acceptance:

- [ ] Retail launch result and each tested feature have actual observed evidence.
- [ ] Any failure includes a reproducible trigger and the relevant logs/version.
- [ ] Retail persistence is explicitly classified, without inheriting SDK claims.
- [ ] Documentation distinguishes the two execution paths and their limitations.

### LS-03 Native QA and run recovery baseline

Priority: P0. Can start with source work; native integration slot for execution.
Owner area: QA helpers, launcher tests and candidate evidence.

Make native QA outcomes unambiguous. Existing helpers capture assertions but a
captured screenshot alone is not a passing assertion. Record the actual observed
result, candidate fingerprints and evidence path; unresolved observations must
remain unresolved. Test ordinary death, retry/new-run, victory, process exit and
Continue, in addition to the existing seeded checks.

Cover held input, partial save writes, corrupted/incompatible saves, stale
pending cores, launch ownership, detached native child lifetime and restoration
of `init.txt`. Preserve production data. Add bounded measurements useful to later
balance work: active time, kills/XP, ranks, actors, shots, pauses and performance
observations. Do not turn the QA launcher into a background production service.

Acceptance:

- [ ] A deliberately false native assertion cannot be reported as passed.
- [ ] QA output identifies the exact candidate and separates observed gameplay
  from mocked behavior and seeded test state.
- [ ] Death, ending, quit/Continue and New Run leave documented recoverable states.
- [ ] QA profiles never commit to the player's profile; old saves remain preserved.
- [ ] Camera/control repair after Continue preserves ranks, actors and cooldowns.

### LS-04 Overhead camera and combat readability

Priority: P1. Can start now; retail confirmation follows LS-02.
Owner area: camera/scenario presentation and contrast.

Improve the bright terrain and low-contrast HUD while keeping the outdoor Halo
setting. Make the player, active enemies, weapon effects and boundaries easy to
read. Inspect all four arenas for camera jumps, rock/structure occlusion,
unreachable enemies and boundary returns. Evaluate reasonable window sizes;
record the tested resolutions rather than claiming all-display support.

Acceptance:

- [ ] Before/after captures show readable player, enemies and HUD in each stage.
- [ ] Real movement around each arena keeps the overhead camera usable.
- [ ] Armory, stage transitions, death recovery and Continue retain the view.
- [ ] Navigation and spawn-clearance behavior remain valid after scenery changes.

### LS-05 Graphical Armory and complete skill tree

Priority: P1. Native feasibility first; presentation work can start beside LS-04.
Owner area: UI authoring, catalog-driven presentation and menu input hooks.

First prototype one weapon's seven nodes plus a support prerequisite in actual
native UI. Show branch connections, selected/locked/purchased/maxed states,
costs, available points, current rank, stage gates and prerequisites. Prove real
keyboard/mouse interaction and a purchase before committing to an implementation
for the full tree. A browser mockup can explain a layout but does not complete
the native feature. If native UI cannot support the desired layout, document the
constraint and provide a clearer native paged design as an explicit interim step.

Then cover all 50 nodes using the catalog as the source of truth. Preserve
exclusive branches, capstone prerequisites, one purchase per held click and
release-latched navigation/chords. Coordinate generator edits with other lanes.

Acceptance:

- [ ] Every node is reachable and displays the correct state, cost and effects.
- [ ] Locked, unaffordable, exclusive and maximum-rank purchases behave correctly.
- [ ] Holding a key/click cannot navigate or spend repeatedly by accident.
- [ ] Armory pauses attacks/clock, protects the player and resumes with real input.
- [ ] Native title/widget budgets are measured, not assumed to have room.
- [ ] Existing save/Continue and branch tests remain valid or are intentionally
  updated with equivalent coverage.

### LS-06 Projectile and melee combat

Priority: P2 expansion. Start with an isolated native spike; retail target uses
LS-02 findings. Owner area: combat emission, effect/projectile tags and catalog.

Prove one ranged attack and one close-range attack before converting all weapons.
Measure launch direction, ownership/team, collision, obstruction, damage
attribution and cleanup. Current cosmetic impacts deliberately omit gameplay
damage, and HSC applies the damage directly. A projectile implementation must
replace the appropriate direct damage rather than apply both.

Expand proven mechanisms to the six weapons where appropriate. Preserve auto
targeting and independent cadence. Make specialization differences visible and
set bounded projectile/effect lifetimes and object budgets. Retain immediate
damage intentionally for any weapon that needs it; document that decision.

Acceptance:

- [ ] Actual travel/contact determines damage for converted attacks.
- [ ] Moving/dead targets, walls, nearby players and team ownership behave correctly.
- [ ] No double damage or duplicate hit rewards occur.
- [ ] Armory pause, stage cleanup, ending and checkpoint reload handle live effects.
- [ ] Each affected weapon/branch has measured damage and cadence, and stress
  testing records actor/object counts and performance before integration.

### LS-07 Physical XP drops and collection

Priority: P2 expansion. Depends on a proved native death/drop mechanism and LS-03
evidence support. Owner area: XP observation, object tags, collection and cleanup.

Current XP is derived from decreases in living squad counts, which does not
provide a death location. Prove a reliable drop location and attribution path
first. Define drop value, collection radius, feedback, lifetime, maximum count
and pooling/aggregation behavior. When pickups become authoritative, disable
the equivalent direct kill credit.

Acceptance:

- [ ] A real kill creates the intended bounded drop value at a valid location.
- [ ] Collection awards XP exactly once and retains batched level-up behavior.
- [ ] Clearing actors during a transition or victory does not create free XP.
- [ ] Uncollected drops have explicit behavior on stage change, death and Continue.
- [ ] Drop/object counts stay bounded during sustained fights and are cleaned up.

### LS-08 Permanent progression between new runs

Priority: P2 expansion. Retail architecture depends on LS-02; protect LS-03's
same-run recovery behavior. Owner area: a separate profile module, launcher,
catalog IDs and narrow generator/UI integration.

Define permanent unlocks/currency separately from run ranks and native checkpoint
state. Write the proposed economy and exactly which bonuses a new run receives.
Keep the first spike to one unlock earned from a real run outcome. Prove a
supported engine-to-profile and profile-to-new-run bridge for the chosen target;
do not parse opaque native cores or assume SDK console/log hooks work in retail.

After the spike, implement stable IDs, versioned schemas, validation, atomic
commits, preserved backups and migrations. Prevent replaying an outcome from
awarding the same permanent reward twice. New Run and Continue must have distinct
semantics: New Run resets run state; Continue never reapplies starting bonuses.

Acceptance:

- [ ] An earned permanent unlock survives a full process restart and a New Run.
- [ ] Run ranks reset on New Run while only specified permanent benefits remain.
- [ ] Continue restores once without multiplying currency or bonuses.
- [ ] Duplicate outcomes, partial writes, invalid profiles and migrations are tested.
- [ ] QA and production profiles remain isolated, including permanent rewards.
- [ ] Unsupported retail behavior is reported rather than replaced by a silent
  SDK-only assumption.

### LS-09 Enemy director and stage pacing

Priority: P1. Begin from LS-03 observations; coordinate common generator/tag files.
Owner area: stage definitions, spawn cohorts, AI objectives and progression costs.

Preserve later-stage family introductions and earlier-family carryover. Tune
cohort cadence, pressure and threat roles from observed combat. Keep navigable
spawn locations and guard every slot against near-player placement. Investigate
stuck/offscreen enemies and kill-count attribution before changing reward rules.

Acceptance:

- [ ] Each stage's family introduction and encounter schedule is documented.
- [ ] All cohort slots respect player clearance, including infection forms.
- [ ] Blocked groups retry while other eligible groups continue.
- [ ] Actor cap, target scan and child-spawn multiplicity remain consistent.
- [ ] Transitions/cleanup do not award kills or XP accidentally.
- [ ] At least one ordinary run demonstrates the intended pacing before final
  balance approval; LS-10 measures it more broadly.

### LS-10 Complete run balance and performance

Priority: P1 gate for each playable release. Depends on the features selected for
that release: LS-03 through LS-05 and LS-09, plus any integrated expansion.
Owner area: measured playtests, tuning and focused regressions.

Play ordinary, uncheated 20-minute runs through all four stages with multiple
meaningful weapon branches. Record the build, chosen ranks, points/XP by stage,
deaths, damage/pressure, stuck or unreachable enemies, actor/object peaks and
frame-rate/frame-time observations. Include a successful full run and death/
restart paths. Record actual sample size and hardware; do not call a small sample
exhaustive. Console-seeded late-stage tests complement ordinary play, not replace it.

Agree on target difficulty and acceptable performance from baseline measurements,
then tune prices, XP, health, spawns and branches. Re-run the affected scenarios.

Acceptance:

- [ ] Ordinary-run records cover all stages and multiple branch choices.
- [ ] The economy permits intentional choices without obvious dominant/dead branches.
- [ ] No reproducible progression softlock, unrecoverable death state or unbounded
  actor/effect growth remains in the tested paths.
- [ ] Camera, UI, save/recovery and sustained combat remain usable late in a run.
- [ ] Performance targets, observed values, sample size and remaining risks are stated.

### LS-11 Packaging installation and release

Priority: P1 final gate. Depends on LS-01, LS-02, LS-03 and LS-10 for the selected
milestone. Owner area: installer/update path, promotion, source packaging and docs.

Provide a reproducible installation/update/rollback path for an owned supported
installation. Run a fresh native compile and read back bindings, validate the
exact candidate, build a new cache, and promote only with matching evidence.
Preserve prior package, launcher, registration and saves. Explain checkpoint
compatibility when updating the build.

Acceptance:

- [ ] A fresh supported installation can load the mod through the intended retail path.
- [ ] Update and rollback are tested without losing unrelated files or archived saves.
- [ ] Native tool exit, success marker, output freshness and hashes are recorded;
  Snap wrapper cleanup is distinguished from actual tool success.
- [ ] Source, generated outputs, version metadata and evidence agree on the candidate.
- [ ] Gameplay clip, controls, known issues and setup instructions match that release.
- [ ] GitHub source remains free of owned game assets, credentials and player data.

### LS-12 Vehicle feasibility prototype

Priority: P3, later user-requested extension. Use LS-02 findings and a stable
camera/combat baseline. Owner area: one isolated arena and one vehicle.

Choose one vehicle after assessing arena size and navigation. Prove entry/exit,
overhead steering, targeting/automatic fire while seated, damage/death, boundary
returns, Armory pause, checkpoint reload and stage transition. Define how player
ranks affect vehicle weapons and how enemies threaten it. Keep the infantry
baseline available while the prototype is evaluated.

Acceptance:

- [ ] One real vehicle can be used in a native encounter with a usable overhead view.
- [ ] Entry/exit, death, recovery and transitions leave valid player/vehicle state.
- [ ] Save/Continue behavior and any retail limitation are demonstrated.
- [ ] Geometry, navigation, enemy interaction and object budgets are measured.
- [ ] The result includes a clip and a concrete integrate/rework/defer decision.

### LS-13 Integrated vehicle encounters

Priority: P3. Implementation depends on LS-12 and the stable baseline. After
integration, the vehicle release needs fresh LS-10/LS-11 validation; those gates
are not prerequisites for beginning LS-13 implementation.
Owner area: scenario/encounters, combat integration and recovery.

Add the proved vehicle loop with explicit availability, spawn/recovery rules,
enemy interactions and progression costs. Tune it independently from the infantry
baseline before expanding to more vehicle types.

Acceptance:

- [ ] Vehicle availability and loss/recovery rules are clear to the player.
- [ ] Stage carry, ranks, auto attacks, camera, saves and final cleanup work while
  entering, seated, exiting and after vehicle destruction.
- [ ] Vehicle encounters respect measured budgets and do not trivialize all stages.
- [ ] Ordinary vehicle-enabled runs and an infantry regression pass are recorded.

## Integration and release evidence

For each task, the handoff must contain the issue/PR, base and result commits,
files changed, commands/tests run, native evidence if relevant, current known
limitations and the next dependency it unlocks. Label checks as source-only,
native SDK, retail MCC or ordinary playthrough; do not combine their claims.

Changes to gameplay, scenario, HSC, private assets or launcher behavior need
focused relevant regressions. A release additionally needs final-candidate
compile/readback, native verification, a fresh cache receipt and a matching
promotion record. If a late fix follows wider QA, record its precise scope and
retest the affected paths; do not imply the old evidence covers new code.

LS-10 and LS-11 are repeatable gates, not one-time sign-offs for every version.
For each later milestone, create linked validation issues or explicitly reopen
the checklist for the new candidate. Do not inherit a closed beta's acceptance
for a later combat, progression or vehicle release.

Keep evidence records compact and link large media stored outside Git. Do not
overwrite v0.4 receipts with future results. The current save fingerprints will
change for many planned features; preserve earlier cores and present clear
compatibility behavior instead of relaxing validation to force a load.

## Work that can begin immediately

- A tooling agent can take LS-01 without controlling the running native game.
- A QA agent can improve source-side reporting/recovery tests under LS-03.
- A presentation agent can design LS-04/LS-05 and queue a bounded native spike.
- A gameplay agent can review encounter/cost data for LS-09 using existing evidence.
- One native integration owner can prepare LS-02 and run queued experiments after
  reserving the shared slot. Owner sign-in remains an external prerequisite.

Use separate branches/worktrees. Coordinate before editing the common generator,
catalog, scenario or UI tags. The live task ownership and native slot are tracked
through the GitHub issues linked in [TASKS.md](TASKS.md).
