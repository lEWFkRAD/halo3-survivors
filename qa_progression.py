"""Explicit native QA only; launch the game and verify open console first."""
from pathlib import Path
import sys,time,json,subprocess
sys.path.insert(0,str(Path.home()/'Documents/Games/Halo3Survivors'))
import remote_build as r
r.window('Halo3')
mode=sys.argv[1]
if mode=='qa-clock':
 for c in ['(set sv_running true)','(set sv_threshold 100000)','(set cheat_deathless_player true)','(set sv_seconds 0)','(sv_close_menu)','(player_action_test_reset)']:r.console(c)
 start=time.monotonic();r.key('grave');time.sleep(10);r.key('grave');elapsed=time.monotonic()-start
 for c in ['(inspect sv_seconds)','(inspect sv_shots)','(inspect sv_xp)','(inspect (ai_living_count sv_hostiles))']:r.console(c)
 r.capture('qa-v3-clock');print('Wall time including console key transitions',elapsed)
elif mode=='qa-stage':
 for c in ['(set sv_tokens 20)','(set sv_selection 1)','(sv_purchase)','(inspect sv_nl_d)','(inspect sv_ar_u)','(sv_advance_stage)','(inspect sv_stage)','(inspect sv_nl_d)','(inspect sv_ar_u)','(inspect sv_tokens)','(player_action_test_reset)']:r.console(c)
 r.key('grave');time.sleep(2);r.capture('qa-v3-stage2');r.key('grave')
elif mode=='qa-hold':
 r.console('(player_action_test_reset)');r.key('grave')
 subprocess.run(['xdotool','keydown','space']);time.sleep(1);subprocess.run(['xdotool','keyup','space']);time.sleep(.3)
 r.key('grave');r.console('(inspect sv_selection)');r.capture('qa-v3-hold')
elif mode=='qa-input':
 r.console('(set sv_running false)')
 r.console('(player_disable_movement true)')
 actions=['jump','melee','action','rotate_grenades','rotate_weapons','primary_trigger','grenade_trigger','zoom']
 for key,action in [('space','jump'),('e','action'),('f','melee'),('g','rotate_grenades'),('1','rotate_weapons'),('mouse1','primary_trigger')]:
  r.console('(player_action_test_reset)');r.key('grave')
  if key.startswith('mouse'):subprocess.run(['xdotool','click',key[5:]])
  else:r.key(key)
  time.sleep(.2);r.key('grave');r.console('(inspect (player_action_test_'+action+'))');r.capture('qa-key-'+key)
  print('Captured',key,flush=True)
 r.console('(player_disable_movement false)')
elif mode=='qa-extra-input':
 r.console('(set sv_running false)');r.console('(player_disable_movement true)')
 for key,action in [('q','grenade_trigger'),('mouse3','zoom'),('Tab','rotate_grenades'),('2','rotate_grenades'),('v','melee')]:
  r.console('(player_action_test_reset)');r.key('grave')
  if key.startswith('mouse'):subprocess.run(['xdotool','click',key[5:]])
  else:r.key(key)
  time.sleep(.2);r.key('grave');r.console('(inspect (player_action_test_'+action+'))');r.capture('qa-extra-'+key)
  print('Captured',key,flush=True)
 r.console('(player_disable_movement false)')
elif mode=='qa-bindings':
 r.console('(set sv_running false)');r.console('(player_disable_movement false)')
 for key in ['space','e','q','f','2','1','mouse1']:
  r.console('(player_action_test_reset)');r.key('grave');time.sleep(.5)
  if key.startswith('mouse'):subprocess.run(['xdotool','mousedown',key[5:]])
  else:subprocess.run(['xdotool','keydown',key])
  time.sleep(.5)
  if key.startswith('mouse'):subprocess.run(['xdotool','mouseup',key[5:]])
  else:subprocess.run(['xdotool','keyup',key])
  time.sleep(.5);r.key('grave')
  actions=['jump','action','melee','primary_trigger','rotate_grenades','rotate_weapons']
  for chunk in [actions[:3],actions[3:]]:
   query='(inspect (+ '+' '.join('(if (player_action_test_'+a+') '+str(2**actions.index(a))+' 0)' for a in chunk)+'))'
   assert len(query)<250
   r.console(query)
  r.capture('qa-binding-'+key)
  from PIL import Image
  p=r.ROOT/('qa-binding-'+key+'.png');im=Image.open(p);im.crop((0,im.height-90,540,im.height)).save(p)
  print('Binding probe',key,flush=True)
else:raise SystemExit('unknown QA mode')
