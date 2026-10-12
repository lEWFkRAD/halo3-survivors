"""Launcher/save behavior in temporary directories; never starts a game or GUI."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import launch_v04 as launcher


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.paths = launcher.Paths(base / 'workspace', base / 'Steam/steamapps/common/H3EK')
        self.paths.root.mkdir()
        files = {
            'halo3_tag_test.exe': b'engine',
            'tags/levels/survivors/last_stand/last_stand.scenario': b'scenario',
            'data/levels/survivors/last_stand/scripts/last_stand.hsc': b'script',
            'tags/objects/survivors/v3/damage.effect': b'damage',
            'tags/ui/survivors/text.multilingual_unicode_string_list': b'UI',
            'init.txt': b'original init\n',
        }
        for relative, data in files.items():
            path = self.paths.kit / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.paths.pending.parent.mkdir()
        self.compatibility = launcher.fingerprint(self.paths)
        self.data = b'A' * (launcher.MIN_CORE + 64)
        self.messages = []
        self.report = lambda message, failure: self.messages.append((message, failure))

    def commit(self, data=None, paths=None):
        return launcher.commit_core(paths or self.paths, data or self.data,
                                    self.compatibility, 'test-session')

    def fake_launch(self, mode, inspect=None):
        def start(command, **kwargs):
            if inspect:
                inspect(command)
            return Mock(poll=Mock(return_value=0))
        with patch.object(launcher, 'native_children', return_value=[]), \
             patch.object(launcher.subprocess, 'Popen', side_effect=start), \
             patch.object(launcher, 'monitor', return_value=0):
            return launcher.launch(self.paths, mode, self.compatibility, self.report)

    def test_missing_profile_validation_is_read_only(self):
        self.assertFalse(launcher.validate_save(self.paths, self.compatibility)['found'])
        self.assertFalse(self.paths.profile.exists())

    def test_choose_continue_accepts_empty_success_output(self):
        status = {'found': True, 'valid': True, 'reason': ''}
        with patch.object(launcher.subprocess, 'run', return_value=Mock(returncode=0, stdout='')) as run:
            self.assertEqual(launcher.choose_run(status), 'continue')
        args = run.call_args.args[0]
        self.assertIn('--question', args)
        self.assertIn('--ok-label=Continue', args)
        self.assertIn('--cancel-label=Cancel', args)
        self.assertIn('--extra-button=New Run', args)
        self.assertEqual(run.call_args.kwargs['stdin'], launcher.subprocess.DEVNULL)

    def test_choose_new_run_extra_button_takes_precedence_over_exit_code(self):
        status = {'found': True, 'valid': True, 'reason': ''}
        for exit_code in (0, 1):
            with self.subTest(exit_code=exit_code), \
                 patch.object(launcher.subprocess, 'run', return_value=Mock(returncode=exit_code, stdout='New Run\n')):
                self.assertEqual(launcher.choose_run(status), 'new')

    def test_choose_cancel_returns_no_launch_mode(self):
        with patch.object(launcher.subprocess, 'run', return_value=Mock(returncode=1, stdout='')):
            self.assertIsNone(launcher.choose_run({'found': True, 'valid': True, 'reason': ''}))

    def test_choose_missing_profile_starts_new_without_ui(self):
        status = launcher.validate_save(self.paths, self.compatibility)
        with patch.object(launcher.subprocess, 'run') as run:
            self.assertEqual(launcher.choose_run(status), 'new')
        run.assert_not_called()
        self.assertFalse(self.paths.profile.exists())

    def test_choose_invalid_save_offers_only_new_or_cancel_and_preserves_save(self):
        metadata = self.commit()
        generation = self.paths.profile / 'generations' / metadata['generation']
        before = {path: path.read_bytes() for path in (self.paths.current, generation / 'core.bin',
                                                     generation / 'metadata.json')}
        status = launcher.validate_save(self.paths, dict(self.compatibility, engine='different-build'))
        self.assertFalse(status['valid'])
        original_status = dict(status)
        for exit_code, expected in ((0, 'new'), (1, None)):
            with self.subTest(exit_code=exit_code), \
                 patch.object(launcher.subprocess, 'run', return_value=Mock(returncode=exit_code, stdout='')) as run:
                self.assertEqual(launcher.choose_run(status), expected)
                args = run.call_args.args[0]
                self.assertIn('--ok-label=New Run', args)
                self.assertIn('--cancel-label=Cancel', args)
                self.assertFalse(any('Continue' in arg or arg.startswith('--extra-button=') for arg in args))
                self.assertTrue(any(arg.startswith('--text=') and status['reason'] in arg for arg in args))
                self.assertEqual(status, original_status)
                self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_commit_and_corrupt_or_incompatible_validation_preserve_data(self):
        metadata = self.commit()
        status = launcher.validate_save(self.paths, self.compatibility)
        self.assertTrue(status['valid'])
        current = self.paths.current.read_bytes()
        self.assertEqual(status['metadata']['sha256'], metadata['sha256'])
        changed = dict(self.compatibility, engine='changed-build')
        self.assertFalse(launcher.validate_save(self.paths, changed)['valid'])
        self.assertEqual(self.paths.current.read_bytes(), current)
        status['core'].write_bytes(b'B' + self.data[1:])
        corrupt = launcher.validate_save(self.paths, self.compatibility)
        self.assertFalse(corrupt['valid']);self.assertIn('corrupt', corrupt['reason'])
        self.assertTrue(status['core'].exists());self.assertEqual(self.paths.current.read_bytes(), current)

    def test_partial_generation_failure_preserves_previous_current(self):
        self.commit();before = self.paths.current.read_bytes()
        original = launcher.atomic_bytes
        def fail_metadata(path, data):
            if path.name == 'metadata.json':
                raise OSError('simulated disk failure')
            return original(path, data)
        with patch.object(launcher, 'atomic_bytes', side_effect=fail_metadata):
            with self.assertRaisesRegex(OSError, 'disk failure'):
                self.commit(b'B' * len(self.data))
        self.assertEqual(self.paths.current.read_bytes(), before)
        self.assertTrue(launcher.validate_save(self.paths, self.compatibility)['valid'])

    def test_current_pointer_failure_preserves_previous_generation(self):
        self.commit();before = self.paths.current.read_bytes()
        original = launcher.atomic_bytes
        def fail_pointer(path, data):
            if path == self.paths.current:
                raise OSError('simulated pointer failure')
            return original(path, data)
        with patch.object(launcher, 'atomic_bytes', side_effect=fail_pointer):
            with self.assertRaises(OSError):self.commit(b'B' * len(self.data))
        self.assertEqual(self.paths.current.read_bytes(), before)
        self.assertTrue(launcher.validate_save(self.paths, self.compatibility)['valid'])

    def test_watcher_requires_stable_content_and_commits_once_per_checkpoint(self):
        watcher = launcher.CheckpointWatcher(self.paths, self.compatibility, 'session', self.report)
        self.paths.pending.write_bytes(self.data)
        watcher.poll(0);watcher.poll(1.9)
        self.assertFalse(self.paths.current.exists())
        self.paths.pending.write_bytes(b'B' * len(self.data))
        watcher.poll(2);watcher.poll(3.9)
        self.assertFalse(self.paths.current.exists())
        watcher.poll(4);self.assertFalse(self.paths.current.exists());watcher.poll(4.5)
        status = launcher.validate_save(self.paths, self.compatibility)
        self.assertTrue(status['valid']);self.assertEqual(status['core'].read_bytes()[0:1], b'B')
        before = self.paths.current.read_bytes()
        with patch.object(launcher, 'core_bytes', side_effect=AssertionError('unchanged core was rehashed')):
            watcher.poll(20)
        self.assertEqual(self.paths.current.read_bytes(), before)
        self.assertEqual(len(list((self.paths.profile / 'generations').iterdir())), 1)

    def test_checkpoint_failure_is_reported_once_and_prior_save_remains(self):
        self.commit();before = self.paths.current.read_bytes()
        watcher = launcher.CheckpointWatcher(self.paths, self.compatibility, 'session', self.report)
        self.paths.pending.write_bytes(b'partial')
        for moment in (0, 1, 3):watcher.poll(moment)
        self.assertEqual(len(self.messages), 1);self.assertTrue(self.messages[0][1])
        self.assertEqual(self.paths.current.read_bytes(), before)
        self.paths.pending.write_bytes(self.data);watcher.poll(4);watcher.poll(6);watcher.poll(6.5)
        self.assertFalse(self.messages[-1][1])

    def test_partial_changing_native_write_is_silent_until_stable(self):
        watcher = launcher.CheckpointWatcher(self.paths, self.compatibility, 'session', self.report)
        with patch.object(launcher, 'core_bytes', side_effect=AssertionError('read before stability')):
            for moment, data in ((0,b''),(.5,b'x'),(1,b'writing'),(1.5,b'still writing')):
                self.paths.pending.write_bytes(data);watcher.poll(moment)
            watcher.poll(3.4)
        self.assertFalse(self.messages);self.assertFalse(self.paths.current.exists())
        watcher.poll(3.5)
        self.assertEqual(len(self.messages),1);self.assertTrue(self.messages[0][1])

    def test_modified_build_cannot_commit_a_new_checkpoint(self):
        self.commit();before = self.paths.current.read_bytes()
        (self.paths.kit / 'tags/objects/survivors/v3/damage.effect').write_bytes(b'new build')
        with self.assertRaisesRegex(launcher.SaveError, 'changed during play'):
            self.commit(b'B' * len(self.data))
        self.assertEqual(self.paths.current.read_bytes(), before)

    def test_new_run_archives_prior_save_and_stale_qa_pending(self):
        status = self.commit();self.paths.pending.write_bytes(b'old QA core')
        original = self.paths.init.read_bytes()
        def inspect(command):
            self.assertEqual(self.paths.init.read_text(), launcher.PREAMBLE + 'game_start ' + launcher.SCENARIO + '\n')
            self.assertFalse(self.paths.pending.exists());self.assertFalse(self.paths.current.exists())
            self.assertIn(str(self.paths.steam / 'steamapps/common/Proton - Experimental/files/bin/wine'), command[-1])
        self.fake_launch('new', inspect)
        archives = list((self.paths.profile / 'archives').iterdir())
        self.assertEqual(len(archives), 2)
        self.assertTrue(any(path.read_bytes() == b'old QA core' for path in archives))
        self.assertTrue((self.paths.profile / 'generations' / status['generation'] / 'core.bin').exists())
        self.assertEqual(self.paths.init.read_bytes(), original)

    def test_continue_uses_verified_core_and_restores_existing_init(self):
        self.commit();original = self.paths.init.read_bytes()
        def inspect(command):
            self.assertEqual(self.paths.resume.read_bytes(), self.data)
            self.assertIn('(core_load_game_name "laststand_v04_resume")', self.paths.init.read_text())
        self.fake_launch('continue', inspect)
        self.assertEqual(self.paths.init.read_bytes(), original)
        self.assertTrue(launcher.validate_save(self.paths, self.compatibility)['valid'])

    def test_failed_process_start_still_restores_init(self):
        original = self.paths.init.read_bytes()
        with patch.object(launcher, 'native_children', return_value=[]), \
             patch.object(launcher.subprocess, 'Popen', side_effect=OSError('launch failed')):
            with self.assertRaises(OSError):
                launcher.launch(self.paths, 'new', self.compatibility, self.report)
        self.assertEqual(self.paths.init.read_bytes(), original)

    def test_invalid_continue_does_not_mutate_profile_or_init(self):
        self.commit();self.paths.current.write_text('{bad json')
        original = self.paths.init.read_bytes();pointer = self.paths.current.read_bytes()
        with patch.object(launcher, 'native_children', return_value=[]), \
             patch.object(launcher.subprocess, 'Popen') as start:
            with self.assertRaises(launcher.SaveError):
                launcher.launch(self.paths, 'continue', self.compatibility, self.report)
        self.assertEqual(self.paths.init.read_bytes(), original)
        self.assertEqual(self.paths.current.read_bytes(), pointer);start.assert_not_called()

    def test_qa_profiles_cannot_replace_production_current(self):
        self.commit();before = self.paths.current.read_bytes()
        qa = launcher.Paths(self.paths.root, self.paths.kit, self.paths.root / 'qa-saves/test')
        self.commit(paths=qa)
        self.assertTrue(launcher.validate_save(qa, self.compatibility)['valid'])
        self.assertEqual(self.paths.current.read_bytes(), before)
        with self.assertRaisesRegex(launcher.SaveError, 'inside ROOT/qa-saves'):
            launcher.Paths(self.paths.root, self.paths.kit, self.paths.root / 'unrelated')
        with self.assertRaisesRegex(launcher.SaveError, 'inside ROOT/qa-saves'):
            launcher.Paths(self.paths.root, self.paths.kit, self.paths.production)

    def test_non_object_metadata_is_invalid_and_preserved(self):
        meta = self.commit()
        path = self.paths.profile / 'generations' / meta['generation'] / 'metadata.json'
        for value in ([], None, 'bad', True):
            path.write_text(json.dumps(value))
            with self.subTest(value=value):
                status = launcher.validate_save(self.paths, self.compatibility)
                self.assertFalse(status['valid']);self.assertIn('must be an object', status['reason'])
                self.assertEqual(json.loads(path.read_text()), value)

    def test_changed_build_before_launch_preserves_save_and_init(self):
        self.commit();before = self.paths.current.read_bytes();original = self.paths.init.read_bytes()
        (self.paths.kit / 'halo3_tag_test.exe').write_bytes(b'new engine')
        with patch.object(launcher, 'native_children', return_value=[]):
            with self.assertRaisesRegex(launcher.SaveError, 'changed while choosing'):
                launcher.launch(self.paths, 'continue', self.compatibility, self.report)
        self.assertEqual(self.paths.current.read_bytes(), before)
        self.assertEqual(self.paths.init.read_bytes(), original)

    def test_external_init_archive_failure_still_restores_original(self):
        original = self.paths.init.read_bytes();write = launcher.atomic_bytes
        def fail_archive(path, data):
            if path.name == 'init-external-change.txt':raise OSError('archive failed')
            return write(path, data)
        with patch.object(launcher, 'atomic_bytes', side_effect=fail_archive):
            with self.assertRaisesRegex(OSError, 'archive failed'):
                with launcher.temporary_init(self.paths, 'new', 'test'):
                    self.paths.init.write_bytes(b'external edit')
        self.assertEqual(self.paths.init.read_bytes(), original)

    def test_monitor_tracks_native_child_after_early_wrapper_exit(self):
        class FakeClock:
            value = 0.0
            def now(self):return self.value
            def sleep(self, duration):self.value += duration
        clock = FakeClock();watcher = Mock()
        process = Mock(poll=Mock(return_value=1))
        # A detached native child appears after the wrapper is already gone.
        children = lambda: [123] if 2 <= clock.value < 6 else []
        result = launcher.monitor(process, children, watcher, self.report,
                                  clock=clock.now, sleep=clock.sleep)
        self.assertEqual(result, 1);self.assertGreaterEqual(clock.value, 8.5)
        self.assertGreaterEqual(watcher.poll.call_args[0][0], 8.5)

    def test_watcher_or_report_failure_does_not_end_native_monitoring(self):
        time = [0.0]
        watcher = Mock();watcher.poll.side_effect = BrokenPipeError('closed output')
        report = Mock(side_effect=BrokenPipeError('closed output'))
        result = launcher.monitor(Mock(poll=Mock(return_value=1)),
                                  lambda: [1] if time[0] < 3 else [], watcher, report,
                                  clock=lambda: time[0], sleep=lambda delay: time.__setitem__(0, time[0]+delay))
        self.assertEqual(result, 1);self.assertGreaterEqual(time[0], 5.5)

    def test_process_scan_requires_exact_prefix_and_excludes_zombies(self):
        proc = self.paths.root / 'fake-proc';proc.mkdir()
        for pid, prefix, state in ((1, self.paths.prefix, 'S'),
                                   (2, Path(str(self.paths.prefix) + '-qa'), 'S'),
                                   (3, self.paths.prefix, 'Z')):
            folder = proc / str(pid);folder.mkdir()
            (folder / 'environ').write_bytes(('WINEPREFIX=' + str(prefix)).encode() + b'\0OTHER=value\0')
            (folder / 'cmdline').write_bytes(b'Z:\\kit\\halo3_tag_test.exe\0-window\0')
            (folder / 'stat').write_text(f'{pid} (halo3_tag_test) {state} 0 0')
        self.assertEqual(launcher.native_children(self.paths, proc), [1])


if __name__ == '__main__':
    unittest.main()
