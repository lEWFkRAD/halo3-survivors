from pathlib import Path
import subprocess,shlex,json
import blam_tags as b
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'private-inputs/v3';OUT.mkdir(parents=True,exist_ok=True)
SSH=r'C:\Windows\System32\OpenSSH\ssh.exe';SCP=r'C:\Windows\System32\OpenSSH\scp.exe'
KIT='/home/jeffrey-watts/snap/steam/common/.local/share/Steam/steamapps/common/H3EK/tags/'
def fetch(remote,name):
 subprocess.run([SCP,'onyx-linux:'+KIT+remote,str(OUT/name)],check=True)
paths={
 'needler':'objects/weapons/pistol/needler/damage_effects/needler_shard_impact.damage_effect',
 'assault_rifle':'objects/weapons/rifle/assault_rifle/damage_effects/assault_rifle_bullet.damage_effect',
 'shotgun':'objects/weapons/rifle/shotgun/damage_effects/shotgun_bullet.damage_effect',
 'plasma_rifle':'objects/weapons/rifle/plasma_rifle/damage_effects/plasma_rifle_bolt.damage_effect',
 'rocket_launcher':'objects/weapons/support_high/rocket_launcher/damage_effects/rocket_launcher_explosion.damage_effect'}
fetch('objects/weapons/melee/energy_blade/energy_blade.weapon','energy_blade.weapon')
refs=[]
def walk(s):
 for name in s.field_names():
  f=s.field(name)
  if f.type_name=='block':
   q=f.as_block()
   for i in range(len(q)):walk(q[i])
  elif f.type_name=='struct':walk(f.as_struct())
  elif 'reference' in f.type_name and isinstance(f.value,tuple) and f.value[0]==0x6a707421:refs.append((name,f.value[1]))
walk(b.TagFile.read(OUT/'energy_blade.weapon').root())
print('Sword damage references',refs)
normal=[p for n,p in refs if 'melee' in n.lower() and 'response' not in n.lower()]
if not normal:normal=[p for n,p in refs if p]
assert normal,'No native sword damage reference'
paths['energy_sword']=normal[0].replace('\\','/')+'.damage_effect'
for key,path in paths.items():fetch(path,key+'.damage_effect')
effects={'needler':'objects/weapons/pistol/needler/fx/impact.effect','assault_rifle':'objects/weapons/rifle/battle_rifle/fx/impact.effect','shotgun':'objects/weapons/rifle/shotgun/fx/impact.effect','plasma_rifle':'objects/weapons/rifle/plasma_rifle/fx/impact.effect','energy_sword':'objects/weapons/melee/energy_blade/fx/impact.effect','rocket_launcher':'objects/weapons/support_high/rocket_launcher/fx/detonation.effect'}
for key,path in effects.items():fetch(path,key+'.effect')
# Private copies fix the stock light's nonexistent literal function name "0".
# Keeping the complete machine preserves its collision and its placed geometry.
support={'watchtower_base':'objects/gear/covenant/military/cov_watchtower/cov_watchtower_base/cov_watchtower_base.device_machine',
         'watchtower_gravlift':'objects/gear/covenant/military/cov_watchtower/fx/gravlift/gravlift.light',
         'floodcarrier':'objects/characters/floodcarrier/floodcarrier.biped'}
for key,path in support.items():fetch(path,key+Path(path).suffix)
# Confirm stock characters exist before authoring references.
characters={'infection':'objects/characters/flood_infection/ai/flood_infection','carrier':'objects/characters/floodcarrier/ai/flood_carrier'}
for key,path in characters.items():fetch(path+'.character',key+'.character')
(OUT/'character-paths.json').write_text(json.dumps({k:v.replace('/','\\') for k,v in characters.items()},indent=2))
(OUT/'sources.json').write_text(json.dumps({'damage':paths,'effects':effects,'characters':characters,'support':support},indent=2))
print('Fetched owned progression inputs.')
