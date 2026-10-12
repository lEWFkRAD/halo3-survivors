from pathlib import Path
from PIL import Image,ImageDraw
import sys
root=Path(__file__).resolve().parent
group=sys.argv[1]
menus={'initial_menu','held_next_once','held_purchase_once','category','unlock_ar','previous','resume','reopen'}
files=[]
for p in sorted(root.glob('qa-check-*.png')):
 name=p.stem.removeprefix('qa-check-')
 if (group=='menu' and name in menus) or (group=='stages' and ('stage' in name or 'enemy' in name or name.startswith('auto_'))) or (group=='weapons' and name.startswith('weapon_')) or (group=='ending' and name=='ending'):files.append(p)
rows=min(12,len(files));cols=(len(files)+rows-1)//rows
out=Image.new('RGB',(800*cols,90*rows),(30,30,30));d=ImageDraw.Draw(out)
for i,p in enumerate(files):
 x=(i//rows)*800;y=(i%rows)*90
 d.text((x+8,y+30),p.stem.removeprefix('qa-check-'),fill='white');out.paste(Image.open(p),(x+245,y))
out.save(root/('qa-results-'+group+'.png'))
print(group,len(files))
