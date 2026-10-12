import random
import unittest
from hsc_vm import VM

class SurvivalTests(unittest.TestCase):
    def setUp(self): self.v=VM(); self.v.boot()
    def test_startup_and_no_free_xp(self):
        self.assertEqual(sum(self.v.living.values()),12)
        self.v.tick(100)
        self.assertEqual(self.v.globals['sv_xp'],0)
        self.assertEqual(self.v.globals['sv_level'],1)
    def test_last_kill_before_respawn_awards_once(self):
        self.v.living['sv_grunts_a']=0
        self.v.tick()
        self.assertEqual(self.v.globals['sv_xp'],60)
        self.assertEqual(self.v.living['sv_grunts_a'],6)
        self.v.tick(15)
        self.assertEqual(self.v.globals['sv_xp'],60)
    def test_multilevel_burst_preserves_remainder(self):
        self.v.globals['sv_xp']=1000
        self.v.tick(5)
        self.assertEqual(self.v.globals['sv_level'],6)
        self.assertEqual(self.v.globals['sv_tokens'],5)
        self.assertEqual(self.v.globals['sv_xp'],0)
        self.assertEqual(self.v.globals['sv_threshold'],350)
    def test_pad_edge_and_caps(self):
        self.v.globals['sv_tokens']=20
        self.v.volumes={'sv_pad_needler'}
        self.v.tick(20)
        self.assertEqual(self.v.globals['sv_needler_rank'],1)
        self.assertEqual(self.v.globals['sv_tokens'],19)
        for _ in range(5):
            self.v.volumes=set(); self.v.tick()
            self.v.volumes={'sv_pad_needler'}; self.v.tick()
        self.assertEqual(self.v.globals['sv_needler_rank'],3)
        self.assertEqual(self.v.globals['sv_tokens'],17)
    def test_adjacent_pads_need_full_exit(self):
        self.v.globals['sv_tokens']=2
        self.v.volumes={'sv_pad_needler'}; self.v.tick()
        self.v.volumes={'sv_pad_aegis'}; self.v.tick()
        self.assertEqual(self.v.globals['sv_tokens'],1)
        self.assertEqual(self.v.globals['sv_aegis_rank'],0)
    def test_no_upgrade_without_token(self):
        self.v.volumes={'sv_pad_needler'}; self.v.tick()
        self.assertEqual(self.v.globals['sv_needler_rank'],0)
    def test_shield_clamps_and_pulses(self):
        self.v.globals['sv_aegis_rank']=5; self.v.shield=.6
        self.v.tick(7); self.assertEqual(self.v.shield,.6)
        self.v.tick(); self.assertEqual(self.v.shield,1.)
    def test_vitality_upgrade(self):
        self.v.globals['sv_tokens']=1; self.v.volumes={'sv_pad_vitality'}
        self.v.tick(); self.assertEqual(self.v.max_vitality,(54.,84.))
    def test_death_precedes_extraction(self):
        self.v.globals['sv_seconds']=1199; self.v.volumes={'sv_extraction'}
        self.v.health=0; self.v.tick()
        self.assertTrue(self.v.lost); self.assertFalse(self.v.won)
    def test_extraction_stops_all_further_spawns(self):
        self.v.globals['sv_seconds']=1199; before=len(self.v.spawns)
        self.v.tick(); self.assertEqual(self.v.globals['sv_seconds'],1200)
        self.assertEqual(len(self.v.spawns),before)
        self.v.volumes={'sv_extraction'}; self.v.tick()
        self.assertTrue(self.v.won)
        self.v.tick(100); self.assertEqual(len(self.v.spawns),before)
        self.assertEqual(self.v.globals['sv_seconds'],1201)
    def test_extraction_deadline(self):
        self.v.globals['sv_seconds']=1258; self.v.tick()
        self.assertFalse(self.v.lost)
        self.v.tick(); self.assertTrue(self.v.lost)
    def test_last_second_extraction_is_allowed(self):
        self.v.globals['sv_seconds']=1259; self.v.volumes={'sv_extraction'}
        self.v.tick(); self.assertTrue(self.v.won); self.assertFalse(self.v.lost)
    def test_missing_player_loses_without_spawning(self):
        before=len(self.v.spawns); self.v.player_count=0; self.v.tick()
        self.assertTrue(self.v.lost); self.assertEqual(len(self.v.spawns),before)
    def test_multiplayer_start_refused(self):
        v=VM(); v.player_count=2; v.boot(); v.tick()
        self.assertFalse(v.globals['sv_running']); self.assertEqual(v.spawns,[])
    def test_full_seeded_run_cap_phases_and_xp(self):
        rng=random.Random(73); expected_xp=0; observed=set()
        weights={s['name']:s['xp_per_death'] for s in self.v.contract['squads']}
        unlocks={s['name']:s['unlock_seconds'] for s in self.v.contract['squads']}
        for second in range(1260):
            for name,alive in list(self.v.living.items()):
                dead=rng.randrange(alive+1) if rng.random()<.3 else 0
                self.v.living[name]-=dead; expected_xp+=dead*weights[name]
            before=len(self.v.spawns); self.v.tick()
            for name,_ in self.v.spawns[before:]:
                self.assertGreaterEqual(self.v.globals['sv_seconds'],unlocks[name])
                self.assertLess(self.v.globals['sv_seconds'],1200)
                observed.add(name)
            self.assertLessEqual(sum(self.v.living.values()),36)
        spent=sum(100+50*i for i in range(self.v.globals['sv_level']-1))
        self.assertEqual(self.v.globals['sv_xp']+spent,expected_xp)
        self.assertEqual(observed,set(weights)); self.assertTrue(self.v.lost)

if __name__=='__main__': unittest.main()
