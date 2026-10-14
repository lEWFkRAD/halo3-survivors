"""Hermetic tests for the LS-08 permanent profile module.

Storage and rules only: no launcher, engine or native core is involved.
The acceptance matrix from issue #9 that source can prove lives here:
anti-replay, atomic saves with preserved backups, invalid profiles,
migrations, and QA/production isolation. Survival across a process
restart and a New Run is represented by save/load round-trips between
fresh module reads; the engine bridge itself is native work.
"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import permanent_profile as pp


class PermanentProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'permanent.json'

    def earned(self, kind='production'):
        profile = pp.new_profile(kind)
        profile, applied = pp.apply_outcome(
            profile, 'run-2026-10-14-victory-1',
            unlocks=('assault_rifle.unlock',), salvage=25)
        self.assertTrue(applied)
        return profile

    def test_round_trip_preserves_everything(self):
        profile = self.earned()
        pp.save_profile(self.path, profile)
        self.assertEqual(pp.load_profile(self.path), profile)
        data = json.loads(self.path.read_text())
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['unlocks'], ['assault_rifle.unlock'])
        self.assertEqual(data['salvage'], 25)

    def test_replayed_outcome_never_awards_twice(self):
        profile = self.earned()
        again, applied = pp.apply_outcome(
            profile, 'run-2026-10-14-victory-1',
            unlocks=('rocket_launcher.unlock',), salvage=500)
        self.assertFalse(applied)
        self.assertEqual(again, profile)

    def test_distinct_outcomes_accumulate(self):
        profile = self.earned()
        profile, applied = pp.apply_outcome(
            profile, 'run-2026-10-15-victory-2',
            unlocks=('energy_sword.unlock',), salvage=10)
        self.assertTrue(applied)
        self.assertEqual(profile.salvage, 35)
        self.assertEqual(profile.unlocks, frozenset(
            {'assault_rifle.unlock', 'energy_sword.unlock'}))
        self.assertEqual(len(profile.outcomes), 2)

    def test_spend_guards(self):
        profile = self.earned()
        profile = pp.spend_salvage(profile, 25)
        self.assertEqual(profile.salvage, 0)
        with self.assertRaises(pp.ProfileError):
            pp.spend_salvage(profile, 1)
        with self.assertRaises(pp.ProfileError):
            pp.spend_salvage(self.earned(), 0)
        with self.assertRaises(pp.ProfileError):
            pp.spend_salvage(self.earned(), -5)

    def test_validation_rejects_bad_unlocks_and_amounts(self):
        with self.assertRaises(pp.ProfileError):
            pp.apply_outcome(pp.new_profile('production'), 'ok-1',
                             unlocks=('not_a_node.unlock',))
        with self.assertRaises(pp.ProfileError):
            # Run-scope nodes are not permanent unlocks.
            pp.apply_outcome(pp.new_profile('production'), 'ok-1',
                             unlocks=('needler.damage',))
        with self.assertRaises(pp.ProfileError):
            pp.apply_outcome(pp.new_profile('production'), 'ok-1',
                             salvage=-1)
        with self.assertRaises(pp.ProfileError):
            pp.apply_outcome(pp.new_profile('production'), 'bad id!')
        with self.assertRaises(pp.ProfileError):
            pp.new_profile('staging')
        data = pp.to_data(self.earned())
        data['surprise'] = True
        with self.assertRaises(pp.ProfileError):
            pp.from_data(data)
        data = pp.to_data(self.earned())
        data['salvage'] = '25'
        with self.assertRaises(pp.ProfileError):
            pp.from_data(data)
        data = pp.to_data(self.earned())
        data['unlocks'] = ['assault_rifle.unlock', 'assault_rifle.unlock']
        with self.assertRaises(pp.ProfileError):
            pp.from_data(data)

    def test_save_preserves_previous_as_backup(self):
        first = pp.new_profile('production')
        pp.save_profile(self.path, first)
        second = self.earned()
        pp.save_profile(self.path, second)
        self.assertEqual(pp.load_profile(self.path), second)
        self.assertEqual(pp.recover_profile(self.path), first)

    def test_corrupt_main_recovers_only_explicitly(self):
        pp.save_profile(self.path, pp.new_profile('production'))
        earned = self.earned()
        pp.save_profile(self.path, earned)
        self.path.write_text('{corrupt', encoding='utf-8')
        with self.assertRaises(pp.ProfileError):
            pp.load_profile(self.path)
        self.assertEqual(pp.recover_profile(self.path),
                         pp.new_profile('production'))

    def test_failed_replace_leaves_original_and_no_temp_litter(self):
        original = self.earned()
        pp.save_profile(self.path, original)
        before = self.path.read_bytes()
        with mock.patch.object(os, 'replace',
                               side_effect=OSError('simulated crash')):
            with self.assertRaises(OSError):
                pp.save_profile(self.path, pp.new_profile('production'))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(pp.load_profile(self.path), original)
        litter = [p.name for p in self.path.parent.iterdir()
                  if p.name.endswith('.tmp')]
        self.assertEqual(litter, [])

    def test_linked_output_is_refused(self):
        target = Path(self.temp.name) / 'elsewhere.json'
        link = Path(self.temp.name) / 'linked.json'
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(pp.ProfileError):
            pp.save_profile(link, pp.new_profile('production'))

    def test_migration_and_future_versions(self):
        upgraded = pp.migrate({'unlocks': ['needler.unlock'], 'salvage': 3})
        profile = pp.from_data(upgraded)
        self.assertEqual(profile.unlocks, frozenset({'needler.unlock'}))
        self.assertEqual(profile.salvage, 3)
        self.assertEqual(profile.outcomes, ())
        with self.assertRaises(pp.ProfileError):
            pp.migrate({'schema_version': 99, 'kind': 'production',
                        'unlocks': [], 'salvage': 0, 'outcomes': []})
        current = pp.to_data(self.earned())
        self.assertEqual(pp.migrate(current), current)

    def test_kind_isolation(self):
        pp.save_profile(self.path, self.earned(kind='qa'))
        with self.assertRaises(pp.ProfileError):
            pp.load_profile(self.path, expected_kind='production')
        self.assertEqual(
            pp.load_profile(self.path, expected_kind='qa').kind, 'qa')

    def test_missing_profile_is_an_error_not_a_default(self):
        with self.assertRaises(pp.ProfileError):
            pp.load_profile(self.path)
        with self.assertRaises(pp.ProfileError):
            pp.recover_profile(self.path)


if __name__ == '__main__':
    unittest.main()
