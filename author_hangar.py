"""Author a private Halo 3 campaign scenario from the user's extracted H3EK tags."""
from pathlib import Path
import json
import blam_tags as bt
from generate import SQUADS,TITLES
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'native-tags'
BASE=ROOT/'private-inputs/tags/levels/solo/020_base/020_base.scenario'

def block(s,n): return s.field(n).as_block()
def put(s,n,v):
    f=s.field(n)
    if f is None: raise KeyError(n)
    if isinstance(v,list) and 'flags' in f.type_name:
        for flag in f.value: f.set_flag(flag,False)
        for flag in v: f.set_flag(flag,True)
    else: f.set(v)
def append_copy(b,i):
    j=b.duplicate(i); b.move_element(j,len(b)-1); return len(b)-1

def write(tag,path):
    p=OUT/path; p.parent.mkdir(parents=True,exist_ok=True)
    tag.recompute_checksum(); tag.write(p)
    assert bt.TagFile.read(p).write_to_bytes()==p.read_bytes(), str(p)
    print('WROTE',path,p.stat().st_size)

# Fail before editing if the native parser does not exactly preserve the source.
base_bytes=BASE.read_bytes(); tag=bt.TagFile.read(BASE)
assert tag.write_to_bytes()==base_bytes
r=tag.root()
# Retain stock geometry, pathfinding, lighting and navigation area identities.
# Give the first zone set the existing hangar BSP/PVS, remove its debug-only flag.
z=block(r,'zone sets'); z.swap(0,16)
put(z[0],'name','sv_hangar'); put(z[0],'flags',[])
put(z[0],'hint previous zone set',-1)
for name in ['scripts','globals','source files','hs syntax datums','references','scenario resources',
             'zone set switch trigger volumes','scenario kill triggers','scenario safe zone triggers',
             'bipeds','vehicles','giants','cinematics','mission scenes','hs unit seats']:
    block(r,name).clear()
# One pursuit objective using the original hangar navigation areas.
objs=block(r,'ai objectives'); old=len(objs); append_copy(objs,1)
for _ in range(old): objs.delete(0)
put(objs[0],'name','sv_hunt'); put(objs[0],'zone index',0);put(objs[0],'first task index',0)
tasks=block(objs[0],'tasks'); old=len(tasks);append_copy(tasks,1)
for _ in range(old):tasks.delete(0)
t=tasks[0]
for k,v in {'name':'surround','flags':[],'inhibit groups':[],'inhibit on difficulty':[],
            'Entry Script':'','Command Script':'','Exhaustion Script':'','Script index':-1,
            'Command script index':-1,'Exhaustion script index':-1,'Squad group filter':-1,
            'first_child':-1,'next_sibling':-1,'parent':-1,'script index ':-1,
            'lifetime count':0,'filter flags':[],'filter':'none','max body count':0,
            'min strength':0.0,'capacity':bt.ShortBounds(0,0)}.items(): put(t,k,v)
block(t,'activation script').clear()
a=block(t,'areas'); a.clear()
# Halo 3 permits at most 32 area references per task.
for i in sorted({round(j*68/31) for j in range(32)}):
    j=a.add(); row=a[j]
    for k,v in {'area type':'search','flags':[],'character flags':[],'zone':0,'area':i}.items():put(row,k,v)
# Add the Flood character from the official kit; other types already exist in this palette.
cp=block(r,'character palette'); fi=cp.add()
put(cp[fi],'reference',(0x63686172,r'objects\characters\floodcombat_human\ai\flood_combat_human'))
# Duplicate authored spawn groups; keep their valid BSP-2 locations.
sq=block(r,'squads'); old=len(sq)
for index,((name,count,_,_),template,char,weapon) in enumerate(zip(SQUADS,[3,4,5,6,2,3,5,6],[3,3,3,3,4,2,fi,19],[4,4,4,4,4,2,0,-1])):
    i=append_copy(sq,template); s=sq[i]
    for k,v in {'name':name,'flags':[],'team':'covenant','parent':-1,'initial zone':0,
                'initial objective':0,'initial task':0,'editor folder':-1}.items():put(s,k,v)
    ft=block(s,'fire-teams')
    while len(ft)>1:ft.delete(len(ft)-1)
    f=ft[0]
    for k,v in {'normal diff count':count,'character type':char,'initial weapon':weapon,
                'initial secondary weapon':-1,'vehicle type':-1,'initial equipment':-1,
                'Placement script':'','placement script index':-1,'point set':-1,'activity':'none'}.items():put(f,k,v)
    block(f,'points').clear()
    loc=block(f,'starting locations')
    while len(loc)<count: append_copy(loc,len(loc)-1)
    while len(loc)>count:loc.delete(len(loc)-1)
    for j in range(len(loc)):
        for k,v in {'name':f'sv_spawn_{index}_{j}','character type':-1,'initial weapon':-1,
                    'initial secondary weapon':-1,'vehicle type':-1,'initial equipment':-1,
                    'Placement script':'','placement script index':-1,'point set':-1,'flags':[]}.items():put(loc[j],k,v)
for _ in range(old):sq.delete(0)
# Player starts on an existing upper-floor AI ground point, with one solo spawn.
pl=block(r,'player starting locations')
while len(pl)>1:pl.delete(len(pl)-1)
put(pl[0],'position',bt.RealPoint3d(-26.57,2.065,-6.65));put(pl[0],'facing',0.0)
put(pl[0],'pitch',0.0);put(pl[0],'bsp index',2);put(pl[0],'campaign player type','masterchief')
profiles=block(r,'player starting profile'); profiles.clear()
for i,name in enumerate(['sv_start','sv_needler_1','sv_needler_2','sv_needler_3']):
    n=profiles.add(); p=profiles[n]
    for k,v in {'name':name,'starting health damage':0.0,'starting shield damage':0.0,
                'primary weapon':(0x77656170,r'objects\weapons\rifle\assault_rifle\assault_rifle' if i==0 else rf'objects\survivors\needler_{i}'),
                'primaryrounds loaded':32 if i==0 else 19,'primaryrounds total':320 if i==0 else [0,180,240,360][i],
                'secondary weapon':None if i==0 else (0x77656170,r'objects\weapons\rifle\assault_rifle\assault_rifle'),
                'secondaryrounds loaded':0 if i==0 else 32,'secondaryrounds total':0 if i==0 else 320,
                'starting fragmentation grenade count':2,'starting plasma grenade count':0,
                'starting claymore grenade count':0,'starting firebomb grenade count':0,'editor folder':-1}.items():put(p,k,v)
# These coordinates are stock floor/firing positions. Visual pad markers still need game QA.
vols=block(r,'trigger volumes');old=len(vols)
locations=[('sv_pad_needler',(-27.67,3.21,-6.95)),('sv_pad_aegis',(-26.76,4.55,-6.95)),
           ('sv_pad_vitality',(-25.38,1.06,-6.95)),('sv_extraction',(-36.07,-1.96,-6.95))]
for name,xyz in locations:
    j=append_copy(vols,0);v=vols[j]
    for k,val in {'name':name,'object name':-1,'runtime node index':-1,'node name':'',
                  'forward':bt.RealVector3d(1,0,0),'up':bt.RealVector3d(0,0,1),
                  'position':bt.RealPoint3d(*xyz),'extents':bt.RealPoint3d(.65,.65,1.5),
                  'kill trigger volume':-1,'editor folder':-1}.items():put(v,k,val)
for _ in range(old):vols.delete(0)
# Title definitions and real localized string data, using English fallback for every language.
ct=block(r,'cutscene titles');old=len(ct)
for name in TITLES:
    j=append_copy(ct,0);put(ct[j],'name',name);put(ct[j],'up time [seconds]',5.0)
for _ in range(old):ct.delete(0)
put(r,'chapter title text',(0x756e6963,r'ui\survivors\last_stand'))
strings=bt.TagFile.read(ROOT/'private-inputs/titles.multilingual_unicode_string_list')
sr=strings.root();refs=block(sr,'string references');refs.clear();data=bytearray()
for name,text in TITLES.items():
    j=refs.add();put(refs[j],'string id',name)
    for field in refs[j].field_names():
        if field.endswith(' offset'):put(refs[j],field,len(data))
    data.extend(text.encode('utf-8')+b'\0')
put(sr,'string data utf8',bytes(data))
write(strings,Path('ui/survivors/last_stand.multilingual_unicode_string_list'))
for i,reserve in enumerate([180,240,360],1):
    w=bt.TagFile.read(ROOT/'private-inputs/needler.weapon');wr=w.root()
    put(block(wr,'barrels')[0],'projectiles per shot',i)
    for field in ['rounds total initial','rounds total maximum']:put(block(wr,'magazines')[0],field,reserve)
    write(w,Path(f'objects/survivors/needler_{i}.weapon'))
write(tag,Path('levels/survivors/last_stand/last_stand.scenario'))
print('Authored native tags. Script compilation and actual gameplay remain required.')



