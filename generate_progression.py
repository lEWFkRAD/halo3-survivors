"""Generate the playable four-stage HaloScript progression from the catalog."""
from pathlib import Path
import json
import re
from armory_live import emit_runtime, page_layout
from progression_hsc import HSC, expr, dispatch, cameras, enemies, combat
ROOT=Path(__file__).resolve().parent

# Native title budget: 50 nodes + 51 points + 4 ranks + 16 notices + 6 next-cost labels.
TITLES={
 'sv_controls':'ARMORY | Space next / Q back / Click buy / Space+Q page / 1 resume\n> selected detail | + buy / - locked / o owned / * max | Autosaves',
 'sv_purchased':'UPGRADE PURCHASED | Your ranks carry into the next stage.',
 'sv_need_points':'NOT ENOUGH POINTS | Defeat enemies to earn more.',
 'sv_prerequisite':'PREREQUISITE REQUIRED | Buy the earlier skill in this branch.',
 'sv_exclusive':'ALTERNATE PATH ALREADY CHOSEN | Choose the matching final upgrade.',
 'sv_stage_locked':'AVAILABLE IN A LATER STAGE',
 'sv_max_rank':'THIS SKILL IS AT MAXIMUM RANK',
 'sv_resumed':'LAST STAND | Move to survive. Weapons fire automatically. Space + Q opens Armory.',
 'sv_win':'LAST STAND COMPLETE | All four stages survived. Close and relaunch for a new run.',
 'sv_loss':'LAST STAND ENDED | Relaunch to start a new run.',
 'sv_solo':'LAST STAND supports one player.',
 'sv_boundary':'RETURNED TO THE ARENA',
}
for i,name in enumerate(['LANDING','INCURSION','OUTBREAK','LAST STAND'],1):
    TITLES[f'sv_stage_{i}']=f'STAGE {i}/4: {name} | Survive five minutes. All purchased ranks retained.'
for i in range(51): TITLES[f'sv_points_{i}']=f'ARMORY | {i} upgrade points available'
for i in range(4): TITLES[f'sv_rank_{i}']=f'SELECTED SKILL | Current rank: {i}'

def normalized_catalog():
    import progression_catalog as c
    return c.native_catalog()


WEAPON_LABELS={'needler':'Needler','assault_rifle':'AR','shotgun':'Shotgun',
               'plasma_rifle':'Plasma','rocket_launcher':'Rocket','energy_sword':'Sword'}
SUPPORT_LABELS={'support.vitality':'Vitality','support.body':'Armor',
                'support.shield':'Shield Cap','support.aegis':'Aegis',
                'support.aegis_cycle':'Shield Cycle','support.reach':'Reach',
                'support.insight':'Insight','support.scholar':'Scholar'}


def node_label(node,include_weapon=True):
    if not node['weapon']:return SUPPORT_LABELS.get(node['id'],node['name'])
    skill=node['id'].split('.',1)[1]
    label={'unlock':'Unlock','damage':'Power','cadence':'Rate'}.get(skill)
    if label is None:label=node['name'].split(': ',1)[-1]
    return (WEAPON_LABELS[node['weapon']]+' ' if include_weapon else '')+label


def compact_node_title(node,byid):
    """Fit the native single-line HUD without dropping costs or prerequisites."""
    units={'damage':'DMG','cadence_ticks':'atk ticks','range':'range',
           'targets':'targets','health_fraction':'%HP','shield_fraction':'%shield',
           'shield_pulse_fraction':'%shield/pulse','shield_pulse_ticks':'pulse ticks',
           'xp_fraction':'%XP'}
    effects=[]
    for effect in node['effects']:
        unit=units[effect['stat']]
        amount=effect['per_rank']*(100 if unit.startswith('%') else 1)
        effects.append(f'{amount:+g}{unit}')
    effect_text=' '.join(effects)+'/rank' if effects else 'Enable auto-fire'
    requirements=[]
    for prerequisite in node['prerequisites']:
        parent=byid[prerequisite['id']]
        label=node_label(parent,include_weapon=parent['weapon']!=node['weapon'])
        requirements.append(label+str(prerequisite['rank']))
    parts=[node_label(node),effect_text,'Cost'+ '/'.join(map(str,node['costs']))]
    if requirements:parts.append('Req '+','.join(requirements))
    parts.append('S'+str(node['stage']))
    # The CHUD objective is the selected skill's detail. Prefix it with an
    # explicit selection marker at zero title/reference cost: an in-graph
    # highlight would need one training-text snapshot per (state, selection)
    # pair (601 -> 3,848 snapshots) and blow the compiler reference budget.
    title='> '+' | '.join(parts)
    assert len(title)<=100,(node['id'],len(title),title)
    return title


def serialize_status_titles(h,titles):
    """Native title calls stack, so emit at most one notice per 90 logical ticks.

    Only the latest pending notice is retained. Node objectives use a separate
    native API and remain immediate. Rewrite callers before adding the sole
    dispatcher that is allowed to invoke cinematic_set_title directly.
    """
    pattern=re.compile(r'\(cinematic_set_title\s+([a-zA-Z0-9_]+)\)')
    names=sorted({match.group(1) for script in h.scripts for match in pattern.finditer(script)})
    assert set(names)<=set(titles)
    helpers={name:'sv_notify_'+name.removeprefix('sv_') for name in names}
    assert all(len(name)<=31 for name in helpers.values())
    h.scripts=[pattern.sub(lambda match:'('+helpers[match.group(1)]+')',script) for script in h.scripts]
    h.global_('short','sv_notice_clock',0)
    h.global_('short','sv_notice_pending',-1)
    dispatch(h,'sv_notice_display','sv_notice_pending',
             [(i,f'(cinematic_set_title {name})') for i,name in enumerate(names)])
    h.script('sv_notice_flush','''(if (and (= sv_notice_clock 0) (>= sv_notice_pending 0))
    (begin (set sv_notice_clock 90)
        (sv_notice_display) (set sv_notice_pending -1)))''')
    for i,name in enumerate(names):
        h.script(helpers[name],f'(set sv_notice_pending {i}) (sv_notice_flush)')
    h.script('sv_notice_tick','''(if (> sv_notice_clock 0)
    (set sv_notice_clock (max 0 (- sv_notice_clock 3))))
(sv_notice_flush)''')


def build(data,layout):
    nodes=data['nodes'];weapons=data['weapons'];stages=layout['stages'];byid={n['id']:n for n in nodes}
    assert len(nodes)==50
    titles=dict(TITLES)
    for i,n in enumerate(nodes):
        titles[f'sv_node_{i}']=compact_node_title(n,byid)
    prices=sorted({price for n in nodes for price in n['costs']})
    titles['sv_cost_max']='SELECTED SKILL | MAX RANK'
    for price in prices:
        titles[f'sv_cost_{price}']=f'SELECTED SKILL | Next rank: {price} points'
    assert len(titles)<=128,len(titles)
    h=HSC()
    initial={'sv_running':('boolean','false'),'sv_finished':('boolean','false'),'sv_menu_open':('boolean','false'),
      'sv_menu_any':('boolean','false'),'sv_menu_latched':('boolean','false'),
      'sv_key_resume':('boolean','false'),'sv_key_category':('boolean','false'),
      'sv_key_buy':('boolean','false'),'sv_key_previous':('boolean','false'),'sv_key_next':('boolean','false'),
      'sv_arm_result':('boolean','false'),'sv_save_dirty':('boolean','false'),
      'sv_restore_clock':('short',30),
      'sv_seconds':('long',0),'sv_stage_seconds':('short',0),'sv_stage':('short',1),
      'sv_xp':('real',0),'sv_threshold':('long',100),'sv_level':('short',1),'sv_tokens':('short',3),
      'sv_level_gain':('long',0),'sv_level_trial':('long',0),'sv_level_bill':('real',0),
      'sv_selection':('short',0),'sv_selected_rank':('short',0),'sv_cost':('short',0),
      'sv_menu_clock':('short',0),'sv_spawn_clock':('short',0),'sv_shield_clock':('short',0),
      'sv_health_scale':('real',1),'sv_shield_scale':('real',1),'sv_xp_scale':('real',1),
      'sv_pulse_fraction':('real',0),'sv_pulse_ticks':('short',240)}
    for name,(kind,value) in initial.items():h.global_(kind,name,value)
    for n in nodes:h.global_('short',n['native_global'],n.get('initial_rank',0))
    h.script('sv_player','(unit (list_get (players) 0))',kind='static unit')
    # Re-prime all watched action queries immediately after reset. Their return
    # values are deliberately discarded; only the next poll dispatches input.
    h.script('sv_reset_actions','''(player_action_test_reset)
(set sv_arm_result (player_action_test_jump))
(set sv_arm_result (player_action_test_melee))
(set sv_arm_result (player_action_test_primary_trigger))
(set sv_arm_result (player_action_test_rotate_weapons))''')
    # Derived values always recompute from ranks, preventing incremental drift or stacking on reload.
    stat_names={'health_fraction':'sv_health_scale','shield_fraction':'sv_shield_scale',
                'xp_fraction':'sv_xp_scale','shield_pulse_fraction':'sv_pulse_fraction','shield_pulse_ticks':'sv_pulse_ticks'}
    support=[]
    for stat,global_ in stat_names.items():
        base=240 if stat=='shield_pulse_ticks' else 0 if stat=='shield_pulse_fraction' else 1
        terms=[(n['native_global'],e['per_rank']) for n in nodes if not n['weapon'] for e in n['effects'] if e['stat']==stat]
        formula=expr(base,terms)
        support.append(f'(set {global_} {formula})')
    h.script('sv_support_stats','\n'.join(support))
    for key,w in weapons.items():
        body=[]
        for stat,base in w['base'].items():
            terms=[(n['native_global'],e['per_rank']) for n in nodes if n['weapon'] in (key,None) for e in n['effects'] if e['stat']==stat]
            formula=expr(base,terms)
            if stat=='cadence_ticks':formula=f'(max 3 {formula})'
            if stat=='range':formula=f'(max 0.5 {formula})'
            if stat=='targets':formula=f'(max 1 {formula})'
            body.append(f'(set sv_w_{key}_{stat} {formula})')
        h.script('sv_stats_'+key,'\n'.join(body))
    h.script('sv_recompute','(sv_support_stats)\n'+'\n'.join(f'(sv_stats_{k})' for k in weapons)+'''
(units_set_maximum_vitality (players) (* 45 sv_health_scale) (* 70 sv_shield_scale))''')
    damage_values=combat(h,weapons,nodes)
    enemies(h,stages);cameras(h,stages)
    dispatch(h,'sv_show_points','sv_tokens',[(i,f'(cinematic_set_title sv_points_{i})') for i in range(51)])
    dispatch(h,'sv_show_rank','sv_selected_rank',[(i,f'(cinematic_set_title sv_rank_{i})') for i in range(4)])
    dispatch(h,'sv_show_stage','sv_stage',[(i,f'(cinematic_set_title sv_stage_{i})') for i in range(1,5)])
    selections=[]
    for i,n in enumerate(nodes):
        rank=n['native_global']
        body=[f'(set sv_selected_rank {rank})','(set sv_cost -1)']
        body.extend(f'(if (= {rank} {r}) (set sv_cost {cost}))' for r,cost in enumerate(n['costs']))
        body.append(f'(cinematic_set_chud_objective sv_node_{i})')
        selections.append((i,'(begin '+' '.join(body)+')'))
    dispatch(h,'sv_show_node','sv_selection',selections)
    purchases=[]
    for i,n in enumerate(nodes):
        rank=n['native_global'];body=['(set sv_cost 0)']
        body.extend(f'(if (= {rank} {r}) (set sv_cost {cost}))' for r,cost in enumerate(n['costs']))
        missing=[f"(< {byid[p['id']]['native_global']} {p['rank']})" for p in n['prerequisites']]
        excludes=[f"(> {other['native_global']} 0)" for other in nodes if other['id']!=n['id'] and n['exclusive_group'] and other['exclusive_group']==n['exclusive_group']]
        any_ = lambda xs: '(or '+' '.join(xs)+')' if len(xs)>1 else xs[0] if xs else 'false'
        body.append(f'''(cond
    ((>= {rank} {n['max_rank']}) (cinematic_set_title sv_max_rank))
    ((< sv_stage {n['stage']}) (cinematic_set_title sv_stage_locked))
    ({any_(missing)} (cinematic_set_title sv_prerequisite))
    ({any_(excludes)} (cinematic_set_title sv_exclusive))
    ((< sv_tokens sv_cost) (cinematic_set_title sv_need_points))
    (true (begin (set sv_tokens (- sv_tokens sv_cost))
        (set {rank} (+ {rank} 1))
        (sv_recompute) (sv_show_node) (set sv_save_dirty true)
        (cinematic_set_title sv_purchased)
        (log_print "LASTSTAND_PURCHASE:{n['id']}"))))''')
        h.script(f'sv_buy_{i}','\n'.join(body));purchases.append((i,f'(sv_buy_{i})'))
    dispatch(h,'sv_purchase','sv_selection',purchases)
    h.script('sv_menu_next',f'''(set sv_selection (+ sv_selection 1))
(if (>= sv_selection {len(nodes)}) (set sv_selection 0)) (sv_show_node) (sv_show_rank)''')
    h.script('sv_menu_previous',f'''(set sv_selection (- sv_selection 1))
(if (< sv_selection 0) (set sv_selection {len(nodes)-1})) (sv_show_node) (sv_show_rank)''')
    indices={n['id']:i for i,n in enumerate(nodes)}
    categories=[(name,indices[ids[0]]) for name,ids in page_layout(data)]
    catcases=[]
    for ci,(cat,start) in enumerate(categories):
        end=categories[ci+1][1] if ci+1<len(categories) else len(nodes)
        next_=categories[(ci+1)%len(categories)][1]
        catcases.append(f'((and (>= sv_selection {start}) (< sv_selection {end})) (set sv_selection {next_}))')
    h.script('sv_menu_category','(cond\n'+'\n'.join(catcases)+')\n(sv_show_node)')
    h.script('sv_checkpoint','''(if (and sv_save_dirty sv_menu_open sv_running (not sv_finished))
    (begin (set sv_save_dirty false)
        (core_save_name "laststand_v04_pending")))''')
    # Core saves serialize script state but not every camera/debug controller.
    # Reassert the presentation within one second, including on a restored core.
    # Retain the chosen anchor so repair does not bypass the movement deadband.
    # Do not reset health, enemies, cooldowns, progression, or input latches here.
    h.script('sv_restore_controls','''(set sv_restore_clock (+ sv_restore_clock 3))
(if (>= sv_restore_clock 30)
    (begin (set sv_restore_clock 0)
        (camera_control true) (player_camera_control false)
        (set sv_view_refresh true)
        (hud_enable_training sv_menu_open)
        (chud_show_weapon_stats false) (chud_show_grenades false)
        (chud_show_crosshair false) (player_disable_weapon_pickup true)
        (if sv_menu_open (ai_enable false))
        (sv_follow)))''')
    h.script('sv_open_menu','''(set sv_menu_open true) (set sv_menu_clock 0)
(set sv_save_dirty true)
(set sv_menu_any false) (set sv_menu_latched true)
(player_disable_movement false)
(ai_enable false)
(object_cannot_take_damage (players))
(object_cannot_take_damage (ai_actors sv_hostiles))
(sv_reset_actions)
(sv_show_node) (cinematic_set_title sv_controls)''')
    h.script('sv_close_menu','''(set sv_menu_open false)
(hud_enable_training false)
(set sv_menu_any false) (set sv_menu_latched false)
(player_disable_movement false)
(object_can_take_damage (players))
(object_can_take_damage (ai_actors sv_hostiles))
(ai_enable true) (sv_reset_actions)
(cinematic_set_chud_objective sv_resumed) (sv_show_stage)''')
    # Read each native action test exactly once. The aggregate and dispatch must
    # use the same sample. The category chord is derived from Jump and Melee.
    # Latch the whole chord until every sampled menu action is released.
    h.script('sv_menu_input','''(set sv_key_resume (player_action_test_rotate_weapons))
(set sv_key_buy (player_action_test_primary_trigger))
(set sv_key_previous (player_action_test_melee))
(set sv_key_next (player_action_test_jump))
(set sv_key_category (and sv_key_next sv_key_previous))
(set sv_menu_any (or sv_key_resume sv_key_category sv_key_buy sv_key_previous sv_key_next))
(if (and sv_menu_any (not sv_menu_latched))
    (begin (set sv_menu_latched true)
        (cond
            (sv_key_resume (sv_close_menu))
            (sv_key_category (sv_menu_category))
            (sv_key_buy (sv_purchase))
            (sv_key_previous (sv_menu_previous))
            (sv_key_next (sv_menu_next)))))
(if (not sv_menu_any) (set sv_menu_latched false))
(sv_reset_actions)
(if sv_menu_open
    (begin
        (set sv_menu_clock (+ sv_menu_clock 3))
        (if (= sv_menu_clock 90) (sv_show_node))
        (if (= sv_menu_clock 180) (sv_show_node))
        (if (>= sv_menu_clock 270)
            (begin (set sv_menu_clock 0) (cinematic_set_title sv_controls)))))''')
    # Reopen without spending a point: two different actions together avoid taking over movement.
    h.script('sv_reopen_test','''(set sv_key_next (player_action_test_jump))
(set sv_key_previous (player_action_test_melee))
(if (and sv_key_next sv_key_previous) (sv_open_menu))
(sv_reset_actions)''')
    h.script('sv_boundary_check','\n'.join(f"(if (and (= sv_stage {st['number']}) (> (objects_distance_to_flag (players) sv_s{st['number']}_center) 21)) (begin (object_teleport (sv_player) sv_s{st['number']}_center) (cinematic_set_title sv_boundary)))" for st in stages))
    entry=[]
    for s in stages:
        num=s['number']
        entry.append((num,f'''(begin
(object_teleport (sv_player) sv_s{num}_center)
(camera_set {s['cameras'][0]['name']} 0)
(cinematic_set_title sv_stage_{num}))'''))
    dispatch(h,'sv_enter_stage_position','sv_stage',entry)
    h.script('sv_enter_stage','''(sv_clear_enemies)
(set sv_stage_seconds 0) (set sv_spawn_clock 0) (set sv_view_current -1)
(sv_enter_stage_position) (sv_recompute)
(units_set_current_vitality (players) (* 45 sv_health_scale) (* 70 sv_shield_scale))
(sv_follow) (sv_open_menu)''')
    # Native ai_erase queues removal until an AI update. Keep that subsystem
    # enabled at victory so the queued hostiles actually disappear. The running
    # and finished flags stop all spawning/attacks/clock; the player is protected.
    h.script('sv_advance_stage','''(if (< sv_stage 4)
    (begin (set sv_stage (+ sv_stage 1)) (set sv_tokens (min 50 (+ sv_tokens 2)))
        (sv_enter_stage))
    (begin (set sv_running false) (set sv_finished true)
        (set sv_menu_open false) (ai_enable true)
        (object_cannot_take_damage (players)) (player_disable_movement true)
        (sv_clear_enemies) (cinematic_set_chud_objective sv_win)
        (cinematic_set_title sv_win) (log_print "LASTSTAND_RUN_COMPLETE")))''')
    # Buying n levels costs n*T + 25*n*(n-1), where T is the current threshold.
    # Binary lifting finds the largest affordable n in 15 independent checks.
    # No script recursion, loop primitive, yield, or per-burst level limit is
    # needed. Bound the final level to its native signed-short storage range.
    level_bill='(* (* 1.0 sv_level_trial) (+ sv_threshold (* 25 (- sv_level_trial 1))))'
    level_batch=['(set sv_level_gain 0)']
    for step in (1 << bit for bit in range(14,-1,-1)):
        level_batch.append(f'''(set sv_level_trial (+ sv_level_gain {step}))
(if (<= (+ sv_level sv_level_trial) 32767)
    (begin (set sv_level_bill {level_bill})
        (if (<= sv_level_bill sv_xp) (set sv_level_gain sv_level_trial))))''')
    level_batch.append(f'''(if (> sv_level_gain 0)
    (begin (set sv_level_trial sv_level_gain)
        (set sv_level_bill {level_bill})
        (set sv_xp (- sv_xp sv_level_bill))
        (set sv_threshold (+ sv_threshold (* 50 sv_level_gain)))
        (set sv_level (+ sv_level sv_level_gain))
        (set sv_tokens (min 50 (+ sv_tokens sv_level_gain)))
        (sv_open_menu)))''')
    h.script('sv_level_up','\n'.join(level_batch))
    h.script('sv_shield_pulse','''(set sv_shield_clock (+ sv_shield_clock 30))
(if (>= sv_shield_clock sv_pulse_ticks)
    (begin (set sv_shield_clock 0)
        (if (> sv_pulse_fraction 0)
            (object_set_shield (sv_player)
                (min 1.0 (+ (/ (unit_get_shield (sv_player)) (* 70 sv_shield_scale)) sv_pulse_fraction))))))''')
    h.script('sv_lose','''(set sv_running false) (set sv_finished true)
(hud_enable_training false)
(cinematic_set_chud_objective sv_loss) (game_lost true)''')
    h.script('sv_step','''(if (and sv_running (not sv_finished) (not sv_menu_open))
    (if (or (!= (list_count (players)) 1) (<= (unit_get_health (sv_player)) 0))
        (sv_lose)
        (begin (sv_observe) (sv_level_up)
            (if (not sv_menu_open)
                (begin
                    (sv_shield_pulse)
                    (set sv_seconds (+ sv_seconds 1))
                    (set sv_stage_seconds (+ sv_stage_seconds 1))
                    (if (>= sv_stage_seconds 300)
                        (sv_advance_stage)
                        (begin
                            (set sv_spawn_clock (- sv_spawn_clock 1))
                            (if (<= sv_spawn_clock 0)
                                (begin (sv_spawn) (set sv_spawn_clock (max 6 (- 16 (* sv_stage 2)))))))))))))''')
    h.script('sv_boot','''(sleep_until (> (list_count (players)) 0) 1)
(if (= (list_count (players)) 1)
    (begin
        (hud_enable_training false)
        (camera_control true) (player_camera_control false)
        (object_set_facing (sv_player) sv_heading)
        (chud_show_weapon_stats false) (chud_show_grenades false)
        (player_enable_input true) (chud_show_crosshair false)
        (player_disable_weapon_pickup true)
        (unit_add_equipment (sv_player) sv_start true false)
        (set sv_running true) (sv_enter_stage))
    (begin (cinematic_set_chud_objective sv_solo) (set sv_finished true)))''',kind='startup')
    h.script('sv_clock','(sleep 30) (sv_step)',kind='continuous')
    h.script('sv_fast_clock','''(sleep 3)
(sv_notice_tick)
(if (and sv_running (not sv_finished))
    (begin (sv_restore_controls) (sv_boundary_check) (sv_follow)
        (if sv_menu_open (begin (sv_checkpoint) (sv_menu_input))
            (begin (sv_reopen_test) (if (not sv_menu_open) (sv_autofire))))))
(sv_tree_tick)''',kind='continuous')
    serialize_status_titles(h,titles)
    # The live tree uses training text; its wallet uses one short-lived title.
    # Keep both outside the serialized status queue, and update after input so
    # a Resume action suppresses a render due on that same frame.
    h.global_('short','sv_tree_clock',0)
    emit_runtime(h,data)
    dispatch(h,'sv_wallet_display','sv_tokens',[(i,f'(cinematic_set_title sv_points_{i})') for i in range(51)])
    dispatch(h,'sv_price_display','sv_cost',[(-1,'(cinematic_set_title sv_cost_max)')]+[(i,f'(cinematic_set_title sv_cost_{i})') for i in prices])
    # Keep the refresh limit through a rapid close/reopen. A saved clock is
    # always 0..30, so Continue repairs the page within one second without
    # touching ranks or run state. Input is handled before this scheduler, so a
    # Resume action suppresses even a refresh due on that same frame.
    # Wallet/price titles live 0.95s, just under the 30-tick graph cycle, so
    # they briefly expired before each redraw. Refresh wallet/price alone at
    # the 15-tick midpoint: the graph throttle, the sub-second title expiry
    # after Resume and the saved-clock range all stay unchanged.
    h.script('sv_tree_tick','''(if (and sv_running (not sv_finished))
    (begin
        (if (> sv_tree_clock 0) (set sv_tree_clock (max 0 (- sv_tree_clock 3))))
        (if (and sv_menu_open (= sv_tree_clock 15))
            (begin (sv_wallet_display) (sv_price_display)))
        (if (and sv_menu_open (= sv_tree_clock 0))
            (begin (set sv_tree_clock 30)
                (hud_enable_training true) (sv_tree_display)
                (hud_show_training_text true) (sv_wallet_display) (sv_show_node) (sv_price_display))))
    (hud_enable_training false))''')
    assert len(h.globals)<512 and len(h.scripts)<1024
    source=h.render()
    for name,code in [('assault_rifle','ar'),('rocket_launcher','rl'),('energy_sword','es'),('plasma_rifle','pr'),('shotgun','sg'),('needler','nl')]:
        source=source.replace('sv_w_'+name,'sv_w_'+code)
    return source,titles,damage_values

def main(root=None):
    root=Path(root) if root is not None else ROOT
    data=normalized_catalog(); layout=json.loads((root/'progression-layout.json').read_text())
    source,titles,damages=build(data,layout)
    (root/'source/progression.hsc').write_text(source,encoding='utf-8')
    contract={'catalog':data,'layout':layout,'titles':titles,'damage_values':damages,'version':'0.4.0',
              'persistence':'Armory checkpoints resume the complete native run through the SDK launcher; saves require the exact same build. Permanent unlocks are not integrated.'}
    (root/'progression-contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    print(f'Generated {len(source)} bytes of HSC; {len(titles)} native titles.')
    return (root/'source/progression.hsc',root/'progression-contract.json')
if __name__=='__main__':main()
