"""PIE physics traces across the long course and actual forward-spawn pursuit."""
import builtins,json,time,traceback
from pathlib import Path
import unreal
saved=Path(unreal.Paths.project_saved_dir());report={'passed':False,'checks':[]}
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pawn=unreal.GameplayStatics.get_player_pawn(world,0);pc=unreal.GameplayStatics.get_player_controller(world,0);hud=pc.call_method('GetHUD')
perf=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings');previous=perf.get_editor_property('bThrottleCPUWhenNotForeground');perf.set_editor_property('bThrottleCPUWhenNotForeground',False)
statics=unreal.get_default_object(unreal.GameplayStatics.static_class())
def write():(saved/'CourseTerrainChaseTest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def check(name,passed,**data):report['checks'].append({'name':name,'passed':bool(passed),**data});write()
def trace_floor():
    misses=[];samples=0
    for y in range(-400,57801,200):
        for x in [-220,0,220]:
            samples+=1
            result=unreal.SystemLibrary.line_trace_single(world,unreal.Vector(x,y,350),unreal.Vector(x,y,-50),unreal.TraceTypeQuery.ECC_VISIBILITY,False,[pawn],unreal.DrawDebugTrace.NONE,True,unreal.LinearColor(),unreal.LinearColor(),0)
            values=result if isinstance(result,(tuple,list)) else [result]
            hit=next((v for v in values if isinstance(v,unreal.HitResult)),None)
            data=statics.call_method('BreakHitResult',args=(hit,)) if hit else None
            if not data or not data[0] or not 49<=data[4].z<=70:misses.append({'x':x,'y':y,'location':str(data[4]) if data else None,'actor':str(data[9]) if data else None})
    check('Three walking lanes have continuous physical floor for the full route',not misses,samples=samples,misses=misses)
    barriers=[]
    capsule=pawn.get_component_by_class(unreal.CapsuleComponent)
    for y in range(0,57501,100):
        result=unreal.SystemLibrary.capsule_trace_single(world,unreal.Vector(0,y,155),unreal.Vector(0,y+100,155),capsule.get_scaled_capsule_radius(),capsule.get_scaled_capsule_half_height(),unreal.TraceTypeQuery.ECC_VISIBILITY,False,[pawn],unreal.DrawDebugTrace.NONE,True,unreal.LinearColor(),unreal.LinearColor(),0)
        values=result if isinstance(result,(tuple,list)) else [result]
        hit=next((v for v in values if isinstance(v,unreal.HitResult)),None)
        data=statics.call_method('BreakHitResult',args=(hit,)) if hit else None
        if data and data[0]:barriers.append({'y':y,'actor':str(data[9]),'component':str(data[10])})
    check('Player capsule can cross every course section without an internal barrier',not barriers,barriers=barriers)

state={'phase':'spawn','since':time.monotonic(),'handle':None,'seen':None}
enemyclass=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class()
def finish(error=None):
    if error:report['error']=str(error)
    report['passed']=not error and all(c['passed'] for c in report['checks'])
    unreal.unregister_slate_post_tick_callback(state['handle']);perf.set_editor_property('bThrottleCPUWhenNotForeground',previous);write()
def tick(dt):
    try:
        if state['phase']=='spawn':
            actors=unreal.GameplayStatics.get_all_actors_of_class(world,enemyclass)
            if actors:
                enemy=next((a for a in actors if a.get_class()==enemyclass),actors[0]);state['enemy']=enemy;state['position']=enemy.get_actor_location()
                delta=enemy.get_actor_location().y-pawn.get_actor_location().y
                check('An actual production spawn appears 16m in FRONT of the player',1500<delta<1700,distance_cm=delta)
                check('Forward spawn stands on the course floor',100<enemy.get_actor_location().z<210,z=enemy.get_actor_location().z)
                pawn.set_actor_location(unreal.Vector(180,300,142.25),False,True)
                state.update(phase='chase',since=time.monotonic())
        elif time.monotonic()-state['since']>.35:
            enemy=state['enemy'];before=state['position'];after=enemy.get_actor_location()
            direction=enemy.get_editor_property('TravelDirection');target=pawn.get_actor_location()-after;target.z=0
            alignment=(direction.x*target.x+direction.y*target.y)/target.length()
            check('Pursuer approaches from in front',after.y<before.y-10,before_y=before.y,after_y=after.y)
            check('Pursuit turns toward the player after lateral movement',alignment>.98,alignment=alignment)
            gun=pawn.get_editor_property('EquippedPistol')
            pixel=unreal.GameplayStatics.project_world_to_screen(pc,pawn.get_actor_location()+unreal.Vector(-200,50,-92.25));pc.set_mouse_location(round(pixel.x),round(pixel.y))
            gun.call_method('Fire')
            shakes=[o for o in unreal.ObjectIterator(unreal.LegacyCameraShake) if 'PlayerCameraManager' in o.get_path_name() and o.get_class().get_name()=='CS_PistolFire_C']
            check('A real shot starts the existing recoil shake',bool(shakes),instances=len(shakes))
            finish()
        if time.monotonic()-started>30:finish('Forward spawn acceptance timed out')
    except Exception:finish(traceback.format_exc())
try:
    trace_floor();hud.call_method('StartGame');started=time.monotonic()
    state['handle']=unreal.register_slate_post_tick_callback(tick);builtins._ols_course_chase=state
except Exception:
    report['error']=traceback.format_exc();perf.set_editor_property('bThrottleCPUWhenNotForeground',previous);write()
