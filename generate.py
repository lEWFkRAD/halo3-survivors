from pathlib import Path
import json
ROOT = Path(__file__).resolve().parent
SQUADS = [
    ('sv_grunts_a', 6, 0, 10), ('sv_grunts_b', 6, 0, 10),
    ('sv_grunts_c', 6, 60, 10), ('sv_grunts_d', 6, 120, 10),
    ('sv_jackals', 4, 180, 20), ('sv_brutes', 4, 360, 30),
    ('sv_flood', 8, 600, 15), ('sv_hunters', 2, 900, 100),
]
TITLES = {
    'sv_intro': 'LAST STAND | WASD to move. Automatic fire. Survive 20 minutes.',
    'sv_upgrade_ready': 'UPGRADE READY | Choose a beacon: BLUE Needler / RED Aegis / YELLOW Vitality.',
    'sv_needler': 'NEEDLER UPGRADED | Leave the pads before choosing again.',
    'sv_aegis': 'AEGIS UPGRADED | Periodic shield recovery enabled.',
    'sv_vitality': 'VITALITY UPGRADED | Maximum health and shields increased.',
    'sv_phase2': 'COVENANT REINFORCEMENTS INBOUND',
    'sv_phase3': 'FLOOD OUTBREAK', 'sv_phase4': 'HUNTERS INBOUND | Five minutes remain.',
    'sv_extract': 'EXTRACTION OPEN | Reach the beacon within 60 seconds.',
    'sv_win': 'EXTRACTED', 'sv_loss': 'LAST STAND ENDED',
    'sv_solo': 'This source prototype supports one player only.',
}

def generate():
    parts = ['''; LAST STAND - native Halo 3 survival mod source.
; Scenario contract is scenario-contract.json. Single-player only.
; Tick assumes Halo 3's default 30 simulation ticks/sec; verify in tag_test.
(global boolean sv_running false)
(global boolean sv_finished false)
(global boolean sv_pad_latched false)
(global long sv_seconds 0)
(global long sv_xp 0)
(global long sv_threshold 100)
(global short sv_level 1)
(global short sv_tokens 0)
(global short sv_needler_rank 0)
(global short sv_aegis_rank 0)
(global short sv_vitality_rank 0)
(global short sv_spawn_clock 0)
(global short sv_shield_clock 0)
(global short sv_cap 36)
(global short sv_now 0)
(global short sv_total 0)
(global object sv_target none)
(global object sv_candidate none)
(global real sv_nearest 12)
(global real sv_distance -1)
(global long sv_shots 0)
(global object_list sv_actor_list (players))
(global object_list sv_players (players))
(global object_list sv_view_players (players))
(global short sv_view_index -1)
(global short sv_view_current -1)
(global real sv_view_distance 0)
(global real sv_view_nearest 100000)
''']
    for name, *_ in SQUADS:
        parts.append(f'(global short {name}_prev 0)\n')
    parts.append('''
(script static unit sv_player (unit (list_get (players) 0)))
(script static void sv_observe
''')
    for name, _, _, reward in SQUADS:
        parts.append(f'''    (set sv_now (ai_living_count {name}))
    (if (< sv_now {name}_prev)
        (set sv_xp (+ sv_xp (* (- {name}_prev sv_now) {reward}))))
    (set {name}_prev sv_now)
''')
    parts.append(')\n(script static void sv_autofire\n')
    parts.append("    (set sv_players (players))\n    (set sv_target none)\n    (set sv_nearest 12)\n")
    for name, size, *_ in SQUADS:
        parts.append(f"    (set sv_actor_list (ai_actors {name}))\n")
        for index in range(size):
            parts.append(f'''    (set sv_candidate (list_get sv_actor_list {index}))
    (if (> (object_get_health sv_candidate) 0)
        (begin
            (set sv_distance (objects_distance_to_object sv_players sv_candidate))
            (if (and (>= sv_distance 0) (< sv_distance sv_nearest))
                (begin (set sv_target sv_candidate) (set sv_nearest sv_distance)))))
''')
    parts.append('''    (if (> (object_get_health sv_target) 0)
        (begin
            (effect_new_on_object_marker "objects\\survivors\\auto_impact" sv_target "")
            (cond
                ((= sv_needler_rank 0) (damage_object_effect "objects\\survivors\\auto_damage_0" sv_target))
                ((= sv_needler_rank 1) (damage_object_effect "objects\\survivors\\auto_damage_1" sv_target))
                ((= sv_needler_rank 2) (damage_object_effect "objects\\survivors\\auto_damage_2" sv_target))
                (true (damage_object_effect "objects\\survivors\\auto_damage_3" sv_target)))
            (set sv_shots (+ sv_shots 1))))
)
(script continuous sv_auto_clock
    (sleep 12)
    (if (and sv_running (not sv_finished) (> (unit_get_health (sv_player)) 0))
        (sv_autofire)))
''')
    parts.append('(script static void sv_spawn\n    (set sv_total 0)\n')
    for name, *_ in SQUADS:
        parts.append(f'    (set sv_total (+ sv_total (ai_living_count {name})))\n')
    # Later, tougher cohorts get admission first, avoiding starvation at the cap.
    for name, size, start, _ in reversed(SQUADS):
        parts.append(f'''    (if (and (>= sv_seconds {start}) (= (ai_living_count {name}) 0)
             (<= (+ sv_total {size}) sv_cap))
        (begin
            (ai_erase {name})
            (ai_place {name} {size})
            (ai_set_team {name} covenant)
            (ai_set_objective {name} sv_hunt)
            (ai_magically_see_object {name} (sv_player))
            (set {name}_prev (ai_living_count {name}))
            (set sv_total (+ sv_total {name}_prev))))
''')
    parts.append(''' )
(script static void sv_level_up
    (if (>= sv_xp sv_threshold)
        (begin
            (set sv_xp (- sv_xp sv_threshold))
            (set sv_level (+ sv_level 1))
            (set sv_tokens (+ sv_tokens 1))
            (hud_activate_team_nav_point_flag player sv_beacon_needler 0.5)
            (hud_activate_team_nav_point_flag player sv_beacon_aegis 0.5)
            (hud_activate_team_nav_point_flag player sv_beacon_vitality 0.5)
            (set sv_threshold (+ sv_threshold 50))
            (cinematic_set_chud_objective sv_upgrade_ready))))

(script static void sv_choices
    (if (not (or (and (>= (objects_distance_to_flag (players) sv_beacon_needler) 0) (<= (objects_distance_to_flag (players) sv_beacon_needler) 1.0))
                 (and (>= (objects_distance_to_flag (players) sv_beacon_aegis) 0) (<= (objects_distance_to_flag (players) sv_beacon_aegis) 1.0))
                 (and (>= (objects_distance_to_flag (players) sv_beacon_vitality) 0) (<= (objects_distance_to_flag (players) sv_beacon_vitality) 1.0))))
        (set sv_pad_latched false))
    (if (and (> sv_tokens 0) (not sv_pad_latched))
        (cond
            ((and (>= (objects_distance_to_flag (players) sv_beacon_needler) 0) (<= (objects_distance_to_flag (players) sv_beacon_needler) 1.0))
                (begin
                    (set sv_pad_latched true)
                    (if (< sv_needler_rank 3)
                        (begin
                            (set sv_needler_rank (+ sv_needler_rank 1))
                            (set sv_tokens (- sv_tokens 1))
                            (cond
                                ((= sv_needler_rank 1) (unit_add_equipment (sv_player) sv_needler_1 true false))
                                ((= sv_needler_rank 2) (unit_add_equipment (sv_player) sv_needler_2 true false))
                                ((= sv_needler_rank 3) (unit_add_equipment (sv_player) sv_needler_3 true false)))
                            (cinematic_set_chud_objective sv_needler)))))
            ((and (>= (objects_distance_to_flag (players) sv_beacon_aegis) 0) (<= (objects_distance_to_flag (players) sv_beacon_aegis) 1.0))
                (begin
                    (set sv_pad_latched true)
                    (if (< sv_aegis_rank 5)
                        (begin
                            (set sv_aegis_rank (+ sv_aegis_rank 1))
                            (set sv_tokens (- sv_tokens 1))
                            (cinematic_set_chud_objective sv_aegis)))))
            ((and (>= (objects_distance_to_flag (players) sv_beacon_vitality) 0) (<= (objects_distance_to_flag (players) sv_beacon_vitality) 1.0))
                (begin
                    (set sv_pad_latched true)
                    (if (< sv_vitality_rank 5)
                        (begin
                            (set sv_vitality_rank (+ sv_vitality_rank 1))
                            (set sv_tokens (- sv_tokens 1))
                            (units_set_maximum_vitality (players)
                                (* 45 (+ 1 (* 0.2 sv_vitality_rank)))
                                (* 70 (+ 1 (* 0.2 sv_vitality_rank))))
                            (units_set_current_vitality (players)
                                (* 45 (+ 1 (* 0.2 sv_vitality_rank)))
                                (* 70 (+ 1 (* 0.2 sv_vitality_rank))))
                            (cinematic_set_chud_objective sv_vitality))))))))

(script static void sv_shield_pulse
    (set sv_shield_clock (+ sv_shield_clock 1))
    (if (>= sv_shield_clock 8)
        (begin
            (set sv_shield_clock 0)
            (if (> sv_aegis_rank 0)
                (object_set_shield (sv_player)
                    (min 1.0 (+ (/ (unit_get_shield (sv_player)) (* 70 (+ 1 (* 0.2 sv_vitality_rank)))) (* 0.15 sv_aegis_rank))))))))

(script static void sv_lose
    (set sv_running false)
    (set sv_finished true)
    (cinematic_set_chud_objective sv_loss)
    (game_lost true))

(script static void sv_step
    (if (and sv_running (not sv_finished))
        (if (or (!= (list_count (players)) 1) (<= (unit_get_health (sv_player)) 0))
            (sv_lose)
            (begin
                (sv_observe)
                (sv_level_up)
                (sv_choices)
                (sv_shield_pulse)
                (set sv_seconds (+ sv_seconds 1))
                (cond
                    ((= sv_seconds 360) (cinematic_set_chud_objective sv_phase2))
                    ((= sv_seconds 600) (cinematic_set_chud_objective sv_phase3))
                    ((= sv_seconds 900) (cinematic_set_chud_objective sv_phase4))
                    ((= sv_seconds 1200) (begin (cinematic_set_chud_objective sv_extract) (hud_activate_team_nav_point_flag player sv_beacon_exit 0.5))))
                (if (< sv_seconds 1200)
                    (begin
                        (set sv_spawn_clock (- sv_spawn_clock 1))
                        (if (<= sv_spawn_clock 0)
                            (begin
                                (sv_spawn)
                                (cond
                                    ((>= sv_seconds 900) (set sv_spawn_clock 6))
                                    ((>= sv_seconds 600) (set sv_spawn_clock 8))
                                    ((>= sv_seconds 360) (set sv_spawn_clock 10))
                                    (true (set sv_spawn_clock 15))))))
                    (cond
                        ((and (>= (objects_distance_to_flag (players) sv_beacon_exit) 0) (<= (objects_distance_to_flag (players) sv_beacon_exit) 1.0))
                            (begin
                                (set sv_running false)
                                (set sv_finished true)
                                (cinematic_set_chud_objective sv_win)
                                (game_won)))
                        ((>= sv_seconds 1260) (sv_lose))))))))

(script startup sv_boot
    (sleep_until (> (list_count (players)) 0) 1)
    (if (= (list_count (players)) 1)
        (begin
            (hud_enable_training false)
            (camera_control true)
            (camera_set sv_overhead 0)
            (player_camera_control false)
            (object_set_facing (sv_player) sv_heading)
            (chud_show_weapon_stats false)
            (chud_show_grenades false)
            (player_enable_input true)
            (chud_show_crosshair false)
            (unit_add_equipment (sv_player) sv_start true false)
            (cinematic_set_chud_objective sv_intro)
            (set sv_running true)
            (sv_spawn))
        (begin
            (cinematic_set_chud_objective sv_solo)
            (set sv_finished true))))

(script continuous sv_clock
    (sleep 30)
    (sv_step))
''')
    anchors=json.loads((ROOT/'camera-grid.json').read_text())
    chunks=[list(enumerate(anchors))[i:i+12] for i in range(0,len(anchors),12)]
    for group,chunk in enumerate(chunks):
        parts.append(f"\n(script static void sv_view_scan_{group}\n")
        for index,name in chunk:
            parts.append(f'''    (set sv_view_distance (objects_distance_to_flag sv_view_players {name}))
    (if (and (>= sv_view_distance 0) (< sv_view_distance sv_view_nearest))
        (begin (set sv_view_nearest sv_view_distance) (set sv_view_index {index})))
''')
        parts.append(f")\n(script static void sv_view_apply_{group}\n")
        for index,name in chunk:
            parts.append(f"    (if (= sv_view_index {index}) (camera_set {name} 6))\n")
        parts.append(")\n")
    parts.append("\n(script static void sv_follow\n    (set sv_view_players (players))\n    (set sv_view_nearest 100000)\n    (set sv_view_index -1)\n")
    for group in range(len(chunks)): parts.append(f"    (sv_view_scan_{group})\n")
    parts.append("    (if (and (>= sv_view_index 0) (!= sv_view_index sv_view_current))\n        (begin\n            (set sv_view_current sv_view_index)\n")
    for group,chunk in enumerate(chunks):
        parts.append(f"            (if (and (>= sv_view_index {chunk[0][0]}) (<= sv_view_index {chunk[-1][0]})) (sv_view_apply_{group}))\n")
    parts.append("        )))\n(script continuous sv_view_clock\n    (sleep 3)\n    (if (and sv_running (not sv_finished)) (sv_follow)))\n")
    return ''.join(parts)

def contract():
    return {
        'status': 'native scenario; overhead and auto-fire revision in runtime validation',
        'scenario': r'levels\survivors\last_stand\last_stand',
        'squads': [dict(name=n, max_members=c, unlock_seconds=s, xp_per_death=x)
                   for n,c,s,x in SQUADS],
        'objective': 'sv_hunt',
        'controls': 'bird-eye camera; movement with automatic nearest-enemy attacks',
        'auto_fire': {'range_world_units':12,'interval_ticks':12,'base_damage':12,'damage_per_needler_rank':8},
        'trigger_volumes': ['sv_pad_needler','sv_pad_aegis','sv_pad_vitality','sv_extraction'],
        'starting_profiles': ['sv_start','sv_needler_1','sv_needler_2','sv_needler_3'],
        'cutscene_titles': TITLES,
        'player_base_vitality': {'body':45,'shield':70},
        'max_alive':36, 'run_seconds':1200, 'extraction_grace_seconds':60,
        'needler_tiers': [
            {'profile':'sv_needler_1','projectiles_per_shot':1,'reserve_rounds':180},
            {'profile':'sv_needler_2','projectiles_per_shot':2,'reserve_rounds':240},
            {'profile':'sv_needler_3','projectiles_per_shot':3,'reserve_rounds':360}],
        'authoring_required': ['campaign scenario and navigable arena BSP',
            'AI squads, firing positions and objective task covering arena',
            'nonoverlapping, visually marked upgrade pads and extraction beacon',
            'starting profiles and private copies of Needler weapon tags',
            'cutscene title strings', 'script compilation in Sapien',
            'cache compilation and MCC mod metadata', 'actual playtest']}

if __name__ == '__main__':
    out = ROOT/'source'
    out.mkdir(exist_ok=True)
    (out/'last_stand.hsc').write_text(generate(), encoding='utf-8')
    (ROOT/'scenario-contract.json').write_text(json.dumps(contract(),indent=2)+'\n',encoding='utf-8')
    print('Generated HaloScript source and authoring contract. No Halo compilation performed.')

