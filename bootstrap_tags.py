"""Author an outdoor baseline directly from three owned, stock H3EK tags.

This module neither imports the native binding nor writes files on import. The
result still needs a native save/readback before progression authoring; it does
not assert that stock navigation equals the historical prepared baseline.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from workspace_config import ConfigError, ProjectConfig, load_config


BOOTSTRAP_INPUTS = (
    'private-inputs/bootstrap/020_base.scenario',
    'private-inputs/bootstrap/070_waste.scenario',
    'private-inputs/bootstrap/020_base.multilingual_unicode_string_list',
)
BOOTSTRAP_OUTPUTS = (
    'native-tags/levels/survivors/last_stand/bootstrap.scenario',
    'native-tags/levels/survivors/last_stand/bootstrap.hsc',
    'native-tags/ui/survivors/last_stand.multilingual_unicode_string_list',
)
MANIFEST_PATH = 'native-tags/levels/survivors/last_stand/bootstrap-manifest.json'
BOOTSTRAP_HSC = b'; Baseline compile only; no scenario object or script bindings.\n(script startup sv_bootstrap\n    (sleep 1)\n)\n'
CLEAR_BLOCKS = (
    'scripts', 'globals', 'source files', 'hs syntax datums', 'references',
    'scenario resources', 'zone set switch trigger volumes',
    'scenario kill triggers', 'scenario safe zone triggers', 'bipeds',
    'vehicles', 'giants', 'cinematics', 'mission scenes', 'hs unit seats',
    'equipment', 'weapons', 'scripting data', 'squad groups', 'creatures',
    'flocks', 'cutscene flags', 'cutscene camera points', 'trigger volumes',
)
# Progression currently addresses these palettes by index. Fail on incompatible
# stock inputs rather than silently assigning the wrong enemy or weapon.
CHARACTER_IDENTITIES = {
    2: r'objects\characters\brute\ai\brute',
    3: r'objects\characters\grunt\ai\grunt',
    4: r'objects\characters\jackal\ai\jackal',
    9: r'objects\characters\brute\ai\brute_captain',
    11: r'objects\characters\brute\ai\brute_chieftain_armor',
    13: r'objects\characters\jackal\ai\jackal_sniper',
    19: r'objects\characters\hunter\ai\hunter',
}
WEAPON_IDENTITIES = {
    0: r'objects\weapons\rifle\smg\smg',
    2: r'objects\weapons\rifle\spike_rifle\spike_rifle',
    4: r'objects\weapons\pistol\plasma_pistol\plasma_pistol',
    6: r'objects\weapons\support_low\brute_shot\brute_shot',
    10: r'objects\weapons\melee\gravity_hammer\gravity_hammer',
    17: r'objects\weapons\rifle\beam_rifle\beam_rifle',
}
FLOOD_CHARACTER = r'objects\characters\floodcombat_human\ai\flood_combat_human'
ASSAULT_RIFLE = r'objects\weapons\rifle\assault_rifle\assault_rifle'


class BootstrapError(ValueError):
    """Inputs, destinations or stock template identities are unsuitable."""


class BootstrapRecoveryError(BootstrapError):
    """Publication rollback failed; recovery files must be retained."""


def block(row, name):
    return row.field(name).as_block()


def put(row, name, value):
    field = row.field(name)
    if field is None:
        raise BootstrapError(f'Missing required native field: {name}')
    if 'flags' in field.type_name and isinstance(value, list):
        for flag in list(field.value):
            field.set_flag(flag, False)
        for flag in value:
            field.set_flag(flag, True)
    else:
        field.set(value)


def clone(source, destination):
    """Copy defined fields recursively; preserve the destination block shape."""
    for name in source.field_names():
        src, dst = source.field(name), destination.field(name)
        if dst is None or src.type_name != dst.type_name:
            raise BootstrapError(f'Incompatible native template field: {name}')
        if src.type_name == 'block':
            child = dst.as_block()
            child.clear()
            for row in src.as_block():
                index = child.add()
                clone(row, child[index])
        elif src.type_name == 'struct':
            clone(src.as_struct(), dst.as_struct())
        elif 'flags' in src.type_name and isinstance(src.value, list):
            put(destination, name, src.value)
        elif src.value is not None or 'reference' in src.type_name:
            dst.set(src.value)


def _replace_block(destination, name, rows):
    output = block(destination, name)
    output.clear()
    for row in rows:
        index = output.add()
        clone(row, output[index])


def _linked(path):
    return path.is_symlink() or getattr(path, 'is_junction', lambda: False)()


def _validate_path(root: Path, relative: str, *, required: bool = False) -> Path:
    path = root / relative
    chain = (path, *path.parents)
    if any(_linked(part) for part in chain if part == root or root in part.parents):
        raise BootstrapError(f'Redirected bootstrap path: {relative}')
    if not path.resolve().is_relative_to(root.resolve()):
        raise BootstrapError(f'Bootstrap path escapes workspace: {relative}')
    if any(part.exists() and not part.is_dir() for part in path.parents
           if part == root or root in part.parents):
        raise BootstrapError(f'Bootstrap parent is not a directory: {relative}')
    if path.exists() and not path.is_file():
        raise BootstrapError(f'Bootstrap path is not a file: {relative}')
    if required and not path.is_file():
        raise BootstrapError(f'Missing owned stock bootstrap input: {relative}')
    return path


def validate_paths(config: ProjectConfig) -> Path:
    """Validate every destination and input before importing bindings or writing.

    Missing output directories are allowed and created only after all three
    inputs have parsed, round-tripped and passed their template assertions.
    """
    root = config.workspace
    if not root.is_absolute() or not root.is_dir() or _linked(root):
        raise BootstrapError('workspace must be an existing, absolute, unlinked directory')
    for relative in BOOTSTRAP_INPUTS + BOOTSTRAP_OUTPUTS + (MANIFEST_PATH,):
        _validate_path(root, relative, required=relative in BOOTSTRAP_INPUTS)
    return root


def _read_exact(binding, path):
    data = path.read_bytes()
    tag = binding.TagFile.read(path)
    if tag.write_to_bytes() != data:
        raise BootstrapError(f'Binding does not preserve owned input bytes: {path.name}')
    return tag, data


def _validate_palettes(source):
    for name, field, group, length, identities in (
        ('character palette', 'reference', 0x63686172, 21, CHARACTER_IDENTITIES),
        ('weapon palette', 'name', 0x77656170, 20, WEAPON_IDENTITIES),
    ):
        rows = block(source, name)
        if len(rows) != length:
            raise BootstrapError(f'Unexpected 020_base {name} length: {len(rows)}')
        for index, expected in identities.items():
            if rows[index].field(field).value != (group, expected):
                raise BootstrapError(f'Unexpected 020_base {name} identity at {index}')


def _select_zone(scenario):
    zones = block(scenario, 'zone sets')
    matches = [i for i, row in enumerate(zones)
               if row.field('name').value == 'bsp_000']
    if len(matches) != 1:
        raise BootstrapError('Expected exactly one outdoor bsp_000 zone set')
    index = matches[0]
    row = zones[index]
    for name, expected in {'bsp zone flags': 1, 'required designer zones': 0,
                           'forbidden designer zones': 0, 'cinematic zones': 0}.items():
        if row.field(name).value != expected:
            raise BootstrapError(f'Unexpected bsp_000 {name}')
    pvs = row.field('pvs index').value
    if not 0 <= pvs < len(block(scenario, 'zone set pvs')):
        raise BootstrapError('bsp_000 lacks a valid owned PVS binding')
    zones.swap(0, index)
    put(zones[0], 'name', 'sv_outdoors')
    put(zones[0], 'flags', [])
    put(zones[0], 'hint previous zone set', -1)
    return index, pvs


def _ground_point(scenario):
    zones = block(scenario, 'zones')
    if not len(zones) or zones[0].field('name').value != 'lz':
        raise BootstrapError('Expected outdoor navigation zone 0 named lz')
    areas = block(zones[0], 'areas')
    candidates = []
    for index, row in enumerate(block(zones[0], 'firing positions')):
        if (row.field('structure bsp').value == 0
                and row.field('reference frame').value == -1
                and row.field('sector index').value >= 0
                and 0 <= row.field('area').value < len(areas)):
            p = row.field('position (local)').value
            candidates.append(((p.x - 101) ** 2 + (p.y - 364) ** 2, index, row))
    if not candidates:
        raise BootstrapError('No bound stock outdoor ground point for bootstrap spawn')
    _, index, row = min(candidates, key=lambda item: (item[0], item[1]))
    return index, row


def _author(binding, stock, outdoor, strings):
    source, target = stock.root(), outdoor.root()
    _validate_palettes(source)
    objective_template = block(source, 'ai objectives')[1]
    task_template = block(objective_template, 'tasks')[1]
    squad_template = block(source, 'squads')[3]
    for row, expected in ((objective_template, 'hangar_a_cov_obj'),
                          (task_template, 'main_attack'),
                          (squad_template, 'hangar_a_cov_init_left')):
        if row.field('name').value != expected:
            raise BootstrapError(f'Unexpected 020_base template identity: {expected}')
    original_zone, pvs = _select_zone(target)
    ground_index, ground = _ground_point(target)
    center = ground.field('position (local)').value
    area_index = ground.field('area').value
    for name in CLEAR_BLOCKS:
        block(target, name).clear()
    # Script binary strings are unrelated to geometry/navigation and refer to
    # the campaign scripts removed above.
    put(target, 'script string data', b'')
    for name in ('character palette', 'weapon palette'):
        _replace_block(target, name, list(block(source, name)))
    characters = block(target, 'character palette')
    index = characters.add()
    if index != 21:
        raise BootstrapError('Flood combat palette index must be 21')
    put(characters[index], 'reference', (0x63686172, FLOOD_CHARACTER))

    _replace_block(target, 'ai objectives', [objective_template])
    objective = block(target, 'ai objectives')[0]
    # Copy task 1 from the stock source, not from the block being replaced.
    _replace_block(objective, 'tasks', [task_template])
    for name, value in {'name': 'sv_hunt', 'zone index': 0, 'first task index': 0}.items():
        put(objective, name, value)
    task = block(objective, 'tasks')[0]
    for name, value in {
        'name': 'surround', 'flags': [], 'inhibit groups': [], 'inhibit on difficulty': [],
        'Entry Script': '', 'Command Script': '', 'Exhaustion Script': '',
        'Script index': -1, 'Command script index': -1, 'Exhaustion script index': -1,
        'Squad group filter': -1, 'first_child': -1, 'next_sibling': -1, 'parent': -1,
        'script index ': -1, 'lifetime count': 0, 'filter flags': [], 'filter': 'none',
        'max body count': 0, 'min strength': 0.0, 'capacity': binding.ShortBounds(0, 0),
        'follow squad': -1,
    }.items():
        put(task, name, value)
    for name in ('activation script', 'direction', 'Pureform distribution', 'areas'):
        block(task, name).clear()
    areas = block(task, 'areas')
    index = areas.add()
    for name, value in {'area type': 'search', 'flags': [], 'character flags': [],
                        'zone': 0, 'area': area_index}.items():
        put(areas[index], name, value)

    _replace_block(target, 'squads', [squad_template])
    squad = block(target, 'squads')[0]
    for name, value in {'name': 'sv_template', 'flags': [], 'team': 'covenant', 'parent': -1,
                        'initial zone': 0, 'initial objective': 0, 'initial task': 0,
                        'editor folder': -1}.items():
        put(squad, name, value)
    fireteams = block(squad, 'fire-teams')
    while len(fireteams) > 1:
        fireteams.delete(len(fireteams) - 1)
    team = fireteams[0]
    for name, value in {'normal diff count': 1, 'character type': 3, 'initial weapon': 4,
                        'initial secondary weapon': -1, 'vehicle type': -1,
                        'initial equipment': -1, 'Placement script': '',
                        'placement script index': -1, 'point set': -1, 'activity': 'none'}.items():
        put(team, name, value)
    block(team, 'points').clear()
    locations = block(team, 'starting locations')
    while len(locations) > 1:
        locations.delete(len(locations) - 1)
    location = locations[0]
    for name, value in {
        'name': 'sv_template_spawn', 'position': binding.RealPoint3d(center.x, center.y, center.z + .15),
        'reference frame': -1, 'structure bsp': 0, 'flags': [], 'place on': [],
        'character type': -1, 'initial weapon': -1, 'initial secondary weapon': -1,
        'vehicle type': -1, 'initial equipment': -1, 'Placement script': '',
        'placement script index': -1, 'point set': -1, 'emitter vehicle': -1,
        'giant body': -1, 'biped body': -1, 'activity': 'none', 'activity name': '',
        'facing (yaw, pitch)': binding.RealEulerAngles2d(0, 0),
    }.items():
        put(location, name, value)
    block(location, 'points').clear()

    _replace_block(target, 'player starting locations', [block(source, 'player starting locations')[0]])
    player = block(target, 'player starting locations')[0]
    for name, value in {'position': binding.RealPoint3d(center.x, center.y, center.z + .2),
                        'facing': 0.0, 'pitch': 0.0, 'bsp index': 0,
                        'campaign player type': 'masterchief'}.items():
        put(player, name, value)
    profiles = block(target, 'player starting profile')
    profiles.clear()
    index = profiles.add()
    for name, value in {
        'name': 'sv_start', 'starting health damage': 0.0, 'starting shield damage': 0.0,
        'primary weapon': (0x77656170, ASSAULT_RIFLE),
        'primaryrounds loaded': 32, 'primaryrounds total': 320, 'secondary weapon': None,
        'secondaryrounds loaded': 0, 'secondaryrounds total': 0,
        'starting fragmentation grenade count': 2, 'starting plasma grenade count': 0,
        'starting claymore grenade count': 0, 'starting firebomb grenade count': 0,
        'editor folder': -1,
    }.items():
        put(profiles[index], name, value)

    _replace_block(target, 'cutscene titles', [block(source, 'cutscene titles')[0]])
    put(block(target, 'cutscene titles')[0], 'name', 'sv_bootstrap')
    put(target, 'chapter title text', (0x756e6963, r'ui\survivors\last_stand'))
    string_root = strings.root()
    refs = block(string_root, 'string references')
    refs.clear()
    index = refs.add()
    put(refs[index], 'string id', 'sv_bootstrap')
    for name in refs[index].field_names():
        if name.endswith(' offset'):
            put(refs[index], name, 0)
    put(string_root, 'string data utf8', b'Last Stand bootstrap\0')
    return {'source_zone_set_index': original_zone, 'pvs_index': pvs,
            'navigation_zone': 0, 'firing_position_index': ground_index,
            'area_index': area_index, 'sector_index': ground.field('sector index').value,
            'position': [center.x, center.y, center.z],
            'character_count': len(characters), 'weapon_count': len(block(target, 'weapon palette'))}


def _record(path, data):
    return {'path': path, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def _publish_outputs(config: ProjectConfig, payloads: tuple[bytes, ...], report: dict) -> None:
    """Stage everything, then replace declared outputs with ordinary-error rollback.

    Replacements are atomic per file, not crash-atomic as a batch. If rollback
    itself fails, leave the previous bytes in a named recovery directory.
    """
    root = validate_paths(config)
    names = BOOTSTRAP_OUTPUTS + (MANIFEST_PATH,)
    contents = payloads + ((json.dumps(report, indent=2) + '\n').encode('utf-8'),)
    staging = Path(tempfile.mkdtemp(prefix='.last-stand-bootstrap-', dir=root))
    keep_recovery = False
    try:
        originals = {}
        for index, (name, data) in enumerate(zip(names, contents)):
            (staging / f'new-{index}').write_bytes(data)
            target = _validate_path(root, name)
            originals[index] = target.read_bytes() if target.exists() else None
            if originals[index] is not None:
                (staging / f'old-{index}').write_bytes(originals[index])
        validate_paths(config)
        published = []
        try:
            for index, name in enumerate(names):
                target = _validate_path(root, name)
                current = target.read_bytes() if target.exists() else None
                if current != originals[index]:
                    raise BootstrapRecoveryError(
                        f'Bootstrap output changed since preflight: {name}; recovery files retained at {staging}')
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging / f'new-{index}', target)
                published.append(index)
        except Exception as error:
            try:
                for index in reversed(published):
                    target = _validate_path(root, names[index])
                    current = target.read_bytes() if target.exists() else None
                    if current != contents[index]:
                        raise BootstrapError(f'Rollback destination changed: {names[index]}')
                    if originals[index] is not None:
                        os.replace(staging / f'old-{index}', target)
                    else:
                        target.unlink()
            except (OSError, BootstrapError) as rollback_error:
                keep_recovery = True
                raise BootstrapRecoveryError(
                    f'Bootstrap rollback failed; recovery files retained at {staging}: {rollback_error}'
                ) from error
            raise
    except BootstrapRecoveryError:
        keep_recovery = True
        raise
    finally:
        if not keep_recovery:
            shutil.rmtree(staging)


def build_bootstrap(config: ProjectConfig, *, check: bool = False) -> dict:
    """Build deterministic baseline artifacts, or validate/render without writes.

    Returned and saved manifests contain only workspace-relative paths and exact
    byte hashes. No timestamp or machine-specific path affects output bytes.
    """
    root = validate_paths(config)
    binding = importlib.import_module('blam_tags')
    parsed = [_read_exact(binding, root / name) for name in BOOTSTRAP_INPUTS]
    stock, outdoor, strings = [item[0] for item in parsed]
    template = _author(binding, stock, outdoor, strings)
    for tag in (outdoor, strings):
        tag.recompute_checksum()
    payloads = (outdoor.write_to_bytes(), BOOTSTRAP_HSC, strings.write_to_bytes())
    for name, data in ((BOOTSTRAP_OUTPUTS[0], payloads[0]), (BOOTSTRAP_OUTPUTS[2], payloads[2])):
        if binding.TagFile.read_from_bytes(data).write_to_bytes() != data:
            raise BootstrapError(f'Authored bootstrap tag does not round-trip: {name}')
    report = {'schema_version': 1, 'stage': 'direct-stock-bootstrap',
              'inputs': [_record(name, item[1]) for name, item in zip(BOOTSTRAP_INPUTS, parsed)],
              'outputs': [_record(name, data) for name, data in zip(BOOTSTRAP_OUTPUTS, payloads)],
              'template': template, 'native_validation': 'required',
              'limitations': ['Stock geometry and navigation are retained before native processing.',
                              'Native baseline save/readback, final compilation, cache and gameplay remain required.']}
    if not check:
        _publish_outputs(config, payloads, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--check', action='store_true', help='Render and validate all inputs without writing outputs.')
    args = parser.parse_args(argv)
    try:
        report = build_bootstrap(load_config(args.config, workspace=args.root), check=args.check)
    except (ConfigError, BootstrapError, ImportError, OSError) as error:
        parser.exit(2, f'bootstrap: {error}\n')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
