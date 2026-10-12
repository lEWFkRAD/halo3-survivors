import unittest
from hsc_vm import VM

class AutoFireTests(unittest.TestCase):
    def setUp(self):
        self.v=VM();self.v.boot()
        self.v.actors={'sv_grunts_a':['far','near','dead','missing']}
        self.v.actor_health={'far':100,'near':100,'dead':0,'missing':100}
        self.v.distances={'far':9,'near':3,'dead':1,'missing':-1}
    def test_nearest_living_valid_target(self):
        self.v.run('sv_auto_clock')
        self.assertEqual(self.v.actor_health['near'],88)
        self.assertEqual(self.v.actor_health['far'],100)
        self.assertEqual(self.v.globals['sv_shots'],1)
    def test_empty_and_outside_range_do_not_fire(self):
        self.v.distances={'far':13,'near':20,'dead':1,'missing':-1}
        self.v.run('sv_auto_clock');self.assertEqual(self.v.globals['sv_shots'],0)
        self.v.actors={};self.v.run('sv_auto_clock');self.assertEqual(self.v.globals['sv_shots'],0)
    def test_upgrade_damage(self):
        self.v.globals['sv_needler_rank']=3;self.v.run('sv_auto_clock')
        self.assertEqual(self.v.actor_health['near'],64)
    def test_no_attacks_before_start_or_after_end(self):
        for name,value in [('sv_running',False),('sv_finished',True)]:
            self.setUp();self.v.globals[name]=value;self.v.run('sv_auto_clock')
            self.assertEqual(self.v.globals['sv_shots'],0)
    def test_no_attacks_while_dead_or_player_missing(self):
        self.v.health=0;self.v.run('sv_auto_clock');self.assertEqual(self.v.globals['sv_shots'],0)
        self.v.health=1;self.v.player_count=0;self.v.run('sv_auto_clock');self.assertEqual(self.v.globals['sv_shots'],0)

    def test_attacks_continue_during_extraction(self):
        self.v.globals['sv_seconds']=1200;self.v.run('sv_auto_clock')
        self.assertEqual(self.v.globals['sv_shots'],1)
