import unreal,json
from pathlib import Path
def run():
 w=unreal.EditorLevelLibrary.get_pie_worlds(False)[0];p=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0);gun=p.get_editor_property('EquippedPistol');assert gun
 bc=unreal.load_asset('/Game/Weapons/Pistol/BP_BulletProjectile').generated_class();ic=unreal.load_asset('/Game/Weapons/Pistol/BP_PistolImpactBits').generated_class();tc=unreal.load_asset('/Game/Weapons/Pistol/BP_TargetActor').generated_class();target=unreal.GameplayStatics.get_all_actors_of_class(w,tc)[0]
 perf=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings');old=perf.get_editor_property('bThrottleCPUWhenNotForeground');perf.set_editor_property('bThrottleCPUWhenNotForeground',False)
 cc=unreal.load_asset('/Game/Weapons/Pistol/BP_PistolCasing').generated_class();p.disable_input(pc)
 for cls in [bc,ic,cc]:
  for actor in unreal.GameplayStatics.get_all_actors_of_class(w,cls):actor.destroy_actor()
 s={'t':0,'phase':0,'trails':[],'bits':[],'bit_positions':[],'casings':[]}
 def sample(b):
  tr=next(c for c in b.get_components_by_class(unreal.StaticMeshComponent) if c.get_name().startswith('Tracer'));pos=b.get_actor_location();start=b.get_editor_property('TrailStartLocation');length=tr.get_editor_property('relative_scale3d').z*100
  s['trails'].append({'distance':(pos-start).length(),'length':length,'tick':b.is_actor_tick_enabled()})
 def tick(dt):
  try:
   s['t']+=dt;t=s['t'];dest=target.get_actor_location() if t>1 else p.get_actor_location()+unreal.Vector(200,-200,-92);pixel=unreal.GameplayStatics.project_world_to_screen(pc,dest);pc.set_mouse_location(round(pixel.x),round(pixel.y))
   if s['phase']==0 and t>.3:
    gun.call_method('Fire');s['phase']=1
    for b in unreal.GameplayStatics.get_all_actors_of_class(w,bc):sample(b)
   if s['phase']==1:
    for b in unreal.GameplayStatics.get_all_actors_of_class(w,bc):sample(b)
   if s['phase']==1 and t>1.4:gun.call_method('Fire');s['phase']=2
   for a in unreal.GameplayStatics.get_all_actors_of_class(w,ic):
    parts=a.get_components_by_class(unreal.StaticMeshComponent);s['bits'].append(len(parts));s['bit_positions'].append([[c.get_world_location().x,c.get_world_location().y,c.get_world_location().z] for c in parts])
   for a in unreal.GameplayStatics.get_all_actors_of_class(w,cc):
    c=a.get_component_by_class(unreal.StaticMeshComponent);pos=c.get_world_location();s['casings'].append([a.get_name(),pos.x,pos.y,pos.z,c.get_physics_linear_velocity().length()])
   if t>2.4:
    unreal.unregister_slate_post_tick_callback(h);perf.set_editor_property('bThrottleCPUWhenNotForeground',old);p.enable_input(pc);s['bits_remaining']=len(unreal.GameplayStatics.get_all_actors_of_class(w,ic));s['casings_remaining']=len(unreal.GameplayStatics.get_all_actors_of_class(w,cc))
    s['pass']=s['trails'][0]['length']==0 and all(q['length']<=q['distance']+.1 for q in s['trails']) and any(q['length']>219 and not q['tick'] for q in s['trails']) and 8 in s['bits'] and s['bits_remaining']==0 and len(s['bit_positions'])>1 and len(s['casings'])>1 and s['casings_remaining']==0
    (Path(unreal.Paths.project_saved_dir()) / 'PistolCosmeticsTest.json').write_text(json.dumps(s));print('TRACER_BITS_TEST',s['pass'])
  except Exception as e:
   unreal.unregister_slate_post_tick_callback(h);perf.set_editor_property('bThrottleCPUWhenNotForeground',old);p.enable_input(pc);(Path(unreal.Paths.project_saved_dir()) / 'PistolCosmeticsTest.json').write_text(json.dumps({'error':str(e),'state':s}))
 h=unreal.register_slate_post_tick_callback(tick)
run()
