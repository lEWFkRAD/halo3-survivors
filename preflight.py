"""Read-only prerequisites for source work, prepared authoring and native QA.

Presence checks do not establish native dependency closure or a playable build.
Remote checks send a standard-library probe over SSH; they never stage files,
run a game/tool, change a profile or control a native window.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from workspace_config import ConfigError, ProjectConfig, load_config

AUTHORING_SOURCES = (
    'prepare_progression.py', 'progression_tags.py', 'generate_progression.py',
    'progression_catalog.py', 'progression_hsc.py', 'author_progression_ui.py',
    'armory_presentation.py',
)
WEAPONS = ('needler', 'assault_rifle', 'shotgun', 'plasma_rifle',
           'rocket_launcher', 'energy_sword')
AUTHORING_INPUTS = (
    'native-tags/levels/survivors/last_stand/outdoor-compiled.scenario',
    'native-tags/ui/survivors/last_stand.multilingual_unicode_string_list',
    'private-inputs/v3/carrier.character',
    'private-inputs/v3/floodcarrier.biped',
    'private-inputs/v3/watchtower_base.device_machine',
    'private-inputs/v3/watchtower_gravlift.light',
) + tuple(f'private-inputs/v3/{weapon}.{kind}'
          for weapon in WEAPONS for kind in ('damage_effect', 'effect'))
AUTHORING_OUTPUTS = (
    'native-tags/levels/survivors/last_stand/progression.scenario',
    'native-tags/levels/survivors/last_stand/progression-ui.scenario',
    'native-tags/objects/survivors/v3',
    'native-tags/ui/survivors/progression.multilingual_unicode_string_list',
    'progression-layout.json', 'progression-contract.json',
    'source/progression.hsc', 'v3-native.tar', 'progression-build.json',
)
NATIVE_REQUIREMENTS = (
    ('tool.exe', 'file'), ('sapien.exe', 'file'),
    ('halo3_tag_test.exe', 'file'), ('tags', 'directory'), ('data', 'directory'),
    ('bin/x64/xaudio2_9redist.dll', 'file'),
    ('bin/x64/steam_api64.dll', 'file'),
    ('fmod/pc/sfx.fsb', 'file'), ('fmod/pc/english.fsb', 'file'),
    ('maps/fonts', 'directory'),
    ('tags/levels/survivors/last_stand/last_stand.scenario', 'file'),
    ('data/levels/survivors/last_stand/scripts/last_stand.hsc', 'file'),
    ('tags/ui/survivors/progression.multilingual_unicode_string_list', 'file'),
) + tuple(
    (f'tags/objects/survivors/v3/impact_{weapon}.effect', 'file')
    for weapon in WEAPONS)
LIMITATIONS = (
    'Prerequisites only: file presence does not verify contents, tag dependency '
    'closure, native compilation, retail compatibility or gameplay.',
    'Direct bootstrap requires an operator-verified native save/readback before '
    'progression authoring; these file checks do not validate it. See BOOTSTRAP.md.',
)


class ProbeError(RuntimeError):
    """A read-only remote check could not return a valid report."""


def path_check(path: Path, *, expected: str, hint: str) -> dict:
    good = path.is_file() if expected == 'file' else path.is_dir()
    return {'path': str(path), 'expected': expected,
            'status': 'ok' if good else ('wrong_type' if path.exists() else 'missing'),
            'hint': hint}


def output_safety(root: Path, relative: str, *, create_parents: bool = False) -> dict:
    """Reject authoring destinations redirected outside this workspace."""
    path = root / relative
    def linked_path(part):
        return part.is_symlink() or getattr(part, 'is_junction', lambda: False)()
    linked = any(linked_path(part) for part in (path, *path.parents)
                 if part == root or root in part.parents)
    safe = not linked and path.resolve().is_relative_to(root.resolve())
    parents_ok = all(not part.exists() or part.is_dir()
                     for part in path.parents if part == root or root in part.parents)
    directory = relative == 'native-tags/objects/survivors/v3'
    # Only the private-tag author creates its output directory. File authors
    # (notably the HSC generator) require their parent directory to exist.
    if not directory and not create_parents:
        parents_ok = parents_ok and path.parent.is_dir()
    kind_ok = not path.exists() or (path.is_dir() if directory else path.is_file())
    # The authored tag directory is flat. Check children too: an old linked tag
    # could otherwise redirect a write even when the directory itself is safe.
    children_ok = not directory or not path.is_dir() or all(
        not linked_path(child) and child.is_file() for child in path.iterdir())
    return {'path': str(path), 'expected': 'safe_output',
            'status': 'ok' if safe and parents_ok and kind_ok and children_ok else 'unsafe',
            'hint': 'Use unlinked output paths and existing file-output parents within the workspace.'}


def binding_available() -> bool:
    try:
        return importlib.util.find_spec('blam_tags') is not None
    except (ImportError, ValueError):
        return False


def make_report(stage: str, root, checks: list[dict]) -> dict:
    return {'schema_version': 1, 'stage': stage, 'workspace': str(root),
            'ready': all(c['status'] == 'ok' for c in checks),
            'checks': checks, 'limitations': list(LIMITATIONS)}


def inspect_workspace(config: ProjectConfig, stage: str,
                      *, binding_probe=None) -> dict:
    root = config.workspace
    checks = [path_check(root, expected='directory', hint='Use a source checkout directory.')]
    if stage == 'source':
        from bundle_source import SOURCE_FILES
        for name in SOURCE_FILES:
            checks.append(path_check(root / name, expected='file',
                                     hint='Restore the authored file from Git.'))
    elif stage == 'bootstrap':
        from bootstrap_tags import BOOTSTRAP_INPUTS, BOOTSTRAP_OUTPUTS, MANIFEST_PATH
        for name in ('bootstrap_tags.py', 'workspace_config.py') + BOOTSTRAP_INPUTS:
            item = path_check(root / name, expected='file',
                              hint='Fetch canonical owned inputs; see BOOTSTRAP.md.')
            if item['status'] == 'ok' and output_safety(root, name)['status'] != 'ok':
                item['status'] = 'unsafe'
            checks.append(item)
        probe = binding_probe or binding_available
        checks.append({'path': 'blam_tags', 'expected': 'python_module',
                       'status': 'ok' if probe() else 'missing',
                       'hint': 'Install the native binding described in DEVELOPMENT.md.'})
        checks.extend(output_safety(root, name, create_parents=True)
                      for name in BOOTSTRAP_OUTPUTS + (MANIFEST_PATH,))
    elif stage == 'authoring':
        for name in AUTHORING_SOURCES:
            checks.append(path_check(root / name, expected='file',
                                     hint='Restore the authoring source from Git.'))
        for name in AUTHORING_INPUTS:
            checks.append(path_check(root / name, expected='file',
                                     hint='Prepare this owned input; see BOOTSTRAP.md.'))
        probe = binding_probe or binding_available
        checks.append({'path': 'blam_tags', 'expected': 'python_module',
                       'status': 'ok' if probe() else 'missing',
                       'hint': 'Install the native binding described in DEVELOPMENT.md.'})
        checks.extend(output_safety(root, name) for name in AUTHORING_OUTPUTS)
    elif stage == 'native':
        if config.editing_kit is None:
            checks.append({'path': 'editing_kit', 'expected': 'configuration',
                           'status': 'missing',
                           'hint': 'Set editing_kit in the config or pass --tools PATH.'})
        else:
            checks.extend(path_check(config.editing_kit / name, expected=kind,
                                     hint='Prepare the owned SDK/staged candidate; see BOOTSTRAP.md.')
                          for name, kind in NATIVE_REQUIREMENTS)
    else:
        raise ValueError(f'Unknown preflight stage: {stage}')
    report = make_report(stage, root, checks)
    if stage == 'authoring':
        report['outputs'] = [str(root / name) for name in AUTHORING_OUTPUTS]
        report['limitations'].append('Binding discovery is checked here; authoring imports '
                                     'validate binding loadability before tag mutation.')
    return report


# No project imports or mutation APIs run on the remote host.
REMOTE_PROBE = '''import json,sys
from pathlib import Path
request=json.load(sys.stdin)
checks=[]
for item in request['paths']:
    path=Path(item['path'])
    good=path.is_file() if item['expected']=='file' else path.is_dir()
    checks.append(dict(item,status='ok' if good else ('wrong_type' if path.exists() else 'missing')))
print(json.dumps(dict(schema_version=1,stage='native',workspace=request['workspace'],
                     ready=all(c['status']=='ok' for c in checks),checks=checks,
                     limitations=request['limitations'])))
'''


def inspect_remote(config: ProjectConfig) -> dict:
    if shutil.which(config.ssh) is None:
        raise ProbeError(f'SSH executable is unavailable: {config.ssh}')
    paths = [{'path': config.remote_workspace, 'expected': 'directory',
              'hint': 'The configured remote workspace must already exist.'}]
    paths.extend({'path': config.remote_editing_kit.rstrip('/') + '/' + name,
                  'expected': kind, 'hint': 'Prepare the owned SDK/staged candidate; see BOOTSTRAP.md.'}
                 for name, kind in NATIVE_REQUIREMENTS)
    request = {'workspace': config.remote_workspace, 'paths': paths,
               'limitations': list(LIMITATIONS)}
    command = [config.ssh, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
               '-o', 'ConnectTimeout=10', '--', config.remote_host,
               shlex.join([config.remote_python, '-c', REMOTE_PROBE])]
    try:
        result = subprocess.run(command, input=json.dumps(request), text=True,
                                capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ProbeError(f'Remote preflight did not complete: {error}') from error
    if result.returncode:
        raise ProbeError(f'Remote preflight failed ({result.returncode}): '
                         f'{result.stderr.strip()[:500]}')
    try:
        report = json.loads(result.stdout)
        if (type(report['schema_version']) is not int or report['schema_version'] != 1
                or report['stage'] != 'native'
                or report['workspace'] != config.remote_workspace
                or not isinstance(report['checks'], list)
                or len(report['checks']) != len(paths)
                or type(report['ready']) is not bool
                or report['limitations'] != list(LIMITATIONS)):
            raise ValueError('Invalid report header')
        for actual, expected in zip(report['checks'], paths):
            if (not all(actual[key] == value for key, value in expected.items())
                    or actual['status'] not in ('ok', 'missing', 'wrong_type')):
                raise ValueError('Invalid path check')
        if report['ready'] != all(c['status'] == 'ok' for c in report['checks']):
            raise ValueError('Inconsistent readiness')
    except (ValueError, KeyError, TypeError) as error:
        raise ProbeError('Remote preflight returned an invalid report.') from error
    return report


def print_report(report: dict, *, as_json=False) -> None:
    if as_json:
        print(json.dumps(report, indent=2))
        return
    failures = [item for item in report['checks'] if item['status'] != 'ok']
    print(f"{report['stage']}: {'READY' if report['ready'] else 'BLOCKED'} "
          f"({len(report['checks']) - len(failures)}/{len(report['checks'])} prerequisites)")
    for item in failures:
        print(f"  {item['status'].upper()}: {item['path']} ({item['expected']})")
        print(f"    {item['hint']}")
    for limitation in report['limitations']:
        print(limitation)


def check(root):
    """Compatibility entry point for the original --tools-only checker."""
    config = replace(load_config(), editing_kit=Path(root).resolve())
    report = inspect_workspace(config, 'native')
    print_report(report)
    return 0 if report['ready'] else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--root', type=Path, help='Source workspace (default: this checkout).')
    parser.add_argument('--stage', choices=('source', 'bootstrap', 'authoring', 'native'))
    parser.add_argument('--tools', type=Path, help='Override local editing_kit; defaults stage to native.')
    parser.add_argument('--remote', action='store_true', help='Check native files over read-only SSH.')
    parser.add_argument('--json', action='store_true', help='Emit a structured report.')
    args = parser.parse_args(argv)
    stage = args.stage or ('native' if args.tools or args.remote else 'source')
    if args.remote and (stage != 'native' or args.tools):
        parser.error('--remote requires native stage and uses remote.editing_kit, not --tools')
    try:
        config = load_config(args.config, workspace=args.root)
        if args.tools:
            config = replace(config, editing_kit=args.tools.expanduser().resolve())
        report = inspect_remote(config) if args.remote else inspect_workspace(config, stage)
        print_report(report, as_json=args.json)
        return 0 if report['ready'] else 2
    except (ConfigError, ProbeError, OSError) as error:
        if args.json:
            print(json.dumps({'schema_version': 1, 'stage': stage, 'ready': False,
                              'error': str(error)}))
        else:
            print(f'Preflight failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
