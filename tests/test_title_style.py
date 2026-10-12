"""Check title authoring policy without owned assets or a native binding.

These checks do not establish native font rendering or on-screen readability.
"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class TitleStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / 'author_progression_ui.py'
        spec = importlib.util.spec_from_file_location('title_style_under_test', path)
        cls.author = importlib.util.module_from_spec(spec)
        binding = SimpleNamespace(Rectangle2d=lambda *bounds: bounds, RgbColor=int)
        with patch.dict('sys.modules', {'blam_tags': binding}):
            spec.loader.exec_module(cls.author)

    def test_status_categories_have_explicit_contrast_without_layout_changes(self):
        for name in ('sv_controls', 'sv_points_3', 'sv_rank_1', 'sv_purchased',
                     'sv_need_points', 'sv_stage_2', 'sv_boundary', 'sv_win'):
            with self.subTest(name=name):
                style = self.author.title_style(name)
                self.assertEqual(style['text color'], 0xFF111820)
                self.assertEqual(style['shadow color'], 0xFFF4F6F8)
                self.assertEqual(style['text bounds (on screen)'], (28, 32, 116, 1120))
                self.assertEqual(style['font'], 'large body text font')
                self.assertEqual(style['justification'], 'left')
                self.assertEqual(style['vertical justification'], 'top')

    def test_separate_node_renderer_keeps_original_style(self):
        for name in ('sv_node_0', 'sv_node_49'):
            with self.subTest(name=name):
                style = self.author.title_style(name)
                self.assertEqual(style['text color'], 0xFFFFFFFF)
                self.assertEqual(style['shadow color'], 0xFF000000)
                self.assertEqual(style['text bounds (on screen)'], (208, 32, 370, 1120))
                self.assertEqual(style['font'], 'large body text font')

    def test_notice_lifetime_stays_below_scheduler_interval_except_victory(self):
        for name in ('sv_controls', 'sv_node_0', 'sv_win'):
            with self.subTest(name=name):
                style = self.author.title_style(name)
                self.assertEqual(style['fade in time [seconds]'], 0.05)
                self.assertEqual(style['fade out time [seconds]'], 0.15)
                self.assertEqual(style['up time [seconds]'], 3600.0 if name == 'sv_win' else 2.1)
                if name != 'sv_win':
                    lifetime = sum(style[field] for field in (
                        'fade in time [seconds]', 'up time [seconds]', 'fade out time [seconds]'))
                    self.assertLess(lifetime, 3.0)

    def test_reference_pages_expire_at_refresh_interval_without_fades(self):
        for index in range(7):
            style = self.author.title_style(f'sv_tree_{index}')
            self.assertEqual(style['text bounds (on screen)'], (125,32,590,1120))
            self.assertEqual(style['font'], 'large body text font')
            self.assertEqual(style['up time [seconds]'], 1.0)
            self.assertEqual(style['fade in time [seconds]'], 0.0)
            self.assertEqual(style['fade out time [seconds]'], 0.0)

    def test_native_line_breaks_leave_other_text_unchanged(self):
        self.assertEqual(self.author.native_title_text('A\nB\r\nC | S2'), 'A|nB|nC | S2')
        self.assertEqual(self.author.native_title_text('Cost1/2/3 |nS4'), 'Cost1/2/3 |nS4')


if __name__ == '__main__':
    unittest.main()
