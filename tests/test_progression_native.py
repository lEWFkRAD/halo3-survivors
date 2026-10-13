"""Behavior tests for generated progression, not substitutes for native compilation."""
from pathlib import Path
import json,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hsc_vm import VM,parse,Symbol
from generate_progression import build,normalized_catalog,node_label

class ProgressionVM(VM):
    def __init__(self):
        super().__init__()
        self.data=normalized_catalog();self.layout=json.loads((ROOT/'progression-layout.json').read_text())
        source,titles,self.damage_values=build(self.data,self.layout)
        self.contract['cutscene_titles']=titles
        self.contract['starting_profiles']=['sv_start']
        self.globals={};self.scripts={};self.input=set();self.held_input=set();self.ai_enabled=True;self.teleports=[]
        self.movement_disabled=False;self.player_protected=False
        self.logical_ticks=0;self.notice_events=[];self.page_events=[]
        self.price_events=[];self.wallet_events=[];self.training_enabled=False;self.training_text=None;self.training_shown=False
        self.queried_since_reset=set()
        self.living={s['name']:0 for st in self.layout['stages'] for s in st['squads']}
        for form in parse(source):
            if form[0]=='global':
                assert form[2] not in self.globals
                self.globals[form[2]]=form[3]
            else:
                i=3 if form[1]=='static' else 2
                assert form[i] not in self.scripts
                self.scripts[form[i]]=form[i+1:]
        assert not set(self.globals).intersection(self.scripts)
        self.byid={n['id']:n for n in self.data['nodes']}
    def eval(self,x):
        if not isinstance(x,list):return super().eval(x)
        op,*args=x
        if op in ('max',):return max(self.eval(a) for a in args)
        if op=='sleep':
            self.logical_ticks+=self.eval(args[0]);return None
        if op.startswith('player_action_test_'):
            if op=='player_action_test_reset':
                self.input.clear();self.queried_since_reset.clear();return None
            # Reset clears accumulated tests, while physical held buttons are
            # sampled again next frame by the native engine.
            action=op.removeprefix('player_action_test_')
            self.queried_since_reset.add(action)
            return action in self.input | self.held_input
        if op=='ai_living_count' and args[0]=='sv_hostiles':return sum(self.living.values())
        if op=='ai_erase':
            if args[0]=='sv_hostiles':
                for k in self.living:self.living[k]=0
                self.actors.clear();self.actor_health.clear()
            else:self.living[args[0]]=0
            return None
        if op=='ai_actors' and args[0]=='sv_hostiles':return [a for group in self.actors.values() for a in group]
        if op=='ai_enable':self.ai_enabled=self.eval(args[0]);return None
        if op=='player_disable_movement':
            self.movement_disabled=self.eval(args[0]);return None
        if op in ('object_cannot_take_damage','object_can_take_damage'):
            targets=self.eval(args[0])
            if 'player' in targets:self.player_protected=op=='object_cannot_take_damage'
            self.calls.append((op,[targets]));return None
        if op=='objects_distance_to_flag':
            return self.camera_distances.get(args[1],10.) if self.eval(args[0]) else -1
        if op=='object_teleport':self.teleports.append(str(args[1]));return None
        if op=='damage_object_effect':
            path,target=[self.eval(a) for a in args]
            self.actor_health[target]-=int(path.rsplit('_d',1)[1]);self.calls.append((op,[path,target]));return None
        if op=='cinematic_set_title':
            values=[self.eval(a) for a in args]
            events=(self.wallet_events if str(values[0]).startswith('sv_points_') else
                    self.price_events if str(values[0]).startswith('sv_cost_') else self.notice_events)
            events.append((self.logical_ticks,str(values[0])))
            self.calls.append((op,values));return None
        if op=='cinematic_set_chud_objective':
            value=str(self.eval(args[0]))
            assert value in self.contract['cutscene_titles'],value
            self.calls.append((op,[value]));return None
        if op=='hud_enable_training':
            self.training_enabled=self.eval(args[0]);return None
        if op=='hud_show_training_text':
            self.training_shown=self.eval(args[0]);return None
        if op=='hud_set_training_text':
            self.training_text=str(self.eval(args[0]))
            if self.training_text!='sv_tree_unavailable':
                self.page_events.append((self.logical_ticks,self.training_text))
            self.calls.append((op,[self.training_text]));return None
        if op in ('log_print','player_disable_weapon_pickup','core_save_name'):
            self.calls.append((op,[self.eval(a) for a in args]));return None
        if op=='ai_set_objective':
            assert args[1] in [s['objective'] for s in self.layout['stages']];return None
        return super().eval(x)
    def buy(self,node_id):
        self.globals['sv_selection']=next(i for i,n in enumerate(self.data['nodes']) if n['id']==node_id)
        self.run('sv_purchase')
    def rank(self,node_id):return self.globals[self.byid[node_id]['native_global']]
    def setrank(self,node_id,rank):self.globals[self.byid[node_id]['native_global']]=rank
    def menu_sample(self,*held):
        self.held_input=set(held);self.run('sv_fast_clock')
    def fast_frames(self,count):
        for _ in range(count):self.run('sv_fast_clock')


class DeferredEraseProgressionVM(ProgressionVM):
    """Native ai_erase queues deletion until an enabled AI simulation update."""
    def __init__(self):
        super().__init__()
        self.pending_erases=set()

    def eval(self,x):
        if isinstance(x,list) and x[0]=='ai_erase':
            group=self.eval(x[1])
            groups=self.living if group=='sv_hostiles' else [group]
            self.pending_erases.update(name for name in groups if self.living[name]>0)
            return None
        return super().eval(x)

    def simulation_tick(self):
        if not self.ai_enabled:return
        for group in self.pending_erases:
            self.living[group]=0
            for actor in self.actors.pop(group,[]):
                self.actor_health.pop(actor,None)
                self.distances.pop(actor,None)
        self.pending_erases.clear()


class NativeProgressionTests(unittest.TestCase):
    def setUp(self):self.v=ProgressionVM();self.v.boot()
    def test_armory_checkpoint_once_per_entry_or_purchase(self):
        v=self.v
        saves=lambda: [c for c in v.calls if c[0]=='core_save_name']
        v.fast_frames(20)
        self.assertEqual(len(saves()),1)
        self.assertFalse(v.globals['sv_save_dirty'])
        v.buy('needler.damage');v.fast_frames(2)
        self.assertEqual(len(saves()),2)
        v.run('sv_close_menu');v.fast_frames(20)
        self.assertEqual(len(saves()),2)
        v.run('sv_open_menu');v.fast_frames(2)
        self.assertEqual(len(saves()),3)
    def test_restore_repairs_camera_and_ai_without_resetting_run(self):
        v=self.v
        v.globals.update(sv_restore_clock=0,sv_xp=80,sv_seconds=40,sv_shots=67,sv_ar_u=1)
        v.ai_enabled=True
        for _ in range(10):v.run('sv_restore_controls')
        self.assertFalse(v.ai_enabled)
        self.assertTrue(any(op=='camera_set' for op,args in v.calls))
        self.assertEqual([v.globals[k] for k in ('sv_xp','sv_seconds','sv_shots','sv_ar_u')],[80,40,67,1])
    def test_checkpoint_never_runs_during_combat_or_after_ending(self):
        v=self.v;v.run('sv_close_menu');v.run('sv_checkpoint')
        self.assertFalse(any(c[0]=='core_save_name' for c in v.calls))
        v.globals.update(sv_menu_open=True,sv_finished=True);v.run('sv_checkpoint')
        self.assertFalse(any(c[0]=='core_save_name' for c in v.calls))
    def test_start_pauses_for_choice(self):
        v=self.v;self.assertTrue(v.globals['sv_menu_open']);self.assertFalse(v.ai_enabled)
        v.tick(30);self.assertEqual(v.globals['sv_seconds'],0);self.assertFalse(v.spawns)
    def test_cannot_overspend_or_skip_prerequisite(self):
        v=self.v
        n=next(n for n in v.data['nodes'] if n['prerequisites'])
        v.globals['sv_tokens']=50;v.globals['sv_stage']=4
        for p in n['prerequisites']:v.setrank(p['id'],0)
        v.buy(n['id']);self.assertEqual(v.rank(n['id']),0);self.assertEqual(v.globals['sv_tokens'],50)
        for p in n['prerequisites']:v.setrank(p['id'],p['rank'])
        v.globals['sv_tokens']=0;v.buy(n['id']);self.assertEqual(v.rank(n['id']),0)
    def test_all_nodes_purchase_and_recompute(self):
        v=self.v
        for i,n in enumerate(v.data['nodes']):
            for other in v.data['nodes']:v.setrank(other['id'],0)
            for p in n['prerequisites']:v.setrank(p['id'],p['rank'])
            v.globals['sv_tokens']=50;v.globals['sv_stage']=4
            for r,cost in enumerate(n['costs'],1):
                old=v.globals['sv_tokens'];v.buy(n['id'])
                self.assertEqual(v.rank(n['id']),r,n['id']);self.assertEqual(v.globals['sv_tokens'],old-cost)
            old=v.globals['sv_tokens'];v.buy(n['id']);self.assertEqual(v.globals['sv_tokens'],old)
    def test_exclusive_branches_and_stage_gate(self):
        v=self.v;v.globals['sv_tokens']=50
        n=next(n for n in v.data['nodes'] if n['stage']>1 and not n['prerequisites'])
        v.buy(n['id']);self.assertEqual(v.rank(n['id']),0)
        n=next(n for n in v.data['nodes'] if n['exclusive_group'])
        alt=next(a for a in v.data['nodes'] if a['id']!=n['id'] and a['exclusive_group']==n['exclusive_group'])
        for p in n['prerequisites']:v.setrank(p['id'],p['rank'])
        v.setrank(alt['id'],1);v.globals['sv_stage']=4
        v.buy(n['id']);self.assertEqual(v.rank(n['id']),0)
    def test_all_ranks_survive_stage_transition_no_despawn_xp(self):
        v=self.v
        expected={n['native_global']:n['max_rank'] for n in v.data['nodes']}
        v.globals.update(expected);v.globals['sv_xp']=17
        for s in v.layout['stages'][0]['squads']:
            v.living[s['name']]=s['count'];v.globals[s['name']+'_prev']=s['count']
        v.run('sv_advance_stage');v.run('sv_observe')
        self.assertEqual(v.globals['sv_stage'],2);self.assertEqual(v.globals['sv_xp'],17)
        self.assertEqual({k:v.globals[k] for k in expected},expected)
        self.assertEqual(v.teleports[-1],'sv_s2_center');self.assertTrue(v.globals['sv_menu_open'])
    def test_enemy_timing_and_cap(self):
        v=self.v
        for stage in v.layout['stages']:
            v.run('sv_clear_enemies');v.globals['sv_stage']=stage['number'];v.globals['sv_stage_seconds']=0
            v.run('sv_spawn')
            for s in stage['squads']:
                if s['unlock_seconds']>0:self.assertEqual(v.living[s['name']],0)
            self.assertLessEqual(sum(v.living.values()),36)
            v.globals['sv_stage_seconds']=250;v.run('sv_spawn');self.assertLessEqual(sum(v.living.values()),36)
    def test_automatic_weapon_branches_hit_unique_targets(self):
        v=self.v
        for n in v.data['nodes']:v.setrank(n['id'],0)
        for key,w in v.data['weapons'].items():
            v.globals[w['unlock_global']]=1
        v.run('sv_recompute')
        v.actors['test']=['a','b','c','d'];v.actor_health={k:10000 for k in v.actors['test']}
        v.distances={k:1+i*.1 for i,k in enumerate(v.actors['test'])}
        v.run('sv_autofire')
        damage=[a for op,a in v.calls if op=='damage_object_effect']
        self.assertGreaterEqual(len(damage),6)
        self.assertEqual(len({a[0].split('\\')[-1].split('_d')[0] for a in damage}),6)
        shots=v.globals['sv_shots'];v.run('sv_autofire');self.assertEqual(v.globals['sv_shots'],shots)
    def test_menu_inputs_and_resume(self):
        v=self.v;v.menu_sample();v.menu_sample('jump');self.assertEqual(v.globals['sv_selection'],1)
        v.menu_sample();self.assertEqual(v.globals['sv_selection'],1)
        v.menu_sample('jump','melee');self.assertEqual(v.globals['sv_selection'],7)
        v.menu_sample();v.menu_sample('rotate_weapons');self.assertFalse(v.globals['sv_menu_open'])
        self.assertTrue(v.ai_enabled);v.tick();self.assertEqual(v.globals['sv_seconds'],1)
    def test_open_menu_ignores_held_opening_chord_until_release(self):
        v=self.v
        for _ in range(8):v.menu_sample('jump','melee')
        self.assertEqual(v.globals['sv_selection'],0);self.assertEqual(v.globals['sv_tokens'],3)
        self.assertTrue(v.globals['sv_menu_latched'])
        v.menu_sample();v.menu_sample('jump')
        self.assertEqual(v.globals['sv_selection'],1)
    def test_held_navigation_requires_full_release_between_actions(self):
        v=self.v;v.menu_sample()
        for _ in range(12):v.menu_sample('jump')
        self.assertEqual(v.globals['sv_selection'],1)
        # Rolling from one key into another without releasing the entire chord
        # must not turn one physical press into another menu action.
        v.menu_sample('jump','melee');v.menu_sample('melee')
        self.assertEqual(v.globals['sv_selection'],1)
        v.menu_sample();v.menu_sample('jump','melee')
        self.assertEqual(v.globals['sv_selection'],7)
        v.menu_sample();v.menu_sample('melee')
        self.assertEqual(v.globals['sv_selection'],6)
    def test_held_purchase_buys_exactly_one_rank(self):
        v=self.v;v.globals['sv_selection']=1;v.globals['sv_tokens']=10;v.menu_sample()
        for _ in range(20):v.menu_sample('primary_trigger')
        self.assertEqual(v.rank('needler.damage'),1);self.assertEqual(v.globals['sv_tokens'],9)
        v.menu_sample();v.menu_sample('primary_trigger')
        self.assertEqual(v.rank('needler.damage'),2);self.assertEqual(v.globals['sv_tokens'],8)
    def test_menu_pauses_ai_keeps_movement_and_close_announces_current_stage(self):
        v=self.v;self.assertFalse(v.movement_disabled);self.assertFalse(v.ai_enabled)
        v.globals['sv_stage']=3;v.menu_sample();v.menu_sample('rotate_weapons')
        self.assertFalse(v.movement_disabled);self.assertFalse(v.globals['sv_menu_latched'])
        self.assertFalse(v.globals['sv_menu_any'])
        v.fast_frames(30)
        titles=[args[0] for op,args in v.calls if op=='cinematic_set_title']
        self.assertEqual(titles[-1],'sv_stage_3')
    def test_jump_melee_chord_reopens_then_selects_category_after_release(self):
        v=self.v;v.run('sv_close_menu')
        v.menu_sample('jump','melee')
        self.assertTrue(v.globals['sv_menu_open']);self.assertFalse(v.ai_enabled)
        for _ in range(8):v.menu_sample('jump','melee')
        self.assertEqual(v.globals['sv_selection'],0)
        v.menu_sample();v.menu_sample('jump','melee')
        self.assertEqual(v.globals['sv_selection'],7)
        self.assertFalse(v.movement_disabled)
    def test_all_four_action_queries_are_primed_after_each_reset_boundary(self):
        v=self.v;watched={'jump','melee','primary_trigger','rotate_weapons'}
        self.assertEqual(v.queried_since_reset,watched)
        for held in [(),('jump',),(),('primary_trigger',),(),('rotate_weapons',),()]:
            v.menu_sample(*held)
            self.assertEqual(v.queried_since_reset,watched)
    def test_help_and_live_wallet_repeat_without_input(self):
        v=self.v;v.calls.clear()
        for _ in range(180):v.menu_sample()
        titles=[str(args[0]) for op,args in v.calls if op=='cinematic_set_title' and not str(args[0]).startswith(('sv_points_','sv_cost_'))]
        self.assertTrue(titles and set(titles)=={'sv_controls'})
        self.assertEqual(len(v.wallet_events),18)
        self.assertTrue(all(name=='sv_points_3' for _,name in v.wallet_events))
        self.assertTrue(all(b[0]-a[0]==30 for a,b in zip(v.wallet_events,v.wallet_events[1:])))
        self.assertTrue(all(b[0]-a[0]>=90 for a,b in zip(v.notice_events,v.notice_events[1:])))
        self.assertEqual(v.globals['sv_seconds'],0)
    def test_rapid_statuses_show_only_latest_when_previous_notice_expires(self):
        v=self.v;self.assertEqual(v.notice_events,[(0,'sv_stage_1')])
        v.buy('needler.damage')  # Would report purchase success.
        v.buy('shotgun.unlock')  # Latest status reports the stage restriction.
        self.assertEqual(v.notice_events,[(0,'sv_stage_1')])
        # Notice delivery must continue even when gameplay has been stopped.
        v.globals['sv_running']=False;v.fast_frames(29)
        self.assertEqual(v.notice_events,[(0,'sv_stage_1')])
        v.fast_frames(1)
        self.assertEqual(v.notice_events,[(0,'sv_stage_1'),(90,'sv_stage_locked')])
        v.fast_frames(60)
        self.assertEqual(len(v.notice_events),2)
    def test_node_selection_updates_immediately_while_status_slot_is_busy(self):
        v=self.v;v.calls.clear();before=len(v.notice_events)
        v.run('sv_menu_next')
        objectives=[args[0] for op,args in v.calls if op=='cinematic_set_chud_objective']
        self.assertEqual(objectives,['sv_node_1'])
        self.assertEqual(v.globals['sv_selection'],1)
        self.assertEqual(len(v.notice_events),before)
    def test_status_burst_never_emits_two_titles_inside_one_display_window(self):
        v=self.v;v.globals['sv_running']=False
        for frame in range(120):
            v.globals['sv_tokens']=frame%51
            v.run('sv_show_points')
            v.globals['sv_selected_rank']=frame%4
            v.run('sv_show_rank')
            v.fast_frames(1)
        events=v.notice_events
        self.assertGreater(len(events),3)
        self.assertTrue(all(b[0]-a[0]>=90 for a,b in zip(events,events[1:])),events)
        self.assertTrue(all(name.startswith('sv_rank_') for _,name in events[1:]))
    def test_node_hud_preserves_information_within_line_budget(self):
        v=self.v;titles=v.contract['cutscene_titles']
        self.assertEqual(len(titles),127)
        for i,n in enumerate(v.data['nodes']):
            text=titles[f'sv_node_{i}']
            self.assertLessEqual(len(text),100,n['id'])
            self.assertIn(node_label(n),text)
            self.assertIn('Cost'+'/'.join(map(str,n['costs'])),text)
            self.assertTrue(text.endswith('S'+str(n['stage'])))
            for prerequisite in n['prerequisites']:
                parent=v.byid[prerequisite['id']]
                label=node_label(parent,include_weapon=parent['weapon']!=n['weapon'])
                self.assertIn(label+str(prerequisite['rank']),text)
        self.assertIn('+20%HP',titles['sv_node_42'])
    def test_every_cadence_rank_increases_actual_fire_rate(self):
        for weapon in self.v.data['weapons']:
            counts=[]
            for rank in range(4):
                v=ProgressionVM();v.boot()
                for n in v.data['nodes']:v.setrank(n['id'],0)
                v.setrank(weapon+'.unlock',1);v.setrank(weapon+'.cadence',rank);v.run('sv_recompute')
                v.actors={'test':['target']};v.actor_health={'target':1000000};v.distances={'target':1}
                for _ in range(330):v.run('sv_autofire')
                count=v.globals['sv_shots'];counts.append(count)
                base=v.data['weapons'][weapon]['base']['cadence_ticks']
                reduction=v.byid[weapon+'.cadence']['effects'][0]['per_rank']
                cadence=max(3,base+rank*reduction)
                self.assertEqual(count,1+987//cadence,(weapon,rank))
            self.assertTrue(all(b>a for a,b in zip(counts,counts[1:])),(weapon,counts))
    def test_boundary_checks_only_current_arena_and_preserves_progress(self):
        v=self.v;v.setrank('needler.damage',2);v.globals['sv_xp']=17
        for stage in range(1,5):
            v.globals['sv_stage']=stage
            for other in range(1,5):v.camera_distances[f'sv_s{other}_center']=100
            center=f'sv_s{stage}_center';before=len(v.teleports)
            for distance in (-1,0,21):
                v.camera_distances[center]=distance;v.run('sv_boundary_check')
                self.assertEqual(len(v.teleports),before)
            v.camera_distances[center]=21.01;v.run('sv_boundary_check')
            self.assertEqual(v.teleports[before:],[center])
            self.assertEqual(v.rank('needler.damage'),2);self.assertEqual(v.globals['sv_xp'],17)
            self.assertEqual(v.globals['sv_tokens'],3)
    def test_level_up_pauses_before_spawning_and_keeps_xp_remainder(self):
        v=self.v;v.run('sv_close_menu');v.globals['sv_xp']=130;v.tick()
        self.assertEqual(v.globals['sv_xp'],30);self.assertEqual(v.globals['sv_tokens'],4)
        self.assertTrue(v.globals['sv_menu_open']);self.assertEqual(v.globals['sv_seconds'],0)
    def test_xp_burst_awards_all_levels_in_one_armory_visit(self):
        v=self.v;v.run('sv_close_menu');v.calls.clear();v.globals['sv_xp']=1000.25
        v.tick()
        self.assertEqual(v.globals['sv_level'],6);self.assertEqual(v.globals['sv_threshold'],350)
        self.assertEqual(v.globals['sv_xp'],.25);self.assertEqual(v.globals['sv_tokens'],8)
        self.assertTrue(v.globals['sv_menu_open']);self.assertEqual(v.globals['sv_seconds'],0)
        self.assertEqual(v.globals['sv_stage_seconds'],0);self.assertFalse(v.spawns)
        objectives=[args[0] for op,args in v.calls if op=='cinematic_set_chud_objective']
        self.assertEqual(objectives,['sv_node_0'])
        # Resuming once must return to gameplay, without another earned-level pause.
        v.run('sv_close_menu');v.tick()
        self.assertFalse(v.globals['sv_menu_open']);self.assertEqual(v.globals['sv_seconds'],1)
    def test_batched_levels_preserve_the_existing_wallet_cap(self):
        v=self.v;v.run('sv_close_menu');v.globals.update(sv_tokens=49,sv_xp=1000)
        v.tick()
        self.assertEqual(v.globals['sv_level'],6);self.assertEqual(v.globals['sv_tokens'],50)
        self.assertEqual(v.globals['sv_xp'],0)
        self.assertTrue(v.globals['sv_menu_open']);self.assertEqual(v.globals['sv_seconds'],0)
    def test_batched_levels_match_iterative_costs_at_boundaries_and_large_bursts(self):
        # Independent oracle buys one level at a time, including fractional XP
        # near exact thresholds and bursts that earn far more than ten levels.
        for level in (1,3,20,32766,32767):
            threshold=100+50*(level-1)
            for xp in (0,threshold-.25,threshold,threshold+.25,
                       2*threshold+49.75,2*threshold+50,50000.25):
                with self.subTest(level=level,xp=xp):
                    expected_level=level;expected_threshold=threshold;remainder=xp;wallet=3
                    while expected_level<32767 and remainder>=expected_threshold:
                        remainder-=expected_threshold;expected_threshold+=50
                        expected_level+=1;wallet=min(50,wallet+1)
                    v=ProgressionVM();v.boot();v.run('sv_close_menu')
                    v.globals.update(sv_level=level,sv_threshold=threshold,sv_xp=xp)
                    v.run('sv_level_up')
                    self.assertEqual(v.globals['sv_level'],expected_level)
                    self.assertEqual(v.globals['sv_threshold'],expected_threshold)
                    self.assertEqual(v.globals['sv_xp'],remainder)
                    self.assertEqual(v.globals['sv_tokens'],wallet)
                    self.assertEqual(v.globals['sv_menu_open'],expected_level>level)
    def test_final_stage_completes_without_unloading_the_scenario(self):
        v=self.v;v.run('sv_close_menu');self.assertFalse(v.player_protected)
        v.globals['sv_stage']=4;v.run('sv_advance_stage')
        self.assertTrue(v.globals['sv_finished']);self.assertFalse(v.globals['sv_running'])
        self.assertFalse(v.globals['sv_menu_open'])
        # Native actor deletion is deferred; AI updates must remain enabled to
        # complete ai_erase while running/finished flags stop our gameplay loops.
        self.assertTrue(v.ai_enabled)
        self.assertTrue(v.player_protected);self.assertTrue(v.movement_disabled)
        self.assertFalse(any(op in ('game_won','game_lost') for op,_ in v.calls))
        objectives=[args[0] for op,args in v.calls if op=='cinematic_set_chud_objective']
        self.assertEqual(objectives[-1],'sv_win')
        self.assertIn(('log_print',['LASTSTAND_RUN_COMPLETE']),v.calls)
        self.assertIn('Close and relaunch',v.contract['cutscene_titles']['sv_win'])
    def test_victory_retains_progress_and_stops_gameplay_despite_menu_input(self):
        v=self.v;v.globals['sv_stage']=4;v.run('sv_enter_stage');v.run('sv_close_menu')
        v.setrank('needler.damage',2);v.setrank('assault_rifle.unlock',1);v.run('sv_recompute')
        v.globals.update(sv_xp=17,sv_tokens=5,sv_seconds=1199,sv_stage_seconds=299)
        v.run('sv_spawn');self.assertGreater(sum(v.living.values()),0)
        v.actors={'fixture':['enemy']};v.actor_health={'enemy':1000};v.distances={'enemy':1}
        v.tick()
        self.assertTrue(v.globals['sv_finished']);self.assertEqual(v.globals['sv_seconds'],1200)
        self.assertEqual(v.globals['sv_stage_seconds'],300)
        self.assertEqual(v.globals['sv_xp'],17);self.assertEqual(v.globals['sv_tokens'],5)
        self.assertEqual(v.rank('needler.damage'),2);self.assertEqual(v.rank('assault_rifle.unlock'),1)
        self.assertEqual(sum(v.living.values()),0);self.assertFalse(v.actors)
        gameplay={k:value for k,value in v.globals.items() if k not in ('sv_notice_clock','sv_notice_pending')}
        spawns=list(v.spawns);teleports=list(v.teleports)
        cameras=[args for op,args in v.calls if op=='camera_set']
        for _ in range(60):
            v.tick();v.menu_sample('jump','melee','primary_trigger','rotate_weapons');v.menu_sample()
        self.assertEqual({k:v.globals[k] for k in gameplay},gameplay)
        self.assertEqual(v.spawns,spawns);self.assertEqual(v.teleports,teleports)
        self.assertEqual([args for op,args in v.calls if op=='camera_set'],cameras)
        self.assertFalse(v.globals['sv_menu_open']);self.assertTrue(v.ai_enabled)
        self.assertTrue(v.player_protected);self.assertTrue(v.movement_disabled)
        self.assertEqual(sum(v.living.values()),0)
        self.assertFalse(any(op in ('game_won','game_lost') for op,_ in v.calls))
    def test_victory_drains_deferred_erases_without_restarting_gameplay(self):
        v=DeferredEraseProgressionVM();v.boot();v.run('sv_close_menu')
        group='sv_s4_grunts';actors=[f'ending_grunt_{i}' for i in range(6)]
        v.living[group]=6;v.actors[group]=actors
        v.actor_health.update({actor:1 for actor in actors})
        v.globals.update(sv_stage=4,sv_stage_seconds=299,sv_seconds=1199,sv_xp=17)
        v.globals[group+'_prev']=6
        v.tick()
        self.assertTrue(v.globals['sv_finished']);self.assertFalse(v.globals['sv_running'])
        self.assertFalse(v.globals['sv_menu_open']);self.assertTrue(v.ai_enabled)
        self.assertTrue(v.player_protected);self.assertTrue(v.movement_disabled)
        # Script execution alone cannot make this assertion pass: an enabled
        # engine update is required, reproducing the observed native regression.
        self.assertEqual(v.living[group],6);self.assertEqual(v.pending_erases,{group})
        v.simulation_tick()
        self.assertEqual(sum(v.living.values()),0);self.assertFalse(v.pending_erases)
        self.assertFalse(v.actors);self.assertFalse(v.actor_health)
        state={name:v.globals[name] for name in ('sv_seconds','sv_stage_seconds','sv_xp','sv_shots')}
        spawns=list(v.spawns)
        for _ in range(30):
            v.tick();v.menu_sample('jump','melee','primary_trigger','rotate_weapons')
            v.menu_sample();v.simulation_tick()
        self.assertEqual({name:v.globals[name] for name in state},state)
        self.assertEqual(v.spawns,spawns);self.assertEqual(sum(v.living.values()),0)
        self.assertTrue(v.globals['sv_finished']);self.assertFalse(v.globals['sv_running'])
        self.assertFalse(v.globals['sv_menu_open'])
        self.assertTrue(v.player_protected);self.assertTrue(v.movement_disabled)
    def test_deferred_erasure_does_not_drain_while_ai_is_paused(self):
        v=DeferredEraseProgressionVM();v.boot()
        group='sv_s4_grunts';v.living[group]=6
        v.run('sv_clear_enemies');v.simulation_tick()
        self.assertFalse(v.ai_enabled);self.assertEqual(v.living[group],6)
        self.assertEqual(v.pending_erases,{group})
        v.ai_enabled=True;v.simulation_tick()
        self.assertEqual(v.living[group],0);self.assertFalse(v.pending_erases)
    def test_victory_replaces_pending_menu_notice_without_overlapping_status(self):
        v=self.v;self.assertEqual(v.notice_events,[(0,'sv_stage_1')])
        v.run('sv_show_points');v.globals['sv_stage']=4;v.run('sv_advance_stage')
        objectives=[args[0] for op,args in v.calls if op=='cinematic_set_chud_objective']
        self.assertEqual(objectives[-1],'sv_win')
        v.fast_frames(29);self.assertEqual(v.notice_events,[(0,'sv_stage_1')])
        v.fast_frames(1);self.assertEqual(v.notice_events,[(0,'sv_stage_1'),(90,'sv_win')])
        v.fast_frames(120);self.assertEqual(len(v.notice_events),2)
        self.assertEqual([args[0] for op,args in v.calls if op=='cinematic_set_chud_objective'][-1],'sv_win')

if __name__=='__main__':unittest.main()
