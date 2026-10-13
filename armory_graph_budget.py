"""Count LS-05 graph snapshots; budgets alone do not establish UI feasibility.

Run ``python -B armory_graph_budget.py`` for JSON stdout, or add ``--output PATH``.
Importing this module does not run enumeration, print or write files. It never
activates native tools. The SDK spike observed four concurrent cinematic titles
and clipping in long training messages. Twelve short lines and a 75-character
sample rendered completely; the unwrapped ruler clipped off-screen, so the
exact character/glyph/bounds limit remains unresolved. Current display behavior
blocks a complete long graph, though further font/bounds work may change that. Budget arithmetic alone cannot resolve the rendering issue.

Catalog rank reachability allows point
earnings up to the shared wallet cap; it does not model timed encounter XP yield.
Selected focus, current stage/wallet labels and selected purchase explanations
are external to each precomputed page string and do not multiply string counts.
"""
from collections import deque
from hashlib import sha256
from math import ceil, prod
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parent
from progression_catalog import CATALOG
from armory_presentation import build_armory_pages

SCHEMES = ('full_reason', 'buy_available', 'coarse_ownership')
WALLET_CAP = 50
DEFAULT_NATIVE_BASELINE = 402  # Estimate input, not a freshly measured count.


def setup(nodes):
    ids = {node['id']: index for index, node in enumerate(nodes)}
    external = [(p['id'], node['id']) for node in nodes
                for p in node['prerequisites'] if p['id'] not in ids]
    if external:
        raise ValueError(f'Enumeration groups must retain dependency context: {external}')
    needs = [[(ids[p['id']], p['rank']) for p in node['prerequisites']] for node in nodes]
    exclusive = [[j for j, other in enumerate(nodes)
                  if j != i and node['exclusive_group']
                  and node['exclusive_group'] == other['exclusive_group']]
                 for i, node in enumerate(nodes)]
    return needs, exclusive


def reachable_ranks(nodes, needs, exclusive, stage):
    initial = tuple(node['initial_rank'] for node in nodes)
    found = {initial}
    pending = deque([initial])
    while pending:
        ranks = pending.popleft()
        for i, node in enumerate(nodes):
            if (ranks[i] >= node['max_rank'] or stage < node['stage']
                    or node['costs'][ranks[i]] > WALLET_CAP
                    or any(ranks[p] < rank for p, rank in needs[i])
                    or any(ranks[j] > 0 for j in exclusive[i])):
                continue
            new = list(ranks)
            new[i] += 1
            new = tuple(new)
            if new not in found:
                found.add(new)
                pending.append(new)
    return found


def visible(nodes, needs, exclusive, ranks, stage, wallet):
    full, available, coarse = [], [], []
    for i, node in enumerate(nodes):
        rank = ranks[i]
        reason = ('maxed' if rank >= node['max_rank'] else
                  'stage' if stage < node['stage'] else
                  'prerequisite' if any(ranks[p] < r for p, r in needs[i]) else
                  'exclusive' if any(ranks[j] > 0 for j in exclusive[i]) else
                  'points' if wallet < node['costs'][rank] else 'available')
        full.append((rank, reason))
        available.append((rank, reason == 'available'))
        coarse.append((rank, 'maxed' if rank >= node['max_rank'] else
                       'purchased' if rank > 0 else
                       'available' if reason == 'available' else 'locked'))
    return tuple(full), tuple(available), tuple(coarse)


def count_page(name, nodes, *, catalog=CATALOG):
    needs, exclusive = setup(nodes)
    all_views = [set(), set(), set()]
    all_reachable = set()
    by_stage = []
    saturation = min(WALLET_CAP, max(max(node['costs']) for node in nodes))
    crosschecks = 0
    # Sorting makes the bounded reference-model sample deterministic as well.
    for stage in range(1, 5):
        reachable = reachable_ranks(nodes, needs, exclusive, stage)
        all_reachable.update(reachable)
        stage_views = [set(), set(), set()]
        for ranks in sorted(reachable):
            for wallet in range(saturation + 1):
                keys = visible(nodes, needs, exclusive, ranks, stage, wallet)
                for bucket, key in zip(stage_views, keys):
                    bucket.add(key)
                for bucket, key in zip(all_views, keys):
                    bucket.add(key)
            # Every greater wallet has identical guards because there are no
            # next-rank prices above saturation. Also check the endpoint.
            assert visible(nodes, needs, exclusive, ranks, stage, saturation) == visible(
                nodes, needs, exclusive, ranks, stage, WALLET_CAP)
            if crosschecks < 80:
                wallet = crosschecks % (saturation + 1)
                snapshot = {node['id']: rank for node, rank in zip(nodes, ranks)}
                model = {node.id: node for page in build_armory_pages(
                    snapshot, stage=stage, points=wallet, catalog=catalog) for node in page.nodes}
                expected = tuple((model[node['id']].rank,
                                  model[node['id']].reason or 'available') for node in nodes)
                assert expected == visible(nodes, needs, exclusive, ranks, stage, wallet)[0]
                crosschecks += 1
        by_stage.append({'stage': stage, 'reachable_rank_tuples': len(reachable),
                         **{scheme: len(bucket) for scheme, bucket in zip(SCHEMES, stage_views)}})
    max_spent = max(sum(sum(node['costs'][node['initial_rank']:rank])
                        for node, rank in zip(nodes, ranks)) for ranks in all_reachable)
    return {
        'page': name, 'node_ids': [node['id'] for node in nodes],
        'raw_including_zero': prod(node['max_rank'] + 1 for node in nodes),
        'raw_initial_rank_lower_bound': prod(node['max_rank'] - node['initial_rank'] + 1 for node in nodes),
        'stage_details': by_stage, 'distinct_rank_tuples': len(all_reachable),
        'max_spent_points': max_spent, 'saturated_wallet': saturation,
        'max_path_fits_one_full_wallet': max_spent <= WALLET_CAP,
        'all_stage_distinct': {scheme: len(bucket) for scheme, bucket in zip(SCHEMES, all_views)},
        'reference_crosschecks': crosschecks,
    }


def dispatch_estimate(pages, leaf_cases, routing_fanout=10, scheme='coarse_ownership',
                      *, native_baseline=DEFAULT_NATIVE_BASELINE):
    if leaf_cases < 1 or routing_fanout < 2 or native_baseline < 0:
        raise ValueError('Leaf cases must be positive, fanout at least two, and baseline nonnegative')
    leaves = [ceil(page['all_stage_distinct'][scheme] / leaf_cases) for page in pages]
    routes = 0
    for number in leaves:
        while number > 1:
            number = ceil(number / routing_fanout)
            routes += number
    page_and_key_helpers = 1 + len(pages)
    total_cases = sum(page['all_stage_distinct'][scheme] for page in pages)
    # One bounded routing forest, with one root per page. A leaf is a static
    # script of independent if statements, not a nested conditional tree.
    edges = sum(leaves) + routes - len(pages)
    return {
        'scheme': scheme, 'leaf_cases': leaf_cases, 'routing_fanout': routing_fanout,
        'literal_training_text_cases': total_cases, 'leaf_scripts': sum(leaves),
        'routing_scripts': routes, 'page_and_key_helpers': page_and_key_helpers,
        'total_added_scripts': sum(leaves) + routes + page_and_key_helpers,
        'native_baseline_estimate': native_baseline,
        'native_total_estimate': native_baseline + sum(leaves) + routes + page_and_key_helpers,
        'approx_leaf_source_bytes': total_cases * 67,
        'leaf_ast_atoms': total_cases * 6, 'leaf_ast_list_forms': total_cases * 3,
        'routing_case_edges': edges,
        'leaf_plus_route_ast_nodes': total_cases * 9 + edges * 14,
    }


def validate_groups(groups, catalog=CATALOG):
    """Reject dropped/duplicated nodes and split prerequisites/exclusive groups."""
    owners = {}
    exclusive_owners = {}
    for page, nodes in groups:
        if not nodes:
            raise ValueError(f'Empty page: {page}')
        setup(nodes)
        for node in nodes:
            if node['id'] in owners:
                raise ValueError(f'Duplicate node: {node["id"]}')
            owners[node['id']] = page
            group = node['exclusive_group']
            if group and exclusive_owners.setdefault(group, page) != page:
                raise ValueError(f'Exclusive group split across pages: {group}')
    if set(owners) != {node['id'] for node in catalog['nodes']}:
        raise ValueError('Pages must cover every catalog node exactly once')


def count_option(name, groups, *, native_baseline=DEFAULT_NATIVE_BASELINE):
    validate_groups(groups)
    pages = [count_page(page, nodes) for page, nodes in groups]
    ids = [node_id for page in pages for node_id in page['node_ids']]
    assert sorted(ids) == sorted(node['id'] for node in CATALOG['nodes'])
    assert len(ids) == len(set(ids)) == 50
    return {
        'name': name, 'page_count': len(pages), 'covered_node_count': len(ids),
        'cross_page_prerequisites': [], 'pages': pages,
        'snapshot_totals': {scheme: sum(page['all_stage_distinct'][scheme] for page in pages)
                            for scheme in SCHEMES},
        'ten_case_dispatch_by_scheme': {scheme: dispatch_estimate(pages, 10, scheme=scheme, native_baseline=native_baseline)
                                        for scheme in SCHEMES},
        'dispatch_estimates': [dispatch_estimate(pages, width, native_baseline=native_baseline) for width in (8, 10, 16, 20, 24, 32, 64)],
    }


def comparison_layouts():
    original = []
    for node in CATALOG['nodes']:
        name = node['weapon'] or 'support'
        if not original or original[-1][0] != name:
            original.append((name, []))
        original[-1][1].append(node)
    support = original[-1][1]
    defense_ids = {'support.vitality', 'support.body', 'support.shield',
                   'support.aegis', 'support.aegis_cycle'}
    split = original[:-1] + [
        ('support_defense', [node for node in support if node['id'] in defense_ids]),
        ('support_reach_xp', [node for node in support if node['id'] not in defense_ids]),
    ]
    vitality_ids = {'support.vitality', 'support.body', 'support.shield'}
    recovery_ids = {'support.aegis', 'support.aegis_cycle'}
    split_three = original[:-1] + [
        ('support_vitality_armor', [node for node in support if node['id'] in vitality_ids]),
        ('support_recovery', [node for node in support if node['id'] in recovery_ids]),
        ('support_reach_xp', [node for node in support if node['id'] not in defense_ids]),
    ]
    # These are the four weakly connected support components. Splitting any
    # further requires a cross-page prerequisite; grouping them is a UX choice.
    connected_components = split_three[:-1] + [
        ('support_reach', [node for node in support if node['id'] == 'support.reach']),
        ('support_xp', [node for node in support if node['id'] in {'support.insight', 'support.scholar'}]),
    ]
    return [('original_seven_pages', original),
            ('six_weapon_plus_two_support_pages', split),
            ('six_weapon_plus_three_support_pages', split_three),
            ('six_weapon_plus_four_connected_support_components', connected_components)]


def build_report(*, native_baseline=DEFAULT_NATIVE_BASELINE):
    if native_baseline < 0:
        raise ValueError('Native script baseline estimate must be nonnegative')
    return {
        'catalog_version': CATALOG['version'],
        'catalog_content_sha256': sha256(json.dumps(CATALOG, sort_keys=True).encode()).hexdigest(),
        'catalog_source_sha256': sha256((ROOT / 'progression_catalog.py').read_bytes()).hexdigest(),
        'assumptions': {
            'stages': [1, 2, 3, 4], 'shared_wallet_range': [0, WALLET_CAP],
            'wallet_saturation': 'Every amount at or above the highest page node cost has identical purchase guards.',
            'reachability': 'Breadth-first single-rank purchases from catalog initial ranks under stage/prerequisite/exclusivity guards, with earnable points. Timed encounter XP yield is not modeled.',
            'full_reason_equivalence': 'Per-node actual rank plus primary purchase reason: maxed, stage, prerequisite, exclusive, points, or available.',
            'buy_available_equivalence': 'Per-node actual rank plus can-buy-next-rank boolean; ownership/maxed are derivable from rank.',
            'coarse_ownership_equivalence': 'Per-node actual rank plus maxed/purchased/available/locked. Purchased-node affordability and reasons belong to selected detail.',
            'external_labels': 'Selected focus/details and exact current stage/wallet labels do not multiply graph strings.',
            'native_string_budget_given': 24576, 'native_script_guard': 1024,
            'baseline_native_scripts_estimate': native_baseline,
            'script_estimate': 'Sum ceil(snapshot_count / leaf_cases) leaves, ten-way routing until one root per page, one category helper and one key helper per page, added to the supplied baseline estimate. These are estimates, not compiled counts.',
            'datum_estimate': 'A flat literal HUD case has 6 AST atoms + 3 list forms; a bounded range-route case has 14 AST nodes. AST nodes are not verified native syntax datums.',
            'native_status': 'Budget counts do not establish feasibility. The SDK spike observed four concurrent cinematic titles and clipping in long training messages. Twelve short lines and a 75-character sample rendered completely. The unwrapped ruler clipped off-screen; the exact character/glyph/bounds limit remains unresolved. Current display behavior blocks a complete graph, though font/bounds work may change that. This enumerator does not validate a replacement renderer, native compilation, runtime stack or actual string-pool capacity.',
        },
        'options': [count_option(name, groups, native_baseline=native_baseline)
                    for name, groups in comparison_layouts()],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Write JSON to this path instead of stdout')
    parser.add_argument('--native-baseline', type=int, default=DEFAULT_NATIVE_BASELINE,
                        help='Existing native script count used only as an estimate (default: 402)')
    args = parser.parse_args(argv)
    if args.native_baseline < 0:
        parser.error('--native-baseline must be nonnegative')
    text = json.dumps(build_report(native_baseline=args.native_baseline), separators=(',', ':')) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
