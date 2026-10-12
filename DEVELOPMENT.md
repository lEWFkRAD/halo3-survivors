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
Halo 3 Editing Kit. Remote helpers currently contain that workspace's paths
and the `onyx-linux` SSH alias. Read and adapt them before using another setup.

## Source tests

Tested with CPython 3.14.6. From the repository root:

```sh
python -B -m unittest discover -s tests -v
```

A source-only export passes 104 tests and reports one skipped module. That
module contains five spawn-geometry tests requiring the external `blam_tags`
binding; its owned-navigation test also needs the local scenario asset. The
complete owner workspace passed all 109 tests for v0.4.0. No third-party Python
package is required for the 104 source-only checks.

The test VM exercises the emitted HaloScript subset. It is not a Halo compiler
or a replacement for engine play testing. Native test evidence is recorded in
`native-validation-v04.json`, including which checks preceded the final narrow
victory fix.

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
2. Review the helper paths and run `prepare_progression.py` in that prepared
   workspace. It authors progression tags, HaloScript, damage effects and UI
   titles. It does not compile a playable map.
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
