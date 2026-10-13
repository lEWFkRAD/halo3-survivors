"""Compile compact live Armory snapshots and bounded native HSC lookup helpers.

This module is import-safe and does not author tags or operate Halo. Messages
use the global HUD training-string channel; selection/details and lifecycle
belong to the integrating generator. Compact rendering remains native-pending.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
from math import prod

from armory_graph_budget import reachable_ranks, setup, validate_groups, visible
from progression_catalog import CATALOG

FALLBACK_ID = 'sv_tree_unavailable'
FALLBACK_TEXT = 'ARMORY VIEW UNAVAILABLE\r\nUse the selected skill details.'
STATE_MARKERS = {'locked': '-', 'available': '+', 'purchased': 'o', 'maxed': '*'}
MAX_CHARACTERS = 110
LEAF_CASES = 10
ROUTING_FANOUT = 10
SUPPORT_LABELS = {
    'support.vitality': 'Vitality', 'support.body': 'Armor',
    'support.shield': 'Shield', 'support.aegis': 'Aegis',
    'support.aegis_cycle': 'Cycle', 'support.reach': 'Reach',
    'support.insight': 'Insight', 'support.scholar': 'Scholar',
}
VITALITY_IDS = frozenset(('support.vitality', 'support.body', 'support.shield'))
RECOVERY_IDS = frozenset(('support.aegis', 'support.aegis_cycle'))


@dataclass(frozen=True)
class Snapshot:
    key: int
    string_id: str
    text: str
    states: tuple
    # One reproducible witness; stage/wallet do not multiply identical text.
    ranks: tuple
    stage: int
    wallet: int


@dataclass(frozen=True)
class Page:
    id: str
    nodes: tuple
    indices: tuple
    radices: tuple
    snapshots: tuple


def _label(node):
    if node['weapon'] is None:
        return SUPPORT_LABELS[node['id']]
    suffix = node['id'].split('.', 1)[1]
    return {'unlock': 'Unlock', 'damage': 'Power', 'cadence': 'Rate'}.get(
        suffix, node['name'].split(': ', 1)[-1])


def _compact(page_id, nodes, states):
    labels = [_label(node) + str(rank) + STATE_MARKERS[state]
              for node, (rank, state) in zip(nodes, states)]
    if nodes[0]['weapon'] is not None:
        # The catalog orders each specialization immediately before its cap.
        unlock, power, cadence, branch_a, cap_a, branch_b, cap_b = labels
        lines = [unlock, ' / \\', power + ' ' + cadence, ' \\ /',
                 branch_a + ' ' + branch_b, ' |     |', cap_a + ' ' + cap_b]
    elif page_id == 'support_vitality_armor':
        vitality, armor, shield = labels
        lines = [vitality, ' / \\', armor + ' ' + shield]
    elif page_id == 'support_recovery':
        aegis, cycle = labels
        lines = [aegis, ' |', cycle]
    else:
        reach, insight, scholar = labels
        lines = [reach, insight, ' |', scholar]
    text = '\r\n'.join(lines)
    if not text.isascii() or len(text) > MAX_CHARACTERS:
        raise ValueError(f'Compact graph exceeds ASCII/{MAX_CHARACTERS}-character budget: {page_id}')
    return text


def _key(states, radices):
    key = 0
    multiplier = 1
    for (rank, state), radix in zip(states, radices):
        digit = rank + 1 if rank else int(state == 'available')
        key += digit * multiplier
        multiplier *= radix
    return key


def _groups(catalog):
    groups = [(key, [n for n in catalog['nodes'] if n['weapon'] == key])
              for key in catalog['weapons']]
    support = [n for n in catalog['nodes'] if n['weapon'] is None]
    groups.extend([
        ('support_vitality_armor', [n for n in support if n['id'] in VITALITY_IDS]),
        ('support_recovery', [n for n in support if n['id'] in RECOVERY_IDS]),
        ('support_reach_xp', [n for n in support if n['id'] not in VITALITY_IDS | RECOVERY_IDS]),
    ])
    validate_groups(groups, catalog)
    if len(groups) != 9 or [len(nodes) for _, nodes in groups] != [7] * 6 + [3, 2, 3]:
        raise ValueError('Compact layout requires six seven-node weapons and three support pages')
    expected_support = list(SUPPORT_LABELS)
    if [n['id'] for n in support] != expected_support:
        raise ValueError('Support topology/order changed; update the compact graph layout')
    for page_id, nodes in groups[:6]:
        ids = [n['id'] for n in nodes]
        if ids[:3] != [page_id + '.' + suffix for suffix in ('unlock', 'damage', 'cadence')]:
            raise ValueError('Weapon topology/order changed; update the compact graph layout')
        if any(ids[cap] != ids[branch] + '_capstone' for branch, cap in ((3, 4), (5, 6))):
            raise ValueError('Weapon branch/capstone order changed')
        expected_edges = [set(), {(ids[0], 1)}, {(ids[0], 1)},
                          {(ids[1], 1), (ids[2], 1)},
                          {(ids[3], 2), (ids[1], 2), (ids[2], 2)},
                          {(ids[1], 1), (ids[2], 1)},
                          {(ids[5], 2), (ids[1], 2), (ids[2], 2)}]
        if any({(p['id'], p['rank']) for p in node['prerequisites']} != expected
               for node, expected in zip(nodes, expected_edges)):
            raise ValueError('Weapon prerequisites changed; update the compact graph layout')
        if (not nodes[3]['exclusive_group']
                or nodes[3]['exclusive_group'] != nodes[5]['exclusive_group']
                or any(node['exclusive_group'] for i, node in enumerate(nodes) if i not in (3, 5))):
            raise ValueError('Weapon branch exclusivity changed; update the compact graph layout')
    support_edges = {
        'support.body': {('support.vitality', 1)},
        'support.shield': {('support.vitality', 1)},
        'support.aegis_cycle': {('support.aegis', 2)},
        'support.scholar': {('support.insight', 3)},
    }
    if any({(p['id'], p['rank']) for p in node['prerequisites']}
           != support_edges.get(node['id'], set()) or node['exclusive_group'] for node in support):
        raise ValueError('Support prerequisites/exclusivity changed; update the compact graph layout')
    return groups


@lru_cache(maxsize=4)
def _cached_model(serialized):
    catalog = json.loads(serialized)
    indices = {node['id']: index for index, node in enumerate(catalog['nodes'])}
    pages = []
    for page_index, (page_id, nodes) in enumerate(_groups(catalog)):
        needs, exclusive = setup(nodes)
        radices = tuple(node['max_rank'] + 2 for node in nodes)
        if prod(radices) > 2147483647:
            raise ValueError('Armory key exceeds signed native long range')
        snapshots = {}
        saturation = min(50, max(max(node['costs']) for node in nodes))
        for stage in range(1, 5):
            for ranks in sorted(reachable_ranks(nodes, needs, exclusive, stage)):
                for wallet in range(saturation + 1):
                    states = visible(nodes, needs, exclusive, ranks, stage, wallet)[2]
                    key = _key(states, radices)
                    if key in snapshots:
                        if snapshots[key].states != states:
                            raise ValueError('Armory state key collision')
                        continue
                    snapshots[key] = Snapshot(
                        key, f'sv_g{page_index}_{key}', _compact(page_id, nodes, states),
                        states, ranks, stage, wallet)
        pages.append(Page(page_id, tuple(nodes), tuple(indices[n['id']] for n in nodes),
                          radices, tuple(snapshots[key] for key in sorted(snapshots))))
    return tuple(pages)


def _model(catalog=None):
    return _cached_model(json.dumps(CATALOG if catalog is None else catalog,
                                    separators=(',', ':'), sort_keys=False))


def page_layout(catalog=None):
    """Return immutable page membership in the same order as runtime dispatch."""
    return tuple((page.id, tuple(n['id'] for n in page.nodes)) for page in _model(catalog))


def messages(catalog=None):
    """Return independent text mapping: all reachable snapshots plus fallback."""
    return {FALLBACK_ID: FALLBACK_TEXT,
            **{snapshot.string_id: snapshot.text for page in _model(catalog)
               for snapshot in page.snapshots}}


def _and(terms):
    return terms[0] if len(terms) == 1 else '(and ' + ' '.join(terms) + ')'


def emit_runtime(h, catalog=None):
    """Add sv_tree_display and bounded helpers to progression_hsc.HSC.

    The caller declares ranks, sv_selection, sv_stage and sv_tokens, owns the
    refresh schedule and enables/shows training text. A display call always
    selects the fallback before lookup, preventing stale text for invalid keys.
    """
    pages = _model(catalog)
    h.global_('long', 'sv_tree_key', 0)
    h.global_('short', 'sv_tree_digit', 0)
    h.global_('boolean', 'sv_tree_valid', 'false')
    select = []
    for page_index, page in enumerate(pages):
        prefix = f'sv_g{page_index}'
        routes = []
        for offset in range(0, len(page.snapshots), LEAF_CASES):
            chunk = page.snapshots[offset:offset + LEAF_CASES]
            name = f'{prefix}_leaf{offset // LEAF_CASES}'
            h.script(name, '\n'.join(
                f'(if (= sv_tree_key {snapshot.key}) (hud_set_training_text {snapshot.string_id}))'
                for snapshot in chunk))
            routes.append((chunk[0].key, chunk[-1].key, name))
        depth = 0
        while len(routes) > 1:
            parents = []
            for offset in range(0, len(routes), ROUTING_FANOUT):
                chunk = routes[offset:offset + ROUTING_FANOUT]
                name = f'{prefix}_route{depth}_{offset // ROUTING_FANOUT}'
                h.script(name, '(cond\n' + '\n'.join(
                    f'((and (>= sv_tree_key {low}) (<= sv_tree_key {high})) ({child}))'
                    for low, high, child in chunk) + ')')
                parents.append((chunk[0][0], chunk[-1][1], name))
            routes = parents
            depth += 1
        by_id = {node['id']: node for node in page.nodes}
        body = ['(set sv_tree_key 0)',
                '(set sv_tree_valid (and (>= sv_stage 1) (<= sv_stage 4) (>= sv_tokens 0) (<= sv_tokens 50)))']
        multiplier = 1
        for node, radix in zip(page.nodes, page.radices):
            rank = node['native_global']
            checks = [f'(>= sv_stage {node["stage"]})', f'(>= sv_tokens {node["costs"][0]})']
            checks.extend(f'(>= {by_id[p["id"]]["native_global"]} {p["rank"]})'
                          for p in node['prerequisites'])
            checks.extend(f'(= {other["native_global"]} 0)' for other in page.nodes
                          if other['id'] != node['id'] and node['exclusive_group']
                          and other['exclusive_group'] == node['exclusive_group'])
            body.extend([
                f'(if (or (< {rank} {node["initial_rank"]}) (> {rank} {node["max_rank"]})) (set sv_tree_valid false))',
                '(set sv_tree_digit 0)',
                f'(if (> {rank} 0) (set sv_tree_digit (+ {rank} 1))',
                f'    (if {_and(checks)} (set sv_tree_digit 1)))',
                f'(set sv_tree_key (+ sv_tree_key (* sv_tree_digit {multiplier})))',
            ])
            multiplier *= radix
        body.append(f'(if sv_tree_valid ({routes[0][2]}))')
        h.script(f'{prefix}_key', '\n'.join(body))
        # Exact membership also supports future non-contiguous catalog order.
        membership = [f'(= sv_selection {index})' for index in page.indices]
        condition = membership[0] if len(membership) == 1 else '(or ' + ' '.join(membership) + ')'
        select.append(f'({condition} ({prefix}_key))')
    h.script('sv_tree_display', f'(hud_set_training_text {FALLBACK_ID})\n(cond\n' + '\n'.join(select) + ')')
