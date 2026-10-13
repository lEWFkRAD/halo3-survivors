"""Small guard/layout checks; the full catalog CLI is audited separately once."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import armory_graph_budget as budget
from progression_catalog import CATALOG


def tiny_catalog():
    def node(name, costs, *, initial=0, stage=1, requirements=(), group=None):
        return {'id': name, 'name': name, 'weapon': None, 'native_global': 'sv_' + name,
                'description': 'fixture', 'effects': [], 'max_rank': len(costs),
                'costs': costs, 'initial_rank': initial, 'stage': stage,
                'prerequisites': [{'id': parent, 'rank': rank} for parent, rank in requirements],
                'exclusive_group': group}
    return {'version': 1, 'weapons': {}, 'nodes': [
        node('root', [1, 2], initial=1),
        node('a', [2, 3], stage=2, requirements=[('root', 2)], group='choice'),
        node('b', [2], stage=2, requirements=[('root', 2)], group='choice')]}


class GraphBudgetTests(unittest.TestCase):
    def test_import_is_silent_and_performs_no_file_writes(self):
        root = Path(__file__).resolve().parents[1]
        code = """import sys
def audit(event, args):
    if event == 'open':
        mode, flags = args[1], args[2]
        if isinstance(mode, str) and any(c in mode for c in 'wax+'):
            raise RuntimeError('Unexpected write during import')
        if isinstance(flags, int) and flags & (1 | 2 | 64 | 512 | 1024):
            raise RuntimeError('Unexpected write during import')
sys.addaudithook(audit)
import armory_graph_budget
"""
        with tempfile.TemporaryDirectory() as directory:
            code = 'import sys; sys.path.insert(0, ' + repr(str(root)) + ')\n' + code
            result = subprocess.run([sys.executable, '-B', '-c', code], cwd=directory,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, '')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_each_layout_preserves_all_fifty_nodes_and_every_prerequisite(self):
        layouts = budget.comparison_layouts()
        self.assertEqual([len(groups) for _, groups in layouts], [7, 8, 9, 10])
        for name, groups in layouts:
            with self.subTest(layout=name):
                budget.validate_groups(groups)
                owners = {node['id']: page for page, nodes in groups for node in nodes}
                self.assertEqual(len(owners), 50)
                self.assertEqual(set(owners), {node['id'] for node in CATALOG['nodes']})
                self.assertEqual(sum(len(nodes) for _, nodes in groups), 50)
                for node in CATALOG['nodes']:
                    for prerequisite in node['prerequisites']:
                        self.assertEqual(owners[node['id']], owners[prerequisite['id']])

    def test_tiny_reachability_honors_initial_ranks_stage_prerequisites_and_exclusivity(self):
        nodes = tiny_catalog()['nodes']
        needs, exclusive = budget.setup(nodes)
        self.assertEqual(budget.reachable_ranks(nodes, needs, exclusive, 1),
                         {(1, 0, 0), (2, 0, 0)})
        self.assertEqual(budget.reachable_ranks(nodes, needs, exclusive, 2),
                         {(1, 0, 0), (2, 0, 0), (2, 1, 0), (2, 2, 0), (2, 0, 1)})

    def test_tiny_guard_reasons_follow_native_priority(self):
        nodes = tiny_catalog()['nodes']
        needs, exclusive = budget.setup(nodes)
        for ranks, stage, wallet, expected in [
            ((1, 2, 1), 1, 0, 'maxed'), ((1, 0, 1), 1, 0, 'stage'),
            ((1, 0, 1), 2, 0, 'prerequisite'), ((2, 0, 1), 2, 0, 'exclusive'),
            ((2, 0, 0), 2, 0, 'points'), ((2, 0, 0), 2, 2, 'available')]:
            with self.subTest(expected=expected):
                full, _, _ = budget.visible(nodes, needs, exclusive, ranks, stage, wallet)
                self.assertEqual(full[1][1], expected)

    def test_reachability_cannot_purchase_a_rank_above_the_shared_wallet_cap(self):
        nodes = tiny_catalog()['nodes']
        nodes[0]['costs'][1] = 60
        needs, exclusive = budget.setup(nodes)
        self.assertEqual(budget.reachable_ranks(nodes, needs, exclusive, 4), {(1, 0, 0)})

    def test_owned_state_deduplicates_affordability_but_detailed_schemes_retain_it(self):
        nodes = tiny_catalog()['nodes']
        needs, exclusive = budget.setup(nodes)
        poor = budget.visible(nodes, needs, exclusive, (2, 1, 0), 2, 0)
        rich = budget.visible(nodes, needs, exclusive, (2, 1, 0), 2, 50)
        self.assertNotEqual(poor[0], rich[0])
        self.assertNotEqual(poor[1], rich[1])
        self.assertEqual(poor[2], rich[2])
        self.assertEqual(poor[2][1], (1, 'purchased'))

    def test_tiny_page_saturates_shared_wallet_and_crosschecks_reference_model(self):
        catalog = tiny_catalog()
        page = budget.count_page('tiny', catalog['nodes'], catalog=catalog)
        self.assertEqual(page['distinct_rank_tuples'], 5)
        self.assertEqual(page['saturated_wallet'], 3)
        self.assertEqual(page['max_spent_points'], 7)
        self.assertEqual([s['reachable_rank_tuples'] for s in page['stage_details']], [2, 5, 5, 5])
        self.assertEqual(page['reference_crosschecks'], 17)

    def test_groups_reject_missing_duplicate_or_external_prerequisite_nodes(self):
        catalog = tiny_catalog()
        nodes = catalog['nodes']
        with self.assertRaisesRegex(ValueError, 'cover every'):
            budget.validate_groups([('one', nodes[:1])], catalog)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            budget.validate_groups([('one', nodes), ('duplicate', nodes)], catalog)
        with self.assertRaisesRegex(ValueError, 'dependency context'):
            budget.validate_groups([('root', nodes[:1]), ('branches', nodes[1:])], catalog)

    def test_groups_do_not_silently_drop_exclusivity_when_splitting(self):
        catalog = deepcopy(tiny_catalog())
        for node in catalog['nodes']:
            node['prerequisites'] = []
        with self.assertRaisesRegex(ValueError, 'Exclusive group split'):
            budget.validate_groups([('first', catalog['nodes'][:2]),
                                    ('second', catalog['nodes'][2:])], catalog)

    def test_dispatch_estimate_has_explicit_baseline_and_bounded_routing(self):
        pages = [{'all_stage_distinct': {'coarse_ownership': 25}}]
        estimate = budget.dispatch_estimate(pages, 10, native_baseline=123)
        self.assertEqual(estimate['leaf_scripts'], 3)
        self.assertEqual(estimate['routing_scripts'], 1)
        self.assertEqual(estimate['page_and_key_helpers'], 2)
        self.assertEqual(estimate['native_total_estimate'], 129)
        self.assertEqual(estimate['leaf_plus_route_ast_nodes'], 25 * 9 + 3 * 14)
        for args in ({'leaf_cases': 0}, {'leaf_cases': 10, 'routing_fanout': 1},
                     {'leaf_cases': 10, 'native_baseline': -1}):
            with self.assertRaises(ValueError):
                budget.dispatch_estimate(pages, **args)

    def test_cli_prints_json_by_default_and_can_write_only_explicit_output(self):
        report = {'fixture': True}
        output = io.StringIO()
        with patch.object(budget, 'build_report', return_value=report) as build:
            with redirect_stdout(output):
                self.assertEqual(budget.main(['--native-baseline', '123']), 0)
            build.assert_called_once_with(native_baseline=123)
        self.assertEqual(json.loads(output.getvalue()), report)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'budget.json'
            output = io.StringIO()
            with patch.object(budget, 'build_report', return_value=report), redirect_stdout(output):
                self.assertEqual(budget.main(['--output', str(target)]), 0)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(json.loads(target.read_text()), report)


if __name__ == '__main__':
    unittest.main()
