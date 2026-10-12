"""Record ordinary native gameplay after a clean launch at the initial Armory."""
from pathlib import Path
import subprocess, sys, time
sys.path.insert(0, str(Path.home()/'Documents/Games/Halo3Survivors'))
import remote_build as r

window = r.window('Halo3')
geometry = dict(line.split('=',1) for line in subprocess.check_output(
    ['xdotool','getwindowgeometry','--shell',window],text=True).splitlines() if '=' in line)
x,y,w,h = [int(geometry[name]) for name in ['X','Y','WIDTH','HEIGHT']]
output = r.ROOT/'Last-Stand-Halo-3-v03-Gameplay.mp4'
assert not output.exists(), 'Preserve the existing clip; choose a new filename.'
log = (r.ROOT/'record-v03.log').open('w')
capture = subprocess.Popen(['ffmpeg','-nostdin','-f','x11grab','-framerate','30',
    '-video_size',f'{w}x{h}','-i',f':0.0+{x},{y}','-t','22','-vf','scale=1280:-2',
    '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
    '-movflags','+faststart',str(output)],stdout=log,stderr=subprocess.STDOUT)
time.sleep(2)
r.key('space')
subprocess.run(['xdotool','mousemove',str(x+w//2),str(y+h//2)],check=True)
subprocess.run(['xdotool','click','1'],check=True);time.sleep(.5)
r.key('space','q')
subprocess.run(['xdotool','click','1'],check=True);time.sleep(.5)
r.key('1')
time.sleep(3)
for direction in ['d','a']:
    subprocess.run(['xdotool','keydown',direction],check=True)
    time.sleep(1.5)
    subprocess.run(['xdotool','keyup',direction],check=True)
time.sleep(2)
r.key('1')
code=capture.wait(timeout=40);log.close()
assert code==0, f'ffmpeg exited {code}'
print(output,output.stat().st_size,flush=True)
