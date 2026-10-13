# Last Stand roadmap

Installed status: v0.4.0 playable prototype. The LS-01 stock bootstrap milestone
has separate SDK evidence; the remaining release/gameplay tasks below stay open.
Completed tooling does not change the installed package.

For detailed implementation steps, dependencies and acceptance criteria, see
[PLAN.md](PLAN.md). Agents can claim bounded work through [TASKS.md](TASKS.md)
and follow the coordination rules in [AGENTS.md](AGENTS.md).

## Release readiness

- [ ] Verify the packaged mod through the retail MCC mod menu after the owner
  completes Xbox/Microsoft sign-in. Current native testing uses the owned
  Halo 3 standalone SDK engine. SDK launcher checkpoints do not establish
  retail MCC save support.
- [ ] Play complete ordinary 20-minute runs through all four stages. Tune XP,
  upgrade prices, weapon branches, health, enemy introductions and difficulty.
  Existing targeted checks do not establish full-run balance.
- [ ] Improve bright terrain, player/enemy contrast and HUD readability.
  Check camera movement, occlusion, terrain edges and arena returns throughout
  every stage.
- [ ] Replace the rotating text Armory with a readable graphical tree showing
  branches, prerequisites, prices, available points and purchased ranks.
- [x] Make a fresh checkout reproducible on another owned installation:
  document and configure external tools, paths, tag inputs and build steps.
  The supported [stock bootstrap route](BOOTSTRAP.md) was exercised against an
  isolated, freshly extracted owned kit without historical private templates.
  [LS-01 evidence](native-validation-ls01.json) records the compile/cache and
  short SDK checks; complete runs, retail and release promotion remain open.
- [ ] Provide a tested player installation/update path after retail loading
  is verified. This repository contains source, not a downloadable playable map.

## Gameplay additions

- [ ] Add permanent progression between separate new runs. Current upgrades
  carry between stages, and Continue restores the same saved run; New Run
  starts fresh.
- [ ] Add travelling projectiles and physical melee behavior where appropriate.
  Current automatic weapons apply immediate damage with distinct effects,
  ranges, cadences and target counts.
- [ ] Add physical XP pickups and collection feedback. Current kill XP is
  awarded directly.
- [ ] Add vehicles as a later extension, including movement/camera behavior,
  enemy interaction and encounter balance.

## Already implemented

- [x] Bird's-eye camera and automatic attacks in native Halo 3.
- [x] Six weapons with branching upgrades and a 50-node total skill tree.
- [x] Four outdoor Ark stages with timed enemy-family introductions.
- [x] Purchased ranks, XP and points carried between stages.
- [x] Same-run Armory checkpoints with Continue/New Run in the SDK launcher.
- [x] Closer navigation-valid spawn rings, player-clearance guards and a
  36-enemy cap.
- [x] Batched level-up awards and protected victory cleanup.

The prototype is solo. Multiplayer support is outside the current verified
scope. See [v0.4 native validation](native-validation-v04.json) for the installed
release and [LS-01 evidence](native-validation-ls01.json) for the later stock
rebuild. Its cache success marker accompanies 25 stock-asset error diagnostic
lines; the native tool exit was not captured. Its 19 short SDK assertions
(18 gameplay checks and one transport control) include seeded/deathless later
stages and do not replace full-run or retail gates.
See [README](README.md) for controls and current limitations.
