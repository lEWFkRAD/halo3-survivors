#!/usr/bin/env python3
"""Launch the owned Halo 3 standalone engine with the Last Stand scenario."""
from pathlib import Path
import subprocess,shlex,fcntl
root=Path(__file__).resolve().parent
lock=open(root/'play.lock','w')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Last Stand is already running.')
steam=Path.home()/'snap/steam/common/.local/share/Steam';kit=steam/'steamapps/common/H3EK'
cmd=['env','WINEPREFIX='+str(root/'tool-prefix/pfx'),'DISPLAY=:0','XAUTHORITY=/run/user/1000/gdm/Xauthority','WINEDEBUG=-all','WINEDLLOVERRIDES=d3dcompiler_47=n,b',str(steam/'steamapps/common/Proton - Experimental/files/bin/wine'),str(kit/'halo3_tag_test.exe'),'-window','1600','900']
with (root/'play.log').open('w') as log:
 result=subprocess.run(['snap','run','--shell','steam','-c','cd '+shlex.quote(str(kit))+' && '+shlex.join(cmd)],stdout=log,stderr=subprocess.STDOUT)

raise SystemExit(result.returncode)
