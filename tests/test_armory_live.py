"""Live graph behavior in the source VM; no claim about native rendering."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import armory_live as live
from armory_presentation import build_armory_pages
from hsc_vm import VM, parse
from progression_catalog import CATALOG
from progression_hsc import HSC


class LiveVM(VM):
    def __init__(self):
        self.globals = {node['native_global']: node['initial_rank'] for node in CATALOG['nodes']}
        self.globals.update(sv_selection=0, sv_stage=1, sv_tokens=3)
        self.scripts = {}
        self.calls = []
        self.trace = []
        h = HSC()
        live.emit_runtime(h)
        for form in parse(h.render()):
            if form[0] == 'global':
                self.globals[form[2]] = form[3]
            else:
                self.scripts[form[3]] = form[4:]

    def run(self, name):
        self.trace.append(name)
        return super().run(name)

    def eval(self, expression):
        if isinstance(expression, list) and expression[0] == 'hud_set_training_text':
            self.calls.append(str(expression[1]))
            return None
        return super().eval(expression)

    def display(self, ranks=None, *, stage=1, wallet=3, selection=0):
        self.globals.update({node['native_global']: node['initial_rank'] for node in CATALOG['nodes']})
        by_id = {node['id']: node for node in CATALOG['nodes']}
        for node_id, rank in (ranks or {}).items():
            self.globals[by_id[node_id]['native_global']] = rank
        self.globals.update(sv_selection=selection, sv_stage=stage, sv_tokens=wallet)
        self.calls.clear()
        self.trace.clear()
        self.run('sv_tree_display')
        return self.calls[-1]


class LiveArmoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = live._model()
        cls.messages = live.messages()

    def test_import_is_silent_and_writes_nothing(self):
        code = '''import sys
def audit(event, args):
    if event == 'open':
        mode, flags = args[1], args[2]
        if isinstance(mode, str) and any(c in mode for c in 'wax+'):
            raise RuntimeError('write on import')
        if isinstance(flags, int) and flags & (1 | 2 | 64 | 512 | 1024):
            raise RuntimeError('write on import')
sys.addaudithook(audit)
import armory_live
'''
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-c',
                                     'import sys; sys.path.insert(0, ' + repr(str(ROOT)) + ')\n' + code],
                                    cwd=directory, capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, '')
            self.assertEqual(result.stderr, '')
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_every_node_has_one_page_and_all_dependencies_remain_local(self):
        layout = live.page_layout()
        self.assertEqual([len(nodes) for _, nodes in layout], [7] * 6 + [3, 2, 3])
        owners = {node_id: page_id for page_id, nodes in layout for node_id in nodes}
        self.assertEqual(sum(len(nodes) for _, nodes in layout), 50)
        self.assertEqual(set(owners), {node['id'] for node in CATALOG['nodes']})
        self.assertEqual(self.pages[6].indices, (42, 43, 44))
        self.assertEqual(self.pages[7].indices, (45, 46))
        self.assertEqual(self.pages[8].indices, (47, 48, 49))
        for node in CATALOG['nodes']:
            for prerequisite in node['prerequisites']:
                self.assertEqual(owners[node['id']], owners[prerequisite['id']])

    def test_all_601_snapshots_match_independent_presentation_and_execute_correct_lookup(self):
        vm = LiveVM()
        seen = set()
        for page in self.pages:
            for snapshot in page.snapshots:
                ranks = dict(zip((node['id'] for node in page.nodes), snapshot.ranks))
                expected = {node.id: node for view in build_armory_pages(
                    ranks, stage=snapshot.stage, points=snapshot.wallet) for node in view.nodes}
                self.assertEqual(snapshot.states,
                                 tuple((expected[node['id']].rank, expected[node['id']].state)
                                       for node in page.nodes))
                actual = vm.display(ranks, stage=snapshot.stage, wallet=snapshot.wallet,
                                    selection=page.indices[0])
                self.assertEqual(actual, snapshot.string_id)
                self.assertEqual(vm.globals['sv_tree_key'], snapshot.key)
                self.assertEqual(vm.calls, [live.FALLBACK_ID, snapshot.string_id])
                # Runtime follows one bounded route; it does not scan all cases.
                self.assertEqual(sum('_leaf' in name for name in vm.trace), 1)
                self.assertLessEqual(len(vm.trace), 5)
                for node, (rank, state) in zip(page.nodes, snapshot.states):
                    self.assertIn(live._label(node) + str(rank) + live.STATE_MARKERS[state],
                                  self.messages[actual])
                seen.add(actual)
        self.assertEqual(len(seen), 601)
        self.assertEqual(seen | {live.FALLBACK_ID}, set(self.messages))

    def test_every_selection_resolves_its_actual_page(self):
        vm = LiveVM()
        for page in self.pages:
            expected = vm.display(selection=page.indices[0])
            self.assertNotEqual(expected, live.FALLBACK_ID)
            for index in page.indices:
                self.assertEqual(vm.display(selection=index), expected)

    def test_live_points_stage_purchase_and_exclusive_state_changes(self):
        vm = LiveVM()
        text = lambda ranks=None, **kw: self.messages[vm.display(ranks, **kw)]
        self.assertIn('Power0-', text(wallet=0))
        self.assertIn('Power0+', text(wallet=1))
        self.assertIn('Power1o', text({'needler.damage': 1}, wallet=0))
        self.assertIn('Power3*', text({'needler.damage': 3}, wallet=0))
        prepared = {'needler.damage': 1, 'needler.cadence': 1}
        self.assertIn('Seeker0-', text(prepared, stage=1))
        self.assertIn('Seeker0+', text(prepared, stage=2))
        self.assertIn('Crystal0+', text(prepared, stage=2))
        prepared['needler.seeker'] = 1
        rendered = text(prepared, stage=2)
        self.assertIn('Seeker1o', rendered)
        self.assertIn('Crystal0-', rendered)
        prepared.update({'needler.damage': 2, 'needler.cadence': 2, 'needler.seeker': 2})
        self.assertIn('Long Reach0-', text(prepared, stage=3))
        self.assertIn('Long Reach0+', text(prepared, stage=4))

    def test_support_prerequisites_and_split_pages_change_at_correct_thresholds(self):
        vm = LiveVM()
        text = lambda ranks=None, **kw: self.messages[vm.display(ranks, **kw)]
        self.assertIn('Armor0-', text(selection=43))
        self.assertIn('Armor0+', text({'support.vitality': 1}, selection=43))
        self.assertIn('Cycle0-', text({'support.aegis': 1}, stage=2, selection=46))
        self.assertIn('Cycle0+', text({'support.aegis': 2}, stage=2, selection=46))
        self.assertIn('Scholar0-', text({'support.insight': 2}, stage=3, selection=49))
        self.assertIn('Scholar0+', text({'support.insight': 3}, stage=3, selection=49))

    def test_unknown_selection_invalid_values_and_unreachable_branches_replace_stale_text(self):
        vm = LiveVM()
        vm.display()
        for ranks, options in [({}, {'selection': -1}), ({}, {'selection': 50}),
                               ({}, {'stage': 0}), ({}, {'stage': 5}),
                               ({}, {'wallet': -1}), ({}, {'wallet': 51}),
                               ({'needler.damage': -1}, {}), ({'needler.damage': 4}, {}),
                               ({'needler.unlock': 0}, {}),
                               ({'needler.damage': 1, 'needler.cadence': 1,
                                 'needler.seeker': 1, 'needler.crystal': 1}, {'stage': 2})]:
            with self.subTest(ranks=ranks, options=options):
                self.assertEqual(vm.display(ranks, **options), live.FALLBACK_ID)
                self.assertEqual(vm.calls, [live.FALLBACK_ID])

    def test_identical_key_is_reasserted_for_external_hud_loss_or_continue(self):
        vm = LiveVM()
        first = vm.display()
        vm.calls.clear()
        vm.run('sv_tree_display')
        self.assertEqual(vm.calls, [live.FALLBACK_ID, first])

    def test_compact_layout_preserves_labels_branches_and_crlf_budget(self):
        self.assertEqual(max(map(len, self.messages.values())), 104)
        for name, text in self.messages.items():
            self.assertRegex(name, r'^[a-z][a-z0-9_]{0,30}$')
            self.assertTrue(text.isascii())
            self.assertLessEqual(len(text), 110)
            self.assertNotIn('\n', text.replace('\r\n', ''))
            self.assertNotIn('\r', text.replace('\r\n', ''))
        for page in self.pages[:6]:
            for snapshot in page.snapshots:
                lines = snapshot.text.split('\r\n')
                self.assertEqual(len(lines), 7)
                self.assertEqual(lines[1], ' / \\')
                self.assertEqual(lines[3], ' \\ /')
                self.assertEqual(lines[5], ' |     |')
                self.assertIn(live._label(page.nodes[3]), lines[4])
                self.assertIn(live._label(page.nodes[4]), lines[6])
                self.assertIn(live._label(page.nodes[5]), lines[4])
                self.assertIn(live._label(page.nodes[6]), lines[6])

    def test_callers_cannot_mutate_cached_messages_and_repeat_generation_is_deterministic(self):
        first = live.messages()
        first[live.FALLBACK_ID] = 'changed'
        first.pop(next(key for key in first if key != live.FALLBACK_ID))
        self.assertEqual(live.messages(), self.messages)
        h1, h2 = HSC(), HSC()
        live.emit_runtime(h1)
        live.emit_runtime(h2, deepcopy(CATALOG))
        self.assertEqual(h1.render(), h2.render())
        self.assertEqual(len(h1.globals), 3)
        self.assertIn('(global long sv_tree_key 0)', h1.render())
        self.assertEqual(len(h1.scripts), 84)
        for form in parse(h1.render()):
            if form[0] == 'script' and '_leaf' in form[3]:
                self.assertLessEqual(len(form[4:]), 10)
            if form[0] == 'script' and '_route' in form[3]:
                self.assertLessEqual(len(form[4][1:]), 10)

    def test_cross_page_prerequisite_and_overlong_labels_fail_visibly(self):
        altered = deepcopy(CATALOG)
        altered['nodes'][1]['prerequisites'].append({'id': 'support.vitality', 'rank': 1})
        with self.assertRaisesRegex(ValueError, 'dependency context'):
            live.messages(altered)
        altered = deepcopy(CATALOG)
        altered['nodes'][4]['name'] = 'Needler: ' + 'A' * 100
        with self.assertRaisesRegex(ValueError, 'character budget'):
            live.messages(altered)

    def test_topology_changes_cannot_silently_render_old_connectors(self):
        altered = deepcopy(CATALOG)
        altered['nodes'][1]['prerequisites'] = [{'id': 'needler.cadence', 'rank': 1}]
        with self.assertRaisesRegex(ValueError, 'Weapon prerequisites changed'):
            live.messages(altered)
        altered = deepcopy(CATALOG)
        altered['nodes'][3]['exclusive_group'] = None
        with self.assertRaisesRegex(ValueError, 'exclusivity changed'):
            live.messages(altered)
        altered = deepcopy(CATALOG)
        altered['nodes'][43]['prerequisites'] = [{'id': 'support.shield', 'rank': 1}]
        with self.assertRaisesRegex(ValueError, 'Support prerequisites/exclusivity changed'):
            live.messages(altered)


if __name__ == '__main__':
    unittest.main()
