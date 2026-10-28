<!-- project-home:start -->
**[Last Stand: Halo 3 Survivors project homepage](https://lewfkrad.github.io/halo3-survivors/)** · [Documentation](https://github.com/lEWFkRAD/halo3-survivors/blob/main/BOOTSTRAP.md)

A native Halo 3 fan-mod prototype with overhead survival combat, automatic attacks, and branching upgrades.

<!-- project-home:end -->

# Last Stand: Halo 3 Survivors

![Last Stand: Halo 3 Survivors — an overhead Spartan surrounded by Covenant and Flood on the Ark](docs/images/last-stand-hero.png)

*Promotional concept art. [Artwork provenance](docs/images/README.md).*

**Installed gameplay baseline: v0.4.0 on Onyx-Linux** (2026-10-12).
This native Halo 3 mod combines a bird's-eye camera, automatic attacks, a
50-node skill tree and four outdoor stages on the Ark.

This is a playable prototype under active development. The repository contains
authored source, tests and release evidence; owned Halo assets, SDK binaries,
compiled maps and player saves remain local. See [ROADMAP.md](ROADMAP.md) for
unfinished work and [DEVELOPMENT.md](DEVELOPMENT.md) for checkout requirements.

Agents joining the project should start with the [full implementation plan](PLAN.md),
[task queue](TASKS.md) and [agent handoff guide](AGENTS.md). The task issues track
ownership, dependencies and acceptance evidence.

Want to help? Read the [contribution rules](CONTRIBUTING.md) and
[community rules](CODE_OF_CONDUCT.md), then
[report a bug or propose an improvement](https://github.com/lEWFkRAD/halo3-survivors/issues/new/choose).
Small fixes and clear playtest reports are welcome; native assets are not needed
for documentation or source-only contributions.

v0.4 adds Armory checkpoints with Continue/New Run, closer enemy spawns with
player-clearance checks, and batched level-ups. It also fixes victory cleanup:
Halo must process its queued actor deletion before enemies disappear.

The LS-04 source candidate adds a small camera switching margin to
reduce repeated pans near anchor boundaries, including during Continue repair.
It also gives cinematic status, help, points and rank notices dark text with a
pale shadow. Selected skill descriptions use a separate CHUD renderer and keep
their existing style. Native compile, four-stage view/movement checks and a
checkpoint process restart passed; see [the bounded test record](native-validation-ls04.json)
for evidence and limits. This candidate has not been promoted as a release.
The previous game and checkpoint are restored, and broader LS-04 work remains open.

The current LS-05 development candidate adds nine live Armory pages covering
all 50 skills: six weapon pages and three support pages. Each node shows its
current rank and a marker for available (`+`), locked (`-`), owned (`o`) or
maximum rank (`*`). Separate wallet and next-price notices accompany the
selected skill's effects, prerequisite ranks and stage requirement. The authored
HUD uses an opaque black panel and white wallet text. Bounded SDK checks cover
readability, Resume/reopen and Continue; refresh gaps and broader UI acceptance
remain open. See [the live Armory guide](ARMORY_LIVE.md) and
[its bounded validation record](native-validation-ls05-live.json).

LS-05 remains open, and the installed release remains v0.4.0. The earlier
[seven-page static prototype](native-validation-ls05.json) and
[HUD feasibility probe](native-validation-ls05-ui-probe.json) are historical
steps, with their own evidence and limits. They do not validate this live
candidate. The live candidate compiled and produced a fresh cache with native
exit 0 and a success marker; 25 stock-asset error diagnostic lines remain.
Retail verification, a full ordinary run and package promotion remain open.

Native QA now has an import-safe [evidence reader](NATIVE_QA.md) that separates
emitted pass/fail results from echoed commands. Missing or ambiguous output
stays unresolved. It records exact candidate hashes and distinguishes SDK,
retail, seeded and ordinary observations. This tooling does not change gameplay
or promote the installed package; broader recovery and full-run testing remain
on the roadmap. The launcher source also keeps shutdown checkpoint archives in
their originating profile. See [LS-03 native evidence](native-validation-ls03.json)
for true/false transport checks, Continue/New Run, a natural level-up and the
native cleanup test. The installed launcher remains the original v0.4 baseline.

The supported build path now starts from extracted stock H3EK tags. It rebuilt
an isolated SDK candidate without the historical private scenario templates;
see the [bootstrap recipe](BOOTSTRAP.md) and [LS-01 evidence](native-validation-ls01.json).
This tooling milestone leaves the installed v0.4 package and player saves intact.
Retail verification, complete runs and the remaining gameplay work stay open.

## Play

Open **Last Stand - Halo 3 Survivors** on Onyx-Linux. The shortcut uses the
owned Halo 3 standalone SDK engine and the new save-aware launcher. Allow
about a minute for the map to load. A saved run offers Continue, New Run and
Cancel; New Run archives the old checkpoint.

WASD moves; unlocked weapons fire automatically. The overhead camera follows
the player, with mouse look disabled.

| Armory action | Binding |
| --- | --- |
| Next skill | Space |
| Previous skill | Q |
| Buy one rank | Left mouse button |
| Next weapon/support category | Space + Q |
| Resume | 1 |
| Reopen Armory during combat | Space + Q |

Release buttons between actions. Enemies, automatic attacks and the survival
clock pause in the Armory; movement remains available and the player is
protected. Help, points and current rank rotate on screen. Each selected skill
shows its effects, price, prerequisite and stage requirement.

The live LS-05 candidate uses these same controls. Its page follows the selected
skill within one second. Node numbers are current ranks; `+` means available,
`-` locked, `o` owned and `*` maximum rank. An owned node can still need more
points for its next rank; the selected detail and next-price notice explain
the purchase. Resume disables the graph; wallet and price notices have a
one-second expiry. Native captures show them gone by two seconds. These changes are in the development
candidate; the installed baseline retains its rotating notices.

## Save your run

Opening the Armory and purchasing an upgrade request a native checkpoint.
Wait about three seconds before quitting. Continue restores the latest
Armory checkpoint, including the stage, clock, enemies, XP, points and upgrades.
Quitting during combat returns to the last Armory checkpoint.

Saves live in `saves/v04` under the Onyx workspace. The launcher checks their
hashes and exact engine/scenario/source/private-asset compatibility. Changed
builds may require a new run; earlier saves remain archived. QA profiles are
separate under `qa-saves` and never become the player's profile.

This resumes the same run. Permanent unlocks between separate runs remain
future work. These checkpoints are an SDK-launcher feature; retail MCC saving
has not been verified.

## Progression and encounters

The tree has seven nodes for each of six weapons and eight support nodes.
Each weapon includes unlock, damage and cadence upgrades, two exclusive
specializations, and a capstone for each specialization. Support upgrades
improve health, shields, recovery, range and XP. Kills award XP; all affordable
levels from a burst are awarded in one Armory visit. The point wallet caps at 50.

| Stage | Active duration | New weapons | New enemy families |
| --- | --- | --- | --- |
| Landing | 5 minutes | Needler, Assault Rifle | Grunts, Jackals, Brutes |
| Incursion | 5 minutes | Shotgun, Plasma Rifle | Captains, Snipers |
| Outbreak | 5 minutes | Rocket Launcher, Energy Sword | Flood combat, infection, carriers |
| Last Stand | 5 minutes | Branch capstones | Hunters, Chieftain |

Needler starts unlocked; other weapons require a purchase. All ranks, unlocked
weapons, XP and points carry between stages. Earlier enemy families continue
appearing later. Most spawn points are now 5.5–8 map units from the arena center;
snipers and heavy enemies retain more distance. A cohort waits if any spawn
point is within two units of the player, while other eligible groups continue.
The global limit remains 36 enemies. Leaving the arena returns you to its center.

Victory clears hostiles and leaves a protected result screen with gameplay
stopped. Close and relaunch, then choose New Run to start again.

Attacks currently apply immediate automatic damage with distinct effects,
range, cadence and target counts. Travelling projectiles, physical XP pickups,
vehicles, remaining Armory polish and exhaustive full-run balancing remain future work.
The prototype is solo. Retail MCC mod-menu loading remains unverified pending
owner Xbox/Microsoft sign-in and testing.

## Validation and release

The v0.4 release passed 109 deterministic tests. Native checks cover eight menu assertions,
22 stage/roster/cap assertions, all six weapons, six spawn-clearance assertions,
three batched-level assertions, and a 10-second clock test. A complete process
restart restored stage 2, 430 seconds, 81.25 XP, 7 points, Assault Rifle unlock
rank 1, Needler damage rank 2, 123 shots and 17 hostiles; the camera, paused
Armory and real resume key worked.
The final victory test began with enemies and confirmed zero actors after
cleanup and a frozen result after six seconds.

Final Sapien readback: 400 scripts, 175 globals, 40,242 syntax datums, 121 titles.
Most combat/menu tests preceded the one-line final victory cleanup fix;
`victory-cleanup-v04.diff` and the validation record identify that scope.
Final compile, restart/camera/input and victory were verified afterward.

- [Native validation](native-validation-v04.json)
- [Build receipt](cache-build-receipt-v04.json)
- [Package promotion](promotion-v04.json)
- [Installed build](build-result-v04.json)
- [Launcher installation](launcher-install-v04.json)
- [v0.4 details](README-v0.4.md)

The map is 704,286,720 bytes, SHA-256
`58b6455b3928874d714cae00e28bb40ffc177e8e4d759376ea44c7c954b21ec3`.
The previous package is preserved in
`backups/package-before-v04-20261012T183644Z-80cf4639`; the prior launcher is in
`backups/launcher-before-v04-69157a49ac`. Package GUIDs and registration remain.
The build receipt records the native tool's exit separately from Snap cleanup.

## Source

Onyx workspace: `/home/jeffrey-watts/Documents/Games/Halo3Survivors`.
The local MCC package is `mods/LastStand`. The private scenario and HSC live
under the owned Steam Snap H3EK installation.

Run `python -B -m unittest discover -s tests` locally. The LS-01 source suite
passes 331 tests with six skipped entries in the owner checkout; its clean
export passes 326 tests with seven skipped entries. Owned bootstrap checks
separately pass all 22 tests, including six asset-dependent tests, and all five
geometry tests pass against the fresh compiled baseline. These are separate
runs, not a full-suite run against every fresh input. The external binding and
skip conditions are described in [DEVELOPMENT.md](DEVELOPMENT.md); earlier
release evidence retains its original test counts.

Follow [BOOTSTRAP.md](BOOTSTRAP.md) for the configured stock-input fetch,
direct baseline authoring, native save/readback, isolated progression preparation,
exact staging and manual SDK compile/cache sequence. Start with
`python -B preflight.py --stage source` and the documented read-only checks.
`native_workspace.py` copies only manifest-verified candidate files and records
readback bytes; an idle-process check or readback receipt is not compilation proof.
Historical Onyx scripts remain available for reference but are not the supported
fresh-build route. Native work still requires the operator slot and session handoff.

[LS-01 evidence](native-validation-ls01.json) records the isolated stock rebuild:
402 scripts, 178 globals, 43,180 syntax datums and 128 titles. Cache output is
702,328,832 bytes with a success marker; 25 stock-asset error diagnostic lines
remain in the log, and the native tool exit code was not captured. Nineteen short
SDK assertions cover all four stages; stage one used ordinary uncheated play,
while stages two through four used seeded, deathless checks. This does not
establish full-run balance, complete arena reachability, retail support or a
release-ready cache receipt. All 20 pre-existing production profile files remain
unchanged; two normal session files were added. The installed package was not promoted.
`promote_v03.py` retains its historical filename but now targets v0.4.0 and
requires matching native evidence and a fresh successful cache receipt.
The original v0.4 version of `launch_v04.py` is installed as the Onyx
workspace's `launch.py`; current development changes have not been promoted.

`bundle_source.py` produces `dist/last-stand-v0.4-source.zip` from an explicit
allowlist with per-file hashes. It contains authored source, tests, contracts,
release evidence and documentation. It excludes owned game tags, native
caches, screenshots and videos, and is not a playable map. No public Workshop
publication is claimed. The v0.3 source ZIP preserves the previous release.
