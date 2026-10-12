"""Native HSC emission helpers. Data is normalized by generate_progression.py."""
from itertools import product

# Native map units: a new anchor must be this much nearer before a pan changes.
CAMERA_SWITCH_MARGIN = 0.35

class HSC:
    def __init__(self): self.globals=[]; self.scripts=[]
    def global_(self, kind, name, value): self.globals.append(f'(global {kind} {name} {value})')
    def script(self, name, body, kind='static void'):
        self.scripts.append(f'(script {kind} {name}\n{body}\n)')
    def render(self):
        return '; LAST STAND v0.4. Generated native progression. Do not hand edit.\n'+'\n'.join(self.globals+self.scripts)+'\n'

def expr(base, terms):
    out=str(base)
    for rank,scale in terms:
        if scale: out=f'(+ {out} (* {rank} {scale}))'
    return out

def chunks(items, size=10):
    return [items[i:i+size] for i in range(0,len(items),size)]

def dispatch(h, name, selector, cases):
    """Short functions avoid the native interpreter's shallow expression stack."""
    calls=[]
    for i,chunk in enumerate(chunks(cases)):
        child=f'{name}_{i}'
        h.script(child,'\n'.join(f'(if (= {selector} {key}) {body})' for key,body in chunk))
        calls.append(f'({child})')
    h.script(name,'\n'.join(calls))

def cameras(h, stages):
    h.global_('short','sv_view_index',-1); h.global_('short','sv_view_current',-1)
    h.global_('real','sv_view_distance',0); h.global_('real','sv_view_nearest',100000)
    h.global_('real','sv_view_current_distance',-1)
    h.global_('boolean','sv_view_refresh','false')
    h.global_('object_list','sv_view_players','(players)')
    all_apply=[]
    for stage in stages:
        num=stage['number']; scans=[]
        for chunk_i,chunk in enumerate(chunks(list(enumerate(stage['cameras'])))):
            name=f'sv_s{num}_scan_{chunk_i}'; body=[]
            for index,cam in chunk:
                camname=cam['name']; key=num*1000+index
                body.append(f'''(set sv_view_distance (objects_distance_to_flag sv_view_players {camname}))
(if (= sv_view_current {key}) (set sv_view_current_distance sv_view_distance))
(if (and (>= sv_view_distance 0) (< sv_view_distance sv_view_nearest))
    (begin (set sv_view_nearest sv_view_distance) (set sv_view_index {key})))''')
                all_apply.append((key,f'(camera_set {camname} 6)'))
            h.script(name,'\n'.join(body)); scans.append(f'({name})')
        h.script(f'sv_s{num}_scan','\n'.join(scans))
    dispatch(h,'sv_view_apply','sv_view_index',all_apply)
    h.script('sv_follow','''(set sv_view_players (players))
(set sv_view_nearest 100000)
(set sv_view_current_distance -1)
(set sv_view_index -1)
'''+ '\n'.join(f"(if (= sv_stage {s['number']}) (sv_s{s['number']}_scan))" for s in stages)+f'''
(if (>= sv_view_index 0)
    (begin
        (if (or (< sv_view_current_distance 0)
                (< (+ sv_view_nearest {CAMERA_SWITCH_MARGIN}) sv_view_current_distance))
            (begin (set sv_view_current sv_view_index) (set sv_view_refresh true)))
        (if sv_view_refresh
            (begin (set sv_view_index sv_view_current) (sv_view_apply)))))
(set sv_view_refresh false)''')

def enemies(h, stages):
    squads=[sq for s in stages for sq in s['squads']]
    for sq in squads: h.global_('short',sq['name']+'_prev',0)
    h.global_('short','sv_now',0);h.global_('short','sv_total',0);h.global_('short','sv_cap',36)
    h.global_('boolean','sv_spawn_clear','false')
    h.global_('real','sv_spawn_distance',-1)
    h.global_('object_list','sv_spawn_players','(players)')
    h.script('sv_clear_enemies','(ai_erase sv_hostiles)\n'+'\n'.join(f"(set {sq['name']}_prev 0)" for sq in squads))
    for s in stages:
        num=s['number']; observe=[]; spawn=['(set sv_total (ai_living_count sv_hostiles))','(set sv_spawn_players (players))']
        for sq in s['squads']:
            name,count,reward,start=[sq[k] for k in ('name','count','xp','unlock_seconds')]
            observe.append(f'''(set sv_now (ai_living_count {name}))
(if (< sv_now {name}_prev)
    (set sv_xp (+ sv_xp (* (* (- {name}_prev sv_now) {reward}) sv_xp_scale))))
(set {name}_prev sv_now)''')
        for sq in reversed(s['squads']):
            name,count,start=[sq[k] for k in ('name','count','unlock_seconds')]
            # Legacy layouts have no placement flags. Newly authored layouts
            # provide exactly one flag per slot; malformed partial lists fail.
            flags=sq.get('spawn_flags',[])
            if 'spawn_flags' in sq:
                assert len(flags)==count and len(set(flags))==count,(name,'incomplete spawn flags')
            checks=[]
            for ci,flag_chunk in enumerate(chunks(flags,6)):
                helper=f'{name}_clear_{ci}'
                h.script(helper,'\n'.join(f'''(set sv_spawn_distance (objects_distance_to_flag sv_spawn_players {flag}))
(if (< sv_spawn_distance 2) (set sv_spawn_clear false))''' for flag in flag_chunk))
                checks.append(f'({helper})')
            h.script(f'{name}_clear','(set sv_spawn_clear true)\n'+'\n'.join(checks))
            spawn.append(f'''(if (and (>= sv_stage_seconds {start}) (= (ai_living_count {name}) 0)
    (<= (+ sv_total {count}) sv_cap))
    (begin
        ({name}_clear)
        (if sv_spawn_clear (begin
        (ai_erase {name}) (ai_place {name} {count})
        (ai_set_team {name} covenant)
        (ai_set_objective {name} {s['objective']})
        (ai_magically_see_object {name} (sv_player))
        (set {name}_prev (ai_living_count {name}))
        (set sv_total (+ sv_total {name}_prev))))))''')
        h.script(f'sv_s{num}_observe','\n'.join(observe))
        h.script(f'sv_s{num}_spawn','\n'.join(spawn))
    h.script('sv_observe','\n'.join(f"(if (= sv_stage {s['number']}) (sv_s{s['number']}_observe))" for s in stages))
    h.script('sv_spawn','\n'.join(f"(if (= sv_stage {s['number']}) (sv_s{s['number']}_spawn))" for s in stages))

def combat(h, weapons, nodes):
    h.global_('object_list','sv_actor_list','(players)');h.global_('object_list','sv_players','(players)')
    for n in ('sv_target','sv_candidate'):h.global_('object',n,'none')
    for n in ('sv_range','sv_nearest','sv_distance'):h.global_('real',n,0)
    h.global_('long','sv_shots',0)
    max_targets=max(int(w['base']['targets']+sum(max(0,e['per_rank'])*n['max_rank'] for n in nodes if n['weapon']==key for e in n['effects'] if e['stat']=='targets')) for key,w in weapons.items())
    assert max_targets<=12
    for i in range(max_targets):h.global_('object',f'sv_hit{i}','none')
    scan=[]
    for ci,indices in enumerate(chunks(list(range(64)),6)):
        body=[]
        for i in indices:
            exclude=' '.join(f'(!= sv_candidate sv_hit{j})' for j in range(max_targets))
            body.append(f'''(set sv_candidate (list_get sv_actor_list {i}))
(if (and (> (object_get_health sv_candidate) 0) {exclude})
    (begin (set sv_distance (objects_distance_to_object sv_players sv_candidate))
        (if (and (>= sv_distance 0) (< sv_distance sv_nearest))
            (begin (set sv_target sv_candidate) (set sv_nearest sv_distance)))))''')
        h.script(f'sv_target_scan_{ci}','\n'.join(body));scan.append(f'(sv_target_scan_{ci})')
    h.script('sv_find_target','(set sv_target none)\n(set sv_nearest sv_range)\n'+'\n'.join(scan))
    h.script('sv_clear_hits','\n'.join(f'(set sv_hit{i} none)' for i in range(max_targets)))
    damage_values={}
    for key,w in weapons.items():
        p='sv_w_'+key
        for field,base in w['base'].items():
            h.global_('real' if field in ('range','damage') else 'short',p+'_'+field,base)
        h.global_('short',p+'_clock',3)
        damage_nodes=[n for n in nodes if n['weapon']==key and any(e['stat']=='damage' for e in n['effects'])]
        values={w['base']['damage']}
        for node in damage_nodes:
            scale=sum(e['per_rank'] for e in node['effects'] if e['stat']=='damage')
            values={v+rank*scale for v in values for rank in range(node['max_rank']+1)}
        values=sorted(values);damage_values[key]=values
        cases=[]
        for value in values:
            assert int(value)==value
            cases.append((int(value),f'(damage_object_effect "objects\\survivors\\v3\\{key}_d{int(value)}" sv_target)'))
        dispatch(h,p+'_damage',p+'_damage',cases)
        # Function and global cannot share a name in HSC; dispatch function gets a verb.
        h.scripts=[x.replace(f'(script static void {p}_damage\n',f'(script static void {p}_apply_damage\n') for x in h.scripts]
        hitbody=[]
        for i in range(max_targets):
            hitbody.append(f'''(if (> {p}_targets {i})
    (begin (sv_find_target)
        (if (> (object_get_health sv_target) 0)
            (begin
                (set sv_hit{i} sv_target)
                (effect_new_on_object_marker "objects\\survivors\\v3\\impact_{key}" sv_target "")
                ({p}_apply_damage)
                (set sv_shots (+ sv_shots 1))))))''')
        h.script(p+'_fire',f'(set sv_range {p}_range)\n(sv_clear_hits)\n'+'\n'.join(hitbody))
        h.script(p+'_tick',f'''(if (> {w['unlock_global']} 0)
    (begin (set {p}_clock (- {p}_clock 3))
        (if (<= {p}_clock 0)
            (begin (set {p}_clock (+ {p}_clock {p}_cadence_ticks)) ({p}_fire)))))''')
    h.script('sv_autofire','(set sv_players (players))\n(set sv_actor_list (ai_actors sv_hostiles))\n'+'\n'.join(f'(sv_w_{key}_tick)' for key in weapons))
    return damage_values
