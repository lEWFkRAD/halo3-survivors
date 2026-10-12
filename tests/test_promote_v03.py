"""Release guards and rollback tested only against isolated temporary packages."""
from contextlib import nullcontext, redirect_stdout
from datetime import timedelta
import io
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import promote_v03 as p


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.paths = p.Paths(base / 'workspace', base / 'kit')
        self.paths.root.mkdir()
        for path, content in [
            (self.paths.source, b'; LAST STAND v0.4 test source'),
            (self.paths.scenario, b'compiled native scenario'),
            (self.paths.kit / 'tags/objects/survivors/v3/fixture.damage_effect', b'damage'),
            (self.paths.kit / 'tags/ui/survivors/progression.multilingual_unicode_string_list', b'titles'),
            (self.paths.cache, b'new-cache' * 150000),
            (self.paths.package / 'maps/last_stand.map', b'old-cache'),
            (self.paths.root / 'project/README.md', b'old project documentation'),
            (self.paths.root / 'launch.py', b'unchanged launcher'),
            (self.paths.root / 'ModManifest.txt', b'unchanged registration'),
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.ids = {'mod': 'mod-id', 'campaign': 'campaign-id', 'map': 'map-id'}
        p.write_json(self.paths.ids, self.ids)
        metadata = {
            'ModInfo.json': {'ModIdentifier': {'ModGuid': 'mod-id', 'HostedModIds': {'keep': 42}},
                             'ModVersion': {'Major': 0, 'Minor': 2, 'Patch': 0},
                             'Description': {'Neutral': 'old'}, 'ExtraField': 'preserve'},
            'CampaignInfo.json': {'CampaignGuid': 'campaign-id', 'CampaignMaps': ['campaign/last_stand.json'],
                                  'Description': {'Neutral': 'old'}},
            'campaign/last_stand.json': {'MapGuid': 'map-id',
                                         'ScenarioFile': 'levels/survivors/last_stand/last_stand',
                                         'Title': {'Neutral': 'Last Stand - Hangar'},
                                         'Description': {'Neutral': 'old'}, 'Flags': ['DisableSavedFilms']},
        }
        for relative, data in metadata.items():
            dest = self.paths.package / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            p.write_json(dest, data)
        p.write_json(self.paths.result, {'sha256': p.sha256(self.paths.package / 'maps/last_stand.map'), 'retained': True})
        self.paths.receipts.mkdir()
        self.log = self.paths.receipts / 'fresh.log'
        self.log.write_text('successfully built cache file.\ntotal time 138.0\n')
        self.tool_status = self.paths.receipts / 'fresh.tool-exit'
        self.tool_status.write_bytes(b'0\n')
        started, finished = p.utcnow() - timedelta(minutes=2), p.utcnow() - timedelta(minutes=1)
        os.utime(self.paths.cache, (finished.timestamp(), finished.timestamp()))
        os.utime(self.log, (finished.timestamp(), finished.timestamp()))
        os.utime(self.tool_status, (finished.timestamp(), finished.timestamp()))
        stat = self.paths.cache.stat()
        self.receipt = {'schema_version': 2, 'candidate_version': p.VERSION, 'candidate': p.candidate(self.paths),
                        'started_at': started.isoformat(), 'finished_at': finished.isoformat(),
                        'exit_code': 0, 'launcher_exit_code': 0,
                        'tool_status': str(self.tool_status.relative_to(self.paths.root)),
                        'tool_status_sha256': p.sha256(self.tool_status),
                        'log': str(self.log.relative_to(self.paths.root)),
                        'log_sha256': p.sha256(self.log), 'cache_sha256': p.sha256(self.paths.cache),
                        'cache_bytes': stat.st_size, 'cache_mtime_ns': stat.st_mtime_ns}
        self.receipt_path = self.paths.receipts / 'fresh.build.json'
        p.write_json(self.receipt_path, self.receipt)
        self.validation = p.validation_template(self.paths)
        self.validation.update(validated_at=(started - timedelta(minutes=1)).isoformat(),
                               weapons_tested=list(p.WEAPONS), stages_tested=[1, 2, 3, 4])
        self.validation['checks'] = {name: {'passed': True, 'evidence': 'Observed in isolated test fixture: ' + name} for name in p.CHECKS}
        self.validation_path = self.paths.root / 'native-validation.json'
        p.write_json(self.validation_path, self.validation)

    def check(self):
        return p.check_release(self.paths, self.receipt_path, self.validation_path)

    def simulated_build(self, tool_status=b'0\n', launcher_exit=0, *,
                        output=b'successfully built cache file.\n', replace_cache=True):
        """Supply independent inner-tool and outer-launcher outcomes, no native process."""
        def run(command, *, stdout, stderr, check):
            self.assertEqual(command[:5], ['snap', 'run', '--shell', 'steam', '-c'])
            shell_lines = command[-1].splitlines()
            native_line = next(i for i, line in enumerate(shell_lines) if 'build-cache-file' in line)
            self.assertEqual(shell_lines[native_line + 1], 'sv_tool_exit=$?')
            self.assertIn('set +e', shell_lines[:native_line])
            write_line = shell_lines[native_line + 2]
            self.assertTrue(write_line.startswith('printf '))
            status_path = Path(shlex.split(write_line)[-1])
            self.assertEqual(status_path.parent, self.paths.receipts)
            self.assertFalse(status_path.exists())
            stdout.write(output)
            if replace_cache:
                self.paths.cache.write_bytes(b'fresh-build-cache' * 100000)
            if tool_status is not None:
                status_path.write_bytes(tool_status)
            return SimpleNamespace(returncode=launcher_exit)
        with patch.object(p, 'release_lock', lambda paths: nullcontext()), \
             patch.object(p, 'private_processes', return_value=[]), \
             patch.object(p.subprocess, 'run', side_effect=run), redirect_stdout(io.StringIO()):
            return p.build_cache(self.paths)

    def test_successful_tool_is_accepted_despite_launcher_cleanup_failure(self):
        receipt_path = self.simulated_build(launcher_exit=1)
        receipt = p.read_json(receipt_path)
        self.assertEqual(receipt['exit_code'], 0)
        self.assertEqual(receipt['launcher_exit_code'], 1)
        self.assertEqual(receipt['schema_version'], 2)
        self.assertEqual((self.paths.root / receipt['tool_status']).read_bytes(), b'0\n')
        info = p.check_release(self.paths, receipt_path, self.validation_path)
        self.assertFalse(info['already_current'])
        self.assertEqual((self.paths.package / 'maps/last_stand.map').read_bytes(), b'old-cache')

    def test_native_failure_cannot_be_overridden_by_successful_launcher_or_log(self):
        before = set(self.paths.receipts.glob('*.build.json'))
        with self.assertRaisesRegex(p.PromotionError, 'Cache tool exited 1'):
            self.simulated_build(tool_status=b'1\n', launcher_exit=0)
        self.assertEqual(set(self.paths.receipts.glob('*.build.json')), before)

    def test_missing_or_malformed_tool_status_never_creates_a_success_receipt(self):
        before = set(self.paths.receipts.glob('*.build.json'))
        for status in (None, b'', b'0', b'0\n1\n', b'bad\n', b'-1\n', b'256\n'):
            with self.subTest(status=status), self.assertRaisesRegex(p.PromotionError, 'Tool exit status'):
                self.simulated_build(tool_status=status)
        self.assertEqual(set(self.paths.receipts.glob('*.build.json')), before)

    def test_tool_success_still_requires_success_log_and_new_cache(self):
        before = set(self.paths.receipts.glob('*.build.json'))
        for output, fresh, error in (
                (b'build interrupted\n', True, 'success marker missing'),
                (b'successfully built cache file.\n-fatal- error\n', True, 'fatal error'),
                (b'successfully built cache file.\n', False, 'fresh output')):
            with self.subTest(output=output, fresh=fresh), self.assertRaisesRegex(p.PromotionError, error):
                self.simulated_build(launcher_exit=1, output=output, replace_cache=fresh)
        self.assertEqual(set(self.paths.receipts.glob('*.build.json')), before)

    def test_promotion_rechecks_tool_status_and_refuses_legacy_receipts(self):
        original = self.tool_status.read_bytes()
        self.tool_status.unlink()
        with self.assertRaisesRegex(p.PromotionError, 'status is missing'):
            self.check()
        for value in (b'1\n', b'bad\n'):
            self.tool_status.write_bytes(value)
            moment = p.timestamp(self.receipt['finished_at']).timestamp()
            os.utime(self.tool_status, (moment, moment))
            with self.subTest(value=value), self.assertRaises(p.PromotionError):
                self.check()
        self.tool_status.write_bytes(original)
        self.receipt['schema_version'] = 1
        p.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(p.PromotionError, 'Unsupported build receipt schema'):
            self.check()

    def test_fresh_matching_release_passes_without_mutation(self):
        before = (self.paths.package / 'ModInfo.json').read_bytes()
        info = self.check()
        self.assertFalse(info['already_current'])
        self.assertEqual(info['ids'], self.ids)
        self.assertEqual((self.paths.package / 'ModInfo.json').read_bytes(), before)
        self.assertFalse((self.paths.root / 'backups').exists())

    def test_nonpassing_template_is_not_native_validation(self):
        p.write_json(self.validation_path, p.validation_template(self.paths))
        with self.assertRaises(p.PromotionError):
            self.check()

    def test_validation_requires_every_check_evidence_and_weapon(self):
        for mutation in ('failed', 'no_evidence', 'missing_weapon'):
            record = json.loads(json.dumps(self.validation))
            if mutation == 'failed': record['checks']['armory_input']['passed'] = False
            if mutation == 'no_evidence': record['checks']['stage_transitions']['evidence'] = ''
            if mutation == 'missing_weapon': record['weapons_tested'].pop()
            p.write_json(self.validation_path, record)
            with self.subTest(mutation=mutation), self.assertRaises(p.PromotionError):
                self.check()

    def test_changed_source_scenario_or_tags_refuses_previous_validation(self):
        for path in (self.paths.source, self.paths.scenario,
                     self.paths.kit / 'tags/objects/survivors/v3/fixture.damage_effect'):
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.subTest(path=path), self.assertRaisesRegex(p.PromotionError, 'current candidate'):
                self.check()
            path.write_bytes(original)

    def test_old_log_cannot_promote_preexisting_cache(self):
        old = p.utcnow() - timedelta(hours=1)
        os.utime(self.paths.cache, (old.timestamp(), old.timestamp()))
        self.receipt['cache_mtime_ns'] = self.paths.cache.stat().st_mtime_ns
        p.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(p.PromotionError, 'Cache is old'):
            self.check()

    def test_receipt_expires_after_twenty_four_hours(self):
        self.receipt['started_at'] = (p.utcnow() - timedelta(hours=26)).isoformat()
        self.receipt['finished_at'] = (p.utcnow() - timedelta(hours=25)).isoformat()
        p.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(p.PromotionError, 'older than 24 hours'):
            self.check()

    def test_changed_cache_log_and_unsafe_log_path_are_rejected(self):
        original = self.log.read_bytes()
        self.log.write_bytes(original + b'changed')
        with self.assertRaisesRegex(p.PromotionError, 'Build log changed'):
            self.check()
        self.log.write_bytes(original)
        self.receipt['log'] = '../../unrelated.log'
        p.write_json(self.receipt_path, self.receipt)
        with self.assertRaisesRegex(p.PromotionError, 'outside the workspace'):
            self.check()

    def test_identical_old_map_and_identity_drift_are_rejected(self):
        old_map = self.paths.package / 'maps/last_stand.map'
        original = old_map.read_bytes()
        old_map.write_bytes(self.paths.cache.read_bytes())
        with self.assertRaisesRegex(p.PromotionError, 'previously packaged map'):
            self.check()
        old_map.write_bytes(original)
        metadata = p.read_json(self.paths.package / 'CampaignInfo.json')
        metadata['CampaignGuid'] = 'unexpected-id'
        p.write_json(self.paths.package / 'CampaignInfo.json', metadata)
        with self.assertRaisesRegex(p.PromotionError, 'GUID mismatch'):
            self.check()

    def test_fixture_promotion_preserves_ids_registration_and_backups(self):
        with patch.object(p, 'release_lock', lambda paths: nullcontext()):
            result = p.promote(self.paths, self.receipt_path, self.validation_path)
        self.assertEqual(result['status'], 'promoted')
        backup = Path(result['backup'])
        self.assertEqual((backup / 'LastStand/maps/last_stand.map').read_bytes(), b'old-cache')
        self.assertEqual((backup / 'project/README.md').read_text(), 'old project documentation')
        self.assertEqual(p.read_json(backup / 'LastStand/ModInfo.json')['ModVersion']['Minor'], 2)
        self.assertEqual(p.package_metadata(self.paths)[0], self.ids)
        new = p.read_json(self.paths.package / 'ModInfo.json')
        self.assertEqual(new['ModVersion'], p.VERSION_PARTS)
        self.assertEqual(new['ExtraField'], 'preserve')
        self.assertEqual(new['ModIdentifier']['HostedModIds'], {'keep': 42})
        self.assertEqual((self.paths.root / 'launch.py').read_bytes(), b'unchanged launcher')
        self.assertEqual((self.paths.root / 'ModManifest.txt').read_bytes(), b'unchanged registration')
        self.assertTrue(p.read_json(self.paths.result)['retained'])
        self.assertIn('Retail MCC', (self.paths.package / 'README.md').read_text(encoding='utf-8'))
        with patch.object(p, 'release_lock', lambda paths: nullcontext()):
            self.assertEqual(p.promote(self.paths, self.receipt_path, self.validation_path)['status'], 'already_current')

    def test_fixture_commit_failure_restores_original_package_and_metadata(self):
        real_replace = os.replace
        def fail_readme(source, destination):
            if Path(destination) == self.paths.root / 'project/README.md':
                raise OSError('simulated metadata replacement failure')
            return real_replace(source, destination)
        old_result = self.paths.result.read_bytes()
        with patch.object(p, 'release_lock', lambda paths: nullcontext()), patch.object(p.os, 'replace', fail_readme):
            with self.assertRaisesRegex(OSError, 'simulated'):
                p.promote(self.paths, self.receipt_path, self.validation_path)
        self.assertEqual((self.paths.package / 'maps/last_stand.map').read_bytes(), b'old-cache')
        self.assertEqual(self.paths.result.read_bytes(), old_result)
        self.assertEqual((self.paths.root / 'project/README.md').read_text(), 'old project documentation')
        self.assertEqual(p.read_json(self.paths.package / 'ModInfo.json')['ModVersion']['Minor'], 2)


if __name__ == '__main__':
    unittest.main()
