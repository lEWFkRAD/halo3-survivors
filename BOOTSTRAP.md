# Native bootstrap status and input inventory

The source checkout supports source tests and read-only prerequisite checks.
Progression authoring still needs an owned, prepared outdoor baseline. A fresh
H3EK installation cannot yet reproduce that baseline using a verified sequence
in this repository. This is the remaining work in
[LS-01](https://github.com/lEWFkRAD/halo3-survivors/issues/2).

Do not run the historical helpers in sequence assuming that they form an
installer. Some execute native operations when imported. Follow the native
ownership rules in [AGENTS.md](AGENTS.md) before staging or compiling anything.

## Read-only checks

Run from the checkout, without staging files or opening Halo:

```sh
python -B preflight.py --stage source
python -B prepare_progression.py --check --json
python -B preflight.py --stage native --tools /path/to/H3EK
python -B preflight.py --remote --json
```

Source checks need no game assets or native binding. Authoring checks report
every missing direct input, discover `blam_tags`, and check output paths before
any authoring module is imported. Native checks inspect the configured editing
kit and selected staged files. The remote check sends only a standard-library
file-stat probe over SSH; it does not copy files, import project helpers,
compile, launch, control a window or alter a save. SSH requires an existing
trusted host key and noninteractive authentication; it does not accept a new
host key automatically.

Exit code 0 means the requested prerequisite checks passed; 2 means blocked
or an invalid configuration/probe. `--json` produces a schema-versioned report
with per-path status and limitations. READY does **not** establish that tag
contents are valid, all referenced dependencies exist, native compilation
succeeds, retail MCC works, or gameplay is correct. See
[DEVELOPMENT.md](DEVELOPMENT.md) for configuration and binding installation.

## Direct inputs for progression authoring

All paths below are relative to the checkout. These 18 files are mandatory
before `prepare_progression.py` writes anything:

| Input | Use |
| --- | --- |
| `native-tags/levels/survivors/last_stand/outdoor-compiled.scenario` | Prepared outdoor scenario with compiled navigation and inherited palettes |
| `native-tags/ui/survivors/last_stand.multilingual_unicode_string_list` | Base native string-list template |
| `private-inputs/v3/carrier.character` | Private carrier character |
| `private-inputs/v3/floodcarrier.biped` | Carrier body with automatic children disabled during authoring |
| `private-inputs/v3/watchtower_base.device_machine` | Private watchtower machine |
| `private-inputs/v3/watchtower_gravlift.light` | Private gravlift light |
| `private-inputs/v3/<weapon>.damage_effect` (six files) | Per-weapon damage templates |
| `private-inputs/v3/<weapon>.effect` (six files) | Cosmetic impact templates |

The six weapon names are `needler`, `assault_rifle`, `shotgun`, `plasma_rifle`,
`rocket_launcher` and `energy_sword`. Every effect is required because the
generated HaloScript references every impact tag. Checking damage templates
alone could otherwise produce a partial candidate with missing effects.
The checkout's `source/` directory must also exist: the HSC generator writes
into it without creating it. Preflight reports a missing output parent as unsafe.

`private-inputs/v3/character-paths.json` is optional metadata read by the tag
author; absent metadata uses the stock infection/carrier references. If present,
its contents must be valid JSON. `sources.json` records fetch provenance.
`infection.character` and `energy_blade.weapon` are fetch-time inputs/evidence,
not direct preparation prerequisites. The sword damage template originates
from `objects/weapons/damage_effects/dash_melee.damage_effect` in the current
owned kit. The fetcher still needs path adaptation and an operator review.

The preflight checks presence and file types, not native tag contents or
optional metadata validity. Preparation imports all authoring modules before
the first write, catching binding-load failures early. Later authoring/content
errors can still leave partial generated outputs; preparation is not a
transaction and does not roll back a failed run.

## Outputs and inherited native dependencies

Preparation runs tag authoring, script generation, damage authoring and UI
authoring, in that order. It creates or replaces:

- `native-tags/levels/survivors/last_stand/progression.scenario`
- `native-tags/levels/survivors/last_stand/progression-ui.scenario`
- Private carrier, watchtower, damage and impact tags under
  `native-tags/objects/survivors/v3/`
- `native-tags/ui/survivors/progression.multilingual_unicode_string_list`
- `progression-layout.json`, `progression-contract.json`, `source/progression.hsc`
- `v3-native.tar`

Generated layout/contract files are outputs, not required seed inputs. Existing
output links, linked parents, wrong path types and non-file children in the
flat private-tag directory block preparation. The archive still includes all
files already in that private-tag directory; pruning stale tags and producing
an exact output manifest remain bootstrap work.

The archive does not contain the inherited
`objects/survivors/needler_1.weapon` through `needler_3.weapon`, which the native
profiles reference. They exist in the current owned kit. Native preflight
checks them, the staged scenario/HSC/UI, six private impact tags, SDK programs
and tags/data directories. This is a selected prerequisite inventory, not a
complete dependency closure for the scenario or damage/effect references.

## Historical baseline sequence and unresolved steps

The early authoring sources refer to these additional owned inputs:

- `private-inputs/tags/levels/solo/020_base/020_base.scenario`
- `private-inputs/titles.multilingual_unicode_string_list`
- `private-inputs/needler.weapon`
- `private-inputs/070_waste.scenario`
- Legacy `private-inputs/auto_damage.damage_effect` and `private-inputs/impact.effect`

The historical sequence was hangar authoring, native compilation/readback,
native polishing, another saved scenario, overhead-camera authoring, outdoor
conversion, another compilation/readback, and progression authoring. It is
**an inventory of dependencies, not a tested rebuild recipe**:

1. `author_hangar.py` produces a hangar scenario, base strings and the three
   inherited Needler weapon tags.
2. `polish_native.py` expects `compiled.scenario`; no checked-in command
   produces that baseline from the current sources.
3. `birds_eye.py` expects `birdbase.scenario`; its native round trip is likewise
   undocumented. It produces the overhead grid and camera bindings.
4. `outdoors.py` combines the hangar baseline and `070_waste.scenario`. It
   reuses `hangar-overhead.scenario` if that backup already exists, which can
   silently preserve an old input.
5. Progression expects `outdoor-compiled.scenario`; its creation also requires
   an explicit, verified native save/readback step.
6. The v3 fetcher obtains private progression templates from the owned kit;
   `prepare_progression.py` authors the final candidate from the prepared set.

Current `generate.py` already references beacon, overhead and camera-grid
bindings that the initial hangar author does not create. Replaying the old
scripts against a fresh kit therefore cannot be presented as a reliable first
compile. The initial generic string and legacy damage/effect template fetch
steps also need explicit provenance.

LS-01 remains open until the baseline sequence is redesigned or recovered,
all helper paths are configurable, the complete required dependency set is
staged, and a fresh owned kit produces a natively verified cache. Retain input
provenance, exact commands and readback/build evidence for that experiment.
