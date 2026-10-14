# Live Armory integration

The LS-05 candidate replaces static branch-reference pages with compact graphs
whose ranks and state markers update from the run. It covers all 50 catalog
nodes. LS-05 remains open: presentation work and broader validation are still
required. [The native receipt](native-validation-ls05-live.json) separates the
behavioral candidate from the final presentation candidate and records their
bounded evidence.

## Implemented model

[armory_live.py](armory_live.py) enumerates 601 reachable display snapshots plus
an explicit unavailable-state fallback. Nine pages keep prerequisite-related
nodes together: six seven-node weapon trees, followed by Vitality/Armor/Shield,
Aegis/Cycle, and Reach/Insight/Scholar. Page selection follows the selected
skill. Compact text shows branches; the separate objective HUD panel gives
selected-skill details, including prerequisite rank requirements.

Each label ends with its current rank and a marker:

| Marker | Meaning |
| --- | --- |
| `-` | Rank zero; a prerequisite, stage, exclusive branch or point requirement blocks purchase. |
| `+` | Rank zero; the first rank is currently purchasable. |
| `o` | Purchased, with more ranks remaining. |
| `*` | Maximum rank reached. |

For example, `Power2o` means rank two with another rank remaining. An `o` does
not promise that the next rank is affordable. The separate selected-skill
display gives the next cost or MAX RANK, while the wallet shows current points.
Existing purchase guards remain authoritative.

The graph uses the training-text channel, with CRLF line breaks and an authored
110-character guard. This is a layout rule, not a proven engine text limit.
Wallet and next-cost titles refresh alongside the graph at most once per 30
simulation ticks, and again at the 15-tick midpoint of that cycle (source
follow-up, native-pending): their authored lifetime is 0.95 seconds, just under
the 30-tick cycle, so a cycle-only refresh let them briefly expire while the
Armory stayed open. The midpoint refresh touches wallet/price only; the graph
throttle, the sub-second title expiry after Resume and the saved-clock range
are unchanged. Input runs before refresh, so Resume suppresses a due update;
close/reopen preserves the refresh limit. Invalid state keys select the fallback
instead of leaving an old graph visible. Held-input purchase latches and
exact-build Continue behavior remain part of the integration contract.

The selected skill's CHUD detail starts with an explicit `> ` marker, and the
controls title explains it. That is the bounded selected-node indication: an
in-graph highlight would need one training-text snapshot per (state,
selection) pair, expanding 601 snapshots to 3,848, and each snapshot costs an
authored script/global reference in the dispatch, which would push the
9,471-reference estimate far past the 9,500 guard and the native 10,240-record
table that crashed the first live candidate.

## Compiler budget and failure

The first full candidate crashed during script compilation despite staying
below the script/global/syntax authoring limits. The failure named an allocation
at `hs_compile.cpp:473`, checked at line 516, with a 245,760-byte buffer overrun.

Static inspection of the owned Jan. 3, 2024 x64 Sapien binary identifies a
separate script/global-reference table. Allocation call `0x1406568b2` supplies
that size; writer `0x140655d60` appends 24-byte records and links them into
per-script or per-global lists. Embedded assertions name the referring and
referred script/global indexes. These observations establish 10,240 records for
this binary's table; the allocation size alone would not establish its purpose.
The writer has no capacity check before its append. This is separate from the
syntax-datum budget and is not a universal limit for other engine builds.

[progression_hsc.py](progression_hsc.py) now checks authored symbol occurrences
in `HSC.render()`, with a conservative maximum of 9,500. It excludes declaration
headers, comments, strings and scoped script parameters. Engine-injected source
and compiler behavior can change the native total, so this estimate does not
claim an exact count of allocated records.

The working baseline estimated 9,215 references; the failed candidate estimated
11,182. Sharing the repeated target-selection predicate and removing a graph
temporary reduced the regenerated candidate to **9,471**. A smaller control
compiled before the full candidate was retried. The final candidate compiled
with **495 scripts, 180 globals, 51,074 syntax datums and 127 title definitions**.

## Bounded evidence and remaining work

The first full behavioral checks bind source `306c772601c85522eeb1e4c2a362d5984b2c532c`
and compiled scenario SHA256
`4336e302d15c386119ca16e19e362cbfa7284dd9337277d5665af02109de99a2`.
The owner source suite recorded 414 entries: **405 passed and nine skipped**.
Private logs and captures remain local; their checksums and outcomes are
summarized in the public receipt. Owned tags, maps and player saves are not
distributed with this source.

The native operator inspected complete captures of all nine pages. Ordinary
purchase input reached Needler Power rank two with one point remaining, and a
held purchase did not buy again. Combat gained XP and reached another level.
A process restart through Continue retained rank two, two points, actors and
run progress in the isolated QA profile.

Seeded branch testing initially expected a stage-four capstone at stage three,
producing two failed assertions. Preserve those failures as incorrect test
expectations. Corrected assertions confirmed the stage-three rejection and the
stage-four purchase, with 43 points remaining afterward. Seeded checks do not
establish ordinary progression or balance.

The final presentation candidate is
`a1b8933c19fd34b5ff60e5de26d6577a1f746869`, scenario SHA256
`74a90adc462a05b07e752082fe7b1f48a188b9428da911649506a9c3bf62054e`.
It retains the same native counts and HSC. The training panel uses an opaque
black solid shader, with white graph, wallet and next-price text. Native captures
show readable text, a real held-click purchase buying one rank, and no Armory
panel/graph/wallet at two and seven seconds after Resume. Reopening and a full
process Continue restore the display. Seven fresh ordinary-run assertions pass,
covering the purchased rank, combat progress, reopened menu, actor cap and
Continue state. The final Continue retains Needler Power rank one and three
points after an ordinary level-up.

In that candidate, wallet and price text could briefly disappear between
refreshes; continuous visibility was not established. A later source follow-up
adds the 15-tick midpoint wallet/price refresh and the `> ` selected-detail
marker described above; both are native-pending and do not change this
candidate's evidence. Selected details can be long, and the compact
graph does not visually highlight the selected node (see the snapshot/reference
accounting above for why). Readability across every
node, resolution and stage needs further work. Broader purchase, death/victory,
full-run and retail acceptance remain open. Use the isolated QA profile and
native ownership rules in [AGENTS.md](AGENTS.md). Changed tag fingerprints make
older-build saves incompatible. The installed v0.4 package and its original
checkpoint are preserved; this candidate is not a release promotion or
completion of LS-05.

The native cache tool returned 0 and emitted its success marker for a fresh
701,202,432-byte map. Its log retains 25 stock-asset error diagnostic lines.
Snap returned 1 during wrapper cleanup after the native result was recorded.
This proves a cache was built; gameplay observations above use SDK tag test,
and neither cache gameplay nor retail loading is established. The original
production Continue was restored with all 24 prior profile files unchanged
and two normal launcher-session files added.
