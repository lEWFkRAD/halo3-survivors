"""Move the verified gameplay into the Ark's outdoor landing area."""
from pathlib import Path
import math,json,shutil
import blam_tags as b
R=Path(__file__).resolve().parent
P=R/'native-tags/levels/survivors/last_stand'
backup=P/'hangar-overhead.scenario'
if not backup.exists():shutil.copy2(P/'last_stand.scenario',backup)
src=b.TagFile.read(backup).root()
tag=b.TagFile.read(R/'private-inputs/070_waste.scenario');r=tag.root()
def block(s,n):return s.field(n).as_block()
def put(s,n,v):s.field(n).set(v)
def clone_struct(src,dst):
 for key in src.field_names():
  sf=src.field(key);df=dst.field(key)
  if sf.type_name=='block':
   a=sf.as_block();out=df.as_block();out.clear()
   for idx in range(len(a)):
    j=out.add();clone_struct(a[idx],out[j])
  elif sf.type_name=='struct':clone_struct(sf.as_struct(),df.as_struct())
  elif 'flags' in sf.type_name and isinstance(sf.value,list):
   for flag in list(df.value):df.set_flag(flag,False)
   for flag in sf.value:df.set_flag(flag,True)
  elif sf.value is not None or 'reference' in sf.type_name:
   try:df.set(sf.value)
   except Exception as e:raise RuntimeError((key,sf.type_name,sf.value)) from e

def append_clone(dst,source):
 j=dst.add();clone_struct(source,dst[j]);return j

def copyblock(n):
 block(r,n).clear()
 for i in range(len(block(src,n))):append_clone(block(r,n),block(src,n)[i])
# Retain outdoor BSP, lightmaps, stock scenery and navigation.
for n in ['scripts','globals','source files','hs syntax datums','references','scenario resources','zone set switch trigger volumes','scenario kill triggers','scenario safe zone triggers','bipeds','vehicles','giants','cinematics','mission scenes','hs unit seats','equipment','weapons','scripting data','squad groups','creatures','flocks']:
 block(r,n).clear()
z=block(r,'zone sets');z.swap(0,14);z=block(r,'zone sets')[0]
put(z,'name','sv_outdoors');put(z,'hint previous zone set',-1)
for f in list(z.field('flags').value):z.field('flags').set_flag(f,False)
for n in ['character palette','weapon palette','player starting profile','player starting locations','cutscene titles','ai objectives','squads','trigger volumes']:
 copyblock(n)
put(r,'chapter title text',src.field('chapter title text').value)
# Use native ground points in the level's first open landing clearing.
f=block(block(r,'zones')[0],'firing positions')
points=[f[i].field('position (local)').value for i in range(len(f))]
def nearest(x,y):return min(points,key=lambda p:(p.x-x)**2+(p.y-y)**2)
center=nearest(101,364)
pl=block(r,'player starting locations')[0];put(pl,'position',b.RealPoint3d(center.x,center.y,center.z+.2));put(pl,'bsp index',0)
t=block(block(r,'ai objectives')[0],'tasks')[0];areas=block(t,'areas');areas.clear()
for i in range(len(block(block(r,'zones')[0],'areas'))):
 a=block(block(block(r,'ai objectives')[0],'tasks')[0],'areas');j=a.add();q=a[j]
 for k,v in {'area type':'search','zone':0,'area':i}.items():put(q,k,v)
# Distributed ground spawns around the player, with valid BSP identities.
for i in range(len(block(r,'squads'))):
 sq=block(r,'squads')[i];put(sq,'initial zone',0)
 ft=block(sq,'fire-teams')[0];loc=block(ft,'starting locations')
 for j in range(len(loc)):
  ang=(i/8+j/max(1,len(loc))*.2)*math.tau
  xyz=nearest(center.x+10*math.cos(ang),center.y+7*math.sin(ang))
  put(loc[j],'position',b.RealPoint3d(xyz.x,xyz.y,xyz.z+.15));put(loc[j],'structure bsp',0);put(loc[j],'reference frame',-1)
# Preserve the known working visible upgrade objects while relocating outdoors.
block(r,'cutscene flags').clear();block(r,'cutscene camera points').clear()
places={n:nearest(center.x+dx,center.y+dy) for n,dx,dy in [('needler',-7,-4),('aegis',7,-4),('vitality',7,4),('exit',-7,4)]}
for num,(name,xyz) in enumerate(places.items()):
 cf=block(r,'cutscene flags');j=cf.add();q=cf[j];put(q,'name','sv_beacon_'+name);put(q,'position',b.RealPoint3d(xyz.x,xyz.y,xyz.z+.1))
 ns=block(src,'object names');ix=next(i for i in range(len(ns)) if ns[i].field('name').value=='sv_marker_'+name)
 obj=block(src,'scenery')[ns[ix].field('scenario_datum_index').value]
 pal=block(r,'scenery palette');pi=append_clone(pal,block(src,'scenery palette')[obj.field('type').value])
 sc=block(r,'scenery');si=append_clone(sc,block(src,'scenery')[ns[ix].field('scenario_datum_index').value])
 names=block(r,'object names');ni=names.add();q=names[ni]
 put(q,'name','sv_marker_'+name);put(q,'object_type',6);put(q,'scenario_datum_index',si)
 q=block(r,'scenery')[si];put(q,'type',pi);put(q,'name',ni);d=q.field('object data').as_struct()
 put(d,'position',b.RealPoint3d(xyz.x+.25,xyz.y+.25,xyz.z+.1));put(d,'manual bsp flags',1)
 put(d.field('object id').as_struct(),'origin bsp index',0)
# 2-unit cells follow the outdoor clearing at a constant 12-unit overhead altitude.
chosen={}
for xyz in points:chosen.setdefault((round(xyz.x/2),round(xyz.y/2)),xyz)
def camera(name,xyz):
 c=block(r,'cutscene camera points');i=c.add();q=c[i]
 put(q,'name',name);put(q,'type','normal');put(q,'position',b.RealPoint3d(xyz.x,xyz.y,center.z+12));put(q,'orientation',b.RealEulerAngles3d(0,-math.pi/2,0))
camera('sv_overhead',center);anchors=[]
for idx,xyz in enumerate(chosen.values()):
 name='sv_view_'+str(idx);anchors.append(name);camera(name,xyz)
 cf=block(r,'cutscene flags');i=cf.add();q=cf[i];put(q,'name',name);put(q,'position',xyz)
cf=block(r,'cutscene flags');i=cf.add();q=cf[i];put(q,'name','sv_heading');put(q,'position',b.RealPoint3d(center.x+1000,center.y,center.z));put(q,'facing',b.RealEulerAngles2d(0,0))
(R/'camera-grid.json').write_text(json.dumps(anchors))
(R/'outdoor-layout.json').write_text(json.dumps({'base':'070_waste','zone':'lz','bsp':0,'center':[center.x,center.y,center.z],'camera_height':12,'anchors':len(anchors),'beacons':{n:[v.x,v.y,v.z] for n,v in places.items()}},indent=2))
tag.recompute_checksum();tag.write(P/'last_stand.scenario')
print('Outdoor authored',len(anchors),'anchors',center)

