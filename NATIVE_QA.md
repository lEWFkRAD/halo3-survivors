# Native assertion evidence

`native_qa.py` reads evidence without launching Halo, sending input, changing a
profile or writing files. The native operator still reserves the shared slot,
preserves the current session, selects an isolated QA profile and confirms the
console is open before dispatch. See [AGENTS.md](AGENTS.md).

Create a fresh assertion and capture the log position **before** entering its
command. After the command and a bounded observation window, evaluate the same
log. One complete emitted marker is required. The command echo contains both
possible outcomes and is never evidence of either outcome.

```python
from pathlib import Path
from native_qa import (
    EvidenceContext, capture_cursor, evaluate, halo_sdk_payload,
    new_assertion, read_window,
)

# The operator supplies and verifies these against the running candidate.
context = EvidenceContext(
    source_commit=full_commit,
    candidate_fingerprint=actual_fingerprint,
    profile="qa-saves/my-test", environment="sdk",
    run_kind="seeded", evidence_kind="native",
)
assertion = new_assertion("(= sv_stage 2)")
cursor = capture_cursor(Path(actual_runtime_log))
# Dispatch assertion.command in the verified native console, then allow the
# independently verified transport to flush. No input is sent by this module.
result = evaluate(assertion, read_window(cursor), context,
                  decode_line=halo_sdk_payload)
```

The observed H3 SDK writes `log_print` messages into its runtime
`reports/reports_*/hs_log.txt`. It lowercases the payload and wraps it in a
timestamped `WARNING hs:` record. Select the active runtime log; its directory
is not a stable session identifier. `halo_sdk_payload` matches that exact
envelope and rejects console-command echoes. Other engine formats need their
own transport proof. The SDK decoder cannot establish a retail result.

Results are `passed`, `failed` or `unresolved`. Missing output, malformed or
partial records, repeated or contradictory markers, a rotated/truncated log,
changed earlier bytes and exceeded byte limits remain unresolved. Re-reading
after a partial write retains the original cursor. Do not dispatch again with
the same nonce to turn an unresolved result into a pass. A later observation
requires a fresh assertion and cursor.

Every report identifies the condition, nonce, command, exact source commit,
candidate hashes, profile, execution environment and whether the run was
seeded or ordinary. Native and synthetic evidence are distinct. The reader
checks log identity, bounds and content; it does **not** prove that supplied
candidate metadata belongs to the emitting process. The operator records
process/profile identity and fingerprints before and after the experiment.

Archive the exact log bytes through `evidence.end_offset`, verify their
`log_sha256`, and retain the JSON result beside them before restarting the game.
Runtime logs can be replaced. The matching line numbers/text and byte offsets
make an observation reviewable; screenshots remain supplementary evidence.
Results describe the explicit observation window, not indefinitely later output.

The assertions are bounded to 240 ASCII command characters and eight expression
nesting levels. Keep checks small and use separate assertions for run values,
ranks, actors and cooldowns. This avoids one large native expression. The helper
does not validate HaloScript types or guarantee that a supplied expression has
no side effects; operators should use read-only conditions.

Source regressions use synthetic logs, including actual SDK envelope examples.
Run them with `python -B -m unittest discover -s tests -p test_native_qa.py -v`.
Synthetic coverage does not validate game recovery, retail compatibility or
ordinary-run balance. Native experiments and remaining work are recorded in
the LS-03 issue and its bounded evidence record.

## Session cleanup

The launcher source archives the final shared pending core into the session's
own profile after both the wrapper and native child have exited. This includes
partial bytes, which remain diagnostic archives and never become `CURRENT`.
The next profile therefore cannot inherit that file during an ordinary managed
shutdown. Signal handlers and `init.txt` are restored even if archival fails;
the error is reported and a preceding monitor exception remains primary.

This does not add crash-owner metadata or change legacy orphan handling at
startup. Forced termination of the launcher or an archival failure can still
leave a pending file; operators must inspect ownership before switching profiles.
The source change does not replace the installed launcher by itself.
