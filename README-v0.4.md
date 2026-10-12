# Last Stand v0.4.0

Built, native-tested and installed on Onyx-Linux on 2026-10-12 at 18:36 UTC.
109 deterministic tests pass. See README.md and the v0.4 release receipts.

This update adds native Armory checkpoints and a Continue/New Run launcher,
closer outdoor enemy spawns, and a single Armory visit for multiple level-ups
earned together. The existing 50-node tree, six automatic weapons and four
outdoor stages remain the core of the mode.

## Save and continue

The desktop shortcut uses the owned Halo 3 SDK engine. Entering the Armory or
buying an upgrade requests a complete native checkpoint. Give it about three
seconds before quitting. Reopening the Armory with Space + Q checkpoints your
current run; quitting during combat returns to the most recent Armory visit.
Continue restores the stage, clock, XP, ranks, points, enemies and encounter
state. The bird's-eye camera and paused Armory controls reapply after loading.

The launcher offers Continue, New Run and Cancel when a valid checkpoint exists.
New Run archives the previous save. Saves live under `saves/v04` in the Onyx
workspace; earlier generations are preserved. A checksum and exact
engine/scenario/source/private-asset fingerprint prevent silently loading
damaged or incompatible saves. A changed build may require a new run.

This is same-run resume. Permanent unlocks across separate runs are still
future work. The SDK save launcher does not establish retail MCC save support.

## Combat and controls

Move with WASD; unlocked weapons fire automatically. Space selects the next
skill, Q selects the previous skill, left mouse buys, Space + Q changes weapon
category, and 1 resumes. Release buttons between actions. Space + Q reopens the
Armory during combat.

Most enemy groups now spawn 5.5–8 map units from each arena center, using valid
navigation locations. Snipers and heavy groups retain more distance. A group
waits if the player is within two units of any of its spawn points; other
groups can still appear. The 36-enemy cap and timed introductions remain.

XP bursts award all affordable levels in one Armory visit and preserve the XP
remainder. The point wallet still caps at 50. Purchased ranks continue across
all four five-minute stages.

Automatic attacks use immediate damage pulses with weapon-specific effects,
range, cadence and target counts. Travelling projectiles, vehicles, physical XP
pickups, a graphical tree and exhaustive run balancing remain future work.
Retail MCC loading still requires owner Xbox/Microsoft sign-in and verification.

## Development and QA

`launch_v04.py` is installed as the workspace's `launch.py`.
It holds the existing launcher lock, preserves `init.txt`, archives stale
pending saves, and atomically commits stable checkpoints. Native QA uses
`--qa-profile ROOT/qa-saves/native-v04`, separate from the player's profile.
QA launches outside this wrapper never commit checkpoints to a profile.

Run deterministic checks with `python -B -m unittest discover -s tests`.
`qa_v04.py` records native assertions separately under `qa-v04`. The existing
`promote_v03.py` filename is retained, but its current version and required
release checks target v0.4.0, including restart, spawn clearance and batched XP.
