"""Last Stand catalog. Native persistence is same-run stage carry only."""
SCHEMA_VERSION=1
CATALOG_VERSION=1
_DATA=(
 ('needler','Needler','nl',1,0,12,12,12,1,4,1,('seeker','Seeker',{'range':2},'Long Reach',{'range':4,'targets':1}),('crystal','Crystal',{'damage':5},'Crystal Storm',{'damage':12,'cadence_ticks':-1})),
 ('assault_rifle','Assault Rifle','ar',1,2,7,6,14,1,3,1,('marksman','Marksman',{'range':2,'damage':1},'Precision Drill',{'damage':8,'range':3}),('suppressor','Suppressor',{'targets':1},'Fire Team',{'targets':2,'damage':2})),
 ('shotgun','Shotgun','sg',2,3,28,30,6,3,10,3,('breacher','Breacher',{'damage':12},'Breach Charge',{'damage':30,'cadence_ticks':-3}),('sweeper','Sweeper',{'targets':1,'range':.5},'Crowd Control',{'targets':2,'range':1})),
 ('plasma_rifle','Plasma Rifle','pr',2,3,10,9,12,1,4,1,('overcharge','Overcharge',{'damage':6},'Plasma Furnace',{'damage':16,'range':2}),('arc','Arc',{'targets':1},'Arc Network',{'targets':2,'cadence_ticks':-1})),
 ('rocket_launcher','Rocket Launcher','rl',3,5,70,60,16,3,22,5,('demolition','Demolition',{'damage':28},'Demolition Expert',{'damage':70,'cadence_ticks':-5}),('barrage','Barrage',{'targets':1,'cadence_ticks':-2},'Full Salvo',{'targets':2,'cadence_ticks':-6})),
 ('energy_sword','Energy Sword','es',3,5,45,24,3,3,15,2,('duelist','Duelist',{'damage':20},'Executioner',{'damage':50,'cadence_ticks':-2}),('whirlwind','Whirlwind',{'targets':1,'range':.4},'Blade Tempest',{'targets':2,'range':.8})),
)
STAGES=(
 {'number':1,'name':'Landing','duration_seconds':300,'new_enemy_types':['grunts','jackals','brutes']},
 {'number':2,'name':'Incursion','duration_seconds':300,'new_enemy_types':['captains','snipers']},
 {'number':3,'name':'Outbreak','duration_seconds':300,'new_enemy_types':['floodcombat','infection','carrier']},
 {'number':4,'name':'Last Stand','duration_seconds':300,'new_enemy_types':['hunters','chieftain']},
)
def _effects(values):return [{'stat':k,'per_rank':v} for k,v in values.items()]
def _description(values):
 labels={'damage':'damage','cadence_ticks':'attack ticks','range':'range','targets':'targets','health_fraction':'health multiplier','shield_fraction':'shield multiplier','shield_pulse_fraction':'shield per pulse','shield_pulse_ticks':'pulse ticks','xp_fraction':'XP multiplier'}
 return '; '.join(f'{v:+g} {labels[k]}/rank' for k,v in values.items())
def native_catalog():
 nodes=[];weapons={}
 def add(id,name,global_,weapon,stage,costs,requirements=(),effects=None,group=None,scope='run'):
  effects=effects or {}
  nodes.append({'id':id,'name':name,'native_global':global_,'weapon':weapon,'max_rank':len(costs),'costs':list(costs),'stage':stage,'prerequisites':[{'id':p,'rank':r} for p,r in requirements],'effects':_effects(effects),'exclusive_group':group,'description':_description(effects) if effects else 'Activates this automatic weapon.','initial_rank':int(id=='needler.unlock'),'scope':scope})
 for wid,title,code,stage,cost,damage,cadence,reach,targets,power,rate,a,b in _DATA:
  unlock=wid+'.unlock';weapons[wid]={'name':title,'base':{'damage':damage,'cadence_ticks':cadence,'range':reach,'targets':targets},'unlock_global':f'sv_{code}_u'}
  add(unlock,'Unlock '+title,f'sv_{code}_u',wid,stage,(cost,),scope='availability')
  add(wid+'.damage',title+': Power',f'sv_{code}_d',wid,1,(1,1,2),((unlock,1),),{'damage':power})
  add(wid+'.cadence',title+': Cadence',f'sv_{code}_c',wid,1,(1,1,2),((unlock,1),),{'cadence_ticks':-rate})
  for letter,spec in [('a',a),('b',b)]:
   branch,label,effects,capname,capeffects=spec;bid=wid+'.'+branch
   add(bid,title+': '+label,f'sv_{code}_{letter}',wid,max(2,stage),(2,2),((wid+'.damage',1),(wid+'.cadence',1)),effects,wid+'.specialization')
   add(bid+'_capstone',title+': '+capname,f'sv_{code}_{letter}c',wid,4,(3,),((bid,2),(wid+'.damage',2),(wid+'.cadence',2)),capeffects)
 def support(key,name,global_,stage,costs,effects,requirements=()):add('support.'+key,name,global_,None,stage,costs,requirements,effects)
 support('vitality','Vitality','sv_vit',1,(1,1,2),{'health_fraction':.2,'shield_fraction':.2})
 support('body','Body Armor','sv_body',1,(1,2),{'health_fraction':.25},(('support.vitality',1),))
 support('shield','Shield Capacity','sv_shield',1,(1,2),{'shield_fraction':.25},(('support.vitality',1),))
 support('aegis','Aegis','sv_aegis',1,(1,1,2),{'shield_pulse_fraction':.1})
 support('aegis_cycle','Shield Cycling','sv_cycle',2,(2,2),{'shield_pulse_ticks':-30},(('support.aegis',2),))
 support('reach','Targeting Reach','sv_reach',1,(1,1,2),{'range':1.5})
 support('insight','Battlefield Insight','sv_insight',1,(1,1,2),{'xp_fraction':.15})
 support('scholar','Combat Scholar','sv_scholar',3,(3,),{'xp_fraction':.2},(('support.insight',3),))
 return {'version':CATALOG_VERSION,'persistence':'same-run stage carry; cross-run profile not integrated','nodes':nodes,'weapons':weapons}
CATALOG=native_catalog()
NODES=tuple(CATALOG['nodes'])
NODE_BY_ID={n['id']:n for n in NODES}
WEAPONS=CATALOG['weapons']
