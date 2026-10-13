"""Author four outdoor native stages; preserve the playable v0.2 scenario."""
from pathlib import Path
from dataclasses import dataclass
import json,math
import blam_tags as b
ROOT=Path(__file__).resolve().parent
P=ROOT/'native-tags/levels/survivors/last_stand'
def B(s,n):return s.field(n).as_block()
def put(s,n,v):
 f=s.field(n)
 if 'flags' in f.type_name and isinstance(v,list):
  for x in list(f.value):f.set_flag(x,False)
  for x in v:f.set_flag(x,True)
 else:f.set(v)
def clone(src,dst):
 for n in src.field_names():
  a=src.field(n);d=dst.field(n)
  if a.type_name=='block':
   aa=a.as_block();dd=d.as_block();dd.clear()
   for k in range(len(aa)):
    j=dd.add();clone(aa[k],dd[j])
  elif a.type_name=='struct':clone(a.as_struct(),d.as_struct())
  elif 'flags' in a.type_name and isinstance(a.value,list):put(dst,n,a.value)
  elif a.value is not None or 'reference' in a.type_name:d.set(a.value)
def addclone(dst,src):
 j=dst.add();clone(src,dst[j]);return j
def xyz(p):return [p.x,p.y,p.z]
def d2(a,c):return (a.x-c.x)**2+(a.y-c.y)**2

@dataclass(frozen=True)
class SpawnPoint:
 index:int
 position:tuple
 area:int
 bsp:int
 reference_frame:int
 sector:int

def spawn_profile(family):
 """Ranges are from stage entry, not the player's changing runtime position."""
 spacing=1.0 if family in ('hunters','chieftain') else .35 if family=='infection' else .8
 if family=='snipers':return 8.0,10.0,(8.5,9.0,9.5),spacing
 if family in ('carrier','hunters','chieftain'):return 7.5,9.0,(8.0,8.5,8.5),spacing
 return 5.5,8.0,(6.5,7.0,7.5),spacing

def select_spawn_points(points,center,areas,family,count,phase):
 """Choose nearby, separated stock floor points; never fall back to unsafe nav."""
 low,high,radii,spacing=spawn_profile(family)
 def distance2(a,c):return (a[0]-c[0])**2+(a[1]-c[1])**2
 ring=[p for p in points if p.bsp==0 and p.reference_frame==-1
       and p.sector>=0 and p.area in areas
       and abs(p.position[2]-center[2])<=3
       and low**2<=distance2(p.position,center)<=high**2]
 if len(ring)<count:raise ValueError((family,'insufficient bound ground spawn points',len(ring)))
 chosen=[]
 for j in range(count):
  angle=math.tau*(j/count+phase);radius=radii[j%len(radii)]
  target=(center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle))
  available=[p for p in ring if all(distance2(p.position,q.position)>=spacing**2 for q in chosen)]
  if not available:raise ValueError((family,'insufficient separated ground spawn points',j))
  chosen.append(min(available,key=lambda p:(distance2(p.position,target),p.index)))
 return chosen

def main(root=None):
 root=Path(root) if root is not None else ROOT
 scenario_dir=root/'native-tags/levels/survivors/last_stand'
 source=b.TagFile.read(scenario_dir/'outdoor-compiled.scenario');src=source.root()
 tag=b.TagFile.read(scenario_dir/'outdoor-compiled.scenario');r=tag.root()
 assert source.write_to_bytes()==(scenario_dir/'outdoor-compiled.scenario').read_bytes()
 written=list(author_watchtower(r,root))
 disabled_occluders=disable_arena_occluders(r)
 for n in ['scripts','globals','source files','hs syntax datums','references','cutscene camera points','cutscene flags','trigger volumes','squads','ai objectives','squad groups']:B(r,n).clear()
 names=B(r,'object names');remove=[]
 for i in range(len(names)):
  q=names[i]
  if q.field('name').value.startswith('sv_marker_'):
   remove.append(q.field('scenario_datum_index').value);put(q,'scenario_datum_index',-1)
 for index in sorted(set(remove),reverse=True):
  B(r,'scenery').delete(index)
  for i in range(len(B(r,'object names'))):
   q=B(r,'object names')[i]
   if q.field('object_type').value==6 and q.field('scenario_datum_index').value>index:put(q,'scenario_datum_index',q.field('scenario_datum_index').value-1)
 group=B(r,'squad groups');i=group.add()
 for k,v in {'name':'sv_hostiles','parent':-1,'initial objective':-1}.items():put(group[i],k,v)
 paths={'infection':r'objects\characters\flood_infection\ai\flood_infection','carrier':r'objects\characters\flood_carrier\ai\flood_carrier'}
 manifest=root/'private-inputs/v3/character-paths.json'
 if manifest.exists():paths.update(json.loads(manifest.read_text()))
 written.extend(author_carrier(root))
 paths['carrier']=r'objects\survivors\v3\carrier'
 chars={'grunts':3,'jackals':4,'brutes':2,'captains':9,'snipers':13,'floodcombat':21,'hunters':19,'chieftain':11}
 for key in ['infection','carrier']:
  pal=B(r,'character palette');i=pal.add();put(pal[i],'reference',(0x63686172,paths[key]));chars[key]=i
 families=[('grunts',6,10,1,0,4),('jackals',4,20,1,30,4),('brutes',3,30,1,90,2),('captains',2,50,2,45,6),('snipers',2,35,2,90,17),('floodcombat',6,20,3,0,0),('infection',10,3,3,45,-1),('carrier',2,40,3,90,-1),('hunters',2,100,4,0,-1),('chieftain',1,150,4,120,10)]
 stages=[]
 for number,(zone_index,tx,ty) in enumerate([(0,101,364),(1,72,351),(2,35,365),(2,18,352)],1):
  zone=B(r,'zones')[zone_index];fps=B(zone,'firing positions')
  points=[(i,fps[i].field('position (local)').value,fps[i].field('area').value) for i in range(len(fps)) if fps[i].field('structure bsp').value==0]
  _,center,_=min(points,key=lambda v:(v[1].x-tx)**2+(v[1].y-ty)**2)
  floor=[v for v in points if d2(v[1],center)<=400 and abs(v[1].z-center.z)<=6]
  spawn_points=[SpawnPoint(i,tuple(xyz(p)),area,fps[i].field('structure bsp').value,
                fps[i].field('reference frame').value,fps[i].field('sector index').value)
                for i,p,area in floor]
  objective=f'sv_hunt_{number}'
  objs=B(r,'ai objectives');oi=addclone(objs,B(src,'ai objectives')[0]);obj=B(r,'ai objectives')[oi]
  for k,v in {'name':objective,'zone index':zone_index,'first task index':0}.items():put(obj,k,v)
  task=B(obj,'tasks')[0]
  for k,v in {'name':'surround','follow':'player','follow radius':1.5,'movement':'run'}.items():put(task,k,v)
  areas=B(task,'areas');areas.clear()
  area_indices=sorted({v[2] for v in floor if v[2]>=0},key=lambda ai:min(d2(v[1],center) for v in floor if v[2]==ai))[:32]
  for ai in area_indices:
   areas=B(B(B(r,'ai objectives')[oi],'tasks')[0],'areas');j=areas.add()
   for k,v in {'area type':'search','flags':[],'character flags':[],'zone':zone_index,'area':ai}.items():put(areas[j],k,v)
  def flag(name,p):
   q=B(r,'cutscene flags');j=q.add();put(q[j],'name',name);put(q[j],'position',b.RealPoint3d(p.x,p.y,p.z+.1));put(q[j],'facing',b.RealEulerAngles2d(0,0));put(q[j],'editor folder',-1)
  flag(f'sv_s{number}_center',center)
  cells={}
  for row in sorted(floor,key=lambda v:d2(v[1],center)):
   p=row[1];cells.setdefault((round(p.x/2.5),round(p.y/2.5)),row)
  candidates=list(cells.values());chosen=[min(candidates,key=lambda v:d2(v[1],center))];candidates.remove(chosen[0])
  while candidates and len(chosen)<72:
   row=max(candidates,key=lambda v:min(d2(v[1],a[1]) for a in chosen));chosen.append(row);candidates.remove(row)
  cams=[]
  for index,(_,p,_) in enumerate(chosen):
   name=f'sv_s{number}_view_{index}';q=B(r,'cutscene camera points');j=q.add()
   for k,v in {'name':name,'type':'normal','position':b.RealPoint3d(p.x,p.y,p.z+12),'orientation':b.RealEulerAngles3d(0,-math.pi/2,0)}.items():put(q[j],k,v)
   flag(name,p);cams.append({'name':name,'position':xyz(p),'camera_position':[p.x,p.y,p.z+12]})
  squads=[]
  for family,count,xp,unlock_stage,delay,weapon in families:
   if unlock_stage>number:continue
   sqs=B(r,'squads');si=addclone(sqs,B(src,'squads')[0]);sq=B(r,'squads')[si];name=f'sv_s{number}_{family}'
   for k,v in {'name':name,'flags':[],'team':'covenant','parent':0,'initial zone':zone_index,'initial objective':oi,'initial task':0,'editor folder':-1}.items():put(sq,k,v)
   ft=B(sq,'fire-teams')[0]
   for k,v in {'normal diff count':count,'character type':chars[family],'initial weapon':weapon,'initial secondary weapon':-1,'vehicle type':-1,'initial equipment':-1,'Placement script':'','placement script index':-1,'point set':-1,'activity':'none'}.items():put(ft,k,v)
   B(ft,'points').clear();loc=B(ft,'starting locations')
   while len(loc)<count:loc.duplicate(0)
   while len(loc)>count:loc.delete(len(loc)-1)
   phase=families.index((family,count,xp,unlock_stage,delay,weapon))/len(families)
   selected=select_spawn_points(spawn_points,tuple(xyz(center)),set(area_indices),family,count,phase)
   low,high,_,spacing=spawn_profile(family);locations=[];spawn_flags=[]
   for j,point in enumerate(selected):
    p=b.RealPoint3d(*point.position)
    row=loc[j]
    for k,v in {'name':f's{number}_{family}_{j}','position':b.RealPoint3d(p.x,p.y,p.z+.15),'reference frame':-1,'structure bsp':0,'flags':[],'character type':-1,'initial weapon':-1,'initial secondary weapon':-1,'vehicle type':-1,'initial equipment':-1,'Placement script':'','placement script index':-1,'point set':-1}.items():put(row,k,v)
    put(row,'facing (yaw, pitch)',b.RealEulerAngles2d(math.atan2(center.y-p.y,center.x-p.x),0))
    # A zero swarm count selects the engine default; require one infection
    # creature per placement so the HSC actor budget reflects actual bodies.
    put(row,'swarm count',1 if family=='infection' else 0)
    locations.append(xyz(p))
    spawn_flag=f'{name}_p{j}';flag(spawn_flag,p);spawn_flags.append(spawn_flag)
   squads.append({'name':name,'enemy':family,'count':count,'xp':xp,'unlock_seconds':delay,'character_palette_index':chars[family],'spawn_positions':locations,'spawn_flags':spawn_flags,'spawn_radius':[low,high],'minimum_spawn_spacing':spacing})
  stages.append({'number':number,'center':xyz(center),'zone':zone_index,'zone_name':zone.field('name').value,'objective':objective,'area_indices':area_indices,'cameras':cams,'squads':squads,'radius':20,'duration_seconds':300})
 start=stages[0]['center'];pl=B(r,'player starting locations')[0]
 put(pl,'position',b.RealPoint3d(start[0],start[1],start[2]+.2));put(pl,'bsp index',0);put(pl,'facing',0.0);put(pl,'pitch',0.0)
 flag('sv_heading',b.RealPoint3d(start[0]+1000,start[1],start[2]))
 tag.recompute_checksum();target=scenario_dir/'progression.scenario';tag.write(target)
 assert b.TagFile.read(target).write_to_bytes()==target.read_bytes()
 layout={'version':'0.3.0','base':'070_waste','bsp':0,'hostiles_group':'sv_hostiles','camera_height':12,'disabled_occluders':disabled_occluders,'stages':stages}
 (root/'progression-layout.json').write_text(json.dumps(layout,indent=2)+'\n')
 check=b.TagFile.read(target).root()
 assert len(B(check,'squads'))==26
 assert all(B(check,'squads')[i].field('parent').value==0 for i in range(26))
 assert all(len(s['cameras'])<=72 for s in stages)
 print('Authored',target.name,[(s['number'],len(s['cameras']),len(s['squads'])) for s in stages])
 return tuple(written+[target,root/'progression-layout.json'])

def author_carrier(root=None):
 """Keep carrier explosions but prevent unbudgeted native infection children."""
 root=Path(root) if root is not None else ROOT
 inputs=root/'private-inputs/v3';out=root/'native-tags/objects/survivors/v3'
 character=b.TagFile.read(inputs/'carrier.character')
 body=b.TagFile.read(inputs/'floodcarrier.biped')
 put(body.root(),'death spawn character',None)
 put(body.root(),'death spawn count',0)
 path=r'objects\survivors\v3\carrier'
 put(character.root(),'unit',(0x62697064,path))
 out.mkdir(parents=True,exist_ok=True)
 for tag,name in [(body,'carrier.biped'),(character,'carrier.character')]:
  dest=out/name;tag.recompute_checksum();tag.write(dest)
  assert b.TagFile.read(dest).write_to_bytes()==dest.read_bytes()
 print('Authored carrier without automatic death children; normal explosion retained.')
 return (out/'carrier.biped',out/'carrier.character')

def disable_arena_occluders(scenario):
 """Omit the campaign AA-gun stand that covers the stage 3/4 overhead view."""
 path=r'objects\levels\shared\bfg_stand\bfg_stand'
 palette=B(scenario,'scenery palette');indices=set()
 for i in range(len(palette)):
  if palette[i].field('name').value==(0x7363656e,path):indices.add(i)
 changed=[];placed=B(scenario,'scenery')
 for i in range(len(placed)):
  row=placed[i]
  if row.field('type').value not in indices:continue
  data=row.field('object data').as_struct();p=data.field('position').value
  if any((p.x-x)**2+(p.y-y)**2<=25**2 for x,y in [(35,365),(18,352)]):
   data.field('placement flags').set_flag('not automatically',True)
   changed.append({'block':'scenery','index':i,'path':path,'position':xyz(p)})
 assert len(changed)==1,'Expected one campaign BFG stand occluding the arenas'
 print('Disabled automatic campaign occluder:',changed)
 return changed

def author_watchtower(scenario,root=None):
 """Fix the private watchtower light without changing stock tags or collision."""
 root=Path(root) if root is not None else ROOT
 inputs=root/'private-inputs/v3';out=root/'native-tags/objects/survivors/v3'
 light=b.TagFile.read(inputs/'watchtower_gravlift.light')
 machine=b.TagFile.read(inputs/'watchtower_base.device_machine')
 obj=machine.root().field('device').as_struct().field('object').as_struct()
 functions=B(obj,'functions')
 assert any(functions[i].field('export name').value=='gravlift' for i in range(len(functions)))
 put(light.root().field('intensity').as_struct(),'Input Variable','gravlift')
 original=r'objects\gear\covenant\military\cov_watchtower\fx\gravlift\gravlift'
 private_light=r'objects\survivors\v3\watchtower_gravlift'
 private_machine=r'objects\survivors\v3\watchtower_base'
 attachments=B(obj,'attachments');changed=0
 for i in range(len(attachments)):
  if attachments[i].field('type').value==(0x6c696768,original):
   put(attachments[i],'type',(0x6c696768,private_light));changed+=1
 assert changed==1,'Expected one stock watchtower light attachment'
 original_machine=r'objects\gear\covenant\military\cov_watchtower\cov_watchtower_base\cov_watchtower_base'
 palette=B(scenario,'machine palette');changed=0
 for i in range(len(palette)):
  if palette[i].field('name').value==(0x6d616368,original_machine):
   put(palette[i],'name',(0x6d616368,private_machine));changed+=1
 assert changed==1,'Expected one stock watchtower machine palette reference'
 out.mkdir(parents=True,exist_ok=True)
 for tag,name in [(light,'watchtower_gravlift.light'),(machine,'watchtower_base.device_machine')]:
  path=out/name;tag.recompute_checksum();tag.write(path)
  assert b.TagFile.read(path).write_to_bytes()==path.read_bytes()
 print('Authored private watchtower gravlift light; collision and placements retained.')
 return (out/'watchtower_gravlift.light',out/'watchtower_base.device_machine')

def cosmetic_impact(tag):
 """Attach impacts at the target root; retain only visual/audio effect parts.

 HSC owns every damage application. Nested effects and object/projectile parts
 could introduce extra damage, so reject them by using a cosmetic allowlist.
 Stock particle references are audited separately against the owned inputs.
 """
 root=tag.root();removed=[]
 allowed={int.from_bytes(x,'big') for x in (b'decs',b'ligh',b'snd!',b'lsnd',b'sefc')}
 events=B(root,'events')
 for ei in range(len(events)):
  parts=B(events[ei],'parts')
  for pi in reversed(range(len(parts))):
   ref=parts[pi].field('type').value
   if ref and ref[0] not in allowed:
    removed.append({'event':ei,'part':pi,'reference':ref[1],'group':ref[0]})
    parts.delete(pi)
 locations=B(root,'locations')
 for i in range(len(locations)):put(locations[i],'marker name','root')
 assert all(locations[i].field('marker name').value=='root' for i in range(len(locations)))
 for ei in range(len(B(root,'events'))):
  parts=B(B(root,'events')[ei],'parts')
  assert all(not parts[i].field('type').value or parts[i].field('type').value[0] in allowed for i in range(len(parts)))
 return removed

def author_damage(root=None):
 root=Path(root) if root is not None else ROOT
 contract=json.loads((root/'progression-contract.json').read_text());values=contract['damage_values']
 inputs=root/'private-inputs/v3';out=root/'native-tags/objects/survivors/v3'
 missing=[str(inputs/(key+'.damage_effect')) for key in values if not (inputs/(key+'.damage_effect')).exists()]
 if missing:raise FileNotFoundError('Missing owned native damage inputs: '+', '.join(missing))
 out.mkdir(parents=True,exist_ok=True);written=[]
 for key,amounts in values.items():
  for amount in amounts:
   assert int(amount)==amount and amount>0
   tag=b.TagFile.read(inputs/(key+'.damage_effect'));r=tag.root()
   put(r,'damage lower bound',float(amount));put(r,'damage upper bound',b.RealBounds(float(amount),float(amount)))
   put(r,'radius',b.RealBounds(0.0,0.0));put(r,'AOE core radius',0.0)
   dest=out/f'{key}_d{int(amount)}.damage_effect';tag.recompute_checksum();tag.write(dest)
   assert b.TagFile.read(dest).write_to_bytes()==dest.read_bytes();written.append(dest)
  ep=inputs/(key+'.effect')
  if ep.exists():
   tag=b.TagFile.read(ep);removed=cosmetic_impact(tag)
   if removed:print('Removed gameplay effect parts from',key,removed)
   dest=out/f'impact_{key}.effect';tag.recompute_checksum();tag.write(dest)
   assert b.TagFile.read(dest).write_to_bytes()==dest.read_bytes();written.append(dest)
 print('Authored private native v3 damage/effects:',len(written))
 return tuple(written)
if __name__=='__main__':main()
