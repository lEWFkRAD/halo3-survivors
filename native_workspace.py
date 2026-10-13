"""Stage exact authored files in a configured local H3EK, or copy readback bytes.

This helper never launches/stops a native process or edits saves, init.txt, maps
or an installed mod. The operator must independently coordinate ownership and
perform compilation/save. An idle-process snapshot is not a cross-process lock.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
import uuid

from workspace_config import ConfigError, ProjectConfig, load_config


SCENARIO = 'tags/levels/survivors/last_stand/last_stand.scenario'
HSC = 'data/levels/survivors/last_stand/scripts/last_stand.hsc'
READBACK = {
    'bootstrap': 'native-tags/levels/survivors/last_stand/outdoor-compiled.scenario',
    'progression': 'native-tags/levels/survivors/last_stand/compiled-progression.scenario',
}
NATIVE_NAMES = {'sapien.exe', 'halo3_tag_test.exe', 'tool.exe', 'guerilla.exe'}
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 256 * 1024 * 1024
LIMITATION = ('File transfer and process snapshots do not prove native compilation, '
              'dependency closure, gameplay, ownership or retail compatibility.')


class WorkspaceError(ValueError):
    """A preflight, exact-input or transfer requirement failed."""


def _relative(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or any(ord(char) < 32 for char in name)
            or str(PurePosixPath(name)) != name
            or PurePosixPath(name).is_absolute()
            or any(part in ('.', '..') for part in PurePosixPath(name).parts)):
        raise WorkspaceError(f'Unsafe relative path: {name!r}')
    return name


def _linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def _root(path):
    if path is None or not path.is_absolute() or not path.is_dir() or _linked(path):
        raise WorkspaceError('Use an existing absolute, unlinked workspace/editing_kit directory')
    return path


def _file(root, name, *, required=True):
    path = root / _relative(name)
    chain = (path, *[parent for parent in path.parents if parent == root or root in parent.parents])
    if (not path.resolve().is_relative_to(root.resolve()) or any(_linked(p) for p in chain)
            or any(p.exists() and not p.is_dir() for p in chain[1:])
            or (path.exists() and not path.is_file()) or (required and not path.is_file())):
        raise WorkspaceError(f'Expected safe regular file: {path}')
    return path


def _record(data):
    return {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def _read(path, maximum=MAX_FILE):
    if path.stat().st_size > maximum:
        raise WorkspaceError(f'File exceeds transfer bound: {path.name}')
    data = path.read_bytes()
    if len(data) > maximum:
        raise WorkspaceError(f'File grew beyond transfer bound: {path.name}')
    return data


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkspaceError(f'Duplicate manifest key: {key}')
        result[key] = value
    return result


def _manifest(root, name):
    data = _read(_file(root, name), 2 * 1024 * 1024)
    try:
        result = json.loads(data, object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise WorkspaceError(f'Invalid manifest: {name}') from error
    if not isinstance(result, dict) or type(result.get('schema_version')) is not int or result['schema_version'] != 1:
        raise WorkspaceError(f'Unsupported manifest schema: {name}')
    return result, _record(data)


def _verify_record(data, record, name):
    if (not isinstance(record, dict) or set(record) != {'size', 'sha256'}
            or type(record['size']) is not int or record['size'] < 0
            or not isinstance(record['sha256'], str)
            or re.fullmatch('[0-9a-f]{64}', record['sha256']) is None
            or _record(data) != record):
        raise WorkspaceError(f'Manifest size/hash mismatch: {name}')


def _verified_files(root, records):
    if not isinstance(records, dict) or not records:
        raise WorkspaceError('Expected a nonempty manifest file map')
    output, total = {}, 0
    for name, record in records.items():
        data = _read(_file(root, name))
        total += len(data)
        if total > MAX_TOTAL:
            raise WorkspaceError('Manifest files exceed total transfer bound')
        _verify_record(data, record, name)
        output[name] = data
    return output


def _bootstrap(root):
    from bootstrap_tags import BOOTSTRAP_INPUTS, BOOTSTRAP_OUTPUTS, MANIFEST_PATH
    manifest, receipt = _manifest(root, MANIFEST_PATH)
    if manifest.get('stage') != 'direct-stock-bootstrap' or manifest.get('native_validation') != 'required':
        raise WorkspaceError('Expected a direct stock bootstrap manifest')
    maps = []
    for key, expected in (('inputs', BOOTSTRAP_INPUTS), ('outputs', BOOTSTRAP_OUTPUTS)):
        records = manifest.get(key)
        if not isinstance(records, list):
            raise WorkspaceError(f'Expected bootstrap {key} list')
        mapped = {}
        for record in records:
            if not isinstance(record, dict) or set(record) != {'path', 'size', 'sha256'}:
                raise WorkspaceError('Invalid bootstrap file record')
            name = _relative(record['path'])
            if name in mapped:
                raise WorkspaceError(f'Duplicate bootstrap file: {name}')
            mapped[name] = {k: record[k] for k in ('size', 'sha256')}
        if set(mapped) != set(expected):
            raise WorkspaceError(f'Bootstrap {key} is not the exact declared set')
        maps.append(_verified_files(root, mapped))
    outputs = maps[1]
    plan = {SCENARIO: outputs[BOOTSTRAP_OUTPUTS[0]], HSC: outputs[BOOTSTRAP_OUTPUTS[1]],
            'tags/ui/survivors/last_stand.multilingual_unicode_string_list': outputs[BOOTSTRAP_OUTPUTS[2]]}
    return plan, {'path': MANIFEST_PATH, **receipt}


def _progression(root):
    from preflight import AUTHORING_INPUTS
    from prepare_progression import FIXED_OUTPUTS, PRIVATE_TAG, UI_OUTPUT, OPTIONAL_INPUTS
    manifest, receipt = _manifest(root, 'progression-build.json')
    if manifest.get('stage') != 'authored' or manifest.get('native_compilation_required') is not True:
        raise WorkspaceError('Expected an authored progression manifest')
    inputs = manifest.get('inputs')
    if (not isinstance(inputs, dict) or not set(AUTHORING_INPUTS) <= set(inputs)
            or set(inputs) - set(AUTHORING_INPUTS) - set(OPTIONAL_INPUTS)):
        raise WorkspaceError('Progression input set differs from declared authoring inputs')
    _verified_files(root, inputs)
    sources = manifest.get('sources')
    if (not isinstance(sources, dict) or 'prepare_progression.py' not in sources
            or any(re.fullmatch('[a-z][a-z0-9_]*[.]py', name) is None for name in sources)):
        raise WorkspaceError('Invalid progression source provenance')
    _verified_files(root, sources)
    records = manifest.get('outputs')
    if (not isinstance(records, dict) or not FIXED_OUTPUTS <= set(records)
            or any(name not in FIXED_OUTPUTS and not PRIVATE_TAG.fullmatch(name) for name in records)):
        raise WorkspaceError('Progression output set contains missing or undeclared artifacts')
    outputs = _verified_files(root, records)
    archive = manifest.get('archive')
    if (not isinstance(archive, dict) or set(archive) != {'path', 'size', 'sha256', 'members'}
            or archive['path'] != 'v3-native.tar' or not isinstance(archive['members'], list)
            or not all(isinstance(name, str) for name in archive['members'])):
        raise WorkspaceError('Invalid progression archive record')
    expected = {name.removeprefix('native-tags/'): data for name, data in outputs.items()
                if PRIVATE_TAG.fullmatch(name) or name == UI_OUTPUT}
    if (len(archive['members']) != len(expected)
            or set(archive['members']) != set(expected)):
        raise WorkspaceError('Archive member manifest differs from exact authored tag set')
    raw = _read(_file(root, archive['path']), MAX_TOTAL)
    _verify_record(raw, {key: archive[key] for key in ('size', 'sha256')}, archive['path'])
    found = set()
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
            for member in tar:
                name = _relative(member.name)
                if (name not in expected or name in found or not member.isfile()
                        or member.pax_headers or member.size != len(expected[name])):
                    raise WorkspaceError(f'Undeclared, duplicated or non-regular archive member: {name}')
                if tar.extractfile(member).read() != expected[name]:
                    raise WorkspaceError(f'Archive bytes differ from authored tag: {name}')
                found.add(name)
    except tarfile.TarError as error:
        raise WorkspaceError('Invalid progression archive') from error
    if found != set(expected):
        raise WorkspaceError('Archive omits authored tags')
    plan = {'tags/' + name: data for name, data in expected.items()}
    plan[SCENARIO] = outputs['native-tags/levels/survivors/last_stand/progression-ui.scenario']
    plan[HSC] = outputs['source/progression.hsc']
    return plan, {'path': 'progression-build.json', **receipt}


def probe_processes(config: ProjectConfig) -> dict:
    """Conservative host-wide inspection; uncertainty is never an idle result.

    Wine command lines are inspected because its native main thread can be
    named MAIN_THREAD. Windows tasklist does not reliably identify toolkit
    ownership, so any matching executable blocks staging on that host.
    """
    matches = []
    try:
        if sys.platform == 'win32':
            result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], check=True,
                                    capture_output=True, text=True, timeout=20)
            rows = list(csv.reader(io.StringIO(result.stdout)))
            if not rows or any(len(row) < 2 or not row[1].isdigit() for row in rows):
                raise WorkspaceError('Windows tasklist did not return a complete process table')
            for row in rows:
                if row[0].lower() in NATIVE_NAMES:
                    matches.append({'pid': int(row[1]), 'name': row[0]})
        elif sys.platform.startswith('linux'):
            proc = Path('/proc')
            entries = [path for path in proc.iterdir() if path.name.isdigit()]
            if not entries:
                raise WorkspaceError('Linux process table is unavailable')
            for path in entries:
                try:
                    comm = (path / 'comm').read_text().strip()
                    argv = (path / 'cmdline').read_bytes().decode('utf-8', 'replace').split('\0')
                except FileNotFoundError:
                    continue  # Process exited while being inspected.
                names = {arg.strip('"').replace('\\', '/').rsplit('/', 1)[-1].lower() for arg in argv}
                native = names & NATIVE_NAMES
                # A launcher may start its native child after a snapshot; stop
                # the launcher's own session normally before staging as well.
                # Installed production and source candidate roots can differ;
                # relative launch.py paths also omit both configured roots.
                # A known launcher anywhere on this host is conservatively busy.
                owned_launcher = bool(names & {'launch_v04.py', 'launch.py'})
                if native or comm.lower() in NATIVE_NAMES or owned_launcher:
                    matches.append({'pid': int(path.name), 'name': sorted(native)[0] if native else comm})
        else:
            raise WorkspaceError(f'Process inspection unsupported on {sys.platform}')
    except (OSError, UnicodeError, subprocess.SubprocessError, WorkspaceError) as error:
        return {'status': 'unresolved', 'processes': matches, 'error': str(error)}
    return {'status': 'busy' if matches else 'idle', 'processes': matches}


def _idle(config, process_probe):
    report = process_probe(config)
    if (not isinstance(report, dict) or report.get('status') != 'idle'
            or report.get('processes') != []):
        raise WorkspaceError(f'Native process preflight is not confirmed idle: {report}')
    return report


def _kit(config):
    root, kit = _root(config.workspace), _root(config.editing_kit)
    for name in ('tool.exe', 'sapien.exe', 'halo3_tag_test.exe'):
        _file(kit, name)
    for name in ('tags', 'data'):
        directory = kit / name
        if not directory.is_dir() or _linked(directory):
            raise WorkspaceError(f'Expected unlinked H3EK directory: {directory}')
    return root, kit


def _destinations(root, payloads, replace):
    originals = {}
    for name in payloads:
        path = _file(root, name, required=False)
        if path.exists():
            if not replace:
                raise WorkspaceError(f'Destination exists; use --replace to preserve a backup: {path}')
            originals[name] = _read(path)
        else:
            originals[name] = None
    return originals


def _metadata_paths(root):
    # Read-only parent/link checks also run for --check. Actual names are unique
    # and individually checked immediately before publication.
    _file(root, 'native-workspace/preflight.json', required=False)
    _file(root, 'backups/native-workspace-preflight/preflight.json', required=False)


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.last-stand-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _publish(config, destination, payloads, originals, report, process_probe):
    root = config.workspace
    operation = uuid.uuid4().hex
    receipt_name = f'native-workspace/{operation}.json'
    if _file(root, receipt_name, required=False).exists():
        raise WorkspaceError('Generated receipt path already exists')
    backups = {name: f'backups/native-workspace-{operation}/{name}'
               for name, data in originals.items() if data is not None}
    for name in backups.values():
        if _file(root, name, required=False).exists():
            raise WorkspaceError('Generated backup path already exists')
    _idle(config, process_probe)
    # Preserve the whole old set before replacing any kit or readback file.
    for name, backup in backups.items():
        _write_atomic(_file(root, backup, required=False), originals[name])
    modified = []
    try:
        for name, data in payloads.items():
            path = _file(destination, name, required=False)
            # A concurrent edit invalidates the preflight; never overwrite it.
            current = _read(path) if path.exists() else None
            if current != originals[name]:
                raise WorkspaceError(f'Destination changed since preflight: {path}')
            _write_atomic(path, data)
            modified.append(name)
        result = {**report, 'status': 'copied-unverified', 'backups': backups,
                  'previous_files': {name: _record(data) if data is not None else None
                                     for name, data in originals.items()},
                  'receipt': receipt_name, 'operation_id': operation}
        _write_atomic(_file(root, receipt_name, required=False),
                      (json.dumps(result, indent=2) + '\n').encode())
        return result
    except Exception as error:
        # Best-effort rollback uses captured bytes. Backups remain for operator
        # recovery; a failure is raised rather than reported as a staged build.
        try:
            for name in reversed(modified):
                path = _file(destination, name, required=False)
                if not path.exists() or _read(path) != payloads[name]:
                    raise WorkspaceError(f'Concurrent edit prevents rollback: {path}')
                if originals[name] is None:
                    path.unlink()
                else:
                    _write_atomic(path, originals[name])
        except Exception as recovery:
            raise WorkspaceError(f'Transfer failed ({error}); rollback incomplete ({recovery}); '
                                 f'preserve backups/native-workspace-{operation}') from error
        raise WorkspaceError(f'Transfer failed and prior destinations restored: {error}; '
                             f'backups remain in backups/native-workspace-{operation}') from error


def stage(config: ProjectConfig, kind: str, *, replace=False, check=False, process_probe=None) -> dict:
    if kind not in READBACK:
        raise WorkspaceError(f'Unknown candidate kind: {kind}')
    root, kit = _kit(config)
    payloads, manifest = (_bootstrap if kind == 'bootstrap' else _progression)(root)
    originals = _destinations(kit, payloads, replace)
    _metadata_paths(root)
    probe = process_probe or probe_processes
    observed = _idle(config, probe)
    report = {'schema_version': 1, 'operation': 'stage', 'kind': kind,
              'status': 'preflight-passed', 'editing_kit': str(kit), 'manifest': manifest,
              'files': {name: _record(data) for name, data in payloads.items()},
              'process_preflight': observed, 'native_compilation_verified': False,
              'limitations': [LIMITATION]}
    return report if check else _publish(config, kit, payloads, originals, report, probe)


def readback(config: ProjectConfig, kind: str, *, replace=False, check=False, process_probe=None) -> dict:
    if kind not in READBACK:
        raise WorkspaceError(f'Unknown candidate kind: {kind}')
    root, kit = _kit(config)
    source = _file(kit, SCENARIO)
    data = _read(source)
    # This deliberately does not label the bytes as successfully compiled. A
    # fresh native save, its logs and binding readback are separate operator work.
    payloads = {READBACK[kind]: data}
    originals = _destinations(root, payloads, replace)
    _metadata_paths(root)
    probe = process_probe or probe_processes
    observed = _idle(config, probe)
    report = {'schema_version': 1, 'operation': 'readback', 'kind': kind,
              'status': 'preflight-passed', 'editing_kit': str(kit),
              'source': {'path': SCENARIO, **_record(data)},
              'files': {READBACK[kind]: _record(data)}, 'process_preflight': observed,
              'native_compilation_verified': False, 'limitations': [LIMITATION]}
    return report if check else _publish(config, root, payloads, originals, report, probe)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--replace', action='store_true', help='Back up existing destinations before replacement.')
    parser.add_argument('--check', action='store_true', help='Read-only full preflight, including process inspection.')
    parser.add_argument('mode', choices=('stage-bootstrap', 'stage-progression', 'readback'))
    parser.add_argument('--kind', choices=tuple(READBACK), help='Required only for readback.')
    args = parser.parse_args(argv)
    if (args.mode == 'readback') != (args.kind is not None):
        parser.error('--kind is required for readback and forbidden for staging modes')
    try:
        config = load_config(args.config, workspace=args.root)
        kind = args.kind if args.mode == 'readback' else args.mode.removeprefix('stage-')
        action = readback if args.mode == 'readback' else stage
        result = action(config, kind, replace=args.replace, check=args.check)
        print(json.dumps(result, indent=2))
        return 0
    except (ConfigError, WorkspaceError, OSError, subprocess.SubprocessError, TypeError) as error:
        print(f'Native workspace transfer failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
