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
Halo 3 Editing Kit. The supported fetch, direct-bootstrap, preparation,
preflight and native-workspace transfer helpers consume local configuration.
Legacy remote build, launch, promotion and QA scripts remain operator-specific
historical tools; they are not a portable installation workflow.

## Configuration and prerequisite checks

Copy `last-stand.example.json` to the ignored `last-stand.local.json` and edit
the paths for your installation. The example's `../H3EK` is a placeholder.
You can omit `editing_kit` for source-only work. Set it to an owned extracted kit
for local fetch or staging. `--root PATH` selects a different input/output
workspace; the Python implementations still come from the executing checkout.

Selection order is `--config FILE`, `LAST_STAND_CONFIG`, then the optional
`last-stand.local.json` in the workspace. An explicitly selected missing or
invalid file is an error. Local paths in a config resolve relative to its
directory. Remote paths must be absolute normalized POSIX paths. Executable
settings name one program, not a command with arguments. Defaults preserve
the current Onyx alias and remote workspace; they do not configure a local kit.

```sh
python -B preflight.py --stage source
python -B fetch_progression_inputs.py --check --json
python -B preflight.py --stage bootstrap
python -B bootstrap_tags.py --check
python -B prepare_progression.py --check --json
python -B preflight.py --config last-stand.local.json --stage native
python -B preflight.py --tools /path/to/H3EK --json
python -B preflight.py --remote --json
```

All listed commands are read-only. Source checks need no owned assets. Fetch
checks use input sizes/types and output safety without reading tag contents.
Bootstrap preflight discovers the binding; `bootstrap_tags.py --check` then
imports it, parses the three stock tags and authors/round-trips the baseline in
memory without writing. Preparation's `--check` lists direct prerequisites and
output safety without importing authors or the native binding. Native preflight
inspects SDK/staged files without running SDK programs. Exit 0 means the selected
operation passed; 2 means blocked/error. None establishes a playable build.

Fetch defaults to a configured local kit. `fetch_progression_inputs.py --remote`
explicitly selects the remote kit, using trusted, noninteractive SSH and Python
stdin requests for literal paths. `--remote --check` is stat-only. Actual fetch
stages all 21 stock tags, validates headers/hashes, and publishes only declared
files plus provenance metadata. Missing or failed inputs preserve the previous
set; ordinary publication failures roll back. `tools.scp` remains unused by this
path. Changing configuration alone does not alter the installed game.

`native_workspace.py` stages or reads back a local `editing_kit`; it has no
remote-execution mode. Its `--check` validates the exact candidate and performs
a conservative native-process inspection without writing. Actual staging checks
manifest hashes and archive contents, rejects existing destinations unless
`--replace` is supplied, backs up replacements, and records transfer receipts.
It neither stops/launches tools nor edits `init.txt`, saves or installed maps.
Readback receipts always report `native_compilation_verified: false`.

See [BOOTSTRAP.md](BOOTSTRAP.md) for exact input/output inventories, check
semantics, the verified direct-stock native milestone and its remaining limits.
The helper modules are import-safe; historical helpers may not be.

## Source tests

Tested with CPython 3.14.6. From the repository root:

```sh
python -B -m unittest discover -s tests -v
```

The LS-01 owner suite passes 331 tests with six skips (337 reported entries).
The clean source export passes 326 tests with seven skipped entries (333
reported entries). Six owned-bootstrap tests skip without canonical private
inputs/binding; a source-only checkout also skips the module containing five
spawn-geometry tests when `blam_tags` is unavailable. An additional run of all
five geometry tests passed using the freshly compiled LS-01 baseline and the
isolated binding. These geometry tests validate navigation selection and safe
cohort rings, not full native path reachability.

The preceding LS-05 baseline passed 217 owner tests and 212 clean-export tests;
the historical v0.4 release passed 109. Source checks requiring neither owned
assets nor the native binding need no third-party Python package. Passing them
does not establish native validation or a new release.

The test VM exercises the emitted HaloScript subset. It is not a Halo compiler
or a replacement for engine play testing. Native test evidence is recorded in
`native-validation-v04.json`, including which checks preceded the final narrow
victory fix.

## Native QA evidence reader

See [NATIVE_QA.md](NATIVE_QA.md) for the read-only `native_qa.py` API and native
operator workflow. A deliberately false engine result is a failure; console
echoes, screenshots, missing output and ambiguous logs cannot count as passes.
The reader records a bounded log window and candidate metadata. Operators must
independently verify the emitting process, profile and build, and preserve log
snapshots before restarting the engine.

The LS-03 reader added 28 synthetic evidence regressions; launcher shutdown added
five profile-cleanup regressions. That historical owner suite passed 250 tests;
the current LS-01 suite counts are recorded above.
Native SDK checks are separate from these source tests and
do not establish retail support or complete ordinary-run recovery coverage.

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

The installed v0.4 package remains unchanged. The historical LS-05 validation
did not include a fresh cache or promotion receipt; the later LS-01 candidate
has its own fresh-kit cache evidence below. Changed scripts, titles and the added tree-clock global
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

The fresh-kit path was exercised at source commit
`dc4d80e58111ad026b0a722899130ce4e5caa2b2`; see
[LS-01 native evidence](native-validation-ls01.json). The isolated kit began with
57,706 files extracted from the owned archive, followed by the 21-tag fetch,
baseline native save/readback, fresh preparation, staging and final compilation.
Baseline staging/readback used the coordinator's private byte-copy helper;
final progression staging exercised `native_workspace.py` with 140 exact files.
Readback contains 402 scripts, 178 globals, 43,180 syntax datums and 128 titles.
The cache log reports success and the fresh map is 702,328,832 bytes. Twenty-five
stock error diagnostics are retained; the tool exit code was not captured.

Nineteen native assertion observations cover brief ordinary stage-one play and
seeded, deathless checks of stages two through four for camera, auto-fire, actor
bounds and movement. Fresh geometry tests also pass as described above. This
does not prove a full ordinary 20-minute run, exhaustive geometry or native path
reachability, retail compatibility or installation/update/rollback. The original
production build and valid checkpoint were preserved and restored. No installed
package was promoted. Repeat the relevant native gates after candidate changes.

1. Install/extract the complete owned Halo 3 Editing Kit, configure its location, then
   check and run `fetch_progression_inputs.py`. It obtains canonical stock
   inputs from that kit, not old prepared intermediates. Explicit `--remote`
   can fetch from another owned kit over SSH. An isolated kit must retain the
   owned runtime/support files as well as tags: the current kit needs its `bin/`
   runtime files, FMOD libraries and `maps/fonts` data. Executables plus the tag
   archive alone failed to launch Sapien with a missing `XAudio2_9Redist.dll`.
2. Check and run `bootstrap_tags.py`. It authors the outdoor baseline directly
   from stock `020_base`, `070_waste` and the base chapter-title string list.
   Palette identities and sanitized templates preserve progression's expected
   indices. One AR starting profile replaces inherited private Needler profiles.
   Stock navigation is preserved before native processing. Native save/readback
   changes some firing-position bindings; revalidate the resulting candidate.
3. Reserve native ownership and use `native_workspace.py stage-bootstrap`
   against an isolated local kit on its host. Open the staged
   `tags/levels/survivors/last_stand/last_stand.scenario` in Sapien. Press
   **Ctrl+Shift+C**, review the fresh compiler diagnostics, then **Ctrl+S**.
   Verify the save completed and close Sapien. Then
   `native_workspace.py readback --kind bootstrap` copies the scenario into
   `outdoor-compiled.scenario`. Validate the actual navigation and bindings;
   the transfer does not certify compilation. See BOOTSTRAP for `--check`,
   configuration and explicit replacement examples.
4. Run `prepare_progression.py --check`, then `prepare_progression.py` with the
   same workspace/config. Preparation copies direct inputs to a private
   temporary workspace before authoring, rejects undeclared writes/input
   mutation, and builds an exact archive. Content/archive failures preserve
   previous outputs. Final files are replaced individually and
   `progression-build.json` is published last; this is not a crash-atomic batch.
   The receipt hashes actual loaded Python sources, owned inputs, outputs and
   archive members. Stale tags outside the declared set cannot enter the archive.
5. Use `native_workspace.py --replace stage-progression` to replace the staged
   baseline with the exact progression candidate, after a read-only check.
   Open the staged scenario in Sapien again, compile with **Ctrl+Shift+C**,
   review diagnostics, save with **Ctrl+S**, and close the tools
   and use `readback --kind progression`. Inspect compiled script/global/title
   counts and bindings before gameplay. An existing readback also requires
   explicit `--replace`; transfer receipts remain compilation-unverified.
6. Run gameplay and launcher QA in an isolated QA profile, then build a fresh
   cache from the kit working directory with
   `tool.exe build-cache-file "levels\survivors\last_stand\last_stand" pc none english`,
   using the established Steam Snap/Proton/private-prefix runtime on Onyx.
   Review errors as well as the success marker; retain the log, fresh map,
   hashes and tool exit code when available. These remain operator steps, not actions
   performed by the configured transfer helper. The LS-01 record demonstrates
   the fresh-kit milestone with bounded gameplay coverage; source checks alone
   cannot establish the remaining release gates or close other roadmap tasks.

The historical `onyx_progression.py`, `remote_build.py` and `promote_v03.py`
helpers are not the portable rebuild interface. The promotion helper retains
its historical filename while targeting v0.4.0; native promotion still requires
matching validation and cache evidence plus a coordinated session handoff.
Never reuse old receipts as proof of a changed build.

The installed launcher is `launch_v04.py`, deployed as the Onyx workspace's
`launch.py`. Checkpoints require matching engine, scenario, script and private
asset fingerprints. Changing the build can invalidate Continue compatibility.
The Git attributes preserve exact file bytes because release receipts include
content hashes.

For an isolated kit outside the usual Steam library layout, pass the Steam
installation root explicitly. It must contain `steamapps`; `--kit` alone cannot
identify the real runtime when the candidate is elsewhere:

```sh
python3 launch_v04.py --root /path/to/LastStand \
  --kit /path/to/isolated/H3EK --steam /path/to/Steam \
  --qa-profile /path/to/LastStand/qa-saves/ls01 --new
```

This explicitly launches the SDK game using the existing Linux/Steam Snap/Proton
environment and prepared private prefix. The QA profile must stay inside
`ROOT/qa-saves`. The new `--steam` override does not make the Linux launcher a
portable retail installer or alter checkpoint compatibility. Coordinate native
ownership before running it; stage/readback helpers themselves never launch it.

The existing native build is documented in the README. Retail MCC menu loading,
retail save support and a portable installation workflow remain unfinished;
see [ROADMAP.md](ROADMAP.md).

## Source archive

The isolated [Armory HUD probe](ARMORY_NATIVE_PROBE.md) documents the tested
private CHUD route, string routing, rendering limits and graph budget tools.
Its [native evidence](native-validation-ls05-ui-probe.json) records four
concurrent cinematic title slots and complete rendering of short training
messages. Long messages clipped; the exact limit is unresolved. These probe
tools retain the compiled baseline and do not implement or promote a live tree.
The combined source suite passed 359 tests with seven skipped entries; all 18
owned-input probe tests also passed separately. Native purchases, a fresh
compile/cache, retail and full-run validation were not performed for this probe.

`python -B bundle_source.py` creates an archive from an explicit source
allowlist, with a per-file hash manifest. An existing archive is preserved
unless `--force` is explicitly supplied. This archive is a source snapshot,
not the playable map. Historical v0.4 release receipts describe the tested
native build; repository documentation updates do not constitute a new build.
