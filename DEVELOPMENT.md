# Developing Last Stand

Read [AGENTS.md](AGENTS.md) for work ownership and native-session coordination,
and [PLAN.md](PLAN.md) for the implementation sequence and acceptance criteria.

## Source checkout

The repository contains authored Python/HaloScript, progression data, tests,
documentation and historical release receipts. It does not contain Halo game
assets, editing-kit executables, compiled maps, native Python extensions,
recorded media or player saves. Cloning it alone does not install the game.

The current development copy is on Windows, with native compilation and play
testing on Onyx-Linux using Steam Snap, Proton Experimental and the owned
Halo 3 Editing Kit. The preflight supports local configuration; legacy remote
build, fetch, launch and QA helpers still contain that workspace's paths and
the `onyx-linux` SSH alias. Read and adapt those helpers before another setup.

## Configuration and prerequisite checks

Copy `last-stand.example.json` to the ignored `last-stand.local.json` and edit
the paths for your installation. The example's `../H3EK` is a placeholder.
You can omit `editing_kit` for source-only work. The workspace is always the
checkout; `preflight.py --root PATH` can inspect a different source workspace.

Selection order is `--config FILE`, `LAST_STAND_CONFIG`, then the optional
`last-stand.local.json` in the workspace. An explicitly selected missing or
invalid file is an error. Local paths in a config resolve relative to its
directory. Remote paths must be absolute normalized POSIX paths. Executable
settings name one program, not a command with arguments. Defaults preserve
the current Onyx alias and remote workspace; they do not configure a local kit.

```sh
python -B preflight.py --stage source
python -B prepare_progression.py --check --json
python -B preflight.py --config last-stand.local.json --stage native
python -B preflight.py --tools /path/to/H3EK --json
python -B preflight.py --remote --json
```

All five commands are read-only. The source check works without owned assets.
The authoring check lists all missing direct inputs and checks output paths;
it does not import the native binding or authors. Native checks inspect the
configured local or remote SDK/staged files, without running SDK programs.
Remote checks require an already trusted SSH host and noninteractive login.
Exit 0 means the selected prerequisites passed; exit 2 means blocked/error.

Configuration currently applies to preflight and preparation's prerequisite
check. Preparation still writes beside its own source files; config cannot
redirect its workspace. `tools.scp` is reserved for subsequent helper migration
and is not invoked here. Existing staging, fetch, compile, launch and QA helpers
do **not** consume this config yet. Do not infer that changing the JSON moves
the installed game or makes the historical bootstrap portable.

See [BOOTSTRAP.md](BOOTSTRAP.md) for the 18 direct authoring inputs, output
inventory, inherited native dependencies and known fresh-installation gaps.

## Source tests

Tested with CPython 3.14.6. From the repository root:

```sh
python -B -m unittest discover -s tests -v
```

The complete owner workspace passes all 217 tests, including 29 Armory model,
scheduler and title-style checks added for LS-05. A clean source export passes
212 tests (213 reported entries, one skipped module). Source-only checkouts skip
one module containing five spawn-geometry tests when the external `blam_tags`
binding is unavailable; its owned-navigation test also needs the local scenario
asset. The remaining source checks require no third-party Python package.
The historical v0.4 native release passed 109 tests. Passing source tests does
not establish native validation or a new release.

The test VM exercises the emitted HaloScript subset. It is not a Halo compiler
or a replacement for engine play testing. Native test evidence is recorded in
`native-validation-v04.json`, including which checks preceded the final narrow
victory fix.

## Current LS-05 Armory candidate

`armory_presentation.py` derives seven reference pages from stable catalog IDs
and actual prerequisite edges: six weapon pages with seven nodes each, and an
eight-node support page. They show stage gates, exclusive specializations and
the matching capstone requirements. The native pages are static reference maps;
they do not display current ranks or purchased/affordable/locked styling for
every node. Selected CHUD details and rotating points/rank notices retain that
existing purchase information. The read-only Python model also exposes live
snapshot facts for future presentation work; it does not replace native guards.

The controls are unchanged: Space/Q select skills, Space+Q changes category,
left click buys one rank, and 1 resumes. `sv_tree_tick` draws the latest selected
category at most once per 30 logical ticks, after input handling. Rapid changes
coalesce; Resume stops refresh on that same frame. A page expires within one
second, and a restored Armory clock redraws within one second without resetting
progression. The existing status notice queue retains its separate 90-tick
throttle. Source VM checks cover these scheduling rules and compare display
availability with generated purchase guards; they do not prove native timing.

Native compilation/readback produced 402 scripts, 178 globals, 43,180 syntax
datums and 128 titles. All seven static pages fit using the large body text font
and native `|n` line breaks. Text contrast against bright terrain still needs
polish. This reaches the current 128-title authoring guard; further UI work must
account for that budget. See [the LS-05 evidence](native-validation-ls05.json)
for the bounded native observations and remaining checks. Fit alone does not
complete LS-05, establish dynamic graphical states or validate retail MCC.

The native checks also passed held navigation/purchase, prerequisite/stage/
exclusive-path/points guards, category switching, Resume/page expiry, reopening,
and a 25-second refresh soak. A full process restart retained the stage-two
checkpoint, ranks, points, timer and 17 enemies, restored the page and overhead
camera, and resumed auto-fire. The original staged build and checkpoint were
restored afterward; all 14 original profile files are byte-identical. Initial
QA-driver failures were excluded and rerun as documented in the evidence.

The installed v0.4 package remains unchanged. This candidate has no fresh cache
or promotion receipt. Changed scripts, titles and the added tree-clock global
produce a new exact-build fingerprint; native testing must use its own QA core,
and existing production checkpoints are not migrated to it.

## LS-04 camera and status candidate

The camera retains its current anchor until another is more than 0.35 map units
nearer. Invalid anchors and stage changes still select a valid view immediately.
The periodic camera/control repair requests a refresh of the retained anchor
instead of clearing it, so the repair does not bypass the switching margin.
Tests cover boundary jitter, stage changes, missing players, refresh behavior
and preservation of run/input state; the VM does not simulate native camera
interpolation or core restoration.

Cinematic status/help/points/rank notices now explicitly use dark charcoal text
and a pale shadow, preserving their font, bounds and lifetime. Node descriptions
use `cinematic_set_chud_objective` and retain their previous style; this change
does not establish improved CHUD rendering. [Native evidence](native-validation-ls04.json)
records compilation/readback (400 scripts, 177 globals, 42,994 syntax datums,
121 titles), four-stage views, short real movement routes, and a full process
restart retaining stage-two progress, 17 actors, overhead view and the resume key.
The initial console-input failures and unsuccessful short stage-one route are
retained in the record; only visually confirmed assertions count as passes.

These checks cover one observed window size. Full arena/occlusion inspection,
death recovery, combat readability, other sizes, ordinary runs and retail remain
open. The exact original staged build and checkpoint were restored after QA;
the installed v0.4 package remains the release baseline. The changed scripts
and two added globals change the save fingerprint. This candidate has no fresh
cache or promotion receipt; previous production cores are not migrated to it.

## Optional authoring and capture dependencies

- `blam_tags` from [camden-smallwood/blam-tags](https://github.com/camden-smallwood/blam-tags).
  The local binding was built from commit
  `6a1225b54ad8522b12c62fa1ad9e7377febde408`, with definitions submodule
  `7706dfb22ff2d436561c264f0e2d469987877f0d`.
  The upstream `blam-tags-py` README documents building a wheel with
  `maturin build --release -o dist` from that crate, then installing the wheel.
  Use the upstream instructions and their toolchain requirements. The current
  Windows development copy instead uses a locally built extension copied into
  the workspace as `blam_tags.pyd`; it is deliberately not vendored here.
- Pillow is used for screenshot capture and contact sheets; local version
  12.2.0 was observed. It is not needed by the source-only test suite.
- Native Onyx capture/control uses X11, `xdotool`, FFmpeg and the owned SDK.
  The launcher uses Linux process/locking facilities and Zenity dialogs.

## Native authoring and validation

1. Install and extract the owned Halo 3 Editing Kit and prepare the private
   scenario/tag inputs. Native authoring currently depends on the existing
   local `private-inputs/` and `native-tags/` baseline, including the outdoor
   navigation scenario. Rebuilding that baseline from a fresh installation is
   not yet a one-command workflow.
2. Run `python -B prepare_progression.py --check` in that prepared workspace.
   Resolve every missing prerequisite before running
   `python -B prepare_progression.py` to author progression tags, HaloScript,
   damage effects and UI titles. Preparation repeats the guard and loads all
   authoring modules before writing. Content errors later in authoring can
   still leave partial outputs; this is not an atomic build. It does not
   compile a playable map.
3. Use the adapted `onyx_progression.py stage` and `compile` helpers to stage
   and compile in Sapien. Check compiler diagnostics and read back the compiled
   script counts/bindings before running the native QA tools.
4. Run native gameplay and launcher QA in an isolated QA profile. These scripts
   drive the active SDK window and can alter test state; they are development
   tools, not a player launcher.
5. Build a fresh cache and retain its receipt. `promote_v03.py` retains its
   historical filename but targets v0.4.0 and requires matching validation and
   cache evidence. Never reuse old receipts as proof of a changed build.

The installed launcher is `launch_v04.py`, deployed as the Onyx workspace's
`launch.py`. Checkpoints require matching engine, scenario, script and private
asset fingerprints. Changing the build can invalidate Continue compatibility.
The Git attributes preserve exact file bytes because release receipts include
content hashes.

The existing native build is documented in the README. Retail MCC menu loading,
retail save support and a portable installation workflow remain unfinished;
see [ROADMAP.md](ROADMAP.md).

## Source archive

`python -B bundle_source.py` creates an archive from an explicit source
allowlist, with a per-file hash manifest. An existing archive is preserved
unless `--force` is explicitly supplied. This archive is a source snapshot,
not the playable map. Historical v0.4 release receipts describe the tested
native build; repository documentation updates do not constitute a new build.
