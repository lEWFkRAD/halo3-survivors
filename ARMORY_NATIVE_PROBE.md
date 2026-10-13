# Armory HUD feasibility probe

LS-05 is still open. These tools reproduce a bounded SDK experiment; they do
not replace the playable Armory or implement a live graphical tree. The exact
candidate hashes, visual observations and restoration checks are in
[the probe receipt](native-validation-ls05-ui-probe.json).

## Findings

- Four cinematic titles could display concurrently. The fifth and later calls
  reported `no free chapter title slots`. The 128-definition authoring budget
  therefore does not permit one live title per graph node.
- A scenario player-representation override can activate a private biped and
  CHUD when scenario flag bit 4 is set. Its schema label is `override globals!`;
  the binding accepts the cleaned name `override globals`.
- Custom training strings worked after the three CHUD global skins referenced
  the appended private HUD message table. The scenario's title table alone did
  not supply those strings. Training and selected-objective text coexisted.
- Long graph messages clipped. All twelve short numbered lines (94 characters)
  and a compact four-state sample (75 characters) rendered completely. The
  unwrapped ruler extended off-screen, so an exact character/glyph limit remains
  unresolved. Do not infer a four-line or 128-character engine limit.
- `hud_show_training_text false` allowed a stock tutorial prompt to return;
  `hud_enable_training false` hid the panel. The normal repair loop already
  disables training, so a future integration must coordinate its lifetime.

The enlarged panel remains translucent and needs contrast/layout work. The
sample states and wallet are fixtures, not live game values. This experiment
retained compiled LS-01 script blocks; it did not perform a fresh HSC compile,
cache build, purchase test, retail test or complete run.

## Author a private candidate

Use your own stock tags and an existing compiled progression baseline. The
binding and stock-input setup are described in [BOOTSTRAP.md](BOOTSTRAP.md).
This example uses PowerShell variables for your actual paths:

```powershell
python -B armory_native_probe.py `
  --scenario "$compiledScenario" --ui "$progressionUi" `
  --biped "$stockBiped" --chud "$stockChud" `
  --chud-globals "$stockChudGlobals" --hud-messages "$stockHudMessages" `
  --globals "$stockGlobals" --binding-dir "$bindingDirectory" `
  --output-dir "$newProbeDirectory" --override-globals
```

Stock templates are `objects/characters/masterchief/masterchief.biped`,
`ui/chud/spartan.chud_definition`, `ui/chud/globals.chud_globals_definition`,
`ui/hud/hud_messages.multilingual_unicode_string_list` and
`globals/globals.globals`. The scenario must be solo with no existing player
representation overrides. The UI input must be the progression title table.
Omitting `--override-globals` authors the negative-control variant.

The import-safe author writes six tags and `armory-probe.json` into a new or
empty directory. It preserves input files, stock message bytes and offsets,
validates tag roles and roundtrips, and records exact native destinations and
hashes. Failed authoring publishes no partial candidate. No native operation
or installed-game mutation is performed. The CHUD globals destination replaces
a stock tag in an isolated kit and must be backed up by its operator.

Follow [AGENTS.md](AGENTS.md) and reserve the native slot before staging. These
probe outputs are deliberately outside `prepare_progression.py`'s production
output allowlist; do not weaken that allowlist or promote the probe. Never use
the production save/profile. Verify the console prompt before sending commands.
With the isolated candidate loaded, suspend the repair loop for the experiment:

```lisp
(set sv_running false)
(hud_enable_training true)
(hud_set_training_text sv_armory_lines)
(hud_show_training_text true)
(cinematic_set_chud_objective sv_node_0)
```

Available fixture IDs: `sv_armory_probe`, `sv_armory_owned`,
`sv_armory_wallet`, `sv_armory_lines`, `sv_armory_compact`, `sv_armory_ruler`.
Close the console to observe native simulation/render updates. Record the exact
candidate, message, visible END/line markers and any clipping. Disable training
and end the isolated session afterward; restore the preserved original session.
These console actions do not prove ordinary Armory interaction or recovery.

## Budget the next implementation

```sh
python -B armory_graph_budget.py --output graph-budget.json
```

The tool enumerates catalog-guard-reachable rank tuples and deduplicates visible
states. It writes only the explicitly requested report; otherwise JSON goes to
stdout. `--native-baseline` defaults to 402 as an estimate input, not a fresh
compiler measurement. It does not model whether timed encounters supply enough
XP to obtain every rank.

| Pages | Four-state snapshots | Estimated scripts with ten-case leaves |
| --- | ---: | ---: |
| Original seven | 10,482 | 1,578 |
| Six weapons plus two support pages | 966 | 524 |
| Six weapons plus three support pages | 601 | 486 |
| Six weapons plus four support pages | 581 | 484 |

All layouts retain all 50 nodes and their prerequisite edges. The eight-page
option groups five defense nodes and three reach/XP nodes. Focus, wallet and
selected-skill explanations are separate and are not multiplied into these
counts. Purchased-node affordability remains a selected-detail concern in the
four-state scheme. This is sizing evidence, not proof that a complete graph
fits the tested text channel.

Next: compose readable labels/connections with compact live states, prove one
weapon and a support prerequisite with a real purchase, then extend to all 50
nodes and recheck held inputs, Resume and Continue. Preserve the current playable
Armory until that candidate passes its native checks.
