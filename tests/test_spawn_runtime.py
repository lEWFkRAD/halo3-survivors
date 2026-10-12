"""Execute generated spawn guards against the existing HaloScript test VM."""
from copy import deepcopy
from pathlib import Path
import sys,unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hsc_vm import VM,parse
from progression_hsc import HSC,enemies


STAGES=[{'number':1,'objective':'sv_hunt_1','squads':[
    {'name':'sv_s1_grunts','count':6,'xp':10,'unlock_seconds':0,
     'spawn_flags':[f'grunt_p{i}' for i in range(6)]},
    {'name':'sv_s1_jackals','count':4,'xp':20,'unlock_seconds':0,
     'spawn_flags':[f'jackal_p{i}' for i in range(4)]},
    {'name':'sv_s1_infection','count':10,'xp':3,'unlock_seconds':45,
     'spawn_flags':[f'infection_p{i}' for i in range(10)]},
]}]


class SpawnVM(VM):
    def __init__(self,stages=None):
        super().__init__()
        self.stages=deepcopy(STAGES if stages is None else stages)
        h=HSC();enemies(h,self.stages)
        h.script('sv_player','(unit (list_get (players) 0))',kind='static unit')
        self.globals={'sv_stage':1,'sv_stage_seconds':90,'sv_xp':0,'sv_xp_scale':1}
        self.scripts={};self.flag_queries=[]
        self.living={s['name']:0 for stage in self.stages for s in stage['squads']}
        self.flag_distances={f:3.0 for stage in self.stages for s in stage['squads'] for f in s.get('spawn_flags',[])}
        for form in parse(h.render()):
            if form[0]=='global':self.globals[form[2]]=form[3]
            else:self.scripts[form[3]]=form[4:]

    def eval(self,x):
        if isinstance(x,list):
            op,*args=x
            if op=='objects_distance_to_flag':
                players,flag=[self.eval(a) for a in args]
                self.flag_queries.append(flag)
                return self.flag_distances.get(flag,-1) if players else -1
            if op=='ai_living_count' and args[0]=='sv_hostiles':return sum(self.living.values())
            if op=='ai_set_objective':return None
        return super().eval(x)


class SpawnRuntimeTests(unittest.TestCase):
    def test_every_infection_slot_blocks_its_cohort_when_player_is_near(self):
        # Includes the final slot, which lives in a separate six-check chunk.
        for index in range(10):
            with self.subTest(index=index):
                v=SpawnVM();v.flag_distances[f'infection_p{index}']=1.999
                v.run('sv_spawn')
                self.assertEqual(v.living['sv_s1_infection'],0)
                self.assertEqual(v.globals['sv_s1_infection_prev'],0)
                self.assertEqual(v.living['sv_s1_grunts'],6)
                self.assertEqual(v.living['sv_s1_jackals'],4)
                self.assertEqual(v.globals['sv_total'],10)

    def test_two_units_or_more_permits_all_cohorts(self):
        v=SpawnVM();v.flag_distances={f:2.0 for f in v.flag_distances};v.run('sv_spawn')
        self.assertEqual(sum(v.living.values()),20)
        self.assertEqual(len(v.spawns),3)

    def test_negative_or_missing_distance_fails_closed(self):
        for invalid in (-1,-10,None):
            with self.subTest(invalid=invalid):
                v=SpawnVM()
                if invalid is None:del v.flag_distances['infection_p9']
                else:v.flag_distances['infection_p9']=invalid
                v.run('sv_spawn');self.assertEqual(v.living['sv_s1_infection'],0)
        v=SpawnVM();v.player_count=0;v.run('sv_spawn');self.assertEqual(v.spawns,[])

    def test_skipped_cohort_retries_without_duplicating_other_cohorts(self):
        v=SpawnVM();v.flag_distances['infection_p9']=1;v.run('sv_spawn')
        self.assertEqual(len(v.spawns),2)
        v.flag_distances['infection_p9']=3;v.run('sv_spawn')
        self.assertEqual(v.spawns.count(('sv_s1_infection',10)),1)
        self.assertEqual(v.spawns.count(('sv_s1_grunts',6)),1)
        self.assertEqual(v.spawns.count(('sv_s1_jackals',4)),1)

    def test_clear_flags_cannot_bypass_actor_cap_or_unlock_time(self):
        v=SpawnVM();v.living['existing_other_cohort']=32;v.run('sv_spawn')
        self.assertEqual(sum(v.living.values()),36)
        self.assertEqual(v.spawns,[('sv_s1_jackals',4)])
        v=SpawnVM();v.globals['sv_stage_seconds']=44;v.run('sv_spawn')
        self.assertEqual(v.living['sv_s1_infection'],0)
        self.assertEqual(sum(v.living.values()),10)

    def test_legacy_layout_without_flags_remains_supported(self):
        stages=deepcopy(STAGES)
        for sq in stages[0]['squads']:sq.pop('spawn_flags')
        v=SpawnVM(stages);v.run('sv_spawn')
        self.assertEqual(sum(v.living.values()),20);self.assertEqual(v.flag_queries,[])

    def test_partial_flag_lists_are_rejected(self):
        stages=deepcopy(STAGES);stages[0]['squads'][0]['spawn_flags'].pop()
        with self.assertRaises(AssertionError):SpawnVM(stages)


if __name__=='__main__':unittest.main()
