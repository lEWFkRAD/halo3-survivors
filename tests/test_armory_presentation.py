"""Catalog topology and display facts; these checks do not prove native UI rendering."""
from copy import deepcopy
import unittest

from armory_presentation import build_armory_pages, native_page_titles
from progression_catalog import CATALOG, NODES


def nodes_by_id(pages):
    return {node.id: node for page in pages for node in page.nodes}


class ArmoryPresentationTests(unittest.TestCase):
    def test_all_nodes_appear_once_in_catalog_order_with_stable_selection_indices(self):
        pages = build_armory_pages()
        self.assertEqual([page.id for page in pages], [
            'needler', 'assault_rifle', 'shotgun', 'plasma_rifle',
            'rocket_launcher', 'energy_sword', 'support'])
        self.assertEqual([len(page.nodes) for page in pages], [7, 7, 7, 7, 7, 7, 8])
        views = [node for page in pages for node in page.nodes]
        self.assertEqual([view.id for view in views], [node['id'] for node in NODES])
        self.assertEqual([view.catalog_index for view in views], list(range(50)))
        self.assertEqual(len({view.id for view in views}), 50)
        for view, node in zip(views, NODES):
            with self.subTest(node=view.id):
                self.assertEqual(view.name, node['name'])
                self.assertEqual(view.description, node['description'])
                self.assertEqual([(e.stat, e.per_rank) for e in view.effects],
                                 [(e['stat'], e['per_rank']) for e in node['effects']])

    def test_needler_edges_include_both_power_and_cadence_and_capstone_requirements(self):
        page = build_armory_pages()[0]
        self.assertEqual([(n.id, n.max_rank) for n in page.nodes], [
            ('needler.unlock', 1), ('needler.damage', 3), ('needler.cadence', 3),
            ('needler.seeker', 2), ('needler.seeker_capstone', 1),
            ('needler.crystal', 2), ('needler.crystal_capstone', 1)])
        actual = {(e.source, e.target, e.required_rank) for e in page.edges}
        expected = {('needler.unlock', 'needler.damage', 1),
                    ('needler.unlock', 'needler.cadence', 1)}
        for branch in ('seeker', 'crystal'):
            expected.update({
                ('needler.damage', f'needler.{branch}', 1),
                ('needler.cadence', f'needler.{branch}', 1),
                (f'needler.{branch}', f'needler.{branch}_capstone', 2),
                ('needler.damage', f'needler.{branch}_capstone', 2),
                ('needler.cadence', f'needler.{branch}_capstone', 2)})
        self.assertEqual(actual, expected)
        self.assertTrue(all(e.source_page == e.target_page == 'needler' for e in page.edges))

    def test_support_dependencies_are_exact_and_not_added_to_weapons(self):
        pages = build_armory_pages()
        self.assertEqual({(e.source, e.target, e.required_rank) for e in pages[-1].edges}, {
            ('support.vitality', 'support.body', 1),
            ('support.vitality', 'support.shield', 1),
            ('support.aegis', 'support.aegis_cycle', 2),
            ('support.insight', 'support.scholar', 3)})
        self.assertFalse(any(e.source.startswith('support.') for page in pages[:-1] for e in page.edges))

    def test_cross_page_requirement_is_exposed_when_explicitly_declared(self):
        catalog = deepcopy(CATALOG)
        catalog['nodes'][1]['prerequisites'].append({'id': 'support.reach', 'rank': 2})
        page = build_armory_pages({'support.reach': 1}, points=10, catalog=catalog)[0]
        power = next(node for node in page.nodes if node.id == 'needler.damage')
        requirement = power.prerequisites[-1]
        self.assertEqual((requirement.id, requirement.page_id, requirement.rank, requirement.actual_rank),
                         ('support.reach', 'support', 2, 1))
        self.assertFalse(requirement.met)
        edge = next(e for e in page.edges if e.source == 'support.reach')
        self.assertEqual((edge.source_page, edge.target_page, edge.target),
                         ('support', 'needler', 'needler.damage'))
        self.assertEqual(power.reason, 'prerequisite')

    def test_initial_needler_is_maxed_with_no_fictitious_free_next_purchase(self):
        needler = nodes_by_id(build_armory_pages(points=50))['needler.unlock']
        self.assertEqual((needler.rank, needler.max_rank, needler.state), (1, 1, 'maxed'))
        self.assertIsNone(needler.next_cost)
        self.assertFalse(needler.affordable)
        self.assertFalse(needler.can_purchase)
        self.assertEqual(needler.reason, 'maxed')

    def test_purchased_selection_and_affordability_are_independent(self):
        ranks = {'needler.damage': 1}
        poor = nodes_by_id(build_armory_pages(ranks, points=0, selected_id='needler.damage'))
        power = poor['needler.damage']
        self.assertEqual((power.state, power.rank, power.next_cost), ('purchased', 1, 1))
        self.assertTrue(power.selected and power.purchased)
        self.assertFalse(power.affordable or power.can_purchase)
        self.assertEqual(power.reason, 'points')
        rich = nodes_by_id(build_armory_pages(ranks, points=1))['needler.damage']
        self.assertTrue(rich.purchased and rich.affordable and rich.can_purchase)
        self.assertEqual(rich.state, 'purchased')
        self.assertFalse(rich.selected)

    def test_stage_locked_weapon_can_be_affordable_but_not_available(self):
        view = nodes_by_id(build_armory_pages(stage=2, points=50))['rocket_launcher.unlock']
        self.assertEqual((view.stage, view.next_cost, view.state, view.reason), (3, 5, 'locked', 'stage'))
        self.assertTrue(view.affordable)
        self.assertFalse(view.stage_unlocked or view.can_purchase)
        poor = nodes_by_id(build_armory_pages(stage=3, points=4))['rocket_launcher.unlock']
        self.assertEqual(poor.reason, 'points')
        ready = nodes_by_id(build_armory_pages(stage=3, points=5))['rocket_launcher.unlock']
        self.assertEqual((ready.state, ready.reason), ('available', None))
        self.assertTrue(ready.can_purchase)

    def test_exclusive_sibling_blocks_branch_but_capstone_uses_its_actual_prerequisites(self):
        ranks = {'needler.damage': 2, 'needler.cadence': 2, 'needler.seeker': 1}
        views = nodes_by_id(build_armory_pages(ranks, stage=4, points=50))
        seeker, crystal, capstone = [views['needler.' + name]
                                     for name in ('seeker', 'crystal', 'crystal_capstone')]
        self.assertEqual(crystal.exclusive_chosen, ('needler.seeker',))
        self.assertEqual(crystal.reason, 'exclusive')
        self.assertTrue(seeker.can_purchase)
        self.assertEqual(seeker.exclusive_chosen, ('needler.seeker',))
        self.assertIsNone(capstone.exclusive_group)
        self.assertEqual(capstone.exclusive_chosen, ())
        self.assertEqual(capstone.reason, 'prerequisite')
        self.assertEqual([(p.id, p.rank) for p in capstone.prerequisites if not p.met],
                         [('needler.crystal', 2)])
        ranks['needler.seeker'] = 2
        views = nodes_by_id(build_armory_pages(ranks, stage=4, points=50))
        self.assertTrue(views['needler.seeker_capstone'].can_purchase)
        self.assertFalse(views['needler.crystal_capstone'].can_purchase)

    def test_all_blockers_retain_native_guard_priority(self):
        ranks = {'needler.crystal': 1}
        seeker = nodes_by_id(build_armory_pages(ranks, stage=1, points=0))['needler.seeker']
        self.assertEqual(seeker.reasons, ('stage', 'prerequisite', 'exclusive', 'points'))
        self.assertEqual(seeker.reason, 'stage')
        ranks['needler.seeker'] = 2
        maxed = nodes_by_id(build_armory_pages(ranks, stage=1, points=0))['needler.seeker']
        self.assertEqual(maxed.reasons, ('maxed', 'stage', 'prerequisite', 'exclusive'))
        self.assertIsNone(maxed.next_cost)

    def test_cost_advances_with_rank_and_requires_all_prerequisite_ranks(self):
        ranks = {'needler.damage': 2, 'needler.cadence': 1, 'needler.seeker': 2}
        views = nodes_by_id(build_armory_pages(ranks, stage=4, points=50))
        self.assertEqual(views['needler.damage'].next_cost, 2)
        self.assertEqual(views['needler.seeker_capstone'].reason, 'prerequisite')
        missing = [p for p in views['needler.seeker_capstone'].prerequisites if not p.met]
        self.assertEqual([(p.id, p.rank, p.actual_rank) for p in missing], [('needler.cadence', 2, 1)])

    def test_snapshot_and_catalog_are_not_mutated(self):
        ranks = {'support.aegis': 2}
        catalog = deepcopy(CATALOG)
        expected = deepcopy(catalog)
        pages = build_armory_pages(ranks, stage=2, points=2, catalog=catalog)
        self.assertEqual(ranks, {'support.aegis': 2})
        self.assertEqual(catalog, expected)
        self.assertTrue(nodes_by_id(pages)['support.aegis_cycle'].can_purchase)

    def test_wrong_snapshot_keys_fail_instead_of_silently_showing_a_fresh_run(self):
        with self.assertRaisesRegex(ValueError, 'Unknown rank IDs'):
            build_armory_pages({'sv_nl_d': 2})
        with self.assertRaisesRegex(ValueError, 'Unknown selected ID'):
            build_armory_pages(selected_id='missing.node')
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            build_armory_pages({'needler.damage': -1})

    def test_display_reason_agrees_with_generated_native_purchase_guards(self):
        from test_progression_native import ProgressionVM
        vm = ProgressionVM()
        vm.boot()
        notices = {None: 'sv_purchased', 'maxed': 'sv_max_rank',
                   'stage': 'sv_stage_locked', 'prerequisite': 'sv_prerequisite',
                   'exclusive': 'sv_exclusive', 'points': 'sv_need_points'}
        # Exercise overlapping blockers as well as a ready purchase for every
        # real catalog node. The model reads facts; the VM executes emitted HSC.
        for node in NODES:
            prepared = {p['id']: p['rank'] for p in node['prerequisites']}
            conflicting = dict(prepared)
            if node['exclusive_group']:
                sibling = next(other for other in NODES if other['id'] != node['id']
                               and other['exclusive_group'] == node['exclusive_group'])
                conflicting[sibling['id']] = 1
            scenarios = [({}, 1, 0), (prepared, 4, 50), (prepared, 4, 0),
                         (conflicting, 1, 0), (conflicting, 4, 50),
                         ({**conflicting, node['id']: node['max_rank']}, 1, 0)]
            for ranks, stage, points in scenarios:
                with self.subTest(node=node['id'], ranks=ranks, stage=stage, points=points):
                    views = nodes_by_id(build_armory_pages(ranks, stage=stage, points=points))
                    view = views[node['id']]
                    for rank_view in views.values():
                        vm.setrank(rank_view.id, rank_view.rank)
                    vm.globals.update(sv_stage=stage, sv_tokens=points,
                                      sv_notice_clock=0, sv_notice_pending=-1)
                    vm.notice_events.clear()
                    vm.buy(node['id'])
                    self.assertEqual(vm.notice_events[-1][1], notices[view.reason])
                    self.assertEqual(vm.rank(node['id']), view.rank + int(view.can_purchase))
                    self.assertEqual(vm.globals['sv_tokens'],
                                     points - (view.next_cost if view.can_purchase else 0))


class NativeReferencePageTests(unittest.TestCase):
    def test_all_seven_static_maps_fit_the_native_text_budget(self):
        titles = native_page_titles()
        self.assertEqual(list(titles), [f'sv_tree_{i}' for i in range(7)])
        for key, title in titles.items():
            with self.subTest(title=key):
                self.assertTrue(title.isascii())
                self.assertLessEqual(len(title.splitlines()), 12)
                self.assertTrue(all(len(line) <= 60 for line in title.splitlines()))
                self.assertIn('S = stage', title)
                self.assertIn('Numbers = required ranks, not current ranks', title)
                for live_label in ('selected', 'purchased', 'affordable', 'points'):
                    self.assertNotIn(live_label, title.lower())

    def test_needler_shows_real_branch_and_capstone_requirements(self):
        lines = native_page_titles()['sv_tree_0'].splitlines()
        self.assertEqual(lines, [
            'NEEDLER | TREE | S = stage',
            'Numbers = required ranks, not current ranks',
            'Unlock [S1]',
            'Unlock1 -> Power [S1] + Cadence [S1]',
            'Power1 + Cadence1 -> choose ONE:',
            '  +-> Seeker [S2]',
            '  |   Seeker2 + Power2 + Cadence2',
            '  |   -> Long Reach [S4]',
            '  +-> Crystal [S2]',
            '      Crystal2 + Power2 + Cadence2',
            '      -> Crystal Storm [S4]'])

    def test_every_weapon_shows_its_own_nodes_and_stage_gates(self):
        titles = native_page_titles()
        for index, page in enumerate(build_armory_pages()[:-1]):
            title = titles[f'sv_tree_{index}']
            with self.subTest(page=page.id):
                self.assertIn(page.name.upper(), title)
                self.assertNotIn('Support:', title)
                positions = []
                for node in page.nodes:
                    label = node.name.removeprefix(page.name + ': ')
                    if label == 'Unlock ' + page.name:
                        label = 'Unlock'
                    positions.append(title.index(f'{label} [S{node.stage}]'))
                self.assertEqual(positions, sorted(positions))

    def test_support_has_all_actual_chains_and_independent_roots(self):
        self.assertEqual(native_page_titles()['sv_tree_6'].splitlines(), [
            'SUPPORT | TREE | S = stage',
            'Numbers = required ranks, not current ranks',
            'Vitality [S1]',
            'Vitality1 -> Body Armor [S1] + Shield Capacity [S1]',
            'Aegis [S1]',
            'Aegis2 -> Shield Cycling [S2]',
            'Targeting Reach [S1]',
            'Battlefield Insight [S1]',
            'Battlefield Insight3 -> Combat Scholar [S3]'])

    def test_maps_follow_catalog_edges_and_gates_instead_of_fixed_weapon_templates(self):
        catalog = deepcopy(CATALOG)
        by_id = {node['id']: node for node in catalog['nodes']}
        by_id['needler.seeker']['stage'] = 3
        by_id['needler.seeker_capstone']['prerequisites'][0]['rank'] = 1
        by_id['support.scholar']['prerequisites'] = [{'id': 'support.reach', 'rank': 2}]
        titles = native_page_titles(catalog)
        self.assertIn('Seeker [S3]', titles['sv_tree_0'])
        self.assertIn('Seeker1 + Power2 + Cadence2', titles['sv_tree_0'])
        self.assertIn('Targeting Reach2 -> Combat Scholar [S3]', titles['sv_tree_6'])
        self.assertNotIn('Battlefield Insight3 ->', titles['sv_tree_6'])

    def test_declared_cross_page_edge_is_not_silently_omitted(self):
        catalog = deepcopy(CATALOG)
        node = next(node for node in catalog['nodes'] if node['id'] == 'support.scholar')
        node['prerequisites'] = [{'id': 'needler.damage', 'rank': 2}]
        self.assertIn('Needler: Power2 -> Combat Scholar [S3]', native_page_titles(catalog)['sv_tree_6'])


if __name__ == '__main__':
    unittest.main()
