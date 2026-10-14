"""Tracked native QA assertion-case runner; no transport of its own.

Operator QA historically ran named assertion cases through untracked probes
on the game host: create an assertion, capture the log cursor, dispatch its
command in the verified console, let the transport flush, then evaluate the
window. This module is the tracked version of that pattern, built on
``native_qa``. The caller supplies the ``dispatch`` callable (their verified
console path) and the runtime log; this module never sends input itself.

A case can only report ``passed`` when ``native_qa.evaluate`` observes the
exact nonce marker in the window captured before dispatch. Command echoes,
missing markers and contradictions stay failed/unresolved exactly as
``evaluate`` classifies them; there is no print-based pass path.

Every result is the ``evaluate`` report for the caller's
``EvidenceContext``, so the reservation candidate-identity binding (LS-03
Slice A, ``native_workspace.run_qa``/``read_qa_reservation``) carries into
case results unchanged. Per-case ``run_kind`` overrides the context's.

Example (operator side, after reserving the slot and opening the console)::

    context = ...  # EvidenceContext bound to the reserved candidate
    cases = load_cases(Path('cases.json'))
    results = run_cases(cases, log_path=hs_log, context=context,
                        dispatch=console.send, settle=lambda: time.sleep(0.5),
                        decode_line=native_qa.halo_sdk_payload)
    write_reports(results, Path('evidence-dir'))
    raise SystemExit(0 if all(r['report']['outcome'] == 'passed'
                              for r in results) else 2)
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from typing import Callable, Iterable

import native_qa

_NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}')
_CASE_KEYS = {'name', 'condition', 'run_kind', 'dispatches'}


@dataclass(frozen=True)
class Case:
    """One named assertion case: a native_qa condition plus report metadata."""

    name: str
    condition: str
    run_kind: str = 'seeded'
    dispatches: int = 1

    def __post_init__(self):
        if not _NAME.fullmatch(self.name):
            raise ValueError('Case name must be a lowercase file-safe token')
        if self.run_kind not in ('seeded', 'ordinary'):
            raise ValueError('Case run kind must be seeded or ordinary')
        if not isinstance(self.dispatches, int) or not 1 <= self.dispatches <= 8:
            raise ValueError('Case dispatches must be between 1 and 8')
        # Reuse the assertion grammar so a malformed condition fails here,
        # not after the operator has dispatched half a case list.
        native_qa.Assertion(self.condition, '0' * 32)


def load_cases(path: Path | str) -> list[Case]:
    """Load case definitions from a JSON list; unknown keys are rejected."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, list) or not data:
        raise ValueError('Cases file must be a non-empty JSON list')
    cases = []
    for entry in data:
        if not isinstance(entry, dict) or not set(entry) <= _CASE_KEYS \
                or not {'name', 'condition'} <= set(entry):
            raise ValueError(f'Invalid case entry: {entry!r}')
        cases.append(Case(**entry))
    names = [case.name for case in cases]
    if len(set(names)) != len(names):
        raise ValueError('Case names must be unique')
    return cases


def run_cases(cases: Iterable[Case], *, log_path: Path | str,
              context: native_qa.EvidenceContext,
              dispatch: Callable[[str], None],
              settle: Callable[[], None] | None = None,
              decode_line: Callable[[str], str | None] = native_qa.halo_sdk_payload
              ) -> list[dict]:
    """Run each case in order and return ``{'name', 'report'}`` results.

    For every case: stamp the context with the case run kind, create the
    assertion, capture the cursor, dispatch its command ``dispatches``
    times, settle, then evaluate the flushed window. A failing or
    unresolved case never stops later cases; the caller decides the exit
    code from the outcomes.
    """
    results = []
    for case in cases:
        case_context = replace(context, run_kind=case.run_kind)
        assertion = native_qa.new_assertion(case.condition)
        cursor = native_qa.capture_cursor(log_path)
        for _ in range(case.dispatches):
            dispatch(assertion.command)
        if settle is not None:
            settle()
        report = native_qa.evaluate(assertion, native_qa.read_window(cursor),
                                    case_context, decode_line=decode_line)
        results.append({'name': case.name, 'report': report})
    return results


def write_reports(results: Iterable[dict], out_dir: Path | str) -> list[Path]:
    """Write one ``<name>.json`` report per case; returns the paths written."""
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = []
    for result in results:
        target = root / f"{result['name']}.json"
        target.write_text(json.dumps(result['report'], indent=2) + '\n',
                          encoding='utf-8')
        paths.append(target)
    return paths


def outcome_counts(results: Iterable[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        outcome = result['report']['outcome']
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts
