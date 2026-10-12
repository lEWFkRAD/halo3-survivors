"""Spawn safety and pacing checks; owned navigation is read without rewriting tags."""
from dataclasses import replace
from pathlib import Path
import json,math,sys,unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
try:
    from progression_tags import SpawnPoint,select_spawn_points,spawn_profile,B,b
except ImportError as error:
    raise unittest.SkipTest('Native tag authoring binding is required') from error


def radial(index,radius,angle=0,**changes):
    p=SpawnPoint(index,(radius*math.cos(angle),radius*math.sin(angle),0),0,0,-1,12)
    return replace(p,**changes)


class SpawnGeometryTests(unittest.TestCase):
    def test_invalid_or_close_points_are_never_used_as_fallback(self):
        safe=[radial(100+i,7,math.tau*i/6) for i in range(6)]
        unsafe=[radial(0,6.5,bsp=1),radial(1,6.5,reference_frame=0),
                radial(2,6.5,sector=-1),radial(3,6.5,area=2),
                radial(4,6.5,position=(6.5,0,3.01)),radial(5,1),radial(6,8.01)]
        selected=select_spawn_points(unsafe+safe,(0,0,0),{0},'grunts',6,0)
        self.assertEqual({p.index for p in selected},{p.index for p in safe})
        with self.assertRaises(ValueError):
            select_spawn_points(unsafe,(0,0,0),{0},'grunts',1,0)

    def test_heavies_and_snipers_keep_longer_entry_clearance(self):
        points=[radial(0,6.5),radial(1,8.0),radial(2,8.5),radial(3,9.5)]
        self.assertEqual(select_spawn_points(points,(0,0,0),{0},'grunts',1,0)[0].index,0)
        self.assertEqual(select_spawn_points(points,(0,0,0),{0},'hunters',1,0)[0].index,1)
        self.assertEqual(select_spawn_points(points,(0,0,0),{0},'snipers',1,0)[0].index,2)

    def test_reordering_source_points_does_not_change_selection(self):
        points=[radial(i,6.75,math.tau*i/24) for i in range(24)]
        a=select_spawn_points(points,(0,0,0),{0},'grunts',6,.1)
        z=select_spawn_points(list(reversed(points)),(0,0,0),{0},'grunts',6,.1)
        self.assertEqual(a,z)

    def test_overlapping_candidates_cannot_form_a_cohort(self):
        points=[radial(i,6.5) for i in range(12)]
        with self.assertRaises(ValueError):
            select_spawn_points(points,(0,0,0),{0},'grunts',2,0)

    @unittest.skipUnless((ROOT/'native-tags/levels/survivors/last_stand/outdoor-compiled.scenario').exists(),
                         'Owner-provided native navigation is unavailable')
    def test_owned_arenas_support_all_cohorts_inside_their_safe_rings(self):
        tag=b.TagFile.read(ROOT/'native-tags/levels/survivors/last_stand/outdoor-compiled.scenario')
        layout=json.loads((ROOT/'progression-layout.json').read_text())
        phases={q['enemy']:i/10 for i,q in enumerate(layout['stages'][3]['squads'])}
        opening=[]
        for stage in layout['stages']:
            fps=B(B(tag.root(),'zones')[stage['zone']],'firing positions')
            candidates=[]
            for i in range(len(fps)):
                row=fps[i];p=row.field('position (local)').value
                candidates.append(SpawnPoint(i,(p.x,p.y,p.z),row.field('area').value,
                                  row.field('structure bsp').value,row.field('reference frame').value,
                                  row.field('sector index').value))
            center=stage['center'];areas=set(stage['area_indices'])
            for squad in stage['squads']:
                family=squad['enemy'];low,high,_,spacing=spawn_profile(family)
                chosen=select_spawn_points(candidates,center,areas,family,squad['count'],phases[family])
                self.assertEqual(len({p.index for p in chosen}),squad['count'])
                for i,p in enumerate(chosen):
                    radius=math.hypot(p.position[0]-center[0],p.position[1]-center[1])
                    self.assertGreaterEqual(radius,low);self.assertLessEqual(radius,high)
                    self.assertEqual((p.bsp,p.reference_frame),(0,-1));self.assertGreaterEqual(p.sector,0)
                    self.assertIn(p.area,areas);self.assertLessEqual(abs(p.position[2]-center[2]),3)
                    for other in chosen[i+1:]:
                        distance=math.hypot(p.position[0]-other.position[0],p.position[1]-other.position[1])
                        self.assertGreaterEqual(distance,spacing)
                    if stage['number']==1:opening.append(radius)
        self.assertLess(sum(opening)/len(opening),7.2)
        self.assertGreaterEqual(min(opening),5.5)


if __name__=='__main__':unittest.main()
