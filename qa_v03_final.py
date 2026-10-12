"""Explicit, temporary native-engine QA. Requires a visible open console."""
from pathlib import Path
import sys,time,subprocess,json
sys.path.insert(0,str(Path.home()/'Documents/Games/Halo3Survivors'))
import remote_build as r
r.window('Halo3')
def cmd(s):
 assert len(s)<250,s
 r.console(s)
def check(label,condition):
 cmd('(inspect '+condition+')')
 r.capture('qa-check-'+label)
 from PIL import Image
 p=r.ROOT/('qa-check-'+label+'.png');im=Image.open(p);im.crop((0,im.height-75,540,im.height)).save(p)
 print('Captured assertion:',label,flush=True)
def play_input(key=None,mouse=None,hold=.15):
 cmd('(player_action_test_reset)');r.key('grave');time.sleep(.4)
 keys=key.split('+') if key else []
 if mouse:
  w=r.window('Halo3')
  g=dict(line.split('=',1) for line in subprocess.check_output(['xdotool','getwindowgeometry','--shell',w],text=True).splitlines() if '=' in line)
  subprocess.run(['xdotool','mousemove',str(int(g['X'])+int(g['WIDTH'])//2),str(int(g['Y'])+int(g['HEIGHT'])//2)],check=True)
 if keys:subprocess.run(['xdotool','keydown',*keys],check=True)
 if mouse:subprocess.run(['xdotool','mousedown',str(mouse)],check=True)
 time.sleep(hold)
 if mouse:subprocess.run(['xdotool','mouseup',str(mouse)],check=True)
 if keys:subprocess.run(['xdotool','keyup',*reversed(keys)],check=True)
 time.sleep(.5);r.key('grave')
mode=sys.argv[1]
if mode=='qa-final-menu':
 check('initial_menu','(and sv_menu_open (= sv_tokens 3) (= sv_selection 0))')
 play_input(key='space',hold=1)
 cmd('(inspect sv_selection)')
 check('held_next_once','(= sv_selection 1)')
 play_input(mouse=1,hold=1)
 check('held_purchase_once','(and (= sv_nl_d 1) (= sv_tokens 2))')
 play_input(key='space+q');check('category','(= sv_selection 7)')
 play_input(mouse=1);check('unlock_ar','(and (= sv_ar_u 1) (= sv_tokens 0))')
 play_input(key='q');check('previous','(= sv_selection 6)')
 play_input(key='1');check('resume','(not sv_menu_open)')
 play_input(key='space+q');check('reopen','sv_menu_open')
 cmd('(set sv_selection 1)');cmd('(sv_show_node)');cmd('(cinematic_set_title sv_controls)')
 cmd('(player_action_test_reset)');r.key('grave');time.sleep(.5);r.capture('qa-final-armory');r.key('grave')
elif mode=='qa-final-stages':
 cmd('(set sv_threshold 100000)');cmd('(set cheat_deathless_player true)')
 for stage in range(1,5):
  if stage>1:cmd('(sv_advance_stage)')
  check('carry_stage_'+str(stage),'(and (= sv_nl_d 1) (= sv_ar_u 1))')
  check('stage_'+str(stage),'(= sv_stage '+str(stage)+')')
  check('stage_position_'+str(stage),'(< (objects_distance_to_flag (players) sv_s'+str(stage)+'_center) 1)')
  cmd('(set sv_stage_seconds 130)');cmd('(sv_spawn)')
  check('enemy_cap_'+str(stage),'(and (> (ai_living_count sv_hostiles) 0) (<= (ai_living_count sv_hostiles) 36))')
  family=['brutes','captains','infection','hunters'][stage-1]
  check('enemy_'+family,'(> (ai_living_count sv_s'+str(stage)+'_'+family+') 0)')
  cmd('(sv_close_menu)');cmd('(player_action_test_reset)');r.key('grave');time.sleep(8);r.capture('qa-final-stage'+str(stage));r.key('grave')
  cmd('(sv_open_menu)')
 check('auto_shots','(> sv_shots 0)');check('auto_xp','(> sv_xp 0)')
elif mode=='qa-final-weapons':
 cmd('(set sv_running false)');cmd('(ai_enable false)');cmd('(object_cannot_take_damage (players))')
 cmd('(ai_erase_all)');cmd('(ai_place sv_s4_grunts 1)')
 cmd('(player_action_test_reset)');r.key('grave');time.sleep(.5);r.key('grave')
 cmd('(set sv_players (players))');cmd('(set sv_actor_list (ai_actors sv_hostiles))')
 cmd('(object_teleport (list_get sv_actor_list 0) sv_s4_center)')
 cmd('(object_teleport (sv_player) sv_s4_center)')
 for key in ['nl','ar','sg','pr','rl','es']:
  cmd('(units_set_maximum_vitality sv_actor_list 5000 0)');cmd('(units_set_current_vitality sv_actor_list 5000 0)')
  cmd('(object_can_take_damage sv_actor_list)');cmd('(set sv_shots 0)');cmd('(sv_w_'+key+'_fire)')
  cmd('(inspect sv_shots)');cmd('(inspect (object_get_health (list_get sv_actor_list 0)))')
  check('weapon_'+key,'(and (> sv_shots 0) (< (object_get_health (list_get sv_actor_list 0)) 1))')
  r.capture('qa-final-weapon-'+key)
elif mode=='qa-final-ending':
 cmd('(set sv_running true)');cmd('(set sv_stage 4)');cmd('(set sv_stage_seconds 299)');cmd('(set sv_threshold 100000)')
 cmd('(sv_close_menu)');cmd('(sv_step)')
 check('ending','(and sv_finished (not sv_running) (not sv_menu_open) (= (ai_living_count sv_hostiles) 0))')
 cmd('(set sv_shots 0)');cmd('(player_action_test_reset)');r.key('grave');time.sleep(6)
 r.capture('qa-final-ending');r.key('grave')
 check('ending_stays','(and sv_finished (not sv_running) (= sv_stage_seconds 300) (= sv_shots 0) (not sv_menu_open))')
else:raise SystemExit('Unknown QA mode')
print('QA mode completed:',mode,flush=True)
