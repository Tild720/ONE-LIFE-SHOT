"""Read-only snapshots of the real encounter, without isolated QA formations."""
import unreal,json,builtins
from pathlib import Path
report={'snapshots':[]}
def pos(a):
    p=a.get_actor_location(); return [round(p.x,1),round(p.y,1),round(p.z,1)]
def prop(a,n):
    try:return str(a.get_editor_property(n))
    except:return None
def sample(dt):
    world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world:return
    t=unreal.GameplayStatics.get_time_seconds(world)
    if report['snapshots'] and t-report['snapshots'][-1]['time']<1:return
    pawn=unreal.GameplayStatics.get_player_pawn(world,0)
    controller=unreal.GameplayStatics.get_player_controller(world,0)
    actors=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.Actor)
    snapshot={'time':t,'player':pawn.get_path_name() if pawn else None,'actors':[]}
    for a in actors:
        name=a.get_class().get_name()
        if any(v in name for v in ['Enemy','Pistol','ThirdPersonCharacter','RunnerProgress','AmmoHUD']):
            snapshot['actors'].append({'name':a.get_name(),'class':name,'pos':pos(a),
                'state':{n:prop(a,n) for n in ['Ammo','EquippedPistol','Dead','WeaponKind','BodyTint','MoveSpeed','CruiseSpeed','Enabled','AliveCount','AmmoLabel','WeaponLabel','StatusLabel','AutoPossessPlayer']}})
    if controller:
        camera=unreal.GameplayStatics.get_player_camera_manager(world,0)
        snapshot['camera']={'position':pos(camera),'rotation':str(camera.get_camera_rotation())}
    report['snapshots'].append(snapshot)
    (Path(unreal.Paths.project_saved_dir())/'LivePlayInspection.json').write_text(json.dumps(report,indent=2))
    if len(report['snapshots'])>=8:unreal.unregister_slate_post_tick_callback(handle)
unreal.EditorPythonScripting.set_keep_python_script_alive(True)
handle=unreal.register_slate_post_tick_callback(sample)
