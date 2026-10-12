"""Build/check/promote a privately validated Last Stand v0.4 cache on Onyx.

No action runs on import. `check` and `template` are read-only. `build` creates
a fresh cache and receipt; `promote` is the only action that replaces the package.
Neither registration nor the launcher is modified. Native validation is supplied
by the coordinating agent after observing the exact candidate in the engine.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import uuid

VERSION = '0.4.0'
VERSION_PARTS = {'Major': 0, 'Minor': 4, 'Patch': 0}
CHECKS = ('native_compile', 'overhead_camera', 'armory_input', 'automatic_attacks',
          'stage_transitions', 'enemy_stages', 'clock', 'ending',
          'checkpoint_restart', 'spawn_clearance', 'batched_levels')
WEAPONS = ('needler', 'assault_rifle', 'shotgun', 'plasma_rifle',
           'rocket_launcher', 'energy_sword')
DESCRIPTION = ('Birds-eye survival across four outdoor stages, with six automatic '
               'weapons and a 50-node skill tree. Upgrades carry between stages '
               'during the same run.')


class PromotionError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise PromotionError(message)


def utcnow():
    return datetime.now(timezone.utc)


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, TypeError, ValueError) as exc:
        raise PromotionError('Expected an ISO timestamp with timezone') from exc
    require(result.tzinfo is not None, 'Timestamps must include their timezone')
    return result.astimezone(timezone.utc)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def inside(path, root):
    resolved = Path(path).resolve()
    require(resolved.is_relative_to(Path(root).resolve()), f'Path is outside the workspace: {path}')
    return resolved


class Paths:
    def __init__(self, root=None, kit=None):
        self.root = Path(root or Path.home() / 'Documents/Games/Halo3Survivors').resolve()
        self.steam = Path.home() / 'snap/steam/common/.local/share/Steam'
        self.kit = Path(kit or self.steam / 'steamapps/common/H3EK').resolve()
        self.package = inside(self.root / 'mods/LastStand', self.root)
        self.cache = self.kit / 'maps/last_stand.map'
        self.scenario = self.kit / 'tags/levels/survivors/last_stand/last_stand.scenario'
        self.source = self.kit / 'data/levels/survivors/last_stand/scripts/last_stand.hsc'
        self.receipts = self.root / 'release-records'
        self.ids = self.root / 'package-ids.json'
        self.result = self.root / 'build-result.json'


def candidate(paths):
    for path in (paths.source, paths.scenario):
        require(path.is_file() and not path.is_symlink(), f'Missing/linked candidate input: {path}')
    require('LAST STAND v0.4' in paths.source.read_text(errors='replace')[:250],
            'Candidate HSC does not identify itself as Last Stand v0.4')
    asset_root = paths.kit / 'tags/objects/survivors'
    require(asset_root.is_dir(), 'Missing private survivor tags')
    files = sorted(path for path in asset_root.rglob('*') if path.is_file())
    ui = paths.kit / 'tags/ui/survivors/progression.multilingual_unicode_string_list'
    require(ui.is_file(), 'Missing progression UI tag')
    files.append(ui)
    manifest = []
    for path in files:
        require(not path.is_symlink(), f'Linked private asset: {path}')
        manifest.append([path.relative_to(paths.kit / 'tags').as_posix(), sha256(path)])
    require(any('/v3/' in name for name, _ in manifest), 'No shared private damage/effect tags')
    return {'source_hsc_sha256': sha256(paths.source), 'scenario_sha256': sha256(paths.scenario),
            'private_assets_sha256': hashlib.sha256(json.dumps(manifest, separators=(',', ':')).encode()).hexdigest(),
            'private_asset_files': len(manifest)}


def validation_template(paths):
    return {'schema_version': 1, 'candidate_version': VERSION,
            'validated_at': None, 'candidate': candidate(paths),
            'checks': {name: {'passed': False, 'evidence': ''} for name in CHECKS},
            'weapons_tested': [], 'stages_tested': [],
            'controls': {'next': 'Space', 'previous': 'Q', 'buy': 'Left mouse button',
                         'category': 'Space + Q', 'resume': '1', 'reopen': 'Space + Q'},
            'limitations': ['Solo prototype; full-run balance is not exhaustively tested.',
                            'SDK Armory checkpoints require the exact build; permanent unlocks, vehicles and physical XP pickups are not implemented.',
                            'Retail MCC loading awaits owner sign-in and menu verification.']}


def validate_record(record, fingerprint):
    require(record.get('schema_version') == 1 and type(record.get('schema_version')) is int,
            'Unsupported native validation schema')
    require(record.get('candidate_version') == VERSION, 'Native validation is not for '+VERSION)
    require(record.get('candidate') == fingerprint, 'Native validation does not match the current candidate')
    validated = timestamp(record.get('validated_at'))
    require(validated <= utcnow() + timedelta(minutes=1), 'Native validation timestamp is in the future')
    for name in CHECKS:
        check = record.get('checks', {}).get(name, {})
        require(check.get('passed') is True, f'Native check has not passed: {name}')
        require(isinstance(check.get('evidence'), str) and bool(check['evidence'].strip()),
                f'Native check requires concrete evidence: {name}')
    require(sorted(record.get('weapons_tested', [])) == sorted(WEAPONS),
            'Record must identify all six engine-tested automatic weapons exactly once')
    require(record.get('stages_tested') == [1, 2, 3, 4], 'Record must identify all four tested stages')
    for name in ('next', 'previous', 'buy', 'category', 'resume', 'reopen'):
        require(isinstance(record.get('controls', {}).get(name), str) and record['controls'][name].strip(),
                f'Missing verified control: {name}')
    require(isinstance(record.get('limitations'), list) and
            all(isinstance(item, str) for item in record['limitations']), 'Limitations must be a list of text')


def private_processes(paths):
    """Inspect only processes running in the private Last Stand Wine prefix."""
    if sys.platform != 'linux':
        return []
    prefix = str(paths.root / 'tool-prefix/pfx').encode()
    result = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            first = (proc / 'cmdline').read_bytes().split(b'\0')[0].decode(errors='replace')
            exe = first.replace('\\', '/').rsplit('/', 1)[-1].lower()
            if exe in {'tool.exe', 'sapien.exe', 'halo3_tag_test.exe'} and prefix in (proc / 'environ').read_bytes():
                result.append({'pid': int(proc.name), 'executable': exe})
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return result


@contextmanager
def release_lock(paths):
    require(sys.platform == 'linux', 'Build and promotion must run on Onyx-Linux')
    import fcntl
    with (paths.root / 'v03-release.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PromotionError('Another v0.4 build/promotion is active') from exc
        yield


def tool_exit_status(path, started, finished):
    """Read the status written by the inner shell, never infer it from Snap."""
    require(path.is_file() and not path.is_symlink(), 'Tool exit status is missing or linked')
    stat = path.stat()
    require(started.timestamp() - 2 <= stat.st_mtime <= finished.timestamp() + 2,
            'Tool exit status is outside the build time window')
    require(2 <= stat.st_size <= 4, 'Tool exit status is malformed')
    raw = path.read_bytes()
    require(re.fullmatch(rb'(0|[1-9][0-9]{0,2})\n', raw) is not None,
            'Tool exit status is malformed')
    code = int(raw)
    require(0 <= code <= 255, 'Tool exit status is malformed')
    return code


def build_cache(paths):
    """Own the fresh build so its exit code, timestamps and source hashes are known."""
    with release_lock(paths):
        require(not private_processes(paths), 'Close private Sapien/tag_test/tool before building')
        before = candidate(paths)
        paths.receipts.mkdir(parents=True, exist_ok=True)
        run_id = utcnow().strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        log = paths.receipts / (run_id + '.cache.log')
        tool_status = paths.receipts / (run_id + '.tool-exit')
        receipt_path = paths.receipts / (run_id + '.build.json')
        require(not tool_status.exists(), 'Tool exit status already exists for this build')
        previous_mtime = paths.cache.stat().st_mtime_ns if paths.cache.exists() else 0
        wine = paths.steam / 'steamapps/common/Proton - Experimental/files/bin/wine'
        args = ['env', 'WINEPREFIX=' + str(paths.root / 'tool-prefix/pfx'), 'DISPLAY=:0',
                'XAUTHORITY=/run/user/1000/gdm/Xauthority', 'WINEDEBUG=-all',
                'WINEDLLOVERRIDES=d3dcompiler_47=n,b', str(wine), str(paths.kit / 'tool.exe'),
                'build-cache-file', r'levels\survivors\last_stand\last_stand', 'pc', 'none', 'english']
        # Snap may fail in launcher cleanup after tool.exe has completed. Save
        # Wine's status before any cleanup command can overwrite the shell $?.
        # Disable errexit so a failing Wine process still writes its real code.
        shell = ('cd ' + shlex.quote(str(paths.kit)) + ' || exit $?\n'
                 'set +e\n' + shlex.join(args) + '\n'
                 'sv_tool_exit=$?\n'
                 'printf \'%s\\n\' "$sv_tool_exit" > ' + shlex.quote(str(tool_status)) + '\n'
                 'exit "$sv_tool_exit"')
        command = ['snap', 'run', '--shell', 'steam', '-c', shell]
        started = utcnow()
        print(json.dumps({'build_started': started.isoformat(), 'log': str(log)}), flush=True)
        with log.open('xb') as stream:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=False)
        finished = utcnow()
        output = log.read_text(errors='replace')
        native_exit = tool_exit_status(tool_status, started, finished)
        require(native_exit == 0, f'Cache tool exited {native_exit}; see {log}')
        require('successfully built cache file.' in output.lower(), f'Cache success marker missing: {log}')
        require('-fatal-' not in output.lower(), f'Cache log contains a fatal error: {log}')
        require(paths.cache.is_file() and paths.cache.stat().st_size > 1024 * 1024, 'Cache output missing or implausibly small')
        stat = paths.cache.stat()
        require(stat.st_mtime_ns > previous_mtime and stat.st_mtime >= started.timestamp() - 2,
                'Build did not replace the previous cache with a fresh output')
        require(candidate(paths) == before, 'Candidate inputs changed during the cache build')
        receipt = {'schema_version': 2, 'candidate_version': VERSION, 'candidate': before,
                   'started_at': started.isoformat(), 'finished_at': finished.isoformat(),
                   'exit_code': native_exit, 'launcher_exit_code': process.returncode,
                   'tool_status': str(tool_status.relative_to(paths.root)),
                   'tool_status_sha256': sha256(tool_status), 'log': str(log.relative_to(paths.root)),
                   'log_sha256': sha256(log), 'cache_sha256': sha256(paths.cache),
                   'cache_bytes': stat.st_size, 'cache_mtime_ns': stat.st_mtime_ns}
        write_json(receipt_path, receipt)
        print(json.dumps({'build_receipt': str(receipt_path), 'cache_sha256': receipt['cache_sha256']}), flush=True)
        return receipt_path


def package_metadata(paths):
    ids = read_json(paths.ids)
    require(set(ids) == {'mod', 'campaign', 'map'}, 'Unexpected package identity schema')
    files = {'ModInfo.json': read_json(paths.package / 'ModInfo.json'),
             'CampaignInfo.json': read_json(paths.package / 'CampaignInfo.json'),
             'campaign/last_stand.json': read_json(paths.package / 'campaign/last_stand.json')}
    require(files['ModInfo.json']['ModIdentifier']['ModGuid'] == ids['mod'], 'Mod GUID mismatch')
    require(files['CampaignInfo.json']['CampaignGuid'] == ids['campaign'], 'Campaign GUID mismatch')
    require(files['campaign/last_stand.json']['MapGuid'] == ids['map'], 'Map GUID mismatch')
    require(files['campaign/last_stand.json']['ScenarioFile'] == 'levels/survivors/last_stand/last_stand',
            'Scenario registration changed unexpectedly')
    require(files['CampaignInfo.json']['CampaignMaps'] == ['campaign/last_stand.json'],
            'Campaign map registration changed unexpectedly')
    return ids, files


def check_release(paths, receipt_path, validation_path):
    require(not private_processes(paths), 'Close private Sapien/tag_test/tool before checking promotion')
    receipt = read_json(receipt_path)
    require(receipt.get('schema_version') == 2 and type(receipt.get('schema_version')) is int,
            'Unsupported build receipt schema')
    require(receipt.get('candidate_version') == VERSION, 'Build receipt is not for '+VERSION)
    require(type(receipt.get('exit_code')) is int and receipt['exit_code'] == 0, 'Build did not exit successfully')
    started, finished = timestamp(receipt.get('started_at')), timestamp(receipt.get('finished_at'))
    require(started <= finished <= utcnow() + timedelta(minutes=1), 'Invalid build timestamps')
    require(utcnow() - finished <= timedelta(hours=24), 'Build receipt is older than 24 hours; rebuild before promotion')
    require(type(receipt.get('launcher_exit_code')) is int, 'Build launcher exit code is missing or invalid')
    status = inside(paths.root / receipt.get('tool_status', ''), paths.receipts)
    require(tool_exit_status(status, started, finished) == receipt['exit_code'],
            'Tool exit status disagrees with the build receipt')
    require(sha256(status) == receipt.get('tool_status_sha256'), 'Tool exit status changed after build')
    fingerprint = candidate(paths)
    require(receipt.get('candidate') == fingerprint, 'Build receipt does not match current candidate inputs')
    log = inside(paths.root / receipt.get('log', ''), paths.receipts)
    require(log.is_file() and sha256(log) == receipt.get('log_sha256'), 'Build log changed or is missing')
    require(log.stat().st_mtime >= started.timestamp() - 2, 'Build log is older than the build')
    text = log.read_text(errors='replace').lower()
    require('successfully built cache file.' in text and '-fatal-' not in text, 'Build log does not establish success')
    require(paths.cache.is_file() and not paths.cache.is_symlink(), 'Cache missing or linked')
    stat = paths.cache.stat()
    require(stat.st_size > 1024 * 1024 and stat.st_size == receipt.get('cache_bytes'), 'Cache size changed')
    require(stat.st_mtime_ns == receipt.get('cache_mtime_ns') and stat.st_mtime >= started.timestamp() - 2,
            'Cache is old or changed after the build receipt')
    require(sha256(paths.cache) == receipt.get('cache_sha256'), 'Cache hash changed after build')
    record = read_json(validation_path)
    validate_record(record, fingerprint)
    ids, metadata = package_metadata(paths)
    old_map = paths.package / 'maps/last_stand.map'
    require(old_map.is_file(), 'Existing package map is missing; refusing to replace an unknown baseline')
    old_hash = sha256(old_map)
    already = metadata['ModInfo.json']['ModVersion'] == VERSION_PARTS and old_hash == receipt['cache_sha256']
    require(already or old_hash != receipt['cache_sha256'], 'Candidate is the previously packaged map; refusing old-cache promotion')
    return {'receipt': receipt, 'validation': record, 'ids': ids, 'metadata': metadata,
            'old_sha256': old_hash, 'already_current': already}


def release_readme(info):
    record, receipt = info['validation'], info['receipt']
    controls = record['controls']
    limitations = '\n'.join('- ' + item for item in record['limitations'])
    evidence = '\n'.join('- ' + name.replace('_', ' ') + ': ' + record['checks'][name]['evidence'] for name in CHECKS)
    return f'''# Last Stand v{VERSION} — private development prototype

Bird's-eye Halo 3 survival across four outdoor stages, with a 50-node skill tree
and six automatic weapons: Needler, Assault Rifle, Shotgun, Plasma Rifle, Rocket
Launcher and Energy Sword. Attacks apply immediate damage; they do not simulate
travelling projectiles. Weapon specializations are mutually exclusive per run.
Health, shields, recovery, range and XP have additional support upgrades.

Purchased ranks, unlocked weapons and XP carry into the next stage of the same
run. The SDK launcher offers Continue from the latest Armory checkpoint or New Run.
Checkpoints preserve the entire encounter and require the exact build.
Enemy introductions progress from Grunts,
Jackals and Brutes to Captains/Snipers, Flood forms, and Hunters/Chieftain.

Move with WASD; firing is automatic. Armory controls verified for this candidate:
next {controls['next']}; previous {controls['previous']}; buy {controls['buy']};
category {controls['category']}; resume {controls['resume']}; reopen {controls['reopen']}.
Release menu buttons between actions. Enemies, automatic attacks and progression
pause in the Armory; movement remains available and the player stays protected.

Native validation recorded at {record['validated_at']}:
{evidence}

Known limitations:
{limitations}

The existing Last Stand desktop shortcut uses the official standalone test engine.
Retail MCC mod-menu loading remains unverified pending owner Xbox/Microsoft sign-in.
Vehicles, physical XP pickups and permanent unlocks between separate runs are not included.

Cache: {receipt['cache_bytes']} bytes; SHA-256 `{receipt['cache_sha256']}`.
Build receipt and exact native validation are included beside this README.
'''


def promote(paths, receipt_path, validation_path):
    with release_lock(paths):
        info = check_release(paths, receipt_path, validation_path)
        if info['already_current']:
            return {'status': 'already_current', 'version': VERSION, 'sha256': info['receipt']['cache_sha256']}
        for path in paths.package.rglob('*'):
            require(not path.is_symlink(), f'Package contains a symlink: {path}')
        token = utcnow().strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        stage = inside(paths.root / ('.v04-promotion-' + token), paths.root)
        backup = inside(paths.root / 'backups' / ('package-before-v04-' + token), paths.root)
        staged_package = stage / 'LastStand'
        stage.mkdir()
        try:
            shutil.copytree(paths.package, staged_package,
                            ignore=lambda folder, names: ['last_stand.map'] if Path(folder) == paths.package / 'maps' else [])
            shutil.copy2(paths.cache, staged_package / 'maps/last_stand.map')
            require(sha256(staged_package / 'maps/last_stand.map') == info['receipt']['cache_sha256'],
                    'Staged map copy failed verification')
            for relative, metadata in info['metadata'].items():
                metadata['Description']['Neutral'] = DESCRIPTION
                if relative == 'ModInfo.json':
                    metadata['ModVersion'] = VERSION_PARTS.copy()
                if relative == 'campaign/last_stand.json':
                    metadata['Title']['Neutral'] = 'Last Stand - Outdoor Stages'
                write_json(staged_package / relative, metadata)
            readme = release_readme(info)
            (staged_package / 'README.md').write_text(readme, encoding='utf-8')
            write_json(staged_package / 'native-validation.json', info['validation'])
            write_json(staged_package / 'cache-build-receipt.json', info['receipt'])
            result = read_json(paths.result) if paths.result.exists() else {}
            result.update(version=VERSION, map=str(paths.package / 'maps/last_stand.map'),
                          bytes=info['receipt']['cache_bytes'], sha256=info['receipt']['cache_sha256'],
                          ids=info['ids'], arena='Four Ark outdoor stages',
                          camera='Birds-eye; four outdoor arenas', automatic_fire=True,
                          built_at=info['receipt']['finished_at'], promoted_at=utcnow().isoformat(),
                          candidate=info['receipt']['candidate'],
                          native_validation=str(paths.package / 'native-validation.json'),
                          metadata_validation='Retail MCC menu/loading unverified; owner Xbox/Microsoft sign-in required')
            write_json(stage / 'build-result.json', result)
            (stage / 'README.md').write_text(readme, encoding='utf-8')
            # Recheck after the large copy, before moving any live package path.
            current = check_release(paths, receipt_path, validation_path)
            require(current['old_sha256'] == info['old_sha256'] and current['ids'] == info['ids'],
                    'Package changed while preparing promotion')
            backup.mkdir(parents=True)
            external = [(paths.result, stage / 'build-result.json', backup / 'build-result.json'),
                        (paths.root / 'project/README.md', stage / 'README.md', backup / 'project/README.md')]
            originals = {}
            for destination, _, saved in external:
                inside(destination, paths.root)
                originals[destination] = destination.exists()
                if destination.exists():
                    require(not destination.is_symlink(), f'External metadata is linked: {destination}')
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, saved)
            write_json(backup / 'backup-manifest.json', {'version_before': current['metadata']['ModInfo.json']['ModVersion'],
                       'ids': info['ids'], 'sha256_before': info['old_sha256'], 'backed_up_at': utcnow().isoformat()})
            os.replace(paths.package, backup / 'LastStand')
            installed = False
            try:
                os.replace(staged_package, paths.package)
                installed = True
                for destination, prepared, _ in external:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    temporary = destination.with_name(destination.name + '.v04-' + token)
                    shutil.copy2(prepared, temporary)
                    os.replace(temporary, destination)
            except Exception:
                if installed:
                    os.replace(paths.package, backup / 'failed-v04-package')
                os.replace(backup / 'LastStand', paths.package)
                for destination, _, saved in external:
                    if originals[destination]:
                        shutil.copy2(saved, destination)
                    elif destination.exists():
                        destination.unlink()
                raise
            return {'status': 'promoted', 'version': VERSION, 'sha256': info['receipt']['cache_sha256'],
                    'bytes': info['receipt']['cache_bytes'], 'backup': str(backup), 'ids': info['ids']}
        finally:
            # Only the exact staging directory created above is removed.
            require(stage.name.startswith('.v04-promotion-'), 'Unexpected staging cleanup path')
            if stage.exists():
                shutil.rmtree(inside(stage, paths.root))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['template', 'build', 'check', 'promote'])
    parser.add_argument('--root', type=Path)
    parser.add_argument('--kit', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--validation', type=Path)
    args = parser.parse_args()
    paths = Paths(args.root, args.kit)
    if args.action == 'template':
        print(json.dumps(validation_template(paths), indent=2))
    elif args.action == 'build':
        build_cache(paths)
    else:
        require(args.receipt is not None and args.validation is not None, '--receipt and --validation are required')
        if args.action == 'promote':
            print(json.dumps(promote(paths, args.receipt, args.validation), indent=2))
        else:
            info = check_release(paths, args.receipt, args.validation)
            print(json.dumps({'status': 'ready' if not info['already_current'] else 'already_current',
                              'version': VERSION, 'sha256': info['receipt']['cache_sha256'],
                              'bytes': info['receipt']['cache_bytes'], 'ids': info['ids']}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (PromotionError, OSError, ValueError, KeyError, TypeError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        raise SystemExit(2)
