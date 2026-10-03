"""Drive production movement/aim/fire/dodge in the untouched encounter via PIE.
No inventory writes, target spawning, damage injection, or screen UI input.
"""
import unreal,json,builtins,time,math
from pathlib import Path
policy=getattr(builtins,'_ols_play_policy','aimed')
advance_limit=getattr(builtins,'_ols_play_advance_limit',1500)
report={'policy':policy,'events':[],'samples':[],'status':'running'}
state={'last_sample':-1,'shot_time':-10,'start':None,'pawn':None,'missed':False,'seen_dead':set(),'last_gun':None,'aim_since':None,'aim_gun':None}
def valid(a):return a is not None and unreal.SystemLibrary.is_valid(a)
def xyz(p):return [round(p.x,1),round(p.y,1),round(p.z,1)]
def write():
    (Path(unreal.Paths.project_saved_dir())/('RealEncounterPlay_'+policy+'.json')).write_text(json.dumps(report,indent=2))
def tick(dt):
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not valid(world):return
    now=time.monotonic()
    if state['start'] is None:state['start']=now
    elapsed=now-state['start']
    def event(name,**data):report['events'].append({'at':round(elapsed,2),'name':name,**data})
    try:
        pawn=unreal.GameplayStatics.get_player_pawn(world,0)
        if not valid(pawn):return
        if state['pawn']!=pawn:
            event('spawn_or_restart',pawn=pawn.get_path_name())
            state['pawn']=pawn
            state['aim_since']=None
        controller=unreal.GameplayStatics.get_player_controller(world,0)
        enemyclass=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class()
        enemies=list(unreal.GameplayStatics.get_all_actors_of_class(world,enemyclass))
        for a in enemies:
            if a.get_editor_property('Dead') and a.get_path_name() not in state['seen_dead']:
                state['seen_dead'].add(a.get_path_name());event('enemy_defeated',kind=a.get_editor_property('WeaponKind'))
        enemies=[a for a in enemies if not a.get_editor_property('Dead')]
        enemies.sort(key=lambda a:a.get_distance_to(pawn))
        gun=pawn.get_editor_property('EquippedPistol')
        ammo=gun.get_editor_property('Ammo') if valid(gun) else 0
        kind=gun.get_editor_property('WeaponKind') if valid(gun) else None
        if valid(gun) and state['last_gun']!=gun.get_path_name():
            state['last_gun']=gun.get_path_name();event('acquired_weapon',kind=kind,ammo=ammo)
        location=pawn.get_actor_location()
        nearest=enemies[0] if enemies else None
        distance=nearest.get_distance_to(pawn) if nearest else 9999
        dead=pawn.get_editor_property('Dead')
        if not dead:
            # Advance to expose ranged roles; retreat/strafe under close pressure.
            dx=math.sin(elapsed*.65)*.35;dy=.55 if location.y<advance_limit else 0
            if distance<320:
                delta=location-nearest.get_actor_location()
                length=max(math.sqrt(delta.x*delta.x+delta.y*delta.y+delta.z*delta.z),1)
                dx=delta.x/length;dy=delta.y/length
            if policy=='miss' and ammo==0 and distance>220:
                dx=(530-location.x)/max(abs(530-location.x),100)
                assaults=[a for a in enemies if a.get_editor_property('WeaponKind')==1]
                dy=.4 if assaults and assaults[0].get_distance_to(pawn)>400 else 0
                if assaults and assaults[0].get_editor_property('ChargeActive') and assaults[0].get_distance_to(pawn)<300:
                    dx=-1;dy=0
            boundary=540 if policy=='miss' and ammo==0 else 350
            if location.x>boundary:dx=min(dx,0)
            if location.x<-boundary:dx=max(dx,0)
            pawn.add_movement_input(unreal.Vector(dx,dy,0),.75,False)
            warning=any(a.get_editor_property('AIState')==1 and a.get_distance_to(pawn)<750 for a in enemies)
            imminent=any(a.get_editor_property('ChargeActive') and a.get_distance_to(pawn)<250 for a in enemies)
            if (distance<180 or imminent or (warning and policy!='miss')) and not pawn.get_editor_property('DodgeCooling'):
                pawn.call_method('TryDodge');event('dodge',ammo=ammo,distance=round(distance))
            target=nearest
            if ammo and target and elapsed-state['shot_time']>.9:
                limit={0:1550,1:600,2:2200,3:1600}[kind]
                if distance<limit:
                    point=target.get_actor_location();point.z=50
                    if policy=='miss' and not state['missed']:
                        point=location+unreal.Vector(-450,200,-92)
                    pixel=unreal.GameplayStatics.project_world_to_screen(controller,point)
                    if pixel:
                        controller.set_mouse_location(round(pixel.x),round(pixel.y))
                        if state['aim_gun']!=gun or state['aim_since'] is None:
                            state['aim_gun']=gun;state['aim_since']=elapsed
                        elif elapsed-state['aim_since']>.2:
                            gun.call_method('Fire');state['shot_time']=elapsed;state['aim_since']=None
                            event('fire',kind=kind,ammo_after=gun.get_editor_property('Ammo'),distance=round(distance),intended_miss=policy=='miss' and not state['missed'])
                            if policy=='miss':state['missed']=True
        if elapsed-state['last_sample']>.25:
            state['last_sample']=elapsed
            camera=unreal.GameplayStatics.get_player_camera_manager(world,0)
            report['samples'].append({'at':round(elapsed,2),'player':xyz(location),'dead':dead,'ammo':ammo,'weapon':kind,
                'enemies':[{'kind':a.get_editor_property('WeaponKind'),'position':xyz(a.get_actor_location()),'state':a.get_editor_property('AIState')} for a in enemies],
                'camera':str(camera.get_camera_rotation())})
            write()
        if elapsed>=30:
            report['status']='complete';write();unreal.unregister_slate_post_tick_callback(handle)
    except Exception as error:
        report['status']='error';report['error']=str(error);write();unreal.unregister_slate_post_tick_callback(handle)
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
handle=unreal.register_slate_post_tick_callback(tick)
