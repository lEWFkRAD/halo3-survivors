"""Fetch declared stock inputs from an extracted, owned Halo 3 Editing Kit.

Importing performs no work. --check reads prerequisites only. Fetching stages
and validates all inputs before replacing declared outputs. Transfer/header
checks do not establish native compatibility or dependency closure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile

from workspace_config import ConfigError, ProjectConfig, load_config

DAMAGE = {
    'needler': 'objects/weapons/pistol/needler/damage_effects/needler_shard_impact.damage_effect',
    'assault_rifle': 'objects/weapons/rifle/assault_rifle/damage_effects/assault_rifle_bullet.damage_effect',
    'shotgun': 'objects/weapons/rifle/shotgun/damage_effects/shotgun_bullet.damage_effect',
    'plasma_rifle': 'objects/weapons/rifle/plasma_rifle/damage_effects/plasma_rifle_bolt.damage_effect',
    'rocket_launcher': 'objects/weapons/support_high/rocket_launcher/damage_effects/rocket_launcher_explosion.damage_effect',
    'energy_sword': 'objects/weapons/damage_effects/dash_melee.damage_effect',
}
EFFECTS = {
    'needler': 'objects/weapons/pistol/needler/fx/impact.effect',
    'assault_rifle': 'objects/weapons/rifle/battle_rifle/fx/impact.effect',
    'shotgun': 'objects/weapons/rifle/shotgun/fx/impact.effect',
    'plasma_rifle': 'objects/weapons/rifle/plasma_rifle/fx/impact.effect',
    'energy_sword': 'objects/weapons/melee/energy_blade/fx/impact.effect',
    'rocket_launcher': 'objects/weapons/support_high/rocket_launcher/fx/detonation.effect',
}
CHARACTERS = {
    'infection': 'objects/characters/flood_infection/ai/flood_infection',
    'carrier': 'objects/characters/floodcarrier/ai/flood_carrier',
}
SUPPORT = {
    'watchtower_base': 'objects/gear/covenant/military/cov_watchtower/cov_watchtower_base/cov_watchtower_base.device_machine',
    'watchtower_gravlift': 'objects/gear/covenant/military/cov_watchtower/fx/gravlift/gravlift.light',
    'floodcarrier': 'objects/characters/floodcarrier/floodcarrier.biped',
}
BOOTSTRAP = {
    '020_base.scenario': 'levels/solo/020_base/020_base.scenario',
    '070_waste.scenario': 'levels/solo/070_waste/070_waste.scenario',
    '020_base.multilingual_unicode_string_list': 'ui/chapter_titles/020_base.multilingual_unicode_string_list',
}
INPUTS = {
    **{f'private-inputs/bootstrap/{name}': path for name, path in BOOTSTRAP.items()},
    'private-inputs/v3/energy_blade.weapon': 'objects/weapons/melee/energy_blade/energy_blade.weapon',
    **{f'private-inputs/v3/{name}.damage_effect': path for name, path in DAMAGE.items()},
    **{f'private-inputs/v3/{name}.effect': path for name, path in EFFECTS.items()},
    **{f'private-inputs/v3/{name}{PurePosixPath(path).suffix}': path for name, path in SUPPORT.items()},
    **{f'private-inputs/v3/{name}.character': path + '.character' for name, path in CHARACTERS.items()},
}
METADATA = ('private-inputs/bootstrap/sources.json', 'private-inputs/v3/sources.json',
            'private-inputs/v3/character-paths.json')
OUTPUTS = tuple(INPUTS) + METADATA
TAG_GROUPS = {
    '.scenario': b'rncs', '.multilingual_unicode_string_list': b'cinu',
    '.weapon': b'paew', '.damage_effect': b'!tpj', '.effect': b'effe',
    '.device_machine': b'hcam', '.light': b'hgil', '.biped': b'dpib', '.character': b'rahc',
}
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
LIMITATION = 'Transfer/header checks do not prove dependency closure, native compilation or gameplay.'


class FetchError(RuntimeError):
    """Input checking, transfer, validation or publication did not complete."""


class RecoveryError(FetchError):
    """Rollback failed; preserve the staging directory for recovery."""


def _linked(path: Path) -> bool:
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def output_check(root: Path, relative: str) -> dict:
    """Permit missing parents, never links, redirects or wrong-type outputs."""
    target = root / relative
    chain = (target, *[p for p in target.parents if p == root or root in p.parents])
    try:
        safe = (root.is_dir() and not _linked(root)
                and target.resolve().is_relative_to(root.resolve())
                and not any(_linked(p) for p in chain)
                and all(not p.exists() or p.is_dir() for p in chain[1:])
                and (not target.exists() or target.is_file()))
    except (OSError, RuntimeError):
        safe = False
    return {'path': str(target), 'expected': 'safe_output', 'status': 'ok' if safe else 'unsafe'}


def _input_check(root: Path, relative: str) -> dict:
    path = root / relative
    item = {'path': str(path), 'expected': 'owned_tag', 'status': 'missing', 'size': None}
    try:
        chain = (path, *[p for p in path.parents if p == root or root in p.parents])
        if any(_linked(p) for p in chain):
            item['status'] = 'unsafe'
        else:
            info = path.stat()
            item['size'] = info.st_size
            item['status'] = ('wrong_type' if not stat.S_ISREG(info.st_mode) else
                              'ok' if 80 <= info.st_size <= MAX_FILE else 'invalid_size')
    except FileNotFoundError:
        pass
    except OSError:
        item['status'] = 'unreadable'
    return item


# Check is stat-only. Fetch emits a bounded tar stream and transfer manifest.
# The receiving side never extracts arbitrary member names or symbolic links.
REMOTE_PROGRAM = r'''import hashlib,io,json,stat,sys,tarfile
from pathlib import Path
r=json.load(sys.stdin)
root=Path(r['kit'])/'tags'
checks=[]
for name,relative in r['inputs'].items():
    path=root/relative
    item=dict(path=str(path),expected='owned_tag',status='missing',size=None)
    try:
        chain=(path,*[p for p in path.parents if p==root or root in p.parents])
        if any(p.is_symlink() for p in chain):
            item['status']='unsafe'
        else:
            info=path.stat()
            item['size']=info.st_size
            item['status']=('wrong_type' if not stat.S_ISREG(info.st_mode) else
                            'ok' if 80<=info.st_size<=r['max_file'] else 'invalid_size')
    except FileNotFoundError:
        pass
    except OSError:
        item['status']='unreadable'
    checks.append(item)
ready=all(i['status']=='ok' for i in checks) and sum(i['size'] or 0 for i in checks)<=r['max_total']
if r['action']=='check':
    print(json.dumps(dict(schema_version=1,checks=checks,ready=ready)))
    sys.exit(0)
if not ready:
    sys.exit('Owned inputs missing, unsafe or oversized; run --check.')
data={}
files={}
total=0
for (name,relative),checked in zip(r['inputs'].items(),checks):
    path=root/relative
    with path.open('rb') as stream:
        blob=stream.read(r['max_file']+1)
    total+=len(blob)
    if len(blob)!=checked['size'] or len(blob)>r['max_file'] or total>r['max_total']:
        sys.exit('Input changed size during transfer.')
    data[name]=blob
    files[name]=dict(source=relative,size=len(blob),sha256=hashlib.sha256(blob).hexdigest())
data['transfer.json']=json.dumps(dict(schema_version=1,files=files)).encode('utf-8')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
    for name,blob in data.items():
        entry=tarfile.TarInfo(name)
        entry.size=len(blob)
        archive.addfile(entry,io.BytesIO(blob))
'''


def _remote_command(config: ProjectConfig) -> list[str]:
    return [config.ssh, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=10', '--', config.remote_host,
            shlex.join([config.remote_python, '-c', REMOTE_PROGRAM])]


def _remote_request(config: ProjectConfig, action: str) -> bytes:
    return json.dumps({'action': action, 'kit': config.remote_editing_kit,
                       'inputs': INPUTS, 'max_file': MAX_FILE,
                       'max_total': MAX_TOTAL}).encode('utf-8')


def _run_remote(config: ProjectConfig, action: str, *, stdout=None):
    try:
        result = subprocess.run(_remote_command(config), input=_remote_request(config, action),
                                stdout=subprocess.PIPE if stdout is None else stdout,
                                stderr=subprocess.PIPE, timeout=30 if action == 'check' else 180)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise FetchError(f'Remote {action} did not complete: {error}') from error
    if result.returncode:
        detail = result.stderr.decode('utf-8', errors='replace').strip()[:500]
        raise FetchError(f'Remote {action} failed ({result.returncode}): {detail}')
    return result


def _remote_checks(config: ProjectConfig) -> list[dict]:
    result = _run_remote(config, 'check')
    try:
        if len(result.stdout) > 65536:
            raise ValueError('oversized probe report')
        report = json.loads(result.stdout)
        checks = report['checks']
        if (type(report['schema_version']) is not int or report['schema_version'] != 1
                or type(report['ready']) is not bool or not isinstance(checks, list)
                or len(checks) != len(INPUTS)):
            raise ValueError('invalid header')
        for item, relative in zip(checks, INPUTS.values()):
            if (item['path'] != str(PurePosixPath(config.remote_editing_kit) / 'tags' / relative)
                    or item['expected'] != 'owned_tag'
                    or item['status'] not in ('ok', 'missing', 'wrong_type', 'invalid_size', 'unsafe', 'unreadable')
                    or not (item['size'] is None or type(item['size']) is int and item['size'] >= 0)
                    or item['status'] == 'ok' and not (80 <= (item['size'] or 0) <= MAX_FILE)):
                raise ValueError('invalid input check')
        ready = all(i['status'] == 'ok' for i in checks) and sum(i['size'] or 0 for i in checks) <= MAX_TOTAL
        if report['ready'] != ready:
            raise ValueError('inconsistent readiness')
    except (ValueError, TypeError, KeyError) as error:
        raise FetchError('Remote check returned an invalid report.') from error
    return checks


def inspect_inputs(config: ProjectConfig, *, remote: bool = False) -> dict:
    outputs = [output_check(config.workspace, name) for name in OUTPUTS]
    if remote:
        checks = _remote_checks(config)
    elif config.editing_kit is None:
        checks = [{'path': 'editing_kit', 'expected': 'configuration', 'status': 'missing', 'size': None}]
    else:
        checks = [_input_check(config.editing_kit / 'tags', path) for path in INPUTS.values()]
    total = sum(item['size'] or 0 for item in checks)
    return {'schema_version': 1, 'stage': 'fetch', 'workspace': str(config.workspace),
            'mode': 'remote' if remote else 'local', 'ready': total <= MAX_TOTAL and
            all(item['status'] == 'ok' for item in checks + outputs),
            'inputs': checks, 'outputs': outputs, 'input_bytes': total,
            'maximum_bytes': MAX_TOTAL, 'limitations': [LIMITATION], 'published': False}


def _record(name: str, blob: bytes) -> dict:
    if (not 80 <= len(blob) <= MAX_FILE or blob[48:52] != TAG_GROUPS[Path(name).suffix]
            or blob[60:68] != b'MALB!gat'):
        raise FetchError(f'Invalid or wrong-kind stock tag header: {name}')
    return {'source': INPUTS[name], 'size': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}


def _stage_remote(config: ProjectConfig, staging: Path) -> dict:
    transfer = staging / 'transfer.tar'
    with transfer.open('wb') as stream:
        _run_remote(config, 'fetch', stdout=stream)
    if transfer.stat().st_size > MAX_TOTAL + 1024 * 1024:
        raise FetchError('Remote transfer is oversized.')
    records = {}
    try:
        with tarfile.open(transfer, 'r:') as archive:
            names, manifest, total = set(), None, 0
            for item in archive:
                if item.name in names or item.name not in (*INPUTS, 'transfer.json') or not item.isfile():
                    raise FetchError('Remote transfer contains duplicate, undeclared or non-file entries.')
                names.add(item.name)
                limit = 65536 if item.name == 'transfer.json' else MAX_FILE
                if not 0 <= item.size <= limit:
                    raise FetchError('Remote transfer member is oversized.')
                total += item.size
                if total > MAX_TOTAL + 65536:
                    raise FetchError('Remote transfer inputs are oversized.')
                blob = archive.extractfile(item).read()
                if len(blob) != item.size:
                    raise FetchError('Truncated remote input.')
                if item.name == 'transfer.json':
                    manifest = json.loads(blob)
                else:
                    records[item.name] = _record(item.name, blob)
                    path = staging / 'files' / item.name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(blob)
            if (names != set(INPUTS) | {'transfer.json'} or not isinstance(manifest, dict)
                    or type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 1
                    or manifest.get('files') != records):
                raise FetchError('Remote transfer manifest, paths or hashes do not match.')
    except (OSError, tarfile.TarError, ValueError, TypeError) as error:
        raise FetchError(f'Invalid remote transfer: {error}') from error
    return records


def _stage_local(config: ProjectConfig, staging: Path, checks: list[dict]) -> dict:
    records, total = {}, 0
    for (name, relative), checked in zip(INPUTS.items(), checks):
        source = config.editing_kit / 'tags' / relative
        if _input_check(config.editing_kit / 'tags', relative)['status'] != 'ok':
            raise FetchError(f'Input is no longer available or safe: {source}')
        with source.open('rb') as stream:
            blob = stream.read(MAX_FILE + 1)
        total += len(blob)
        if len(blob) != checked['size'] or total > MAX_TOTAL:
            raise FetchError(f'Input changed size during fetch: {source}')
        records[name] = _record(name, blob)
        path = staging / 'files' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
    return records


def _stage_metadata(config: ProjectConfig, staging: Path, records: dict, remote: bool) -> None:
    origin = {'mode': 'remote' if remote else 'local',
              'editing_kit': config.remote_editing_kit if remote else str(config.editing_kit)}
    if remote:
        origin['host'] = config.remote_host
    for area in ('bootstrap', 'v3'):
        prefix = f'private-inputs/{area}/'
        manifest = {'schema_version': 1, 'source': origin,
                    'files': {name: record for name, record in records.items() if name.startswith(prefix)},
                    'limitations': [LIMITATION]}
        if area == 'v3':
            manifest.update(damage=DAMAGE, effects=EFFECTS, characters=CHARACTERS, support=SUPPORT)
        path = staging / 'files' / prefix / 'sources.json'
        path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    path = staging / 'files/private-inputs/v3/character-paths.json'
    path.write_text(json.dumps({k: v.replace('/', '\\') for k, v in CHARACTERS.items()}, indent=2) + '\n', encoding='utf-8')


def _publish(root: Path, staging: Path) -> None:
    if any(output_check(root, name)['status'] != 'ok' for name in OUTPUTS):
        raise FetchError('Output paths became unsafe before publication.')
    # Only declared preimages are saved. Each replace is atomic; an ordinary
    # publication failure rolls back. This is not a crash-atomic batch.
    originals, payloads = {}, {}
    for name in OUTPUTS:
        target = root / name
        originals[name] = target.read_bytes() if target.exists() else None
        payloads[name] = (staging / 'files' / name).read_bytes()
        if originals[name] is not None:
            saved = staging / 'previous' / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(originals[name])
    published = []
    try:
        for name in OUTPUTS:
            if output_check(root, name)['status'] != 'ok':
                raise FetchError(f'Output path became unsafe: {name}')
            target = root / name
            current = target.read_bytes() if target.exists() else None
            if current != originals[name]:
                raise RecoveryError(
                    f'Output changed since preflight: {name}; recovery files retained at {staging}')
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staging / 'files' / name, target)
            published.append(name)
    except Exception as error:
        for name in reversed(published):
            if output_check(root, name)['status'] != 'ok':
                raise RecoveryError(f'Rollback path unsafe; recovery files retained at {staging}') from error
            target = root / name
            try:
                current = target.read_bytes() if target.exists() else None
                if current != payloads[name]:
                    raise RecoveryError(
                        f'Rollback destination changed: {name}; recovery files retained at {staging}') from error
                if originals[name] is not None:
                    os.replace(staging / 'previous' / name, target)
                else:
                    target.unlink()
            except OSError as rollback_error:
                raise RecoveryError(f'Rollback failed; recovery files retained at {staging}: {rollback_error}') from error
        raise


def fetch_inputs(config: ProjectConfig, *, remote: bool = False, check: bool = False) -> dict:
    report = inspect_inputs(config, remote=remote)
    if check or not report['ready']:
        return report
    staging = Path(tempfile.mkdtemp(prefix='.fetch-inputs-', dir=config.workspace))
    keep_recovery = False
    try:
        records = _stage_remote(config, staging) if remote else _stage_local(config, staging, report['inputs'])
        _stage_metadata(config, staging, records, remote)
        _publish(config.workspace, staging)
        report.update(published=True, files=records)
    except RecoveryError:
        keep_recovery = True
        raise
    except OSError as error:
        raise FetchError(f'Fetch did not complete: {error}') from error
    finally:
        if not keep_recovery:
            shutil.rmtree(staging)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--root', type=Path, help='Destination source workspace (default: this checkout).')
    parser.add_argument('--remote', action='store_true', help='Read configured remote kit over trusted, noninteractive SSH.')
    parser.add_argument('--check', action='store_true', help='Read-only input and output prerequisite report.')
    parser.add_argument('--json', action='store_true', help='Emit a structured report.')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config, workspace=args.root)
        report = fetch_inputs(config, remote=args.remote, check=args.check)
    except (ConfigError, FetchError) as error:
        if args.json:
            print(json.dumps({'schema_version': 1, 'stage': 'fetch', 'ready': False, 'published': False, 'error': str(error)}))
        else:
            print(f'Fetch blocked: {error}', file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print('Owned inputs published.' if report['published'] else 'Fetch prerequisites ready.' if report['ready'] else 'Fetch prerequisites blocked.')
        for item in report['inputs'] + report['outputs']:
            if item['status'] != 'ok':
                print(f"  {item['status']}: {item['path']}")
        if report['input_bytes'] > report['maximum_bytes']:
            print('  Input set exceeds transfer size limit.')
        if not args.remote and config.editing_kit is None:
            print('  Configure editing_kit for local files, or select --remote explicitly.')
        print(LIMITATION)
    return 0 if report['ready'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
