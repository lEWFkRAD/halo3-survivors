"""Execute the emitted HSC subset against a fake engine; not a Halo compiler."""
import re
import operator
from pathlib import Path
import json

class Symbol(str): pass

def parse(text):
    tokens = re.findall(r'"[^"\n]*"|[()]|[^\s()]+',re.sub(r';[^\n]*','',text))
    stack=[[]]
    for t in tokens:
        if t=='(':
            child=[]; stack[-1].append(child); stack.append(child)
        elif t==')':
            if len(stack)==1: raise ValueError('Unexpected closing parenthesis')
            stack.pop()
        else:
            try: value=float(t) if '.' in t else int(t)
            except ValueError:
                value={'true':True,'false':False}.get(t, t[1:-1] if t.startswith('"') else Symbol(t))
            stack[-1].append(value)
    if len(stack)!=1: raise ValueError('Unclosed parenthesis')
    return stack[0]

class VM:
    def __init__(self):
        root=Path(__file__).resolve().parents[1]
        self.contract=json.loads((root/'scenario-contract.json').read_text())
        self.globals={}; self.scripts={}; self.living={s['name']:0 for s in self.contract['squads']}
        self.health=1.; self.shield=1.; self.player_count=1; self.volumes=set()
        self.calls=[]; self.spawns=[]; self.won=False; self.lost=False
        self.max_vitality=(45,70)
        self.actors={}; self.actor_health={}; self.distances={}; self.camera_distances={}
        for form in parse((root/'source/last_stand.hsc').read_text()):
            if form[0]=='global':
                if len(form)!=4: raise ValueError('Bad global')
                self.globals[form[2]]=form[3]
            elif form[0]=='script':
                name_idx=3 if form[1]=='static' else 2
                self.scripts[form[name_idx]]=form[name_idx+1:]
            else: raise ValueError(f'Invalid top-level form: {form[0]}')
    def run(self,name):
        result=None
        for x in self.scripts[name]: result=self.eval(x)
        return result
    def eval(self,x):
        if not isinstance(x,list):
            return self.globals.get(x,x) if isinstance(x,Symbol) else x
        op,*args=x
        if op=='set':
            if args[0] not in self.globals: raise ValueError('Undeclared global')
            self.globals[args[0]]=self.eval(args[1]); return None
        if op=='if':
            if len(args) not in (2,3): raise ValueError('Bad if arity')
            return self.eval(args[1]) if self.eval(args[0]) else self.eval(args[2]) if len(args)==3 else None
        if op=='cond':
            for branch in args:
                if self.eval(branch[0]):
                    result=None
                    for item in branch[1:]: result=self.eval(item)
                    return result
            return None
        if op=='begin':
            result=None
            for a in args: result=self.eval(a)
            return result
        if op=='and': return all(self.eval(a) for a in args)
        if op=='or': return any(self.eval(a) for a in args)
        if op=='not': return not self.eval(args[0])
        if op in self.scripts:
            if args: raise ValueError('Unexpected script arguments')
            return self.run(op)
        a=[self.eval(v) for v in args]
        operators={'+':operator.add,'-':operator.sub,'*':operator.mul,'/':operator.truediv,'<':operator.lt,
                   '>':operator.gt,'<=':operator.le,'>=':operator.ge,'=':operator.eq,
                   '!=':operator.ne,'min':min}
        if op in operators: return operators[op](*a)
        if op=='players': return ['player']*self.player_count
        if op=='list_get': return a[0][a[1]] if a[1]<len(a[0]) else None
        if op=='list_count': return len(a[0])
        if op=='unit': return a[0]
        if op=='unit_get_health': return self.health if a[0] else -1
        if op=='unit_get_shield': return self.shield*self.max_vitality[1] if a[0] else -1
        if op=='volume_test_object':
            if a[0] not in self.contract['trigger_volumes']: raise ValueError('Unknown volume')
            return a[0] in self.volumes and a[1] is not None
        if op=='objects_distance_to_flag':
            if str(a[1]).startswith('sv_view_'): return self.camera_distances.get(a[1],1000.) if a[0] else -1
            volume={'sv_beacon_needler':'sv_pad_needler','sv_beacon_aegis':'sv_pad_aegis','sv_beacon_vitality':'sv_pad_vitality','sv_beacon_exit':'sv_extraction'}[a[1]]
            return -1 if not a[0] else 0.5 if volume in self.volumes else 10.
        if op=='ai_actors': return self.actors.get(a[0],[])
        if op=='object_get_health': return self.actor_health.get(a[0],-1)
        if op=='objects_distance_to_object': return self.distances.get(a[1],-1) if a[0] else -1
        if op=='ai_living_count': return self.living[a[0]]
        if op=='ai_erase':
            if self.living[a[0]]: raise AssertionError('Erased a living cohort')
        elif op=='ai_place':
            self.living[a[0]]=a[1]; self.spawns.append(tuple(a))
            if sum(self.living.values())>self.globals['sv_cap']: raise AssertionError('Actor cap exceeded')
        elif op=='damage_object': self.actor_health[a[0]]-=a[2]
        elif op=='damage_object_effect': self.actor_health[a[1]]-=12+8*int(a[0][-1])
        elif op=='effect_new_on_object_marker': pass
        elif op=='object_set_shield': self.shield=a[1]
        elif op=='units_set_maximum_vitality': self.max_vitality=tuple(a[1:])
        elif op=='units_set_current_vitality': self.health=1.; self.shield=1.
        elif op=='unit_add_equipment':
            if a[1] not in self.contract['starting_profiles']: raise ValueError('Unknown profile')
        elif op=='cinematic_set_chud_objective':
            if a[0] not in self.contract['cutscene_titles']: raise ValueError('Unknown title')
        elif op=='ai_set_objective':
            if a[1]!=self.contract['objective']: raise ValueError('Unknown objective')
        elif op=='game_won': self.won=True
        elif op=='game_lost': self.lost=a[0]
        elif op=='sleep_until':
            if not a[0]: raise ValueError('This mock cannot wait for a player')
        elif op not in ('sleep','ai_set_team','ai_magically_see_object','hud_enable_training','hud_activate_team_nav_point_flag','camera_control','camera_set_relative','camera_set_field_of_view','player_enable_input','chud_show_crosshair','camera_set','player_camera_control','object_set_facing','chud_show_weapon_stats','chud_show_grenades'):
            raise ValueError(f'Unmodelled engine function: {op}')
        self.calls.append((str(op),a))
    def boot(self): self.run('sv_boot')
    def tick(self,n=1):
        for _ in range(n): self.run('sv_step')
