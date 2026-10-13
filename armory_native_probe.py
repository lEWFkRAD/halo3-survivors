"""Author an isolated, native-pending Armory HUD probe; never stage or run it.

All seven owned inputs are explicit. The six output tags and receipt are built
privately, then published into a new or empty directory. The messages contain a
static catalog page and a labelled seeded example, not a live skill-tree UI.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile


INPUT_GROUPS = {
    'scenario': 'scnr', 'ui': 'unic', 'biped': 'bipd', 'chud': 'chdt',
    'chud_globals': 'chgd', 'hud_messages': 'unic', 'globals': 'matg',
}
DESTINATIONS = {
    'scenario': 'tags/levels/survivors/last_stand/last_stand.scenario',
    'ui': 'tags/ui/survivors/progression.multilingual_unicode_string_list',
    'biped': 'tags/objects/survivors/armory_probe.biped',
    'chud': 'tags/ui/survivors/armory_probe.chud_definition',
    'hud_messages': 'tags/ui/survivors/armory_messages.multilingual_unicode_string_list',
    'chud_globals': 'tags/ui/chud/globals.chud_globals_definition',
}
MANIFEST = 'armory-probe.json'
BACKGROUND_ARGB = 0xF2111820
TEXT_ARGB = 0xFFFAFCFF


class ProbeError(ValueError):
    """An unsupported template or unsafe output request."""


def _require(condition, message):
    if not condition:
        raise ProbeError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


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


def make_messages():
    """Use catalog data for a reference page and an explicitly static example."""
    from armory_presentation import build_armory_pages, native_page_titles

    ranks = {'needler.unlock': 1, 'needler.damage': 1}
    page = build_armory_pages(ranks, stage=2, points=3, selected_id='needler.damage')[0]
    _require(page.id == 'needler', 'The probe expects the Needler page first')
    _require({node.state for node in page.nodes} ==
             {'maxed', 'purchased', 'available', 'locked'}, 'Expected four example states')
    nodes = {node.id: node for node in page.nodes}
    codes = {'maxed': 'MAX', 'purchased': 'OWN', 'available': 'BUY', 'locked': 'LOCK'}

    def row(node_id, prefix):
        node = nodes[node_id]
        label = node.name.removeprefix(page.name + ': ')
        if label == 'Unlock ' + page.name:
            label = 'Unlock'
        focus = ' <selected>' if node.selected else ''
        return f'{prefix}[{codes[node.state]}] {label} {node.rank}/{node.max_rank}{focus}'

    lines = [
        'NEEDLER | SEEDED DISPLAY PROBE', 'Read-only sample: stage 2 | points 3',
        row('needler.unlock', ''), row('needler.damage', ' +-> '),
        row('needler.cadence', ' +-> '), 'Power1 + Cadence1 -> choose ONE:',
        row('needler.seeker', ' +-> '), row('needler.seeker_capstone', ' |   +-> '),
        row('needler.crystal', ' +-> '), row('needler.crystal_capstone', '     +-> '),
        'MAX=maxed OWN=purchased BUY=available LOCK=locked', 'END SEEDED DISPLAY',
    ]
    messages = {
        'sv_armory_probe': native_page_titles()['sv_tree_0'].replace('\n', '\r\n')
                            + '\r\nEND ARMORY PROBE',
        'sv_armory_owned': '\r\n'.join(lines),
        'sv_armory_wallet': 'ARMORY / 3 UPGRADE POINTS',
        'sv_armory_lines': '\r\n'.join(f'LINE{i:02d}' for i in range(1, 13)),
        'sv_armory_compact': 'SEEDED S2 P3 | MAX Unlock1 | OWN Power1 | BUY Cadence0 | LOCK Seeker0 | END',
        # Each group starts at the zero-based character index printed in it.
        'sv_armory_ruler': ''.join(f'{offset:03d}......|' for offset in range(0, 320, 10)),
    }
    for string_id, text in messages.items():
        _require(text.isascii(), 'Probe text must remain ASCII')
        if string_id == 'sv_armory_ruler':
            _require(len(text) == 320 and len(text.splitlines()) == 1, 'Invalid truncation ruler')
        elif string_id == 'sv_armory_compact':
            _require(len(text) <= 110 and len(text.splitlines()) == 1, 'Compact sample too long')
        else:
            _require(len(text.splitlines()) <= 12 and max(map(len, text.splitlines())) <= 60,
                     'Probe text exceeded its bounded ASCII layout')
        _require('\n' not in text.replace('\r\n', ''), 'Expected literal CRLF line breaks')
    return messages, {
        'kind': 'explicit_static_example_not_live_game_state', 'stage': 2, 'points': 3,
        'supplied_ranks': ranks, 'selected_id': 'needler.damage',
        'nodes': [{'id': n.id, 'rank': n.rank, 'max_rank': n.max_rank,
                   'state': n.state, 'selected': n.selected} for n in page.nodes],
    }


def _binding(binding_dir):
    original = sys.path[:]
    try:
        if binding_dir is not None:
            directory = Path(binding_dir).expanduser().resolve(strict=True)
            _require(directory.is_dir(), 'Binding path must be a directory')
            sys.path.insert(0, str(directory))
        module = importlib.import_module('blam_tags')
        if binding_dir is not None:
            _require(Path(module.__file__).resolve().is_relative_to(directory),
                     'Already-loaded binding does not match --binding-dir')
        return module
    finally:
        sys.path[:] = original


def _build_payloads(originals, b, override_globals):
    tags = {}
    for name, group in INPUT_GROUPS.items():
        tag = b.TagFile.read_from_bytes(originals[name])
        _require(tag.group_tag == group, f'{name} must have tag group {group}')
        _require(tag.write_to_bytes() == originals[name], f'{name} input did not roundtrip')
        tags[name] = tag

    scenario, biped = tags['scenario'], tags['biped']
    _require(scenario.root().field('type').value == 'solo', 'Probe requires a solo scenario')
    for role, needed in (('ui', {'sv_node_0', 'sv_controls'}),
                         ('hud_messages', {'training_shieldsrecharging'})):
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
    target.field('third person unit').set((0x62697064, r'objects\survivors\armory_probe'))
    scenario.root().field('flags').set_flag('override globals', override_globals)
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
    hud.set((0x63686474, r'ui\survivors\armory_probe'))

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
    bitmap_placements[0].field('widget scale').set(b.RealPoint2d(55.0, 8.0))
    bitmap.field('flags').set_flag('scale alpha by col. out A', True)
    renders = bitmap_base.field('render data').as_block()
    _require(len(renders) == 1 and renders[0].field('shader type').value == 'simple',
             'Unexpected bitmap shader')
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

    messages, seeded = make_messages()
    strings = tags['hud_messages'].root()
    before_strings = _snapshot(strings)
    refs = strings.field('string references').as_block()
    old_count = len(refs)
    old_data = strings.field('string data utf8').value
    data = bytearray(old_data)
    _require(not {refs[i].field('string id').value for i in range(old_count)}.intersection(messages),
             'Probe string IDs already exist')
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
        if name != 'ui':
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
        'seeded_view': seeded, 'appended_messages': appended,
        'stock_message_references_preserved': old_count,
        'stock_message_utf8_bytes_preserved': len(old_data),
        'language_policy': 'New English payloads shared by twelve languages; existing offsets unchanged',
        'panel': {'background_argb': f'{BACKGROUND_ARGB:08X}', 'text_argb': f'{TEXT_ARGB:08X}',
                  'bitmap_scale': [55.0, 8.0], 'anchor': 'top center', 'offset': [0.0, 280.0]},
        'scenario_inverse_audit': True, 'biped_normalized_inverse_audit': True,
        'ui_copy_unchanged': payloads['ui'] == originals['ui'],
        'override_globals': override_globals,
        'visibility': 'Unchanged player training available; no HSC bridge authored',
        'ruler': 'Single-line numbered ten-character groups: labels are zero-based character positions. Observe the actual cutoff; no buffer limit is assumed.',
    }


def _unlinked(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    for part in (path, *path.parents):
        _require(not part.is_symlink() and not getattr(part, 'is_junction', lambda: False)(), f'Linked path rejected: {part}')
    return path


def _empty_output(path):
    _unlinked(path)
    _require(path.parent.is_dir(), 'Output parent must already exist')
    if path.exists():
        _require(path.is_dir() and not any(path.iterdir()), 'Output directory must be new or empty')


def author_probe(*, scenario, ui, biped, chud, chud_globals, hud_messages,
                 globals, output_dir, binding_dir=None, override_globals=False):
    """Return a receipt after all authored files are published; inputs stay read-only."""
    values = dict(scenario=scenario, ui=ui, biped=biped, chud=chud,
                  chud_globals=chud_globals, hud_messages=hud_messages, globals=globals)
    paths = {name: _unlinked(path).resolve(strict=True) for name, path in values.items()}
    output = _unlinked(output_dir)
    _empty_output(output)
    for name, path in paths.items():
        _require(path.is_file(), f'{name} input must be a regular file')
        _require(not path.is_relative_to(output), 'Output directory contains an input')
    path_list = list(paths.values())
    _require(all(not a.samefile(c) for i, a in enumerate(path_list) for c in path_list[i+1:]),
             'Inputs must be distinct files, including hard-link aliases')
    originals = {name: path.read_bytes() for name, path in paths.items()}
    payloads, audit = _build_payloads(originals, _binding(binding_dir), override_globals)
    _require(set(payloads) == set(DESTINATIONS), 'Author returned undeclared or missing outputs')
    _require(all(isinstance(data, bytes) and data for data in payloads.values()),
             'Author returned an empty or non-byte output')
    receipt = {
        'schema_version': 1, 'kind': 'static_armory_hud_probe', 'native_status': 'not_run',
        'inputs': {name: {'path': str(paths[name]), 'bytes': len(data), 'sha256': _sha(data)}
                   for name, data in originals.items()},
        'outputs': {DESTINATIONS[name]: {'native_destination': DESTINATIONS[name],
                                       'bytes': len(data), 'sha256': _sha(data)}
                    for name, data in payloads.items()},
        'audit': audit,
        'limits': [
            'Dry authoring only. No staging, compilation, launcher, save or installed-package changes.',
            'Default palette, bitmap size and font are a proof configuration, not an approved production graph.',
            'Catalog reference and SEEDED DISPLAY messages are static examples, not live ranks or wallet state.',
            'Native routing, string lookup, line breaks, bounds, alpha, visibility and input behavior need observation.',
            'Long reference/seeded probes may truncate. Compact and ruler messages isolate character-limit experiments.',
            'CHUD globals destination replaces a stock tag in an isolated candidate; native operator must preserve it.',
        ],
    }
    # No final files exist until every output and the complete manifest are ready.
    with tempfile.TemporaryDirectory(prefix='.armory-probe-', dir=output.parent) as directory:
        staging = Path(directory) / 'candidate'
        staging.mkdir()
        for name, data in payloads.items():
            target = staging / DESTINATIONS[name]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (staging / MANIFEST).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        _require(all(path.read_bytes() == originals[name] for name, path in paths.items()),
                 'An input changed during authoring; candidate was not published')
        _empty_output(output)
        existed = output.exists()
        if existed:
            output.rmdir()  # Fails closed if another writer has populated it.
        try:
            os.rename(staging, output)
        except OSError:
            if existed and not output.exists():
                output.mkdir()
            raise
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in INPUT_GROUPS:
        parser.add_argument('--' + name.replace('_', '-'), type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--binding-dir', type=Path)
    parser.add_argument('--override-globals', action='store_true',
                        help='Set the scenario override globals flag; recorded as a native-pending choice')
    args = parser.parse_args(argv)
    try:
        receipt = author_probe(**vars(args))
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        parser.exit(2, f'Armory probe not published: {error}\n')
    print(json.dumps({'output_dir': str(args.output_dir), 'manifest': MANIFEST,
                      'output_tags': len(receipt['outputs']), 'native_status': 'not_run'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
