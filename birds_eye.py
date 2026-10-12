from pathlib import Path
import math
import blam_tags as b
root=Path(__file__).resolve().parent
p=root/'native-tags/levels/survivors/last_stand'
tag=b.TagFile.read(p/'birdbase.scenario');r=tag.root()
def block(s,n):return s.field(n).as_block()
def put(s,n,v):s.field(n).set(v)
block(r,'equipment').clear()
block(r,'weapons').clear()
c=block(r,'cutscene camera points');i=c.add();cam=c[i]
put(cam,'name','sv_overhead');put(cam,'type','ignore target orientation')
cam.field('flags').set_flag('edit as relative',False)
put(cam,'position',b.RealPoint3d(-5.9323,5.50402,-5.2));put(cam,'orientation',b.RealEulerAngles3d(0,-math.pi/2,0))
put(block(r,'player starting locations')[0],'position',b.RealPoint3d(-5.9323,5.50402,-9.49975))
# Ground points from the stock hangar's navigation data.
f=block(block(r,'zones')[0],'firing positions')
places={name:f[idx].field('position (local)').value for name,idx in [('needler',259),('aegis',284),('vitality',75),('exit',141)]}
cf=block(r,'cutscene flags');names=block(r,'object names');sc=block(r,'scenery')
for i in range(len(cf)):
 name=cf[i].field('name').value
 if name.startswith('sv_beacon_'):
  xyz=places[name.removeprefix('sv_beacon_')];put(cf[i],'position',b.RealPoint3d(xyz.x,xyz.y,xyz.z+.1))
for i in range(len(names)):
 name=names[i].field('name').value
 if name.startswith('sv_marker_'):
  xyz=places[name.removeprefix('sv_marker_')];idx=names[i].field('scenario_datum_index').value
  put(sc[idx].field('object data').as_struct(),'position',b.RealPoint3d(xyz.x+.25,xyz.y+.25,xyz.z+.1))
# Fixed-world overhead camera grid: nearest floor anchor chooses a smooth pan.
chosen={}
for idx in range(len(f)):
 xyz=f[idx].field('position (local)').value
 if -18<xyz.x<13 and -4<xyz.y<15 and -11<xyz.z<-7:
  key=(round(xyz.x/2),round(xyz.y/2))
  if key not in chosen:chosen[key]=xyz
anchors=[]
for idx,xyz in enumerate(chosen.values()):
 name='sv_view_'+str(idx);anchors.append(name)
 c=block(r,'cutscene camera points');i=c.add();q=c[i]
 put(q,'name',name);put(q,'type','normal');put(q,'position',b.RealPoint3d(xyz.x,xyz.y,-5.2));put(q,'orientation',b.RealEulerAngles3d(0,-math.pi/2,0))
 cf=block(r,'cutscene flags');i=cf.add();q=cf[i];put(q,'name',name);put(q,'position',b.RealPoint3d(xyz.x,xyz.y,xyz.z))
cf=block(r,'cutscene flags');i=cf.add();q=cf[i];put(q,'name','sv_heading');put(q,'position',b.RealPoint3d(1000,5,-9));put(q,'facing',b.RealEulerAngles2d(0,0))
import json
(root/'camera-grid.json').write_text(json.dumps(anchors))
print('Camera grid',len(anchors),'anchors')
tag.recompute_checksum();tag.write(p/'last_stand.scenario');print('Authored overhead follow camera and hangar-floor spawn/beacons.')


