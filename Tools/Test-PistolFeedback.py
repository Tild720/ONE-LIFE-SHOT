import unreal,json
from pathlib import Path
def run():
 w=unreal.EditorLevelLibrary.get_pie_worlds(False)[0];p=unreal.GameplayStatics.get_player_pawn(w,0);pc=unreal.GameplayStatics.get_player_controller(w,0);gun=p.get_editor_property('EquippedPistol');assert gun
 target=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.load_asset('/Game/Weapons/Pistol/BP_TargetActor').generated_class())[0]
 bc=unreal.load_asset('/Game/Weapons/Pistol/BP_BulletProjectile').generated_class();light=gun.get_component_by_class(unreal.PointLightComponent);tm=target.get_component_by_class(unreal.StaticMeshComponent)
 perf=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings');old=perf.get_editor_property('bThrottleCPUWhenNotForeground');perf.set_editor_property('bThrottleCPUWhenNotForeground',False);unreal.SystemLibrary.execute_console_command(w,'t.MaxFPS 30')
 s={'t':0,'phase':0,'light_peak':0,'red_seen':False,'red_cleared':False,'flight':[],'hud':pc.get_hud().get_class().get_name()}
 def tick(dt):
  try:
   s['t']+=dt;t=s['t'];dest=target.get_actor_location() if t>1.8 else p.get_actor_location()+unreal.Vector(200,-200,-92)
   pixel=unreal.GameplayStatics.project_world_to_screen(pc,dest);pc.set_mouse_location(round(pixel.x),round(pixel.y))
   if s['phase']==0 and t>.4:
    gun.call_method('Fire');s['light_peak']=light.get_editor_property('intensity');s['phase']=1
   if s['phase']==1:
    for bullet in unreal.GameplayStatics.get_all_actors_of_class(w,bc):
     pos=bullet.get_actor_location();s['flight'].append([t,pos.x,pos.y,pos.z])
   if s['phase']==1 and t>2.3:gun.call_method('Fire');s['phase']=2
   overlay=tm.get_overlay_material()
   if overlay:s['red_seen']=True
   elif s['red_seen']:s['red_cleared']=True
   if t>3.5:
    unreal.unregister_slate_post_tick_callback(h);perf.set_editor_property('bThrottleCPUWhenNotForeground',old)
    s['light_off']=light.get_editor_property('intensity')==0
    s['shake_classes']=[o.get_class().get_name() for o in unreal.ObjectIterator(unreal.LegacyCameraShake) if 'PlayerCameraManager' in o.get_path_name()]
    s['pass']=s['light_peak']>0 and s['light_off'] and s['red_seen'] and s['red_cleared'] and len(s['flight'])>5 and max(v[3] for v in s['flight'])-min(v[3] for v in s['flight'])<2 and sum((s['flight'][-1][i]-s['flight'][0][i])**2 for i in (1,2))>1500**2 and 'BP_AmmoHUD' in s['hud']
    (Path(unreal.Paths.project_saved_dir()) / 'PistolFeedbackTest.json').write_text(json.dumps(s));print('FEEDBACK_TEST',s['pass'])
  except Exception as e:
   unreal.unregister_slate_post_tick_callback(h);perf.set_editor_property('bThrottleCPUWhenNotForeground',old);(Path(unreal.Paths.project_saved_dir()) / 'PistolFeedbackTest.json').write_text(json.dumps({'error':str(e),'state':s}))
 h=unreal.register_slate_post_tick_callback(tick)
run()
