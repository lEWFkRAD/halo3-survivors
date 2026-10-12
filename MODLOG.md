# Mod log

## 2026-10-11 - codex
User requested a real MCC Halo 3 x Vampire Survivors mod and mentioned mashup software seen on X.
Found and cloned Universal Modder; ran python -B -m um scan --list and kb search halo.
Detected library contains Geometry Dash and Steam redistributables, no MCC or editing kit.
No existing relevant wiki topic found. Asked which PC has MCC and for the software name/link; pending.
Route: reimplement survival mechanics in native HaloScript, using official editing kit and owned game assets.
Closest toolkit field note ports Halo into Minecraft; that reverses the requested host, so it is not used as
an implementation. No guest executable, asset extraction, native injection or online service is needed.
First vertical slice: solo native campaign scenario, waves, XP, upgrade pads, extraction.
Source and mock-engine tests can proceed; actual scenario/tag authoring, Halo compilation and gameplay cannot.
No game folder, save, fleet setting, service or Steam account was changed. Before first modded launch,
locate and back up the actual MCC saves/profile with Universal Modder. No game version has been verified.
Onyx bounded logic review attempted: first call refused, permitted retry returned a truncated response;
no correctness claims are based on it.

## Source verification - codex
15/15 tests passed against the generated HSC using tests/hsc_vm.py, including a seeded 1260-second run.
First run found sv_level was both a global and a cutscene title. Renamed title sv_upgrade_ready and reran:
all passed. This mock interpreter is NOT the Halo compiler and does NOT validate engine implementation,
AI pathfinding, spawn timing, title display, weapon tags, frame rate or actual game behavior.
Universal Modder package lint: PASS, 8 files, 0 failures, 0 warnings. Nothing published.
Default H3EK preflight: blocked, all required tools/assets/scenario absent.
Next: obtain actual MCC/tool installation location; author arena scenario, weapon tags and title bindings;
compile in Sapien; test in tag_test; compile cache; package and play in MCC.

## 2026-10-12 — Outdoor bird-eye revision
- Preserved compiled overhead hangar build and moved gameplay to Ark BSP0 landing clearing.
- 73 overhead anchors, 12WU height; native camera pans and outdoor enemy pursuit verified.
- Auto-targeted Needler damage and XP verified without firing input; nearest-target tests pass.
- Native outdoor cache compilation succeeded; packaged version0.2.0.
- Retail MCC starts with official Mods option but requires owner Xbox/Microsoft sign-in.


## 2026-10-12 - v0.3 progression candidate, validation in progress - codex

- Implemented 50 skill nodes across six automatic weapon trees and eight
  support skills. Weapon trees include unlocks, damage/cadence ranks, mutually
  exclusive specializations and branch capstones; health, shields, recovery,
  range and XP support skills supplement them.
- Four five-minute outdoor stages: Landing, Incursion, Outbreak and Last Stand.
  Purchased ranks, weapon unlocks, XP and unspent points carry across stages in
  the same run. Quitting resets progression; cross-run saves are not implemented.
- Needler and Assault Rifle become available in stage 1, Shotgun and Plasma
  Rifle in stage 2, Rocket Launcher and Energy Sword in stage 3; branch
  capstones are gated to stage 4. The attacks apply instant damage rather than
  simulating travelling projectiles or sword swings.
- Later stages introduce Captains/Snipers, Flood combat/infection/carrier forms,
  then Hunters/Chieftain alongside earlier enemy families. Arena boundary
  recovery preserves progress. Completing stage 4 replaces the old extraction
  beacon ending; final native ending verification is still underway.
- Final Armory bindings: Space next, Q previous, LMB buy, 1 resume, Space+Q
  category; Space+Q also reopens during combat. Full release is required between
  actions. Movement stays available while enemies, automatic attacks and
  progression pause; the player is protected. Cached action polling and
  reset/prime handling replace the earlier E/2 control candidate.
- Compact node information and serialized status notices keep controls, points
  and ranks discoverable without overlapping title messages.
- 58 deterministic tests pass. All 8 native menu assertions and all 22 native
  stage assertions now pass. Native six-weapon and ending QA remain in progress.
  The native timing check advanced 11 script seconds over 11.058 wall seconds;
  no conversion to a 60-tick script clock was made.
- Package is NOT promoted: installed MCC package remains v0.2.0. Final native
  validation record: PENDING. Fresh successful build receipt: PENDING. v0.3
  map size/SHA-256 and promotion receipt/backup path: PENDING.
- Safe promotion tooling requires matching candidate fingerprints, native
  validation and a fresh successful build; it preserves GUIDs/registration and
  backs up the old package. No release action was taken by this documentation
  update. Retail sign-in/menu validation, vehicles, physical XP pickups and
  full-run balancing remain outstanding.


## 2026-10-12 17:27 UTC - v0.3.0 promoted - codex

- Supersedes the pending-release status above. Native-tested v0.3.0 was built
  fresh and promoted to Onyx mods/LastStand, preserving mod/campaign/map GUIDs
  and registration. The desktop shortcut uses the private official SDK engine.
- 65 deterministic tests pass. Native assertions passed for menu 8/8, stages
  22/22 and weapons 6/6. Final native compile readback: 344 scripts, 167 globals,
  36680 syntax datums and 121 titles, with no fresh HSC fatal errors.
- The original game_won unload reached a failing stock SDK main-menu UI.
  Replaced it with a protected terminal victory in the current scenario:
  enemies clear, movement/gameplay stop, victory remains visible, and the user
  closes/relaunches for a new run. Native ending and ending_stays assertions
  passed; stage time and shots remained frozen after six seconds.
- qa_provenance in native-validation-v03.json records that the broad gameplay
  checks preceded the final narrow victory change. victory-fix.diff confirms
  the final branch/notice-dispatch scope; UI edits adjusted the victory title
  lifetime/text and controls separator. Final compile, clean boot/UI and
  terminal victory were retested after that change; a second full gameplay
  test run is not claimed. Latest clock probe: 10 script seconds over
  11.058391 wall seconds including console transitions, retaining sleep30.
- An earlier otherwise successful cache build was refused because Snap cleanup
  returned 1. The build wrapper now captures the actual inner Wine/tool exit
  immediately in a unique hashed status sidecar. A NEW build produced tool
  exit 0, outer launcher exit 1, the explicit success marker and fresh matching
  cache/input hashes. Schema-2 receipt checks then permitted promotion.
- Final map: 704221184 bytes; SHA-256
  3b6ff9a73d39761814f177091be80df609098f0a1a3dea9624235d6ee40e3b49.
  Build finished 2026-10-12T17:27:12.280730+00:00; promoted at
  2026-10-12T17:27:42.346521+00:00.
- Backup: Onyx workspace backups/package-before-v03-20261012T172742Z-09c32ad4.
  Local receipts: promotion-v03.json, cache-build-receipt-v03.json,
  native-validation-v03.json and build-result-v03.json. These agree on final
  map size/hash and candidate fingerprints; generated HSC matches the receipt.
- Final README files now describe the promoted release. Source bundling uses an
  explicit allowlist including release receipts and victory diff; native-owned
  tags/assets, caches, media and stale QA snapshots remain excluded.
- Retail MCC menu/loading still awaits owner Xbox/Microsoft sign-in. Solo
  scope, instant-damage attacks, same-run-only carry, future vehicles/physical
  XP pickups and incomplete exhaustive balance testing remain explicit.
  A fresh gameplay clip is being handled separately; delivery is not claimed
  by this entry.


## 2026-10-12 - v0.4.0 installed - codex

- Added Armory checkpoints and a verified Continue/New Run launcher. A full
  process restart preserves the native encounter.
- Added closer spawn rings on valid navigation locations, with two-unit player
  clearance and batched XP levels; corrected deferred victory cleanup.
- 109 deterministic tests passed. Native validation scope and the narrow final
  fix are recorded in native-validation-v04.json.
- Package: 704,286,720 bytes; SHA-256
  58b6455b3928874d714cae00e28bb40ffc177e8e4d759376ea44c7c954b21ec3.
  The prior package and launcher are backed up.
- Permanent unlocks between separate runs remain unimplemented. Retail MCC
  loading remains unverified.
