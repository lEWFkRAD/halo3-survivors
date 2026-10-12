# Last Stand roadmap

Status: v0.4.0 playable prototype, 2026-10-12. These are remaining tasks,
not features included in the current build.

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
- [ ] Make a fresh checkout reproducible on another owned installation:
  document and configure external tools, paths, tag inputs and build steps.
  Current scripts preserve the existing Onyx development setup.
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
scope. See [native validation](native-validation-v04.json) for the exact test
scope and [README](README.md) for controls and current limitations.
