"""Read-only native assertion evidence; importing this module performs no work.

Capture a cursor BEFORE dispatching ``Assertion.command`` in the native console,
then observe the same log after a bounded window. A caller must verify its log
transport before supplying a decoder: the default accepts only a bare payload
line. Command echoes, screenshots and absent output are not observed assertions.
These helpers never start a game, send input, write files or change a profile.
Context labels and hashes are supplied by the caller; format validation does
not bind them to a process, loaded candidate or source revision. The operator
must establish that association and retain before/after candidate checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import stat
from typing import Callable, Mapping
from types import MappingProxyType
import uuid


MAX_COMMAND = 240
MAX_LOG_BYTES = 64 * 1024 * 1024
MAX_APPENDED_BYTES = 1024 * 1024
MARKER = re.compile(r'LSQA:([0-9a-f]{32}):(PASS|FAIL)')
HALO_SDK_MARKER = re.compile(
    r'(?:0[1-9]|1[0-2])\.(?:0[1-9]|[12][0-9]|3[01])\.[0-9]{2} '
    r'(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{3} '
    r'[0-9]{7} (?:g[0-9]{6}| {7}) f[0-9]{7}  WARNING hs: '
    r'lsqa:([0-9a-f]{32}):(pass|fail) ')
SHA256 = re.compile(r'[0-9a-f]{64}')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Assertion:
    condition: str
    nonce: str

    def __post_init__(self):
        if not re.fullmatch(r'[0-9a-f]{32}', self.nonce):
            raise ValueError('Assertion nonce must contain 32 lowercase UUID hex digits')
        # Only one bounded, balanced expression (or atom); strings and console
        # separators are deliberately unsupported by this small assertion path.
        expression = self.condition
        if (not expression or expression != expression.strip()
                or not re.fullmatch(r'[A-Za-z0-9_().<>=+*/ -]+', expression)):
            raise ValueError('Condition must be one ASCII expression without quotes or newlines')
        depth = 0
        for index, character in enumerate(expression):
            if character == '(':
                depth += 1
                if depth > 8:
                    raise ValueError('Condition nesting exceeds the bounded console path')
            elif character == ')':
                depth -= 1
                if depth < 0 or (depth == 0 and index != len(expression) - 1):
                    raise ValueError('Condition must be one balanced expression')
        if depth or (not expression.startswith('(') and (' ' in expression or ')' in expression)):
            raise ValueError('Condition must be one balanced expression or atom')
        if len(self.command) > MAX_COMMAND:
            raise ValueError(f'Assertion command exceeds {MAX_COMMAND} ASCII characters')

    @property
    def command(self) -> str:
        return (f'(if {self.condition} (log_print "LSQA:{self.nonce}:PASS") '
                f'(log_print "LSQA:{self.nonce}:FAIL"))')


def new_assertion(condition: str) -> Assertion:
    return Assertion(condition, uuid.uuid4().hex)


@dataclass(frozen=True)
class EvidenceContext:
    """Caller-supplied provenance, checked for shape but not independently bound.

    ``source_commit`` is the claimed source revision of the candidate, not proof
    that its artifacts were built from that commit. Fingerprints, profile, run
    kind and native/synthetic classification likewise need operator evidence.
    """
    source_commit: str
    candidate_fingerprint: Mapping[str, str]
    profile: str
    environment: str
    run_kind: str
    evidence_kind: str

    def __post_init__(self):
        if not re.fullmatch(r'[0-9a-f]{40}', self.source_commit):
            raise ValueError('Use the full source Git commit, not a branch or abbreviated SHA')
        required = {'engine', 'scenario', 'hsc', 'private_assets'}
        if (not required.issubset(self.candidate_fingerprint)
                or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name)
                       for name in self.candidate_fingerprint)
                or any(not isinstance(value, str) or not SHA256.fullmatch(value)
                       for value in self.candidate_fingerprint.values())):
            raise ValueError('Candidate needs SHA256 engine, scenario, hsc and private_assets hashes')
        object.__setattr__(self, 'candidate_fingerprint', MappingProxyType(dict(self.candidate_fingerprint)))
        if not self.profile or len(self.profile) > 160 or any(ord(c) < 32 for c in self.profile):
            raise ValueError('Supply a short explicit profile label')
        if self.environment not in ('sdk', 'retail'):
            raise ValueError('Environment must explicitly be sdk or retail')
        if self.run_kind not in ('seeded', 'ordinary'):
            raise ValueError('Run kind must explicitly be seeded or ordinary')
        if self.evidence_kind not in ('native', 'synthetic'):
            raise ValueError('Evidence kind must explicitly be native or synthetic')


@dataclass(frozen=True)
class LogCursor:
    path: str
    device: int
    inode: int
    offset: int
    prefix_sha256: str
    newline_count: int
    at_line_boundary: bool
    captured_at: str


@dataclass(frozen=True)
class LogLine:
    number: int
    text: str


@dataclass(frozen=True)
class LogWindow:
    cursor: LogCursor
    observed_at: str
    end_offset: int | None
    log_sha256: str | None
    lines: tuple[LogLine, ...] = ()
    issue: str | None = None


def _snapshot(path: Path, max_bytes: int) -> tuple[os.stat_result, bytes]:
    """Read one stable, bounded regular-file snapshot, rejecting linked paths."""
    if max_bytes <= 0:
        raise ValueError('Log byte limit must be positive')
    if path.is_symlink():
        raise OSError('Linked logs are not accepted')
    if not stat.S_ISREG(path.stat().st_mode):
        raise OSError('Log is not a regular file')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise OSError('Log is not a bounded regular file')
        data = stream.read(before.st_size)
        after = os.fstat(stream.fileno())
        current = path.stat()
    if ((before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
            or before.st_size != len(data) or after.st_size < before.st_size
            or current.st_size < before.st_size
            or (after.st_size == before.st_size and after.st_mtime_ns != before.st_mtime_ns)):
        raise OSError('Log changed or rotated while taking its snapshot')
    return before, data


def capture_cursor(path: Path | str, *, max_bytes: int = MAX_LOG_BYTES) -> LogCursor:
    """Prepare before dispatch. An unreadable/missing baseline raises OSError."""
    path = Path(path).absolute()
    info, data = _snapshot(path, max_bytes)
    return LogCursor(str(path), info.st_dev, info.st_ino, len(data), digest(data),
                     data.count(b'\n'), not data or data.endswith(b'\n'), now())


def read_window(cursor: LogCursor, *, max_bytes: int = MAX_LOG_BYTES,
                max_appended_bytes: int = MAX_APPENDED_BYTES) -> LogWindow:
    """Read only complete appended lines; integrity failures remain unresolved.

    The whole snapshot hash identifies the evidence file at ``end_offset``.
    Prefix hashing detects same-inode truncation/rewrites even after regrowth;
    byte-identical history reconstruction cannot be distinguished from append.
    A partial tail deliberately keeps the whole observation unresolved. Repeat
    this read after the native transport flushes, retaining the original cursor.
    """
    if max_appended_bytes <= 0:
        raise ValueError('Append byte limit must be positive')
    try:
        info, data = _snapshot(Path(cursor.path), max_bytes)
    except OSError as error:
        return LogWindow(cursor, now(), None, None, issue=f'log_unavailable: {error}')
    window = dict(cursor=cursor, observed_at=now(), end_offset=len(data), log_sha256=digest(data))
    if (info.st_dev, info.st_ino) != (cursor.device, cursor.inode):
        return LogWindow(**window, issue='log_rotated')
    if len(data) < cursor.offset:
        return LogWindow(**window, issue='log_truncated')
    if digest(data[:cursor.offset]) != cursor.prefix_sha256:
        return LogWindow(**window, issue='log_prefix_changed')
    appended = data[cursor.offset:]
    if len(appended) > max_appended_bytes:
        return LogWindow(**window, issue='append_limit_exceeded')
    first_line = cursor.newline_count + 1
    if not cursor.at_line_boundary:
        # Never treat completion of a pre-dispatch partial line as fresh output.
        _, separator, appended = appended.partition(b'\n')
        first_line += 1
        if not separator:
            return LogWindow(**window, issue='incomplete_baseline_line')
    pieces = appended.split(b'\n')
    lines = tuple(LogLine(first_line + index, line.removesuffix(b'\r').decode('utf-8', errors='replace'))
                  for index, line in enumerate(pieces[:-1]))
    issue = 'incomplete_tail' if pieces[-1] else None
    return LogWindow(**window, lines=lines, issue=issue)


def bare_payload(line: str) -> str | None:
    """Only a complete marker line, with no whitespace, prefix or echoed HSC."""
    return line if MARKER.fullmatch(line) else None


def halo_sdk_payload(line: str) -> str | None:
    """Decode the observed H3 SDK ``reports_*/hs_log.txt`` warning envelope.

    That runtime lowercases log_print payloads and adds one trailing space.
    Match the timestamp, counters and warning channel in full; never case-fold
    arbitrary log lines or accept its ``hs:evaluate: console_command`` echoes.
    The blank seven-character g field occurs during startup. Retail and other
    engine/logger formats require independent transport validation.
    """
    match = HALO_SDK_MARKER.fullmatch(line)
    return f'LSQA:{match[1]}:{match[2].upper()}' if match else None


def evaluate(assertion: Assertion, window: LogWindow, context: EvidenceContext,
             *, decode_line: Callable[[str], str | None] = bare_payload) -> dict:
    """Classify a closed observation window, never a screenshot or a dispatch.

    A custom decoder must match an independently verified native log envelope
    in full and return its exact payload. It must not search for substrings.
    Even with a decoder, obvious command echoes and multiple-marker lines are
    rejected. One observation is required; repeats and contradictions are
    unresolved. Later output is outside this explicit bounded evidence window.
    A pass means the marker was observed, not that the caller's context binding
    was independently verified. The built-in SDK decoder cannot certify retail.
    """
    transport = ('halo_sdk_hs_log' if decode_line is halo_sdk_payload else
                 'bare_payload' if decode_line is bare_payload else 'custom')
    matches = []
    for line in window.lines:
        if ('log_print' in line.text
                or line.text.count('LSQA:') + line.text.count('lsqa:') != 1):
            continue
        payload = decode_line(line.text)
        marker = MARKER.fullmatch(payload) if isinstance(payload, str) else None
        if marker and marker[1] == assertion.nonce:
            matches.append({'line': line.number, 'text': line.text, 'outcome': marker[2]})
    if window.issue:
        outcome, reason = 'unresolved', window.issue
    elif decode_line is halo_sdk_payload and context.environment != 'sdk':
        outcome, reason = 'unresolved', 'decoder_environment_mismatch'
    elif not matches:
        outcome, reason = 'unresolved', 'no_native_marker'
    elif len(matches) != 1:
        outcome, reason = 'unresolved', 'multiple_native_markers'
    else:
        outcome = 'passed' if matches[0]['outcome'] == 'PASS' else 'failed'
        reason = 'observed_marker'
    return {
        'schema': 1, 'outcome': outcome, 'reason': reason,
        'assertion': {'condition': assertion.condition, 'nonce': assertion.nonce,
                      'command': assertion.command},
        'candidate': {'source_commit': context.source_commit,
                      'fingerprint': dict(context.candidate_fingerprint)},
        'profile': context.profile, 'environment': context.environment,
        'run_kind': context.run_kind, 'evidence_kind': context.evidence_kind,
        'transport': transport,
        'evidence': {'path': window.cursor.path, 'cursor_at': window.cursor.captured_at,
                     'observed_at': window.observed_at, 'start_offset': window.cursor.offset,
                     'end_offset': window.end_offset, 'prefix_sha256': window.cursor.prefix_sha256,
                     'log_sha256': window.log_sha256, 'observations': matches},
    }
