"""Create a readable contact sheet of the captured native assertions."""
from pathlib import Path
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent/'qa-v04'
files=sorted(root.glob('qa-check-*.png'))
rows=min(15,len(files));cols=(len(files)+rows-1)//rows
out=Image.new('RGB',(820*cols,85*rows),(30,30,30));draw=ImageDraw.Draw(out)
for i,p in enumerate(files):
    x=(i//rows)*820;y=(i%rows)*85
    draw.text((x+5,y+25),p.stem.removeprefix('qa-check-'),fill='white')
    out.paste(Image.open(p),(x+270,y))
out.save(root/'assertions.png')
print('Captured assertions:',len(files))
