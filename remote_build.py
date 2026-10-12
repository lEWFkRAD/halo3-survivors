from pathlib import Path
import os, subprocess, time, shlex, signal, shutil, sys
ROOT=Path.home()/'Documents/Games/Halo3Survivors'
STEAM=Path.home()/'snap/steam/common/.local/share/Steam'
KIT=STEAM/'steamapps/common/H3EK'
os.environ.update(DISPLAY=':0',XAUTHORITY='/run/user/1000/gdm/Xauthority')
BASE=['env','WINEPREFIX='+str(ROOT/'tool-prefix/pfx'),'DISPLAY=:0','XAUTHORITY=/run/user/1000/gdm/Xauthority','WINEDEBUG=-all','WINEDLLOVERRIDES=d3dcompiler_47=n,b',str(STEAM/'steamapps/common/Proton - Experimental/files/bin/wine')]
def launch(exe,args):
 f=open(ROOT/(exe+'-current.log'),'w');p=subprocess.Popen(['snap','run','--shell','steam','-c','cd '+shlex.quote(str(KIT))+' && '+shlex.join(BASE+[str(KIT/exe)]+args)],stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print(exe,p.pid,flush=True)
def stop(exe):
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   try:
    cmd=(p/'cmdline').read_bytes().split(b'\0')[0].decode(errors='replace');env=(p/'environ').read_bytes()
    if cmd.replace('\\','/').endswith('/'+exe) and b'Halo3Survivors/tool-prefix/pfx' in env:
     print('stopping',p.name,exe,flush=True);os.kill(int(p.name),signal.SIGTERM)
   except (FileNotFoundError,PermissionError,ProcessLookupError):pass
 time.sleep(2)
def window(name):
 w=subprocess.check_output(['xdotool','search','--name','^'+name+'$'],text=True).splitlines()[-1];subprocess.run(['xdotool','windowactivate','--sync',w]);time.sleep(.5);return w
def key(*keys):
 subprocess.run(['xdotool','keydown',*keys]);time.sleep(.15);subprocess.run(['xdotool','keyup',*reversed(keys)]);time.sleep(.35)
def capture(name):
 from PIL import ImageGrab
 try:
  w=subprocess.check_output(['xdotool','search','--name','^Halo3$'],text=True).splitlines()[-1]
  values=dict(line.split('=',1) for line in subprocess.check_output(['xdotool','getwindowgeometry','--shell',w],text=True).splitlines() if '=' in line)
  x,y,width,height=[int(values[k]) for k in ['X','Y','WIDTH','HEIGHT']]
  ImageGrab.grab(bbox=(x,y,x+width,y+height)).save(ROOT/(name+'.png'))
 except subprocess.CalledProcessError:
  ImageGrab.grab().save(ROOT/(name+'.png'))
def console(cmd):
 subprocess.run(['xdotool','type','--clearmodifiers','--delay','12',cmd]);key('Return');time.sleep(.8)
a=sys.argv[1]
if a=='compile':
 from datetime import datetime
 compile_started=datetime.now()
 stop('halo3_tag_test.exe');stop('sapien.exe')
 shutil.copy2(ROOT/'candidate.scenario',KIT/'tags/levels/survivors/last_stand/last_stand.scenario')
 shutil.copy2(ROOT/'last_stand.hsc',KIT/'data/levels/survivors/last_stand/scripts/last_stand.hsc')
 launch('sapien.exe',['Z:'+str(KIT/'tags/levels/survivors/last_stand/last_stand.scenario').replace('/','\\')]);time.sleep(30)
 window('H3 Sapien');key('ctrl','shift','c');time.sleep(3);key('ctrl','s');capture('compile-current')
 fatal=[]
 for p in (KIT/'reports').glob('*/debug_full.txt'):
  lines=p.read_text(errors='replace').splitlines()
  for v in lines:
   if '-FATAL- design:hs' in v:
    try:
     if datetime.strptime(v[:21],'%m.%d.%y %H:%M:%S.%f')>=compile_started: fatal.append(v)
    except ValueError: pass
 print('HSC_FATALS',fatal,flush=True)
 if fatal: raise SystemExit(2)
elif a=='play':
 stop('halo3_tag_test.exe');launch('halo3_tag_test.exe',['-window','1280','720']);time.sleep(32);print('window',window('Halo3'));capture('play-current');key('grave')
elif a=='console':
 window('Halo3')
 for cmd in sys.argv[2:]: console(cmd)
 capture('console-current')
elif a=='show':
 window('Halo3');key('grave');time.sleep(float(sys.argv[2]));capture('play-current');key('grave')
elif a=='cache':
 stop('halo3_tag_test.exe');stop('sapien.exe');launch('tool.exe',['build-cache-file',r'levels\survivors\last_stand\last_stand','pc','none','english'])

elif a=='movement':
 window('Halo3')
 console('(set cheat_deathless_player true)')
 console('(inspect sv_seconds)');console('(inspect sv_shots)');console('(inspect sv_xp)');capture('qa-before')
 key('grave');subprocess.run(['xdotool','keydown','w']);time.sleep(1);subprocess.run(['xdotool','keyup','w']);time.sleep(5)
 capture('qa-moved');key('grave');console('(inspect sv_seconds)');console('(inspect sv_shots)');console('(inspect sv_xp)');capture('qa-after')

elif a=='camera_probe':
 window('Halo3');console('(set cheat_deathless_player true)')
 for typ in range(4):
  for sign in ['p','n']:
   name='sv_cam_'+str(typ)+'_'+sign
   console('(camera_set_relative '+name+' 0 (sv_player))');key('grave');time.sleep(.6);capture(name);key('grave')
   console('(debug_camera_save_name "'+name+'")');print(name,(KIT/(name+'_last_stand.txt')).read_text().replace('\n',' | '),flush=True)
 console('cls');console('(inspect sv_shots)');console('(inspect sv_xp)');capture('autofire-counters')
