"""Record a clean native run using ordinary Armory and movement inputs only."""
from pathlib import Path
import subprocess,sys,time
sys.path.insert(0,str(Path.home()/'Documents/Games/Halo3Survivors'))
import remote_build as r
w=r.window('Halo3')
g=dict(line.split('=',1) for line in subprocess.check_output(
    ['xdotool','getwindowgeometry','--shell',w],text=True).splitlines() if '=' in line)
x,y,width,height=[int(g[k]) for k in ('X','Y','WIDTH','HEIGHT')]
output=r.ROOT/'Last-Stand-Halo-3-v04-Gameplay.mp4'
assert not output.exists(),'Preserve earlier clips.'
with (r.ROOT/'record-v04.log').open('w') as log:
    capture=subprocess.Popen(['ffmpeg','-nostdin','-f','x11grab','-framerate','30',
        '-video_size',f'{width}x{height}','-i',f':0.0+{x},{y}','-t','38',
        '-vf','scale=1280:-2','-c:v','libx264','-preset','fast','-crf','20',
        '-pix_fmt','yuv420p','-movflags','+faststart',str(output)],stdout=log,stderr=subprocess.STDOUT)
    def buy():
        subprocess.run(['xdotool','mousemove',str(x+width//2),str(y+height//2)],check=True)
        subprocess.run(['xdotool','mousedown','1'],check=True);time.sleep(.25)
        subprocess.run(['xdotool','mouseup','1'],check=True);time.sleep(.5)
    time.sleep(1);r.key('space');buy();r.key('space','q');buy();r.key('1')
    for key in ('d','a','w','s'):
        time.sleep(2)
        subprocess.run(['xdotool','keydown',key],check=True);time.sleep(1.2)
        subprocess.run(['xdotool','keyup',key],check=True)
        time.sleep(2);r.key('1')
    code=capture.wait(timeout=50)
assert code==0,code
# Leave the ordinary run in its Armory; this produces a real playable checkpoint.
r.key('space','q');time.sleep(3)
r.capture('v04-gameplay-armory')
print(output,output.stat().st_size,flush=True)
