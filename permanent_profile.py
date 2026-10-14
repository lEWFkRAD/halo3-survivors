"""Permanent progression profile for LS-08: storage and rules only.

Permanent state (unlocks and salvage earned across runs) is kept strictly
separate from run ranks and from the opaque native checkpoint cores the
launcher manages. This module owns the on-disk profile: a versioned JSON
schema, validation against the catalog's stable node IDs, an
applied-outcome ledger that makes run-outcome rewards idempotent, and
atomic saves with a preserved backup, mirroring launch_v04 discipline.

It performs no engine I/O and parses no native cores. The bridge that
earns outcomes from real runs and seeds bonuses into a New Run is
launcher/native work specified in LS08_PROFILE.md.

Schema v1 fields (exact set):
    schema_version: 1
    kind: "production" | "qa"
    unlocks: sorted list of catalog node IDs with scope "availability"
    salvage: non-negative int
    outcomes: list of applied outcome IDs, in application order

A v0 profile is the pre-schema shape {"unlocks": [...]} (optionally with
"salvage"); migrate() upgrades it in memory. Loading never migrates or
rewrites silently: callers decide, then save explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import json
import os
from pathlib import Path
import re
import uuid

from progression_catalog import NODES

SCHEMA_VERSION = 1
KINDS = ('production', 'qa')
AVAILABILITY_IDS = frozenset(
    node['id'] for node in NODES if node['scope'] == 'availability')
_FIELDS = {'schema_version', 'kind', 'unlocks', 'salvage', 'outcomes'}
_OUTCOME_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')


class ProfileError(ValueError):
    """Raised for any invalid profile data, file or operation."""


@dataclass(frozen=True)
class PermanentProfile:
    kind: str
    unlocks: frozenset = frozenset()
    salvage: int = 0
    outcomes: tuple = ()

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ProfileError(f'Profile kind must be one of {KINDS}')
        unknown = set(self.unlocks) - AVAILABILITY_IDS
        if unknown:
            raise ProfileError(
                f'Unlocks must be catalog availability IDs: {sorted(unknown)}')
        if not isinstance(self.salvage, int) or self.salvage < 0:
            raise ProfileError('Salvage must be a non-negative int')
        if len(set(self.outcomes)) != len(self.outcomes):
            raise ProfileError('Outcome ledger contains duplicates')
        for outcome in self.outcomes:
            if not _OUTCOME_ID.fullmatch(outcome):
                raise ProfileError(f'Invalid outcome ID: {outcome!r}')


def new_profile(kind: str) -> PermanentProfile:
    return PermanentProfile(kind=kind)


def apply_outcome(profile: PermanentProfile, outcome_id: str, *,
                  unlocks=(), salvage: int = 0):
    """Apply one run outcome's permanent reward, at most once.

    Returns (profile, applied). Replaying an outcome ID returns the
    profile unchanged with applied=False, whether or not the replay
    carries the same reward: the ledger, not the payload, decides.
    """
    if not _OUTCOME_ID.fullmatch(outcome_id):
        raise ProfileError(f'Invalid outcome ID: {outcome_id!r}')
    if outcome_id in profile.outcomes:
        return profile, False
    if not isinstance(salvage, int) or salvage < 0:
        raise ProfileError('Outcome salvage must be a non-negative int')
    merged = PermanentProfile(
        kind=profile.kind,
        unlocks=profile.unlocks | frozenset(unlocks),
        salvage=profile.salvage + salvage,
        outcomes=profile.outcomes + (outcome_id,))
    return merged, True


def spend_salvage(profile: PermanentProfile, amount: int) -> PermanentProfile:
    if not isinstance(amount, int) or amount <= 0:
        raise ProfileError('Spend amount must be a positive int')
    if amount > profile.salvage:
        raise ProfileError('Insufficient salvage')
    return replace(profile, salvage=profile.salvage - amount)


def to_data(profile: PermanentProfile) -> dict:
    return {
        'schema_version': SCHEMA_VERSION,
        'kind': profile.kind,
        'unlocks': sorted(profile.unlocks),
        'salvage': profile.salvage,
        'outcomes': list(profile.outcomes),
    }


def from_data(data) -> PermanentProfile:
    if not isinstance(data, dict):
        raise ProfileError('Profile must be a JSON object')
    if set(data) != _FIELDS:
        raise ProfileError(
            f'Profile fields must be exactly {sorted(_FIELDS)}')
    if data['schema_version'] != SCHEMA_VERSION:
        raise ProfileError(
            f"Unsupported schema version: {data['schema_version']!r}")
    if not isinstance(data['unlocks'], list) \
            or not all(isinstance(u, str) for u in data['unlocks']):
        raise ProfileError('Unlocks must be a list of node IDs')
    if len(set(data['unlocks'])) != len(data['unlocks']):
        raise ProfileError('Unlocks contain duplicates')
    if not isinstance(data['outcomes'], list) \
            or not all(isinstance(o, str) for o in data['outcomes']):
        raise ProfileError('Outcomes must be a list of outcome IDs')
    return PermanentProfile(kind=data['kind'],
                            unlocks=frozenset(data['unlocks']),
                            salvage=data['salvage'],
                            outcomes=tuple(data['outcomes']))


def migrate(data) -> dict:
    """Upgrade a v0 profile dict to v1 data; reject anything newer."""
    if not isinstance(data, dict):
        raise ProfileError('Profile must be a JSON object')
    version = data.get('schema_version', 0)
    if version == SCHEMA_VERSION:
        from_data(data)
        return data
    if version != 0:
        raise ProfileError(f'Unsupported schema version: {version!r}')
    if not set(data) <= {'unlocks', 'salvage', 'kind'}:
        raise ProfileError('Unrecognized v0 profile fields')
    upgraded = {
        'schema_version': SCHEMA_VERSION,
        'kind': data.get('kind', 'production'),
        'unlocks': data.get('unlocks', []),
        'salvage': data.get('salvage', 0),
        'outcomes': [],
    }
    from_data(upgraded)
    return upgraded


def _fsync_dir(path: Path):
    if hasattr(os, 'O_DIRECTORY'):
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _atomic_bytes(path: Path, data: bytes):
    if path.is_symlink():
        raise ProfileError(f'Refusing linked output: {path}')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def backup_path(path: Path | str) -> Path:
    path = Path(path)
    return path.with_name(path.name + '.bak')


def save_profile(path: Path | str, profile: PermanentProfile):
    """Atomically save, preserving the previous file as <name>.bak."""
    path = Path(path)
    payload = (json.dumps(to_data(profile), indent=2) + '\n').encode()
    if path.exists():
        _atomic_bytes(backup_path(path), path.read_bytes())
    _atomic_bytes(path, payload)


def _read_profile(path: Path, expected_kind) -> PermanentProfile:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProfileError(f'Cannot read profile {path}: {exc}') from exc
    profile = from_data(data)
    if expected_kind is not None and profile.kind != expected_kind:
        raise ProfileError(
            f'Profile kind is {profile.kind}, expected {expected_kind}')
    return profile


def load_profile(path: Path | str, *, expected_kind: str | None = None,
                 ) -> PermanentProfile:
    path = Path(path)
    if not path.exists():
        raise ProfileError(f'No profile at {path}')
    return _read_profile(path, expected_kind)


def recover_profile(path: Path | str, *, expected_kind: str | None = None,
                    ) -> PermanentProfile:
    """Load the preserved backup explicitly; never used silently."""
    backup = backup_path(path)
    if not backup.exists():
        raise ProfileError(f'No backup profile at {backup}')
    return _read_profile(backup, expected_kind)
