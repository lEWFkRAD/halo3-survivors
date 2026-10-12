from pathlib import Path
import blam_tags as b
from generate import TITLES
root=Path(__file__).resolve().parent
tag=b.TagFile.read(root/'native-tags/levels/survivors/last_stand/compiled.scenario'); r=tag.root()
def block(s,n):return s.field(n).as_block()
def put(s,n,v):s.field(n).set(v)
t=block(block(r,'ai objectives')[0],'tasks')[0]
put(t,'follow','player');put(t,'follow radius',1.5)
# Keep authored floor points, make distinct beacons beside the purchase volumes.
markers=[('needler',(-27.67,3.21,-6.95),r'objects\levels\dlc\spacecamp\flag_waver_blue\flag_waver_blue'),
 ('aegis',(-26.76,4.55,-6.95),r'objects\levels\dlc\spacecamp\flag_waver_red\flag_waver_red'),
 ('vitality',(-25.38,1.06,-6.95),r'objects\levels\dlc\warehouse\security_yellow_light\security_yellow_light'),
 ('exit',(-36.07,-1.96,-6.95),r'objects\levels\multi\shrine\marinebeacon\marinebeacon')]
flags=block(r,'cutscene flags');pal=block(r,'scenery palette');sc=block(r,'scenery');names=block(r,'object names')
for num,(name,xyz,path) in enumerate(markers):
 j=flags.add();f=flags[j];put(f,'name','sv_beacon_'+name);put(f,'position',b.RealPoint3d(*xyz));put(f,'editor folder',-1)
 pi=pal.add();put(pal[pi],'name',(0x7363656e,path))
 si=sc.duplicate(0);sc.move_element(si,len(sc)-1);si=len(sc)-1
 ni=names.add();put(names[ni],'name','sv_marker_'+name);put(names[ni],'object_type',6);put(names[ni],'scenario_datum_index',si)
 st=sc[si];put(st,'type',pi);put(st,'name',ni);d=st.field('object data').as_struct()
 for flag in d.field('placement flags').value:d.field('placement flags').set_flag(flag,False)
 put(d,'position',b.RealPoint3d(xyz[0]+.25,xyz[1]+.25,xyz[2]+.15));put(d,'scale',0.65 if name in ('needler','aegis') else 1.0)
 put(d,'rotation',b.RealEulerAngles3d(0,0,0));put(d,'manual bsp flags',4)
 oid=d.field('object id').as_struct();put(oid,'unique id',1945000000+num);put(oid,'origin bsp index',2)
# Standard chapter title bounds; CHUD objectives are retained as the gameplay display.
for i in range(len(block(r,'cutscene titles'))):
 ct=block(r,'cutscene titles')[i];put(ct,'text bounds (on screen)',b.Rectangle2d(80,40,150,600));put(ct,'justification','center')
strings=b.TagFile.read(root/'native-tags/ui/survivors/last_stand.multilingual_unicode_string_list');sr=strings.root();refs=block(sr,'string references');refs.clear();data=bytearray()
for name,text in TITLES.items():
 j=refs.add();put(refs[j],'string id',name)
 for field in refs[j].field_names():
  if field.endswith(' offset'):put(refs[j],field,len(data))
 data.extend(text.encode()+b'\0')
put(sr,'string data utf8',bytes(data));strings.recompute_checksum();strings.write(root/'native-tags/ui/survivors/last_stand.multilingual_unicode_string_list')
tag.recompute_checksum();tag.write(root/'native-tags/levels/survivors/last_stand/last_stand.scenario')
print('Updated pursuit, four visible beacons, title layout and strings.')
