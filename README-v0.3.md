# Last Stand v0.3.0 release notes

**Built, native-tested and promoted on Onyx-Linux on 2026-10-12.**
[README.md](README.md) is the authoritative gameplay guide, controls and release
record. The local MCC package is v0.3.0; retail MCC loading remains unverified
pending owner Xbox/Microsoft sign-in and menu testing.

Implemented: 50 skill nodes, six instant automatic weapons, four outdoor
stages, a bird's-eye camera, and purchased ranks/XP/unspent points carried
between stages of the same run. Cross-run saves and vehicles remain future
work.

Controls: WASD moves; weapons fire automatically. In the Armory, Space selects
next, Q selects previous, LMB buys, 1 resumes, and Space+Q changes category.
Space+Q also reopens the Armory during combat. Release buttons between actions.
Movement remains available while enemies, automatic attacks and progression
pause in the Armory.

**65 deterministic tests pass.** Native checks passed for all eight menu
assertions, 22 stage assertions and six weapons. The latest clock check
advanced 10 script seconds over 11.058 wall seconds, including console
transitions; the 30-tick clock is retained.

The final terminal victory passed native checks: the result stays in the
scenario, enemies clear, the player is protected, and gameplay/movement stop.
The victory remained visible with frozen stage time and shots after six
seconds. Close and relaunch for another run. This avoids the SDK main-menu
unload failure.

The [native validation record](native-validation-v03.json) includes
`qa_provenance`: gameplay checks preceded the limited terminal-victory change;
[victory-fix.diff](victory-fix.diff) documents its scope. The final compile,
clean boot/UI and terminal victory were retested after that change. This is
not a claim that every earlier gameplay check was rerun or that full-run
balance is exhaustive.

The promoted map is **704221184 bytes**, SHA-256
`3b6ff9a73d39761814f177091be80df609098f0a1a3dea9624235d6ee40e3b49`.
See [build receipt](cache-build-receipt-v03.json),
[promotion receipt](promotion-v03.json) and
[installed build metadata](build-result-v03.json). The prior package is saved
under `backups/package-before-v03-20261012T172742Z-09c32ad4` in the Onyx
workspace; package GUIDs and registration were retained.

`bundle_source.py` produces the source ZIP described in the main README,
including final receipts and the validation diff. It does not bundle native
maps, screenshots/videos or owned game assets. The earlier outdoor preview
shows v0.2; no new gameplay-clip delivery is claimed here.
