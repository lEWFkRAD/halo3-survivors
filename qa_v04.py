"""Temporary native QA; run only with the SDK console visibly open."""
from pathlib import Path
import sys,time,runpy
sys.path.insert(0,str(Path.home()/'Documents/Games/Halo3Survivors'))
import remote_build as r
PROJECT=r.ROOT
r.ROOT=PROJECT/'qa-v04';r.ROOT.mkdir(exist_ok=True)
mode=sys.argv[1]
if (mode.startswith('qa-final-') and mode!='qa-final-ending') or mode=='qa-clock':
    runpy.run_path(str(PROJECT/('qa_progression.py' if mode=='qa-clock' else 'qa_v03_final.py')),run_name='__main__')
    raise SystemExit(0)
r.window('Halo3')
def cmd(s):
    assert len(s)<250,s
    r.console(s)
def check(label,condition):
    cmd('(inspect '+condition+')');r.capture('qa-check-'+label)
    from PIL import Image
    p=r.ROOT/('qa-check-'+label+'.png');im=Image.open(p)
    im.crop((0,im.height-75,540,im.height)).save(p)
    print('Captured assertion:',label,flush=True)
if mode=='qa-final-ending':
    cmd('(set sv_running true)');cmd('(set sv_finished false)');cmd('(set sv_stage 4)')
    cmd('(sv_enter_stage)');cmd('(set sv_stage_seconds 130)');cmd('(sv_spawn)')
    check('ending_had_enemies','(> (ai_living_count sv_hostiles) 0)')
    cmd('(set sv_stage_seconds 299)');cmd('(set sv_threshold 100000)')
    cmd('(sv_close_menu)');cmd('(sv_step)')
    # Native actor erasure is applied by the next simulation update. The open
    # debug console pauses that update, so yield gameplay before checking it.
    r.key('grave');time.sleep(.5);r.key('grave')
    check('ending','(and sv_finished (not sv_running) (not sv_menu_open) (= (ai_living_count sv_hostiles) 0))')
    cmd('(set sv_shots 0)');r.key('grave');time.sleep(6);r.capture('qa-final-ending');r.key('grave')
    check('ending_stays','(and sv_finished (not sv_running) (= sv_stage_seconds 300) (= sv_shots 0) (not sv_menu_open) (= (ai_living_count sv_hostiles) 0))')
elif mode=='qa-v04-spawn':
    cmd('(set sv_running false)');cmd('(ai_enable false)')
    cmd('(set sv_stage 1)');cmd('(set sv_stage_seconds 0)');cmd('(sv_clear_enemies)')
    cmd('(object_teleport (sv_player) sv_s1_grunts_p0)');cmd('(sv_spawn)')
    check('spawn_blocks_near','(= (ai_living_count sv_s1_grunts) 0)')
    cmd('(object_teleport (sv_player) sv_s1_center)');cmd('(sv_spawn)')
    check('spawn_retries_clear','(= (ai_living_count sv_s1_grunts) 6)')
    check('spawn_near_ring','(and (> (objects_distance_to_flag (players) sv_s1_grunts_p0) 5) (< (objects_distance_to_flag (players) sv_s1_grunts_p0) 8))')
    cmd('(sv_clear_enemies)');cmd('(set sv_stage 3)');cmd('(set sv_stage_seconds 130)')
    cmd('(object_teleport (sv_player) sv_s3_infection_p9)');cmd('(sv_spawn)')
    check('spawn_blocks_last_slot','(= (ai_living_count sv_s3_infection) 0)')
    check('spawn_other_cohorts','(> (ai_living_count sv_hostiles) 0)')
    cmd('(object_teleport (sv_player) sv_s3_center)');cmd('(sv_spawn)')
    check('spawn_cap','(<= (ai_living_count sv_hostiles) 36)')
elif mode=='qa-v04-batch':
    cmd('(set sv_running true)');cmd('(set sv_finished false)');cmd('(set sv_stage 1)');cmd('(sv_enter_stage)')
    cmd('(set sv_level 1)');cmd('(set sv_threshold 100)');cmd('(set sv_xp 1000.25)');cmd('(set sv_tokens 3)')
    cmd('(sv_close_menu)');cmd('(sv_step)')
    check('batch_levels','(and (= sv_level 6) (= sv_threshold 350) (= sv_tokens 8) (= sv_xp 0.25))')
    check('batch_paused','(and sv_menu_open (= sv_stage_seconds 0))')
    cmd('(sv_close_menu)');cmd('(sv_step)')
    check('batch_one_visit','(and (not sv_menu_open) (= sv_stage_seconds 1))')
    cmd('(sv_open_menu)')
elif mode=='qa-v04-save-setup':
    cmd('(set sv_running true)');cmd('(set sv_finished false)');cmd('(set sv_stage 2)');cmd('(sv_enter_stage)')
    cmd('(set sv_stage_seconds 130)');cmd('(set sv_seconds 430)');cmd('(set sv_xp 81.25)')
    cmd('(set sv_level 6)');cmd('(set sv_threshold 350)');cmd('(set sv_tokens 7)')
    cmd('(set sv_ar_u 1)');cmd('(set sv_nl_d 2)');cmd('(set sv_shots 123)');cmd('(set sv_selection 8)')
    cmd('(sv_recompute)');cmd('(sv_spawn)');cmd('(sv_open_menu)')
    cmd('(player_action_test_reset)');r.key('grave');time.sleep(3);r.capture('save-before');r.key('grave')
    check('save_before','(and (= sv_stage 2) (= sv_seconds 430) (= sv_xp 81.25) (= sv_tokens 7) (= sv_ar_u 1) (= sv_nl_d 2) (= sv_shots 123) sv_menu_open)')
    check('save_actors_before','(= (ai_living_count sv_hostiles) 17)')
elif mode=='qa-v04-save-after':
    check('save_after','(and (= sv_stage 2) (= sv_seconds 430) (= sv_xp 81.25) (= sv_tokens 7) (= sv_ar_u 1) (= sv_nl_d 2) (= sv_shots 123) sv_menu_open)')
    check('save_actors_after','(= (ai_living_count sv_hostiles) 17)')
    cmd('(inspect sv_view_current)')
    cmd('(player_action_test_reset)');r.key('grave');time.sleep(3);r.capture('save-after');r.key('grave')
    check('save_clock_paused','(and (= sv_seconds 430) (= sv_shots 123) sv_menu_open)')
    # Real key input must still resume after a restored menu/input latch.
    cmd('(player_action_test_reset)');r.key('grave');r.key('1');time.sleep(2);r.key('grave')
    check('save_resume_works','(and (not sv_menu_open) (> sv_seconds 430) (> sv_shots 123))')
    cmd('(sv_open_menu)')
else:raise SystemExit('Unknown v0.4 QA mode')
print('QA mode completed:',mode,flush=True)
