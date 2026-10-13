"""Exercise emitted page scheduling; native HUD rendering still needs SDK QA."""
from copy import deepcopy
import unittest
import re

from test_progression_native import ProgressionVM


def pages(vm):
    return [(tick, 'sv_tree_'+re.fullmatch(r'sv_g(\d+)_[0-9]+', name).group(1))
            for tick,name in vm.page_events]


class ArmorySchedulerTests(unittest.TestCase):
    def setUp(self):
        self.vm = ProgressionVM()
        self.vm.boot()

    def test_purchase_updates_rank_next_cost_wallet_and_graph(self):
        v=self.vm
        v.globals['sv_selection']=1
        v.menu_sample()
        before=v.training_text
        v.menu_sample('primary_trigger')
        self.assertEqual(v.globals['sv_nl_d'],1)
        self.assertEqual(v.globals['sv_tokens'],2)
        self.assertEqual([a[0] for op,a in v.calls if op=='cinematic_set_chud_objective'][-1],'sv_node_1')
        self.assertEqual(v.globals['sv_selected_rank'],1)
        self.assertEqual(v.globals['sv_cost'],1)
        v.menu_sample();v.fast_frames(8)
        self.assertNotEqual(v.training_text,before)
        self.assertEqual(v.wallet_events[-1][1],'sv_points_2')

    def test_training_hidden_on_resume_loss_and_victory(self):
        for action in ('sv_close_menu','sv_lose','sv_advance_stage'):
            v=ProgressionVM();v.boot();v.fast_frames(1)
            self.assertTrue(v.training_enabled and v.training_shown)
            if action=='sv_advance_stage':v.globals['sv_stage']=4
            v.run(action);v.fast_frames(1)
            self.assertFalse(v.training_enabled,action)

    def test_support_category_chord_visits_both_pages_then_wraps(self):
        v=self.vm;v.globals['sv_selection']=42
        v.menu_sample();v.menu_sample('jump','melee')
        self.assertEqual(v.globals['sv_selection'],47)
        v.menu_sample();v.menu_sample('jump','melee')
        self.assertEqual(v.globals['sv_selection'],0)

    def test_selected_detail_reports_exact_next_price_or_max_for_every_rank(self):
        v=self.vm
        for i,node in enumerate(v.data['nodes']):
            v.globals['sv_selection']=i
            for rank in range(node['max_rank']+1):
                v.setrank(node['id'],rank);v.run('sv_show_node')
                self.assertEqual(v.globals['sv_selected_rank'],rank)
                expected=-1 if rank==node['max_rank'] else node['costs'][rank]
                self.assertEqual(v.globals['sv_cost'],expected)
                v.run('sv_price_display')
                self.assertEqual(v.price_events[-1][1],'sv_cost_max' if expected<0 else f'sv_cost_{expected}')

    def test_all_eight_pages_follow_first_and_last_node_of_each_category(self):
        v = self.vm
        for category, (first, last) in enumerate([(0, 6), (7, 13), (14, 20),
                                                 (21, 27), (28, 34), (35, 41), (42, 46), (47, 49)]):
            for selection in (first, last):
                with self.subTest(category=category, selection=selection):
                    before = len(pages(v))
                    v.globals['sv_selection'] = selection
                    v.fast_frames(10)
                    self.assertEqual(pages(v)[before:][0][1], f'sv_tree_{category}')
                    self.assertEqual(len(pages(v)) - before, 1)
        self.assertTrue(all(b[0] - a[0] == 30 for a, b in zip(pages(v), pages(v)[1:])))

    def test_rapid_category_input_coalesces_to_latest_category_at_refresh(self):
        v = self.vm
        v.menu_sample()
        self.assertEqual(pages(v), [(3, 'sv_tree_0')])
        for _ in range(3):
            v.menu_sample('jump', 'melee')
            v.menu_sample()
        self.assertEqual(v.globals['sv_selection'], 21)
        self.assertEqual(pages(v), [(3, 'sv_tree_0')])
        v.fast_frames(3)
        self.assertEqual(len(pages(v)), 1)
        v.fast_frames(1)
        self.assertEqual(pages(v), [(3, 'sv_tree_0'), (33, 'sv_tree_3')])

    def test_navigation_crossing_category_boundary_is_visible_at_next_refresh(self):
        v = self.vm
        v.globals['sv_selection'] = 6
        v.menu_sample()
        v.menu_sample('jump')
        self.assertEqual(v.globals['sv_selection'], 7)
        v.menu_sample()
        v.fast_frames(8)
        self.assertEqual(pages(v), [(3, 'sv_tree_0'), (33, 'sv_tree_1')])

    def test_resume_on_due_frame_stops_refresh_and_reopening_uses_latest_selection(self):
        v = self.vm
        v.menu_sample()
        v.fast_frames(9)
        self.assertEqual(v.globals['sv_tree_clock'], 3)
        v.menu_sample('rotate_weapons')
        self.assertFalse(v.globals['sv_menu_open'])
        v.held_input.clear()
        v.fast_frames(40)
        self.assertEqual(pages(v), [(3, 'sv_tree_0')])
        v.globals['sv_selection'] = 42
        v.run('sv_open_menu')
        v.fast_frames(1)
        self.assertEqual(pages(v)[-1][1], 'sv_tree_6')

    def test_fast_close_and_reopen_preserves_refresh_throttle(self):
        v = self.vm
        v.menu_sample()
        v.run('sv_close_menu')
        v.globals['sv_selection'] = 35
        v.run('sv_open_menu')
        v.fast_frames(9)
        self.assertEqual(pages(v), [(3, 'sv_tree_0')])
        v.fast_frames(1)
        self.assertEqual(pages(v), [(3, 'sv_tree_0'), (33, 'sv_tree_5')])

    def test_finished_or_not_running_never_refreshes_or_changes_saved_tree_clock(self):
        for flags in ({'sv_running': False}, {'sv_finished': True}):
            with self.subTest(flags=flags):
                v = ProgressionVM()
                v.boot()
                v.fast_frames(1)
                clock = v.globals['sv_tree_clock']
                v.globals.update(flags)
                v.fast_frames(40)
                self.assertEqual(pages(v), [(3, 'sv_tree_0')])
                self.assertEqual(v.globals['sv_tree_clock'], clock)

    def test_restored_armory_clock_redraws_current_page_without_resetting_progress(self):
        v = self.vm
        v.fast_frames(1)
        v.globals.update(sv_stage=3, sv_selection=42, sv_tokens=17, sv_xp=35,
                         sv_seconds=602, sv_stage_seconds=2, sv_nl_d=2)
        restored = ProgressionVM()
        restored.globals = deepcopy(v.globals)
        before = {key: restored.globals[key] for key in (
            'sv_stage', 'sv_selection', 'sv_tokens', 'sv_xp', 'sv_seconds',
            'sv_stage_seconds', 'sv_nl_d')}
        restored.fast_frames(9)
        self.assertEqual(pages(restored), [])
        restored.fast_frames(1)
        self.assertEqual(pages(restored), [(30, 'sv_tree_6')])
        self.assertEqual({key: restored.globals[key] for key in before}, before)

    def test_page_refresh_and_status_notice_throttle_are_independent_under_input_bursts(self):
        v = self.vm
        for frame in range(120):
            v.globals['sv_selection'] = frame % 50
            v.globals['sv_tokens'] = frame % 51
            v.globals['sv_selected_rank'] = frame % 4
            v.run('sv_show_rank')
            v.fast_frames(1)
        self.assertEqual(len(pages(v)), 12)
        self.assertGreaterEqual(len(v.notice_events), 4)
        self.assertTrue(all(b[0] - a[0] == 30 for a, b in zip(pages(v), pages(v)[1:])))
        self.assertTrue(all(b[0] - a[0] >= 90 for a, b in zip(v.notice_events, v.notice_events[1:])))
        for tick, title in pages(v):
            selection = ((tick // 3) - 1) % 50
            self.assertEqual(title, f'sv_tree_{min(selection // 7, 6) if selection < 47 else 7}')
        self.assertTrue(all(not name.startswith('sv_tree_') for _, name in v.notice_events))


if __name__ == '__main__':
    unittest.main()
