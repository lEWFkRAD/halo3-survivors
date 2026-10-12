"""Private native build operations. UI commands require an observed ready window."""
from pathlib import Path
from datetime import datetime
import os,sys,shutil,json,time,subprocess
ROOT=Path.home()/'Documents/Games/Halo3Survivors'
sys.path.insert(0,str(ROOT))
# Unique command names avoid triggering old remote_build dispatch during import.
import remote_build as r
KIT=r.KIT
cmd=sys.argv[1]
if cmd=='v3-stage':
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S');backup=ROOT/'backups'/('outdoor-v02-'+stamp);backup.mkdir(parents=True)
    for rel in ['tags/levels/survivors/last_stand/last_stand.scenario','data/levels/survivors/last_stand/scripts/last_stand.hsc','maps/last_stand.map']:
        p=KIT/rel
        if p.exists():shutil.copy2(p,backup/p.name)
    (ROOT/'v3-backup.txt').write_text(str(backup))
    import tarfile
    with tarfile.open(ROOT/'v3-native.tar') as tf:
        for member in tf.getmembers():
            assert not member.name.startswith('/') and '..' not in Path(member.name).parts
        tf.extractall(KIT/'tags',filter='data')
    shutil.copy2(ROOT/'v3-candidate.scenario',KIT/'tags/levels/survivors/last_stand/last_stand.scenario')
    shutil.copy2(ROOT/'progression.hsc',KIT/'data/levels/survivors/last_stand/scripts/last_stand.hsc')
    (ROOT/'v3-compile-start.txt').write_text(datetime.now().isoformat())
    r.stop('halo3_tag_test.exe');r.stop('sapien.exe')
    r.launch('sapien.exe',['Z:'+str(KIT/'tags/levels/survivors/last_stand/last_stand.scenario').replace('/','\\')])
    print('BACKUP',backup)
elif cmd=='v3-capture':
    from PIL import ImageGrab
    ImageGrab.grab().save(ROOT/'v3-desktop.png')
    r.capture('v3-current')
elif cmd=='v3-compile':
    r.window('H3 Sapien');r.key('ctrl','shift','c');time.sleep(4);r.key('ctrl','s');time.sleep(2)
    started=datetime.fromisoformat((ROOT/'v3-compile-start.txt').read_text());fatal=[]
    for p in (KIT/'reports').glob('*/debug_full.txt'):
        for line in p.read_text(errors='replace').splitlines():
            if '-FATAL- design:hs' in line:
                try:
                    if datetime.strptime(line[:21],'%m.%d.%y %H:%M:%S.%f')>=started:fatal.append(line)
                except ValueError:pass
    print(json.dumps(fatal,indent=2))
    from PIL import ImageGrab
    ImageGrab.grab().save(ROOT/'v3-compile.png')
    if fatal:raise SystemExit(2)
elif cmd=='v3-play':
    r.stop('halo3_tag_test.exe');r.stop('sapien.exe')
    r.launch('halo3_tag_test.exe',['-window','1280','720'])
elif cmd=='v3-stop':
    r.stop('halo3_tag_test.exe');r.stop('sapien.exe')
elif cmd=='v4-launch-qa':
    mode=sys.argv[2]
    assert mode in ('new','continue','choose')
    args=['python3',str(ROOT/'launch_v04.py'),'--qa-profile',str(ROOT/'qa-saves/native-v04')]
    if mode!='choose':args.append('--'+mode)
    with (ROOT/'qa-v04-launcher.log').open('a') as output:
        p=subprocess.Popen(args,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    print('QA launcher',p.pid,mode)
elif cmd=='v4-launch-production':
    with (ROOT/'launcher-v04.log').open('a') as output:
        p=subprocess.Popen(['python3',str(ROOT/'launch.py')],stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    print('Production launcher',p.pid)
elif cmd=='v3-console-open':
    r.window('Halo3');r.key('grave');r.capture('v3-console')
elif cmd=='v3-console':
    r.window('Halo3')
    for command in sys.argv[2:]:r.console(command)
    r.capture('v3-console')
elif cmd=='v3-key':
    r.window('Halo3')
    for key in sys.argv[2:]:r.key(key)
    time.sleep(.4);r.capture('v3-input')
else:raise SystemExit('unknown action')
