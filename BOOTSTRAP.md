# Native bootstrap and input inventory

The supported authoring path now starts from three canonical stock scenario/UI
tags and the owned progression templates. Configured helpers fetch those inputs,
author a direct outdoor baseline, prepare progression in isolation, and transfer
exact manifests to a local editing kit. They do not automate native compilation
or establish a playable release. The complete fresh-kit native sequence remains
pending operator evidence in [LS-01](https://github.com/lEWFkRAD/halo3-survivors/issues/2).

Read [AGENTS.md](AGENTS.md) before staging or compiling. Reserve the native slot,
identify the current game/session owner, and preserve its build and checkpoint.
Use an isolated kit and QA profile. The helpers never stop an existing session,
launch SDK tools, change saves or `init.txt`, or promote an installed package.

## Configuration and check semantics

Use `last-stand.local.json`, an explicit `--config FILE`, or `LAST_STAND_CONFIG`.
Set `editing_kit` to an owned H3EK installation with its stock tags extracted
under `tags/`. `--root PATH` selects the input/output workspace; it does not
select a different Python implementation. See [DEVELOPMENT.md](DEVELOPMENT.md)
for configuration precedence and the optional native binding.

Keep the complete owned SDK runtime and support files when preparing an isolated
kit. Copying only the three executables and extracting the tag archive is not
enough to run Sapien. The current kit also needs its owned `bin/` runtime files,
FMOD libraries and `maps/fonts` support data. The fresh baseline experiment
initially failed on missing `XAudio2_9Redist.dll` until the owned runtime/support
files were restored. The preflight inventories selected prerequisites; it does
not certify that every runtime dependency is installed.

| Check | What it reads | What success establishes |
| --- | --- | --- |
| `preflight.py --stage source` | Authored source inventory | Required source files exist |
| `fetch_progression_inputs.py --check` | Stock input sizes/types and output paths | Declared fetch inputs are present and destinations are safe |
| `preflight.py --stage bootstrap` | Three fetched stock inputs, binding discovery, output paths | Bootstrap prerequisites are present |
| `bootstrap_tags.py --check` | Owned tags through `blam_tags`; authors output in memory | Templates, palette identities and byte round trips pass without writing outputs |
| `prepare_progression.py --check --json` | Direct preparation inputs, binding discovery, output paths | Preparation prerequisites pass; authoring modules are not imported |
| `native_workspace.py --check stage-bootstrap` / `stage-progression` | Exact manifests/files and local native processes | Candidate bytes and transfer destinations pass before staging |
| `native_workspace.py --check readback --kind bootstrap` / `progression` | Kit scenario, destination and local native processes | Readback bytes can be copied; compilation is not verified |
| `preflight.py --stage native` | Configured kit tools and selected staged files | A selected native prerequisite inventory is present |

These checks write no outputs. `preflight.py --remote --json` uses only a
standard-library file-stat probe on the configured SSH host. Fetch `--remote
--check` similarly checks remote stock inputs without transferring tag bytes.
SSH requires an already trusted host key and noninteractive authentication;
paths travel as JSON data, not shell-interpreted copy arguments.

Exit 0 means the requested operation/check succeeded; 2 means blocked/error.
Preflight and fetch support `--json`; preparation supports it with `--check`.
Bootstrap and native-workspace commands always print JSON on success.
Presence, hashes, headers and parser round trips do not prove dependency closure,
native compilation, gameplay, retail MCC support or save compatibility.

## Fetch canonical owned inputs

From a workspace with a configured local kit:

```sh
python -B fetch_progression_inputs.py --config last-stand.local.json --check --json
python -B fetch_progression_inputs.py --config last-stand.local.json
```

Explicitly add `--remote` to both commands to read the configured remote kit.
Omitting `editing_kit` does not implicitly contact Onyx. Remote fetching needs
only Python's standard library and SSH; fetching never imports `blam_tags`.

The exact 21-tag inventory is declared in `fetch_progression_inputs.py`. Its
three baseline inputs are:

| Canonical path under the kit's `tags/` | Fetched workspace path |
| --- | --- |
| `levels/solo/020_base/020_base.scenario` | `private-inputs/bootstrap/020_base.scenario` |
| `levels/solo/070_waste/070_waste.scenario` | `private-inputs/bootstrap/070_waste.scenario` |
| `ui/chapter_titles/020_base.multilingual_unicode_string_list` | `private-inputs/bootstrap/020_base.multilingual_unicode_string_list` |

The other 18 tags go to `private-inputs/v3/`: six damage templates, six effect
templates, the energy-blade weapon, infection/carrier characters, carrier biped,
watchtower machine and gravlift light. The sword damage source is the canonical
`objects/weapons/damage_effects/dash_melee.damage_effect`; the weapon is retained
as supporting provenance. Source mappings are explicit, including the stock
Battle Rifle impact used for the Assault Rifle's cosmetic effect.

Fetching checks all required inputs and output paths before staging. It validates
tag kinds/headers and SHA-256 hashes before publishing only declared outputs.
Missing, changed, corrupt or failed remote transfers preserve previous fetched
data. Ordinary publication errors roll back; a rollback failure retains recovery
files at the path reported in the error. Publication is not crash-atomic across
the whole set. Unrelated files remain untouched.

`private-inputs/bootstrap/sources.json` and `private-inputs/v3/sources.json`
record source paths, origin, byte sizes and hashes. The v3 manifest also retains
its legacy `damage`, `effects`, `characters` and `support` mappings.
`private-inputs/v3/character-paths.json` retains the character-ID to native-tag-path
mapping consumed by progression authoring. These owned files stay local.

## Author the direct outdoor baseline

```sh
python -B preflight.py --stage bootstrap --config last-stand.local.json
python -B bootstrap_tags.py --config last-stand.local.json --check
python -B bootstrap_tags.py --config last-stand.local.json
```

The baseline preserves stock `070_waste` geometry, lighting, scenery, machines,
navigation and PVS. It selects the outdoor `bsp_000` zone set by identity and BSP
mask. Character/weapon palettes and sanitized objective/squad templates come
from stock `020_base`, with explicit identity checks for progression's palette
indices. It creates one Master Chief spawn, one AR `sv_start` profile, one title,
and a minimal bootstrap script. It ignores old prepared intermediate files and
does not inherit the three private Needler profiles or upgrade beacons.

Exact authored outputs are:

- `native-tags/levels/survivors/last_stand/bootstrap.scenario`
- `native-tags/levels/survivors/last_stand/bootstrap.hsc`
- `native-tags/ui/survivors/last_stand.multilingual_unicode_string_list`
- `native-tags/levels/survivors/last_stand/bootstrap-manifest.json`

The manifest records exact input/output hashes and the selected stock navigation
point. All tags parse and round-trip before publication. Publication stages all
four files and restores prior bytes on ordinary replacement failures; this is
not a crash-atomic batch. `--check` renders the same report without creating
outputs or staging directories.

Stock navigation differs from the historical `outdoor-compiled.scenario` at some
firing positions and bindings. Source preservation does not explain that delta.
The fresh baseline native save/readback also changed firing-position bindings
and still differed from the historical prepared navigation. Do not label the two
baselines equivalent. Navigation/spawn validation on the final progression
candidate remains mandatory.

## Stage, compile and read back

`native_workspace.py` operates on a **local** configured `editing_kit`. Run it
on the kit host with the source workspace, owned candidate files and matching
manifests present. Remote fetch settings do not turn staging into an SSH command.
This helper needs no tag binding and provides no native compiler automation.

For a fresh, isolated destination:

```sh
python -B native_workspace.py --config last-stand.local.json --check stage-bootstrap
python -B native_workspace.py --config last-stand.local.json stage-bootstrap
```

Staging validates the manifest against input/output bytes, then copies the
scenario to `tags/levels/survivors/last_stand/last_stand.scenario`, HSC to
`data/levels/survivors/last_stand/scripts/last_stand.hsc`, and only the declared
UI/private tags to their kit paths. It rejects existing destinations by default.
`--replace` explicitly permits replacement after backing up the previous set
under workspace `backups/native-workspace-<operation-id>/`.

The operator must compile and save with the owned native tools, inspect fresh
diagnostics, and close the tools before readback:

```sh
python -B native_workspace.py --config last-stand.local.json --check readback --kind bootstrap
python -B native_workspace.py --config last-stand.local.json readback --kind bootstrap
```

Bootstrap readback writes `native-tags/levels/survivors/last_stand/outdoor-compiled.scenario`.
It only copies bytes: every transfer receipt explicitly records
`native_compilation_verified: false`. A filename ending in `compiled` is not
compilation evidence. Retain the separate native save/readback results and
navigation/binding checks before preparing progression.

Native-workspace receipts are stored at `native-workspace/<operation-id>.json`.
Stage/readback include a conservative host-wide native-process check and refuse
when a relevant process is active or the check is unresolved. This snapshot is
not an ownership lock; the issue reservation and session handoff remain required.
No command automatically stops a process, starts a tool, edits a save or publishes
a package. Existing readback files also require explicit `--replace`.

## Prepare the progression candidate

These 18 direct files are required before preparation starts:

| Input | Use |
| --- | --- |
| `native-tags/levels/survivors/last_stand/outdoor-compiled.scenario` | Native baseline readback with outdoor navigation and sanitized templates |
| `native-tags/ui/survivors/last_stand.multilingual_unicode_string_list` | Baseline string-list template |
| `private-inputs/v3/carrier.character` | Carrier character template |
| `private-inputs/v3/floodcarrier.biped` | Carrier body; automatic death children are removed during authoring |
| `private-inputs/v3/watchtower_base.device_machine` | Watchtower machine template |
| `private-inputs/v3/watchtower_gravlift.light` | Gravlift light template |
| `private-inputs/v3/<weapon>.damage_effect` (six) | Damage templates |
| `private-inputs/v3/<weapon>.effect` (six) | Cosmetic impact templates |

Weapon IDs are `needler`, `assault_rifle`, `shotgun`, `plasma_rifle`,
`rocket_launcher` and `energy_sword`. `source/` must exist. Optional
`private-inputs/v3/character-paths.json` is copied into the isolated input snapshot
when present. `infection.character`, `energy_blade.weapon` and fetch provenance
files are not direct preparation prerequisites.

```sh
python -B prepare_progression.py --config last-stand.local.json --check --json
python -B prepare_progression.py --config last-stand.local.json
```

Preparation imports the authors before writing, copies exact owned inputs to a
temporary workspace, and runs scenario, HSC, damage/effect and UI authors there.
It checks the exact returned outputs and rejects undeclared files or changes to
the input snapshot. Authoring/archive failures leave previous outputs untouched.
Publication uses individual atomic replacements, not an atomic batch; the build
manifest is published last. Consumers must validate its hashes before staging.

Outputs include progression and progression-UI scenarios, declared private tags
under `native-tags/objects/survivors/v3/`, the progression UI string list,
`progression-layout.json`, `progression-contract.json`, `source/progression.hsc`,
`v3-native.tar` and `progression-build.json`. The manifest records exact input,
loaded-source and output hashes, plus the archive hash and member list. Existing
stale private tags stay on disk but cannot enter this archive or receipt.

Stage this candidate with `native_workspace.py --replace stage-progression`
(run the same command with `--check` first). It validates the authored manifest,
source hashes and exact archive contents. After the operator's final native
compile/save and tool shutdown, `native_workspace.py readback --kind progression`
copies the result to `native-tags/levels/survivors/last_stand/compiled-progression.scenario`.
Use the same `--config`/`--root` settings and explicit `--replace` for an existing
destination. Readback still reports compilation as unverified.

Fresh compiler diagnostics, script/global/title readback, dependency-resolving
cache creation, isolated gameplay/launcher checks and a cache receipt remain
separate native gates. A source archive or transfer receipt cannot substitute
for those observations. Retail installation/update/rollback is also unfinished.

## Historical helpers

`author_hangar.py`, `polish_native.py`, `birds_eye.py` and `outdoors.py` describe
the earlier hangar-to-outdoor experiment. Its `compiled.scenario`,
`birdbase.scenario` and `hangar-overhead.scenario` intermediates are historical
private exports, not prerequisites for the direct bootstrap. Some legacy scripts
execute work on import or select stale backups by existence.

Legacy remote build, launch, promotion and QA scripts are operator-specific
historical tools. Do not run them as a portable installer or infer that they
consume the new configuration. The supported configured fetch/bootstrap/prepare/
transfer path above replaces the old authoring chain; native compilation and
release evidence must still be collected for its exact candidate. LS-01 remains
open until that fresh-kit sequence and the remaining configuration scope are
verified.
