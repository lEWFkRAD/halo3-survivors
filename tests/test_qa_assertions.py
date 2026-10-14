"""Hermetic tests for the tracked QA assertion-case runner.

The fake dispatch stands in for the operator's verified console transport:
it appends log lines exactly as a native transport would after a command.
No game process, console or network is involved.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import native_qa as qa
import qa_assertions as runner


class QaAssertionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.log = Path(self.temp.name) / 'hs_log.txt'
        self.log.write_bytes(b'startup\n')
        fingerprint = {'engine': 'b' * 64, 'scenario': 'c' * 64,
                       'hsc': 'd' * 64, 'private_assets': 'e' * 64}
        self.context = qa.EvidenceContext(
            source_commit='a' * 40, candidate_fingerprint=fingerprint,
            profile='qa-saves/ls03', environment='sdk', run_kind='seeded',
            evidence_kind='native', candidate_path='/candidates/candidate.zip')
        self.commands = []

    def nonce_of(self, command):
        import re
        return re.search(r'LSQA:([0-9a-f]{32}):', command).group(1)

    def append(self, text):
        with self.log.open('ab') as stream:
            stream.write(text.encode())

    def dispatch_pass(self, command):
        self.commands.append(command)
        self.append(f'LSQA:{self.nonce_of(command)}:PASS\n')

    def dispatch_fail(self, command):
        self.commands.append(command)
        self.append(f'LSQA:{self.nonce_of(command)}:FAIL\n')

    def dispatch_silent(self, command):
        self.commands.append(command)

    def dispatch_echo(self, command):
        self.commands.append(command)
        self.append(f'(log_print "LSQA:{self.nonce_of(command)}:PASS")\n')

    def run_one(self, dispatch, **case_kwargs):
        case = runner.Case(name='stage-two', condition='(= sv_stage 2)',
                           **case_kwargs)
        results = runner.run_cases([case], log_path=self.log,
                                   context=self.context, dispatch=dispatch,
                                   decode_line=qa.bare_payload)
        self.assertEqual(len(results), 1)
        return results[0]

    def test_observed_pass_is_bound_to_the_candidate(self):
        result = self.run_one(self.dispatch_pass)
        report = result['report']
        self.assertEqual(result['name'], 'stage-two')
        self.assertEqual(report['outcome'], 'passed')
        self.assertEqual(report['candidate']['source_commit'], 'a' * 40)
        self.assertEqual(report['candidate']['fingerprint'],
                         dict(self.context.candidate_fingerprint))
        self.assertEqual(report['candidate']['path'], '/candidates/candidate.zip')
        self.assertEqual(report['profile'], 'qa-saves/ls03')
        self.assertEqual(report['assertion']['condition'], '(= sv_stage 2)')

    def test_false_condition_reports_failed_never_passed(self):
        result = self.run_one(self.dispatch_fail)
        self.assertEqual(result['report']['outcome'], 'failed')
        self.assertEqual(result['report']['reason'], 'observed_marker')

    def test_missing_marker_is_unresolved(self):
        result = self.run_one(self.dispatch_silent)
        self.assertEqual(result['report']['outcome'], 'unresolved')
        self.assertEqual(result['report']['reason'], 'no_native_marker')

    def test_command_echo_cannot_pass(self):
        result = self.run_one(self.dispatch_echo)
        self.assertNotEqual(result['report']['outcome'], 'passed')

    def test_dispatches_and_run_kind_override(self):
        result = self.run_one(self.dispatch_pass, dispatches=3,
                              run_kind='ordinary')
        self.assertEqual(len(self.commands), 3)
        self.assertTrue(all(c == self.commands[0] for c in self.commands))
        self.assertEqual(result['report']['run_kind'], 'ordinary')
        # The nonce appears three times in the window, so evaluate must
        # refuse a clean pass; the runner surfaces that honestly.
        self.assertEqual(result['report']['outcome'], 'unresolved')
        self.assertEqual(result['report']['reason'], 'multiple_native_markers')

    def test_later_cases_still_run_after_a_failure(self):
        cases = [runner.Case(name='one', condition='(= sv_stage 2)'),
                 runner.Case(name='two', condition='(= sv_stage 3)')]
        calls = []

        def dispatch(command):
            calls.append(command)
            outcome = 'FAIL' if len(calls) == 1 else 'PASS'
            self.append(f'LSQA:{self.nonce_of(command)}:{outcome}\n')

        results = runner.run_cases(cases, log_path=self.log,
                                   context=self.context, dispatch=dispatch,
                                   decode_line=qa.bare_payload)
        self.assertEqual([r['report']['outcome'] for r in results],
                         ['failed', 'passed'])
        self.assertEqual(runner.outcome_counts(results),
                         {'failed': 1, 'passed': 1})

    def test_sdk_envelope_case_passes_with_sdk_decoder(self):
        def dispatch(command):
            nonce = self.nonce_of(command)
            self.append('10.13.26 22:04:21.461 0000666 g001650 f0003788  '
                        f'WARNING hs: lsqa:{nonce}:pass \n')

        case = runner.Case(name='sdk-case', condition='(= sv_stage 2)')
        results = runner.run_cases([case], log_path=self.log,
                                   context=self.context, dispatch=dispatch)
        self.assertEqual(results[0]['report']['outcome'], 'passed')
        self.assertEqual(results[0]['report']['transport'], 'halo_sdk_hs_log')

    def test_case_validation(self):
        with self.assertRaises(ValueError):
            runner.Case(name='Bad Name', condition='(= sv_stage 2)')
        with self.assertRaises(ValueError):
            runner.Case(name='ok', condition='(= sv_stage 2)', run_kind='fast')
        with self.assertRaises(ValueError):
            runner.Case(name='ok', condition='(= sv_stage 2)', dispatches=0)
        with self.assertRaises(ValueError):
            runner.Case(name='ok', condition='(= sv_stage 2')

    def test_load_cases_round_trip_and_rejects_bad_files(self):
        path = Path(self.temp.name) / 'cases.json'
        path.write_text(json.dumps([
            {'name': 'boot', 'condition': '(= sv_boot 1)'},
            {'name': 'stage', 'condition': '(= sv_stage 2)',
             'run_kind': 'ordinary', 'dispatches': 2},
        ]))
        cases = runner.load_cases(path)
        self.assertEqual([c.name for c in cases], ['boot', 'stage'])
        self.assertEqual(cases[1].dispatches, 2)
        path.write_text(json.dumps([{'name': 'x', 'condition': '(= a 1)',
                                     'surprise': True}]))
        with self.assertRaises(ValueError):
            runner.load_cases(path)
        path.write_text(json.dumps([{'name': 'x', 'condition': '(= a 1)'},
                                    {'name': 'x', 'condition': '(= a 2)'}]))
        with self.assertRaises(ValueError):
            runner.load_cases(path)

    def test_write_reports_one_file_per_case(self):
        result = self.run_one(self.dispatch_pass)
        out = Path(self.temp.name) / 'evidence'
        paths = runner.write_reports([result], out)
        self.assertEqual(len(paths), 1)
        saved = json.loads(paths[0].read_text())
        self.assertEqual(saved['outcome'], 'passed')
        self.assertEqual(saved['candidate']['source_commit'], 'a' * 40)
        self.assertEqual(paths[0].name, 'stage-two.json')


if __name__ == '__main__':
    unittest.main()
