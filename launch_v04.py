#!/usr/bin/env python3
"""Save-aware standalone Halo 3 launcher; importing this module performs no work."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid

VERSION = '0.4.0'
MIN_CORE, MAX_CORE = 1024 * 1024, 64 * 1024 * 1024
SCENARIO = r'levels\survivors\last_stand\last_stand'
PREAMBLE = '(events_suppress_console_display true)\n(set ai_render false)\n'


class SaveError(RuntimeError):
    pass


@dataclass
class Paths:
    root: Path
    kit: Path
    profile: Path | None = None

    def __post_init__(self):
        self.root = self.root.resolve()
        self.kit = self.kit.resolve()
        self.production = self.root / 'saves/v04'
        self.qa = self.profile is not None
        self.profile = self.profile.resolve() if self.profile else self.production
        qa_base = (self.root / 'qa-saves').resolve()
        if self.qa and (self.profile == qa_base or not self.profile.is_relative_to(qa_base)):
            raise SaveError('QA profiles must be inside ROOT/qa-saves')
        self.current = self.profile / 'CURRENT'
        self.pending = self.kit / 'core/laststand_v04_pending.bin'
        self.resume = self.kit / 'core/laststand_v04_resume.bin'
        self.init = self.kit / 'init.txt'
        self.prefix = self.root / 'tool-prefix/pfx'
        self.steam = self.kit.parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise SaveError(f'Missing or linked file: {path}')
    return path.read_bytes()


def fingerprint(paths):
    fixed = {
        'engine': paths.kit / 'halo3_tag_test.exe',
        'scenario': paths.kit / 'tags/levels/survivors/last_stand/last_stand.scenario',
        'hsc': paths.kit / 'data/levels/survivors/last_stand/scripts/last_stand.hsc',
    }
    result = {name: digest(regular(path)) for name, path in fixed.items()}
    assets = []
    # Include legacy private equipment still referenced by the scenario, too.
    for folder in ('objects/survivors', 'ui/survivors'):
        base = paths.kit / 'tags' / folder
        if base.is_symlink() or not base.is_dir():
            raise SaveError(f'Missing or linked private asset directory: {base}')
        files = sorted(base.rglob('*'))
        if not any(p.is_file() for p in files):
            raise SaveError(f'Empty private asset directory: {base}')
        for path in files:
            if path.is_symlink():
                raise SaveError(f'Linked private asset: {path}')
            if path.is_file():
                assets.append([path.relative_to(paths.kit / 'tags').as_posix(), digest(regular(path))])
    result['private_assets'] = digest(json.dumps(assets, separators=(',', ':')).encode())
    return result


def core_bytes(path):
    if path.is_symlink() or not path.is_file():
        raise SaveError('Checkpoint file is missing or linked')
    before = path.stat()
    if not MIN_CORE <= before.st_size <= MAX_CORE:
        raise SaveError('Checkpoint size is outside the supported 1–64 MiB range')
    data = path.read_bytes()
    after = path.stat()
    signature = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    if signature(before) != signature(after) or len(data) != before.st_size:
        raise SaveError('Checkpoint is still being written')
    # The native core header is opaque; do not invent a magic/header validator.
    return data, signature(after)


def read_json(path, limit=16384):
    if path.stat().st_size > limit:
        raise SaveError(f'Metadata is too large: {path.name}')
    return json.loads(regular(path).decode('utf-8'))


def validate_save(paths, compatibility=None):
    """Read-only validation, including on corrupt/incompatible profiles."""
    if not paths.current.exists() and not paths.current.is_symlink():
        return {'found': False, 'valid': False, 'reason': 'No saved run'}
    try:
        pointer = read_json(paths.current, 4096)
        generation = pointer['generation']
        if not isinstance(generation, str) or re.fullmatch('[0-9a-f]{32}', generation) is None:
            raise SaveError('Invalid checkpoint generation pointer')
        folder = paths.profile / 'generations' / generation
        if folder.is_symlink():
            raise SaveError('Linked checkpoint generation')
        metadata = read_json(folder / 'metadata.json')
        if not isinstance(metadata, dict):
            raise SaveError('Checkpoint metadata must be an object')
        if type(metadata.get('schema_version')) is not int or metadata['schema_version'] != 1 or metadata.get('format') != 'laststand.native-core':
            raise SaveError('Unsupported checkpoint format')
        if metadata.get('generation') != generation or metadata.get('mod_version') != VERSION:
            raise SaveError('Checkpoint version/generation mismatch')
        if metadata.get('origin') != ('qa' if paths.qa else 'production'):
            raise SaveError('Checkpoint belongs to a different launcher mode')
        if metadata.get('fingerprint') != (compatibility or fingerprint(paths)):
            raise SaveError('Checkpoint is incompatible with this exact engine/scenario/source/assets build')
        data, _ = core_bytes(folder / 'core.bin')
        if type(metadata.get('bytes')) is not int or metadata['bytes'] != len(data) or metadata.get('sha256') != digest(data):
            raise SaveError('Checkpoint content is corrupt or changed')
        return {'found': True, 'valid': True, 'reason': 'Verified Armory checkpoint',
                'metadata': metadata, 'core': folder / 'core.bin'}
    except (SaveError, OSError, ValueError, KeyError, TypeError) as exc:
        return {'found': True, 'valid': False, 'reason': str(exc)}


def fsync_dir(path):
    if hasattr(os, 'O_DIRECTORY'):
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise SaveError(f'Refusing linked output: {path}')
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def commit_core(paths, data, compatibility, session):
    if not MIN_CORE <= len(data) <= MAX_CORE:
        raise SaveError('Refusing implausible checkpoint size')
    if fingerprint(paths) != compatibility:
        raise SaveError('Build inputs changed during play; checkpoint was not committed')
    generation = uuid.uuid4().hex
    folder = paths.profile / 'generations' / generation
    folder.mkdir(parents=True, exist_ok=False)
    metadata = {'schema_version': 1, 'format': 'laststand.native-core', 'mod_version': VERSION,
                'generation': generation, 'session_id': session, 'created_at': now(),
                'origin': 'qa' if paths.qa else 'production', 'name': 'Armory checkpoint',
                'fingerprint': compatibility, 'bytes': len(data), 'sha256': digest(data)}
    atomic_bytes(folder / 'core.bin', data)
    atomic_bytes(folder / 'metadata.json', (json.dumps(metadata, indent=2) + '\n').encode())
    fsync_dir(folder)
    fsync_dir(folder.parent)
    # A crash before this commit point leaves the previous generation active.
    atomic_bytes(paths.current, (json.dumps({'generation': generation}) + '\n').encode())
    return metadata


def archive_file(paths, path, label):
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            raise SaveError(f'Refusing to archive a linked file: {path}')
        destination = paths.profile / 'archives' / (uuid.uuid4().hex + '-' + label)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Copy durably before unlinking: kit and profile may be on different disks.
        atomic_bytes(destination, regular(path))
        path.unlink()
        fsync_dir(path.parent)
        return destination


class CheckpointWatcher:
    def __init__(self, paths, compatibility, session, report, stable_seconds=2.0):
        self.paths, self.compatibility, self.session = paths, compatibility, session
        self.report, self.stable_seconds = report, stable_seconds
        self.seen = None
        self.since = 0.0
        self.content = None
        self.content_since = 0.0
        self.committed = None
        self.last_error = None

    def poll(self, moment):
        try:
            stat = self.paths.pending.stat()
            signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
            if signature != self.seen:
                self.seen, self.since, self.content = signature, moment, None
                return
            if moment - self.since < self.stable_seconds or signature == self.committed:
                return
            # Normal native writes may temporarily be empty/partial. Only inspect
            # content after stat stability, then require two matching full reads.
            data, confirmed = core_bytes(self.paths.pending)
            if confirmed != signature:
                self.seen = None
                return
            identity = (confirmed, digest(data))
            if identity != self.content:
                self.content, self.content_since = identity, moment
                return
            if moment - self.content_since < .5:
                return
            metadata = commit_core(self.paths, data, self.compatibility, self.session)
            self.committed = signature
            self.last_error = None
            self.report('Checkpoint saved: ' + metadata['created_at'], False)
        except FileNotFoundError:
            self.seen, self.content = None, None
        except (SaveError, OSError, ValueError) as exc:
            if str(exc) == 'Checkpoint is still being written' or not self.paths.pending.exists():
                self.seen, self.content = None, None
                return
            message = 'Checkpoint not saved: ' + str(exc)
            if message != self.last_error:
                self.report(message, True)
                self.last_error = message


def native_children(paths, proc_root=Path('/proc')):
    """Match exact Wine prefix entries, not substring matches or unrelated Wine."""
    found = []
    expected = b'WINEPREFIX=' + os.fsencode(paths.prefix)
    for proc in proc_root.iterdir():
        if not proc.name.isdigit():
            continue
        try:
            stat = (proc / 'stat').read_text()
            if stat[stat.rfind(')') + 2:].startswith('Z'):
                continue
            env = (proc / 'environ').read_bytes().split(b'\0')
            command = (proc / 'cmdline').read_bytes().split(b'\0')
            executable = command[0].decode(errors='replace').replace('\\', '/').rsplit('/', 1)[-1].lower()
            if expected in env and executable in ('halo3_tag_test.exe', 'sapien.exe', 'tool.exe'):
                found.append(int(proc.name))
        except (FileNotFoundError, PermissionError, ProcessLookupError, IndexError):
            continue
    return found


@contextmanager
def launcher_lock(paths):
    import fcntl  # Linux only; import remains safe for Windows unit tests.
    with (paths.root / 'play.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SaveError('Last Stand is already running') from exc
        yield


def choose_run(status):
    if not status['found']:
        return 'new'
    if status['valid']:
        args = ['zenity', '--question', '--title=Last Stand', '--width=640',
                '--text=Continue your saved run or start a new run.\nNew Run archives the previous save.',
                '--ok-label=Continue', '--cancel-label=Cancel', '--extra-button=New Run']
        result = subprocess.run(args, stdin=subprocess.DEVNULL, text=True, capture_output=True, check=False)
        if result.stdout.strip() == 'New Run':
            return 'new'
        return 'continue' if result.returncode == 0 else None
    result = subprocess.run(['zenity', '--question', '--title=Last Stand', '--ok-label=New Run',
                             '--cancel-label=Cancel', '--text=Saved run cannot be continued: ' + status['reason'] +
                             '\nThe original will be preserved. Start a new run?'], check=False)
    return 'new' if result.returncode == 0 else None


@contextmanager
def temporary_init(paths, mode, session):
    original = regular(paths.init) if paths.init.exists() else None
    folder = paths.profile / 'launcher-sessions' / session
    folder.mkdir(parents=True, exist_ok=False)
    if original is not None:
        atomic_bytes(folder / 'init-before.txt', original)
    command = 'game_start ' + SCENARIO if mode == 'new' else '(core_load_game_name "laststand_v04_resume")'
    content = (PREAMBLE + command + '\n').encode()
    try:
        atomic_bytes(paths.init, content)
        yield folder
    finally:
        try:
            if paths.init.exists() and regular(paths.init) != content:
                atomic_bytes(folder / 'init-external-change.txt', regular(paths.init))
        finally:
            if original is None:
                paths.init.unlink(missing_ok=True)
                fsync_dir(paths.init.parent)
            else:
                atomic_bytes(paths.init, original)


def game_command(paths):
    wine = paths.steam / 'steamapps/common/Proton - Experimental/files/bin/wine'
    args = ['env', 'WINEPREFIX=' + str(paths.prefix), 'DISPLAY=:0',
            'XAUTHORITY=/run/user/1000/gdm/Xauthority', 'WINEDEBUG=-all',
            'WINEDLLOVERRIDES=d3dcompiler_47=n,b', str(wine), str(paths.kit / 'halo3_tag_test.exe'),
            '-window', '1600', '900']
    return ['snap', 'run', '--shell', 'steam', '-c',
            'cd ' + shlex.quote(str(paths.kit)) + ' && ' + shlex.join(args)]


def monitor(process, children, watcher, report, *, clock=time.monotonic, sleep=time.sleep):
    """Do not restore init/release ownership while the native child still lives."""
    empty_since = None
    seen_child = False
    while True:
        moment = clock()
        alive = children()
        seen_child = seen_child or bool(alive)
        safe_poll(watcher, moment, report)
        outer = process.poll()
        if outer is not None and not alive:
            if empty_since is None:
                empty_since = moment
            # Also allow a detached Wine child time to appear after wrapper exit.
            grace = 2.5 if seen_child else 10.0
            if moment - empty_since >= grace:
                if outer:
                    safe_report(report, f'Snap launcher exited {outer}; checkpoint watcher finished after native processes exited.', False)
                return outer
        else:
            empty_since = None
        sleep(.5)


def safe_report(report, message, failure):
    try:
        report(message, failure)
    except Exception:
        # A closed desktop stderr/notification sink cannot release live-game ownership.
        pass


def safe_poll(watcher, moment, report):
    try:
        watcher.poll(moment)
    except Exception as exc:
        safe_report(report, 'Checkpoint watcher error: ' + str(exc), True)


def launch(paths, mode, compatibility, report):
    if native_children(paths):
        raise SaveError('Close private Halo/Sapien/tool processes before launching')
    if fingerprint(paths) != compatibility:
        raise SaveError('Build inputs changed while choosing a run; saved progress was preserved')
    status = validate_save(paths, compatibility)
    if mode == 'continue':
        if not status['valid']:
            raise SaveError(status['reason'])
        data, _ = core_bytes(status['core'])
        if digest(data) != status['metadata']['sha256']:
            raise SaveError('Checkpoint changed before Continue')
        atomic_bytes(paths.resume, data)
    elif mode == 'new':
        archive_file(paths, paths.current, 'previous-CURRENT.json')
    else:
        raise SaveError('Unknown launch mode')
    archive_file(paths, paths.pending, 'stale-pending.bin')
    session = uuid.uuid4().hex
    watcher = CheckpointWatcher(paths, compatibility, session, report)
    with temporary_init(paths, mode, session) as folder:
        with (folder / 'play.log').open('wb') as stream:
            # Signals request native shutdown; never restore init beneath a live child.
            process = None
            previous = {}
            original_error = None
            def stop(signum, frame):
                safe_report(report, 'Launcher stopping: requesting the private game to close.', False)
                for pid in native_children(paths):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                if process is not None and process.poll() is None:
                    process.terminate()
            try:
                for number in (signal.SIGINT, signal.SIGTERM):
                    previous[number] = signal.signal(number, stop)
                process = subprocess.Popen(game_command(paths), stdout=stream, stderr=subprocess.STDOUT)
                safe_report(report, 'Game log: ' + str(folder / 'play.log'), False)
                return monitor(process, lambda: native_children(paths), watcher, report)
            except BaseException as exc:
                original_error = exc
                raise
            finally:
                try:
                    # Unexpected monitor failures also wait for the exact-prefix child.
                    while process is not None and (process.poll() is None or native_children(paths)):
                        safe_poll(watcher, time.monotonic(), report)
                        time.sleep(.5)
                    if process is not None:
                        try:
                            # The kit's pending path is shared between profiles. Once
                            # native writers are gone, preserve even partial bytes in
                            # this session's profile so the next launch cannot adopt
                            # them as its own stale checkpoint. Never update CURRENT.
                            archive_file(paths, paths.pending, 'session-pending.bin')
                        except Exception as exc:
                            message = ('Pending checkpoint cleanup failed for profile '
                                       + str(paths.profile) + ': ' + str(exc))
                            safe_report(report, message, True)
                            if original_error is None:
                                raise
                            if hasattr(original_error, 'add_note'):
                                original_error.add_note(message)
                finally:
                    for number, handler in previous.items():
                        signal.signal(number, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--kit', type=Path, default=Path.home() / 'snap/steam/common/.local/share/Steam/steamapps/common/H3EK')
    parser.add_argument('--qa-profile', type=Path, help='Isolated profile strictly inside ROOT/qa-saves')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--new', action='store_true')
    group.add_argument('--continue', dest='continue_run', action='store_true')
    parser.add_argument('--validate', action='store_true', help='Print checkpoint validation without modifying anything')
    args = parser.parse_args()
    notices = set()
    def report(message, failure=False):
        print(message, file=sys.stderr, flush=True)
        if failure and not args.validate and message not in notices:
            notices.add(message)
            try:
                subprocess.Popen(['zenity', '--warning', '--title=Last Stand checkpoint', '--text=' + message],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
    try:
        paths = Paths(args.root, args.kit, args.qa_profile)
        compatibility = fingerprint(paths)
        if args.validate:
            print(json.dumps(validate_save(paths, compatibility), default=str, indent=2))
            return 0
        with launcher_lock(paths):
            status = validate_save(paths, compatibility)
            mode = 'new' if args.new else 'continue' if args.continue_run else choose_run(status)
            return launch(paths, mode, compatibility, report) if mode else 0
    except (SaveError, OSError, ValueError) as exc:
        report(str(exc), True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
