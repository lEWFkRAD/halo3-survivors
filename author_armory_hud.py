"""Author the live Armory HUD into an isolated progression workspace.

Importing is inert. ``main(root)`` runs after author_progression_ui.main, updates
its already-declared scenario, and returns four additional native tags. Prepare
owns the final publication and manifest; this module never stages or runs Halo.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parent
SCENARIO = 'native-tags/levels/survivors/last_stand/progression-ui.scenario'
INPUTS = {
    'scenario': SCENARIO,
    'biped': 'private-inputs/armory/masterchief.biped',
    'chud': 'private-inputs/armory/spartan.chud_definition',
    'chud_globals': 'private-inputs/armory/globals.chud_globals_definition',
    'hud_messages': 'private-inputs/armory/hud_messages.multilingual_unicode_string_list',
    'globals': 'private-inputs/armory/globals.globals',
}
INPUT_GROUPS = {
    'scenario': 'scnr', 'biped': 'bipd', 'chud': 'chdt',
    'chud_globals': 'chgd', 'hud_messages': 'unic', 'globals': 'matg',
}
DESTINATIONS = {
    'scenario': SCENARIO,
    'biped': 'native-tags/objects/survivors/armory.biped',
    'chud': 'native-tags/ui/survivors/armory.chud_definition',
    'hud_messages': 'native-tags/ui/survivors/armory_messages.multilingual_unicode_string_list',
    'chud_globals': 'native-tags/ui/chud/globals.chud_globals_definition',
}
ADDITIONAL_OUTPUTS = tuple(path for role, path in DESTINATIONS.items() if role != 'scenario')
BACKGROUND_ARGB = 0xFF000000
TEXT_ARGB = 0xFFFAFCFF
PANEL_SCALE = (85.0, 8.0)


class ArmoryAuthorError(ValueError):
    """Unsupported templates, messages or workspace paths."""


def _require(condition, message):
    if not condition:
        raise ArmoryAuthorError(message)


def validate_messages(messages):
    _require(isinstance(messages, dict) and messages, 'Expected a nonempty message dictionary')
    for name, text in messages.items():
        _require(isinstance(name, str) and re.fullmatch(r'sv_[a-z0-9_]+', name),
                 'Expected a private Armory string ID')
        _require(isinstance(text, str) and text and text.isascii() and len(text) <= 110,
                 'Armory messages must contain 1 to 110 ASCII characters')
        _require('\0' not in text and '\n' not in text.replace('\r\n', '')
                 and '\r' not in text.replace('\r\n', ''),
                 'Armory messages require literal CRLF breaks and no NUL')


def _snapshot(row):
    result = {}
    for name in row.field_names():
        field = row.field(name)
        if field.type_name in ('block', 'array'):
            values = field.as_block() if field.type_name == 'block' else field.as_array()
            result[name] = [_snapshot(values[i]) for i in range(len(values))]
        elif field.type_name == 'struct':
            result[name] = _snapshot(field.as_struct())
        else:
            result[name] = repr(field.value)
    return result


def build_payloads(originals, b, messages):
    """Validate owned templates and return five in-memory outputs before any write."""
    validate_messages(messages)
    tags = {}
    for name, group in INPUT_GROUPS.items():
        tag = b.TagFile.read_from_bytes(originals[name])
        _require(tag.group_tag == group, f'{name} must have tag group {group}')
        _require(tag.write_to_bytes() == originals[name], f'{name} input did not roundtrip')
        tags[name] = tag

    scenario, biped = tags['scenario'], tags['biped']
    _require(scenario.root().field('type').value == 'solo', 'Armory requires a solo scenario')
    for role, needed in (('hud_messages', {'training_shieldsrecharging'}),):
        ids = {row.field('string id').value for row in tags[role].root().field('string references').as_block()}
        _require(needed <= ids, f'{role} has the wrong string-table role')
    overrides = scenario.root().field('override player representations').as_block()
    _require(len(overrides) == 0, 'Scenario already has player overrides; review separately')
    representations = tags['globals'].root().field('@player representation').as_block()
    _require(len(representations) > 0, 'Missing campaign player representation')
    source = representations[0]
    _require([source.field(n).value for n in ('name', 'model choice', 'class')] ==
             ['masterchief', 'spartan', 'campaign'], 'Unexpected campaign player template')
    original_flags = scenario.root().field('flags').value
    scenario.recompute_checksum()
    scenario_baseline = scenario.write_to_bytes()
    target = overrides[overrides.add()]
    _require(source.field_names() == target.field_names(), 'Representation schemas differ')
    for name in source.field_names():
        field = source.field(name)
        _require(field.as_struct() is None and field.as_block() is None
                 and field.as_array() is None, 'Unsupported nested representation field')
        target.field(name).set(field.value)
    target.field('third person unit').set((0x62697064, r'objects\survivors\armory'))
    scenario.root().field('flags').set_flag('override globals', True)
    expected_rep = _snapshot(target)

    hud_rows = biped.root().field('unit').as_struct().field('NEW HUD INTERFACES').as_block()
    _require(len(hud_rows) > 0, 'Biped has no HUD interface')
    hud = hud_rows[0].field('chud interface')
    old_hud = hud.value
    _require(old_hud == (0x63686474, r'ui\chud\spartan'), 'Unexpected biped HUD template')
    # The binding normalizes reference terminators on assignment, even no-ops.
    hud.set(old_hud)
    biped.recompute_checksum()
    biped_baseline = biped.write_to_bytes()
    hud.set((0x63686474, r'ui\survivors\armory'))

    chud = tags['chud']
    before_chud = _snapshot(chud.root())
    collections = chud.root().field('widget collections').as_block()
    indices = [i for i in range(len(collections)) if collections[i].field('base').as_struct()
               .field('artist name').value == 'player_training']
    _require(len(indices) == 1, 'Expected one player_training collection')
    index = indices[0]
    training = collections[index]
    base = training.field('base').as_struct()
    states = base.field('state data').as_block()
    _require(len(states) == 1 and states[0].field('misc state').value ==
             ['player training available'], 'Unexpected training visibility')
    for name in states[0].field_names():
        _require(name == 'misc state' or states[0].field(name).value in ([], None),
                 'Unexpected training visibility condition')
    placement = base.field('placement data').as_block()
    _require(len(placement) == 1, 'Expected one training placement')
    placement[0].field('anchor type').set('top center')
    placement[0].field('origin offset').set(b.RealPoint2d(0.0, 280.0))
    bitmaps, texts = training.field('bitmap widgets').as_block(), training.field('text widgets').as_block()
    _require(len(bitmaps) == len(texts) == 1, 'Expected one training bitmap and text')
    bitmap = bitmaps[0]
    _require(bitmap.field('bitmap').value == (0x6269746D, r'ui\chud\bitmaps\help'),
             'Unexpected panel bitmap')
    bitmap_base = bitmap.field('base').as_struct()
    bitmap_placements = bitmap_base.field('placement data').as_block()
    _require(len(bitmap_placements) == 1, 'Expected one bitmap placement')
    bitmap_placements[0].field('widget scale').set(b.RealPoint2d(*PANEL_SCALE))
    bitmap.field('flags').set_flag('scale alpha by col. out A', True)
    renders = bitmap_base.field('render data').as_block()
    _require(len(renders) == 1 and renders[0].field('shader type').value == 'simple',
             'Unexpected bitmap shader')
    # The stock simple shader takes opacity from the help bitmap. The solid
    # shader's native enum retains its historical warning; an isolated SDK
    # experiment verifies this opaque panel, while retail remains unverified.
    renders[0].field('shader type').set("solid (don't use)")
    renders[0].field('custom color A').set(b.ArgbColor(BACKGROUND_ARGB))
    for letter in 'ABCDEF':
        renders[0].field(f'color output {letter}').set('custom color A')
    _require(texts[0].field('input string').value == 'chud_training_text',
             'Unexpected training text source')
    renders = texts[0].field('base').as_struct().field('render data').as_block()
    _require(len(renders) == 1 and renders[0].field('shader type').value == 'text simple',
             'Unexpected text shader')
    renders[0].field('custom color A').set(b.ArgbColor(TEXT_ARGB))
    after_chud = _snapshot(chud.root())
    expected = json.loads(json.dumps(before_chud))
    expected['widget collections'][index] = after_chud['widget collections'][index]
    _require(after_chud == expected, 'CHUD changes escaped player_training')
    _require(before_chud['widget collections'][index]['base']['state data'] ==
             after_chud['widget collections'][index]['base']['state data'],
             'Training visibility changed')

    strings = tags['hud_messages'].root()
    before_strings = _snapshot(strings)
    refs = strings.field('string references').as_block()
    old_count = len(refs)
    old_data = strings.field('string data utf8').value
    data = bytearray(old_data)
    _require(not {refs[i].field('string id').value for i in range(old_count)}.intersection(messages),
             'Armory string IDs already exist')
    appended = []
    for string_id, text in messages.items():
        row_index = refs.add()
        row = refs[row_index]
        offset = len(data)
        row.field('string id').set(string_id)
        languages = [n for n in row.field_names() if n.endswith(' offset')]
        _require(len(languages) == 12, 'Expected twelve language offsets')
        for name in languages:
            row.field(name).set(offset)
        data.extend(text.encode('utf-8') + b'\0')
        appended.append({'id': string_id, 'index': row_index, 'offset': offset, 'text': text,
                         'intended_ascii_characters': len(text)})
    strings.field('string data utf8').set(bytes(data))
    after_strings = _snapshot(strings)
    expected = json.loads(json.dumps(after_strings))
    expected['string references'] = expected['string references'][:old_count]
    expected['string data utf8'] = before_strings['string data utf8']
    _require(expected == before_strings and data[:len(old_data)] == old_data,
             'Existing message fields or UTF-8 data changed')

    chud_globals = tags['chud_globals'].root()
    before_globals = _snapshot(chud_globals)
    skins = chud_globals.field('skins').as_block()
    _require(len(skins) == 3, 'Expected three CHUD skins')
    message_ref = (0x756E6963, r'ui\survivors\armory_messages')
    for i in range(len(skins)):
        field = skins[i].field('chud text')
        _require(field.value == (0x756E6963, r'ui\hud\hud_messages'),
                 'Unexpected original CHUD text reference')
        field.set(message_ref)
    expected = json.loads(json.dumps(before_globals))
    for skin in expected['skins']:
        skin['chud text'] = repr(message_ref)
    _require(_snapshot(chud_globals) == expected, 'Unintended CHUD globals change')

    payloads = {}
    for name in DESTINATIONS:
        tag = tags[name]
        tag.recompute_checksum()
        result = tag.write_to_bytes()
        readback = b.TagFile.read_from_bytes(result)
        _require(readback.write_to_bytes() == result, f'{name} output did not roundtrip')
        if name == 'scenario':
            block = readback.root().field('override player representations').as_block()
            _require(len(block) == 1 and _snapshot(block[0]) == expected_rep,
                     'Scenario representation failed readback')
            block.clear()
            readback.root().field('flags').set_flag('override globals',
                                                   'override globals' in original_flags)
            readback.recompute_checksum()
            _require(readback.write_to_bytes() == scenario_baseline,
                     'Reversing scenario edits did not restore canonical source')
        elif name == 'biped':
            field = readback.root().field('unit').as_struct().field('NEW HUD INTERFACES').as_block()[0].field('chud interface')
            _require(field.value == hud.value, 'Biped HUD reference failed readback')
            field.set(old_hud)
            readback.recompute_checksum()
            _require(readback.write_to_bytes() == biped_baseline,
                     'Reversing biped edit did not restore normalized source')
        else:
            _require(_snapshot(readback.root()) == _snapshot(tag.root()),
                     f'{name} fields changed on readback')
        payloads[name] = result
    return payloads, {
        'appended_messages': appended,
        'stock_message_references_preserved': old_count,
        'stock_message_utf8_bytes_preserved': len(old_data),
        'language_policy': 'New English payloads shared by twelve languages; existing offsets unchanged',
        'panel': {'background_argb': f'{BACKGROUND_ARGB:08X}', 'text_argb': f'{TEXT_ARGB:08X}',
                  'bitmap_scale': list(PANEL_SCALE), 'anchor': 'top center', 'offset': [0.0, 280.0]},
        'scenario_inverse_audit': True, 'biped_normalized_inverse_audit': True,
        'override_globals': True,
        'visibility': 'Unchanged player training available; generated HSC owns training lifetime',
    }



def _workspace_file(root, relative, *, required):
    path = root / relative
    _require(path.resolve().is_relative_to(root.resolve()), 'Path escapes the workspace')
    for part in (path, *path.parents):
        if part != root and root not in part.parents:
            continue
        _require(not part.is_symlink() and not getattr(part, 'is_junction', lambda: False)(),
                 f'Linked workspace path: {part}')
        if part != path:
            _require(not part.exists() or part.is_dir(), f'Non-directory parent: {part}')
    _require((not required and not path.exists()) or path.is_file(), f'Expected regular file: {path}')
    return path


def main(root=None):
    """Update the authored scenario and return the four new, explicit tag paths."""
    root = Path(root) if root is not None else ROOT
    root = Path(os.path.abspath(root.expanduser()))
    _require(root.is_dir(), 'Workspace must exist')
    paths = {role: _workspace_file(root, path, required=True) for role, path in INPUTS.items()}
    targets = {role: _workspace_file(root, path, required=False) for role, path in DESTINATIONS.items()}
    inputs = list(paths.values())
    _require(all(not left.samefile(right) for i, left in enumerate(inputs)
                 for right in inputs[i + 1:]), 'Owned inputs must be distinct files')
    for role, target in targets.items():
        if not target.exists():
            continue
        _require(all(not target.samefile(path) for input_role, path in paths.items()
                     if role != 'scenario' or input_role != 'scenario'),
                 'Output aliases an owned input')
    originals = {role: path.read_bytes() for role, path in paths.items()}
    binding = importlib.import_module('blam_tags')
    messages = importlib.import_module('armory_live').messages()
    payloads, _audit = build_payloads(originals, binding, messages)
    _require(set(payloads) == set(DESTINATIONS), 'Author omitted or added an output')
    _require(all(path.read_bytes() == originals[role] for role, path in paths.items()),
             'An input changed during authoring')
    # All validation precedes these writes. prepare_progression supplies an
    # isolated root and hashes the complete result before live publication.
    with tempfile.TemporaryDirectory(prefix='.armory-hud-', dir=root) as temporary:
        temporary = Path(temporary)
        for role, data in payloads.items():
            _require(isinstance(data, bytes) and data, 'Empty or non-byte tag output')
            (temporary / role).write_bytes(data)
        for role, target in targets.items():
            _workspace_file(root, DESTINATIONS[role], required=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary / role, target)
    print(f'Authored {len(messages)} live Armory strings and private HUD; native validation required.')
    return tuple(root / path for path in ADDITIONAL_OUTPUTS)


if __name__ == '__main__':
    main()
