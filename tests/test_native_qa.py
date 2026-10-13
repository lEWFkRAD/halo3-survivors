"""Synthetic evidence falsification; these tests do not run or validate Halo."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_qa as qa


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'debug.log'
        self.path.write_bytes(b'old unrelated line\r\n')
        self.assertion = qa.new_assertion('(= sv_stage 2)')
        self.context = qa.EvidenceContext('a' * 40, {name: 'b' * 64 for name in
            ('engine', 'scenario', 'hsc', 'private_assets')}, 'qa-saves/ls03',
            'sdk', 'seeded', 'synthetic')
        self.cursor = qa.capture_cursor(self.path)

    def marker(self, outcome='PASS', nonce=None):
        return f'LSQA:{nonce or self.assertion.nonce}:{outcome}'

    def append(self, text):
        with self.path.open('ab') as stream:
            stream.write(text.encode('utf-8'))

    def result(self, *, context=None, **kwargs):
        return qa.evaluate(self.assertion, qa.read_window(self.cursor),
                           context or self.context, **kwargs)

    def test_false_assertion_is_failed_with_exact_evidence(self):
        self.append(self.marker('FAIL') + '\r\n')
        result = self.result()
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(result['reason'], 'observed_marker')
        self.assertEqual(result['evidence']['observations'], [
            {'line': 2, 'text': self.marker('FAIL'), 'outcome': 'FAIL'}])
        self.assertEqual(result['evidence']['log_sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(result['evidence']['start_offset'], self.cursor.offset)
        self.assertEqual(result['evidence']['end_offset'], self.path.stat().st_size)

    def test_single_complete_marker_passes_with_explicit_scope(self):
        self.append(self.marker() + '\n')
        result = self.result()
        self.assertEqual(result['outcome'], 'passed')
        self.assertEqual(result['candidate']['source_commit'], 'a' * 40)
        self.assertEqual(result['candidate']['fingerprint'], dict(self.context.candidate_fingerprint))
        self.assertEqual(result['environment'], 'sdk')
        self.assertEqual(result['run_kind'], 'seeded')
        self.assertEqual(result['evidence_kind'], 'synthetic')
        self.assertEqual(result['transport'], 'bare_payload')
        self.assertEqual(result['profile'], 'qa-saves/ls03')
        self.assertTrue(result['evidence']['cursor_at'])
        self.assertTrue(result['evidence']['observed_at'])
        json.dumps(result)

    def test_stale_pass_before_cursor_is_not_evidence(self):
        self.append(self.marker() + '\n')
        self.cursor = qa.capture_cursor(self.path)
        self.assertEqual(self.result()['outcome'], 'unresolved')
        self.append(self.marker('FAIL') + '\n')
        self.assertEqual(self.result()['outcome'], 'failed')

    def test_missing_and_other_nonce_output_are_unresolved(self):
        self.assertEqual(self.result()['reason'], 'no_native_marker')
        self.append(self.marker(nonce='0' * 32) + '\n')
        self.assertEqual(self.result()['outcome'], 'unresolved')

    def test_command_echo_is_never_a_pass(self):
        self.append(self.assertion.command + '\nH3( ' + self.assertion.command + '\n')
        self.assertEqual(self.result()['outcome'], 'unresolved')
        self.append(self.marker('FAIL') + '\n')
        self.assertEqual(self.result()['outcome'], 'failed')

    def test_substrings_whitespace_and_malformed_outcomes_are_not_markers(self):
        for line in ('prefix ' + self.marker(), self.marker() + ' suffix', ' ' + self.marker(),
                     self.marker('PASSED'), self.marker() + ' ', self.marker() + '\r\r'):
            self.append(line + '\n')
        self.assertEqual(self.result()['outcome'], 'unresolved')

    def test_duplicate_and_conflicting_output_are_unresolved(self):
        self.append(self.marker() + '\n' + self.marker() + '\n')
        self.assertEqual(self.result()['reason'], 'multiple_native_markers')
        self.append(self.marker('FAIL') + '\n')
        self.assertEqual(self.result()['outcome'], 'unresolved')

    def test_partial_marker_stays_unresolved_until_completed(self):
        self.append(self.marker())
        self.assertEqual(self.result()['reason'], 'incomplete_tail')
        self.append('\n')
        self.assertEqual(self.result()['outcome'], 'passed')

    def test_partial_conflict_cannot_leave_previous_pass(self):
        self.append(self.marker() + '\n' + self.marker('FAIL'))
        self.assertEqual(self.result()['outcome'], 'unresolved')
        self.append('\n')
        self.assertEqual(self.result()['reason'], 'multiple_native_markers')

    def test_preexisting_partial_line_cannot_be_completed_into_fresh_pass(self):
        self.append('LSQA:')
        self.cursor = qa.capture_cursor(self.path)
        self.append(self.assertion.nonce + ':PASS\n')
        self.assertEqual(self.result()['outcome'], 'unresolved')
        self.append(self.marker('FAIL') + '\n')
        result = self.result()
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(result['evidence']['observations'][0]['line'], 3)

    def test_empty_log_starts_at_first_line(self):
        self.path.write_bytes(b'')
        self.cursor = qa.capture_cursor(self.path)
        self.append(self.marker() + '\n')
        self.assertEqual(self.result()['evidence']['observations'][0]['line'], 1)

    def test_deleted_log_is_unresolved(self):
        self.path.unlink()
        self.assertEqual(self.result()['outcome'], 'unresolved')
        self.assertTrue(self.result()['reason'].startswith('log_unavailable'))

    def test_truncated_log_is_unresolved(self):
        self.path.write_bytes(b'')
        self.assertEqual(self.result()['reason'], 'log_truncated')

    def test_same_inode_rewrite_then_regrowth_is_unresolved(self):
        self.path.write_bytes(b'x' * self.cursor.offset + (self.marker() + '\n').encode())
        self.assertEqual(self.result()['reason'], 'log_prefix_changed')

    def test_rotated_log_with_identical_prefix_is_unresolved(self):
        old_data = self.path.read_bytes()
        self.path.rename(self.path.with_suffix('.old'))
        self.path.write_bytes(old_data + (self.marker() + '\n').encode())
        self.assertEqual(self.result()['reason'], 'log_rotated')

    def test_oversized_log_or_append_is_unresolved(self):
        self.append(self.marker() + '\n')
        window = qa.read_window(self.cursor, max_bytes=10)
        self.assertEqual(qa.evaluate(self.assertion, window, self.context)['outcome'], 'unresolved')
        window = qa.read_window(self.cursor, max_appended_bytes=10)
        self.assertEqual(window.issue, 'append_limit_exceeded')

    def test_missing_baseline_cannot_prepare_an_observation(self):
        self.path.unlink()
        with self.assertRaises(OSError):
            qa.capture_cursor(self.path)

    def test_explicit_transport_decoder_must_extract_a_complete_payload(self):
        self.append('script: ' + self.marker('FAIL') + '\n')
        self.assertEqual(self.result()['outcome'], 'unresolved')
        def synthetic_decoder(line):
            return line[len('script: '):] if line.startswith('script: ') else None
        result = self.result(decode_line=synthetic_decoder)
        self.assertEqual(result['outcome'], 'failed')
        self.assertEqual(result['transport'], 'custom')

    def test_echo_rejection_still_applies_with_a_permissive_decoder(self):
        self.append('(log_print "' + self.marker() + '")\n')
        self.assertEqual(self.result(decode_line=lambda line: self.marker())['outcome'], 'unresolved')

    def sdk_line(self, outcome='pass', game='g001650'):
        return ('10.12.26 22:04:21.461 0000666 ' + game + ' f0003788  WARNING hs: '
                + f'lsqa:{self.assertion.nonce}:{outcome} ')

    def test_observed_sdk_warning_envelope_pass_and_false_fail(self):
        echo = ('10.12.26 22:04:21.461 0000665 g001650 f0003788  '
                + 'message hs:evaluate: console_command: ' + self.assertion.command + ' ')
        self.append(echo + '\r\n' + self.sdk_line() + '\r\n')
        self.assertEqual(self.result()['outcome'], 'unresolved')
        result = self.result(decode_line=qa.halo_sdk_payload)
        self.assertEqual(result['outcome'], 'passed')
        self.assertEqual(result['transport'], 'halo_sdk_hs_log')
        self.assertEqual(result['evidence']['observations'][0]['text'], self.sdk_line())
        self.cursor = qa.capture_cursor(self.path)
        self.append(self.sdk_line('fail') + '\r\n')
        self.assertEqual(self.result(decode_line=qa.halo_sdk_payload)['outcome'], 'failed')

    def test_sdk_echo_alone_cannot_pass(self):
        self.append('10.12.26 22:04:21.461 0000665 g001650 f0003788  '
                    + 'message hs:evaluate: console_command: ' + self.assertion.command + ' \r\n')
        self.assertEqual(self.result(decode_line=qa.halo_sdk_payload)['outcome'], 'unresolved')

    def test_sdk_decoder_cannot_certify_retail_context(self):
        self.append(self.sdk_line() + '\r\n')
        for kind in ('synthetic', 'native'):
            with self.subTest(evidence_kind=kind):
                context = replace(self.context, environment='retail', evidence_kind=kind)
                result = qa.evaluate(self.assertion, qa.read_window(self.cursor), context,
                                     decode_line=qa.halo_sdk_payload)
                self.assertEqual(result['outcome'], 'unresolved')
                self.assertEqual(result['reason'], 'decoder_environment_mismatch')
                self.assertEqual(result['transport'], 'halo_sdk_hs_log')
                self.assertEqual(result['evidence']['observations'][0]['outcome'], 'PASS')

    def test_sdk_startup_blank_game_counter_has_exact_width(self):
        self.assertEqual(qa.halo_sdk_payload(self.sdk_line(game=' ' * 7)), self.marker())
        self.assertIsNone(qa.halo_sdk_payload(self.sdk_line(game=' ' * 6)))

    def test_sdk_malformed_envelopes_or_case_changes_are_not_observations(self):
        line = self.sdk_line()
        malformed = (line.lstrip('1'), 'prefix ' + line, line + 'suffix', line.rstrip(),
                     line.replace('WARNING', 'warning'), line.replace('hs:', 'other:'),
                     line.replace('lsqa:', 'LSQA:'), line.replace(':pass', ':PASS'),
                     line.replace('g001650', 'g01650'), line.replace('f0003788', 'f000378'),
                     line.replace('22:04:21', '25:04:21'), line.replace('10.12.26', '99.12.26'),
                     line.replace('WARNING hs:', 'message hs:'), line + '\r',
                     line.replace('  WARNING', ' WARNING'))
        for invalid in malformed:
            with self.subTest(line=invalid):
                self.assertIsNone(qa.halo_sdk_payload(invalid))

    def test_sdk_contradictions_and_incomplete_native_tail_remain_unresolved(self):
        self.append(self.sdk_line() + '\r\n' + self.sdk_line('fail'))
        self.assertEqual(self.result(decode_line=qa.halo_sdk_payload)['reason'], 'incomplete_tail')
        self.append('\r\n')
        self.assertEqual(self.result(decode_line=qa.halo_sdk_payload)['reason'], 'multiple_native_markers')

    def test_new_nonce_and_bounded_command(self):
        other = qa.new_assertion('false')
        self.assertNotEqual(other.nonce, self.assertion.nonce)
        self.assertLessEqual(len(self.assertion.command), qa.MAX_COMMAND)
        self.assertIn('(log_print "' + self.marker('FAIL') + '")', self.assertion.command)
        for condition in ('true false', '(true) (false)', '(= a 2', '(= a 2))',
                          'true\n', '"true"', '(begin\nfalse)', '(' * 9 + 'false' + ')' * 9,
                          '(= ' + 'a' * 250 + ' 2)', ' true', 'true;false'):
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                qa.new_assertion(condition)
        with self.assertRaises(ValueError):
            qa.Assertion('true', 'invalid')

    def test_context_requires_exact_candidate_and_explicit_classification(self):
        for change in ({'source_commit': 'main'}, {'candidate_fingerprint': {'hsc': 'b' * 64}},
                       {'candidate_fingerprint': {name: 'different' for name in self.context.candidate_fingerprint}},
                       {'environment': 'unknown'}, {'run_kind': ''}, {'evidence_kind': ''}, {'profile': ''}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(self.context, **change)
        retail = replace(self.context, environment='retail', run_kind='ordinary', evidence_kind='native')
        self.append(self.marker() + '\n')
        result = qa.evaluate(self.assertion, qa.read_window(self.cursor), retail)
        self.assertEqual((result['environment'], result['run_kind'], result['evidence_kind']),
                         ('retail', 'ordinary', 'native'))

    def test_candidate_cannot_change_after_context_capture(self):
        hashes = dict(self.context.candidate_fingerprint)
        context = replace(self.context, candidate_fingerprint=hashes)
        hashes['hsc'] = 'c' * 64
        self.assertEqual(context.candidate_fingerprint['hsc'], 'b' * 64)
        with self.assertRaises(TypeError):
            context.candidate_fingerprint['hsc'] = 'c' * 64

    def test_candidate_path_defaults_empty_and_appears_in_report(self):
        legacy = replace(self.context)
        self.assertEqual(legacy.candidate_path, '')
        self.append(self.marker() + '\n')
        result = self.result()
        self.assertEqual(result['candidate']['path'], '')
        bound = replace(self.context, candidate_path='C:/kit/pkg.zip')
        self.assertEqual(self.result(context=bound)['candidate']['path'], 'C:/kit/pkg.zip')

    def test_candidate_path_rejects_control_characters(self):
        for bad in ('line\nbreak', 'tab\there', 'nul\x00', 'bell\x07'):
            with self.subTest(candidate_path=bad), self.assertRaises(ValueError):
                replace(self.context, candidate_path=bad)

    def test_fingerprint_from_files_hashes_exact_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            files = {}
            expected = {}
            for index, key in enumerate(('engine', 'scenario', 'hsc', 'private_assets')):
                path = Path(temp) / key
                data = bytes([index]) * (index + 1)
                path.write_bytes(data)
                files[key] = path
                expected[key] = hashlib.sha256(data).hexdigest()
            self.assertEqual(qa.candidate_fingerprint_from_files(files), expected)
            (Path(temp) / 'hsc').write_bytes(b'mutated')
            self.assertNotEqual(qa.candidate_fingerprint_from_files(files)['hsc'],
                                expected['hsc'])
            for change in ({}, {**files, 'extra': files['engine']},
                           {key: value for key, value in files.items() if key != 'hsc'}):
                with self.subTest(keys=sorted(change)), self.assertRaises(ValueError):
                    qa.candidate_fingerprint_from_files(change)


if __name__ == '__main__':
    unittest.main()
