"""Prepare progression in isolation, then publish an exact, hashed output set.

Authoring and archive failures leave existing outputs untouched. Publication uses
individual atomic replacements; replacing the complete output set is not atomic.
The build manifest is published last so consumers can verify a complete set.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile

from preflight import AUTHORING_INPUTS, inspect_workspace, print_report
from workspace_config import ConfigError, load_config

ROOT = Path(__file__).resolve().parent
OPTIONAL_INPUTS = ('private-inputs/v3/character-paths.json',)
FIXED_OUTPUTS = frozenset((
    'native-tags/levels/survivors/last_stand/progression.scenario',
    'native-tags/levels/survivors/last_stand/progression-ui.scenario',
    'native-tags/ui/survivors/progression.multilingual_unicode_string_list',
    'progression-layout.json', 'progression-contract.json', 'source/progression.hsc',
))
PRIVATE_TAG = re.compile(
    r'native-tags/objects/survivors/v3/[a-z][a-z0-9_]*\.'
    r'(?:light|device_machine|biped|character|damage_effect|effect)\Z')
UI_OUTPUT = 'native-tags/ui/survivors/progression.multilingual_unicode_string_list'


def _safe_file(root: Path, relative: str, *, required: bool) -> Path:
    """Require a regular, unlinked file within the given workspace."""
    path = root / relative
    if (Path(relative).is_absolute() or '..' in Path(relative).parts
            or not path.resolve().is_relative_to(root.resolve())):
        raise ValueError(f'Path escapes the workspace: {relative}')
    for part in (path, *path.parents):
        if part != root and root not in part.parents:
            continue
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError(f'Linked path is not supported: {part}')
        if part != path and part.exists() and not part.is_dir():
            raise ValueError(f'Output parent is not a directory: {part}')
    if (required and not path.is_file()) or (path.exists() and not path.is_file()):
        raise ValueError(f'Expected a regular file: {path}')
    return path


def _record(path: Path) -> dict:
    content = path.read_bytes()
    return {'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content)}


def _declared_outputs(stage: Path, declared) -> dict[str, Path]:
    result = {}
    for item in declared:
        path = Path(item)
        if not path.is_absolute():
            raise ValueError(f'Author must return an absolute written path: {path}')
        try:
            relative = path.relative_to(stage).as_posix()
        except ValueError as error:
            raise ValueError(f'Author declared an output outside staging: {path}') from error
        if relative not in FIXED_OUTPUTS and not PRIVATE_TAG.fullmatch(relative):
            raise ValueError(f'Unexpected authored output: {relative}')
        if relative in result:
            raise ValueError(f'Duplicate authored output: {relative}')
        result[relative] = _safe_file(stage, relative, required=True)
    missing = FIXED_OUTPUTS - result.keys()
    if missing:
        raise ValueError('Authors omitted required outputs: ' + ', '.join(sorted(missing)))
    return result


def _archive(stage: Path, outputs: dict[str, Path]) -> list[str]:
    """Only declared private tags and the declared UI enter the native archive."""
    names = sorted(name for name in outputs if PRIVATE_TAG.fullmatch(name) or name == UI_OUTPUT)
    members = []
    with tarfile.open(stage / 'v3-native.tar', 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name in names:
            path = _safe_file(stage, name, required=True)
            member = path.relative_to(stage / 'native-tags').as_posix()
            info = tarfile.TarInfo(member)
            info.size = path.stat().st_size
            info.mode = 0o644
            # All other metadata retains TarInfo's stable zero/empty defaults.
            with path.open('rb') as source:
                archive.addfile(info, source)
            members.append(member)
    return members


def prepare(config, tags, generator, ui, *, source_modules=()) -> dict:
    """Run already-loaded authors against copied inputs and publish their outputs."""
    root = config.workspace
    input_names = list(AUTHORING_INPUTS)
    input_names.extend(name for name in OPTIONAL_INPUTS if (root / name).exists()
                       or (root / name).is_symlink())
    inputs = {name: _safe_file(root, name, required=True) for name in input_names}
    # Hash the actual loaded implementations, not possibly different files in
    # --root. A separate root selects owned inputs and outputs, not Python code.
    sources = {}
    for module in source_modules:
        path = Path(module.__file__).resolve()
        sources[path.name] = _record(path)
    sources[Path(__file__).name] = _record(Path(__file__))
    with tempfile.TemporaryDirectory(prefix='.last-stand-prepare-', dir=root) as temporary:
        stage = Path(temporary).resolve()
        input_records = {}
        for name, source in inputs.items():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            input_records[name] = _record(target)
        (stage / 'source').mkdir()
        declared = [*tags.main(root=stage), *generator.main(root=stage),
                    *tags.author_damage(root=stage), *ui.main(root=stage)]
        outputs = _declared_outputs(stage, declared)
        # An author's forgotten return entry must not silently disappear from
        # the receipt. Neither may an author rewrite its input snapshot.
        actual = {path.relative_to(stage).as_posix() for path in stage.rglob('*') if path.is_file()}
        if actual != set(inputs) | set(outputs):
            raise ValueError('Authors wrote undeclared files or removed input files.')
        if any(_record(stage / name) != record for name, record in input_records.items()):
            raise ValueError('Authoring modified an owned input snapshot.')
        members = _archive(stage, outputs)
        manifest = {
            'schema_version': 1,
            'stage': 'authored',
            'native_compilation_required': True,
            'inputs': input_records,
            'sources': sources,
            'outputs': {name: _record(path) for name, path in sorted(outputs.items())},
            'archive': {'path': 'v3-native.tar', **_record(stage / 'v3-native.tar'),
                        'members': members},
        }
        receipt = stage / 'progression-build.json'
        receipt.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        outputs['v3-native.tar'] = stage / 'v3-native.tar'
        outputs['progression-build.json'] = receipt
        # Recheck the live destination set immediately before publication.
        report = inspect_workspace(config, 'authoring')
        if not report['ready']:
            raise ValueError('Authoring destinations changed after preflight; nothing was published.')
        for name in outputs:
            _safe_file(root, name, required=False)
        for name, source in outputs.items():
            target = _safe_file(root, name, required=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, target)
        return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--root', type=Path, help='Owned inputs/output workspace (default: this checkout).')
    parser.add_argument('--check', action='store_true', help='Read-only prerequisites; do not author tags.')
    parser.add_argument('--json', action='store_true', help='Structured report (requires --check).')
    args = parser.parse_args(argv)
    if args.json and not args.check:
        parser.error('--json requires --check')
    try:
        config = load_config(args.config, workspace=args.root or ROOT)
        report = inspect_workspace(config, 'authoring')
        print_report(report, as_json=args.json)
        if not report['ready']:
            return 2
        if args.check:
            return 0
        # Load every implementation before creating even the staging directory,
        # including transitive helpers and the native binding.
        names = ('progression_tags', 'generate_progression', 'author_progression_ui',
                 'progression_catalog', 'progression_hsc', 'armory_presentation',
                 'workspace_config', 'preflight')
        modules = {name: importlib.import_module(name) for name in names}
        prepare(config, modules['progression_tags'], modules['generate_progression'],
                modules['author_progression_ui'], source_modules=modules.values())
        print('Prepared native tags and scripts; hashes are in progression-build.json. '
              'Engine compilation still required.')
        return 0
    except (ConfigError, ImportError, SyntaxError, OSError, ValueError, TypeError,
            AssertionError) as error:
        if args.json:
            print(json.dumps({'schema_version': 1, 'stage': 'authoring',
                              'ready': False, 'error': str(error)}))
        else:
            print(f'Preparation failed: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
