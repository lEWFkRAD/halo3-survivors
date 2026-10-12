"""Synchronize and inspect only the private Last Stand workspace on Onyx."""
from pathlib import Path
import subprocess,shlex,sys
ROOT=Path(__file__).resolve().parent
REMOTE='/home/jeffrey-watts/Documents/Games/Halo3Survivors/'
KIT='/home/jeffrey-watts/snap/steam/common/.local/share/Steam/steamapps/common/H3EK/'
SSH=r'C:\Windows\System32\OpenSSH\ssh.exe';SCP=r'C:\Windows\System32\OpenSSH\scp.exe'
def run(args):return subprocess.run(args,check=True)
def remote(action,*args):run([SSH,'onyx-linux',shlex.join(['python3',REMOTE+'progression_remote.py',action,*args])])
def put(paths,dest=REMOTE):run([SCP,*[str(ROOT/p) for p in paths],'onyx-linux:'+dest])
def get(src,dest):run([SCP,'onyx-linux:'+src,str(ROOT/dest)])
a=sys.argv[1]
if a=='stage':
 put(['progression_remote.py','v3-native.tar','source/progression.hsc'])
 put(['native-tags/levels/survivors/last_stand/progression-ui.scenario'],REMOTE+'v3-candidate.scenario')
 remote('v3-stage')
elif a=='compile':
 remote('v3-compile')
 get(KIT+'tags/levels/survivors/last_stand/last_stand.scenario','native-tags/levels/survivors/last_stand/progression-compiled.scenario')
 import blam_tags as b
 t=b.TagFile.read(ROOT/'native-tags/levels/survivors/last_stand/progression-compiled.scenario');r=t.root()
 for field in ['scripts','globals','source files','hs syntax datums','cutscene titles']:print(field,len(r.field(field).as_block()))
 names={r.field('scripts').as_block()[i].field('name').value for i in range(len(r.field('scripts').as_block()))}
 assert {'sv_boot','sv_step','sv_purchase','sv_open_menu','sv_advance_stage','sv_autofire'}<=names
 print('Native compiled candidate read back and key scripts verified.')
elif a=='capture':
 remote('v3-capture')
 get(REMOTE+'v3-desktop.png','v3-desktop.png');get(REMOTE+'v3-current.png','v3-current.png')
elif a in ('console','console-open','key'):
 remote('v3-'+a,*sys.argv[2:]);get(REMOTE+('v3-input.png' if a=='key' else 'v3-console.png'),'v3-input.png' if a=='key' else 'v3-console.png')
elif a=='play':remote('v3-play')
elif a=='stop':remote('v3-stop')
elif a=='launch-qa':remote('v4-launch-qa',sys.argv[2])
elif a=='launch-production':remote('v4-launch-production')
elif a=='cache':run([SSH,'onyx-linux','python3 '+REMOTE+'remote_build.py cache'])
else:raise SystemExit('unknown action')
