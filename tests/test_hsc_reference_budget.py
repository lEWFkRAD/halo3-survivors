"""Source reference pressure checks; these are not a native compiler model."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from progression_hsc import (
    HSC, MAX_AUTHORED_REFERENCES, analyze_reference_budget,
    validate_reference_budget,
)


class ReferenceBudgetTests(unittest.TestCase):
    def test_counts_references_not_declarations_and_resolves_forward_names(self):
        report = analyze_reference_budget('''
            (global short first second)
            (global short second 0)
            (script startup start (worker) (wake worker))
            (script static void worker (set first (+ first second)))
        ''')
        self.assertEqual(report['global_declarations'], 2)
        self.assertEqual(report['script_declarations'], 2)
        self.assertEqual(report['global_references'], 4)
        self.assertEqual(report['script_references'], 2)
        self.assertEqual(report['total_references'], 6)
        self.assertEqual(report['per_declaration'],
                         {'first': 1, 'second': 0, 'start': 2, 'worker': 3})
        self.assertFalse(report['native_count_exact'])

    def test_comments_and_quoted_names_are_not_references(self):
        source = r'''
            ; counter (runner)
            (global short counter 0)
            ;* (counter runner)
               counter counter *;
            (script static void runner
                (print "counter; runner (counter) \"counter\"")
                (set counter 1)) ; runner counter
        '''
        report = analyze_reference_budget(source)
        self.assertEqual(report['total_references'], 1)

    def test_parameter_header_and_local_uses_do_not_consume_global_records(self):
        source = '''
            (global short key 0)
            (script static void (leaf (short key))
                (if (= key 1) (print "yes"))
                (if (= key 2) (print "two")))
            (script static void caller (leaf key))
        '''
        report = analyze_reference_budget(source)
        self.assertEqual(report['global_references'], 1)
        self.assertEqual(report['script_references'], 1)
        self.assertEqual(report['per_declaration']['leaf'], 0)

    def test_repeated_occurrences_count_individually(self):
        report = analyze_reference_budget('''
            (global short x 0)
            (script static short value (+ x (+ x x)))
            (script static void repeat (value) (value) (value))
        ''')
        self.assertEqual(report['global_references'], 3)
        self.assertEqual(report['script_references'], 3)

    def test_guard_boundary_preserves_injected_source_headroom(self):
        self.assertEqual(MAX_AUTHORED_REFERENCES, 9500)
        source = '(global short x 0) (script static short value (+ x x))'
        self.assertEqual(validate_reference_budget(source, maximum=2)['total_references'], 2)
        with self.assertRaisesRegex(ValueError, 'estimate 2 exceeds guard 1'):
            validate_reference_budget(source, maximum=1)

    def test_render_refuses_excess_before_source_can_be_written(self):
        hsc = HSC()
        hsc.global_('short', 'key', 0)
        hsc.script('too_many', '\n'.join('(set key 1)' for _ in range(MAX_AUTHORED_REFERENCES + 1)))
        with self.assertRaisesRegex(ValueError, '9501 exceeds guard 9500'):
            hsc.render()

    def test_render_keeps_successful_source_bytes(self):
        hsc = HSC()
        hsc.global_('short', 'key', 0)
        hsc.script('ok', '(set key 1)')
        expected = ('; LAST STAND v0.4. Generated native progression. Do not hand edit.\n'
                    '(global short key 0)\n(script static void ok\n(set key 1)\n)\n')
        self.assertEqual(hsc.render(), expected)

    def test_unclosed_tokens_or_declarations_fail_closed(self):
        invalid = (
            '(global short x 0', ')', '(script startup go (print "unterminated))',
            ';* never closed\n(global short x 0)',
            ';* nested ;* comment *; *;', '(unknown a b)',
            '(global short x 0) (global short x 1)',
            '(global short x 0) (script static void x (print "x"))',
            '(script static void (leaf (short x) (long x)) (print "x"))',
            '(script static void (leaf (short)) (print "x"))',
        )
        for source in invalid:
            with self.subTest(source=source), self.assertRaises(ValueError):
                analyze_reference_budget(source)

    def test_invalid_maximum_rejected(self):
        for maximum in (-1, True, 2.5, '9500'):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                validate_reference_budget('', maximum=maximum)

    def test_deep_expressions_do_not_need_python_recursion(self):
        expression = '(' * 1500 + 'x' + ')' * 1500
        report = analyze_reference_budget(
            '(global short x 0) (script static short depth ' + expression + ')')
        self.assertEqual(report['total_references'], 1)


if __name__ == '__main__':
    unittest.main()
