"""Disposable native PIE acceptance; calls real menu, weapon and overlap paths."""
import builtins,json,time,traceback
from pathlib import Path
import unreal

def run():
    saved=Path(unreal.Paths.project_saved_dir());report={'passed':False,'checks':[],'limitations':'Menu functions and actual overlap are tested. Physical keyboard/mouse comfort and a full 577.5m combat run require manual play.'}
    state={'phase':'start','since':time.monotonic(),'handle':None}
    perf=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
    previous=perf.get_editor_property('bThrottleCPUWhenNotForeground');perf.set_editor_property('bThrottleCPUWhenNotForeground',False)
    def write():(saved/'CourseFlowTest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    def check(name,passed,**data):
        report['checks'].append({'name':name,'passed':bool(passed),**data});write()
    def transition(phase):state.update(phase=phase,since=time.monotonic())
    def screenshot(world,pc,name):unreal.SystemLibrary.execute_console_command(world,'Shot SHOWUI filename="'+str(saved/(name+'.png'))+'" -nosuffix',pc)
    def finish():
        report['passed']=all(c['passed'] for c in report['checks']) and not report.get('error')
        perf.set_editor_property('bThrottleCPUWhenNotForeground',previous)
        unreal.unregister_slate_post_tick_callback(state['handle']);write()
    def tick(dt):
        try:
            world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
            if not world:return
            pawn=unreal.GameplayStatics.get_player_pawn(world,0);pc=unreal.GameplayStatics.get_player_controller(world,0)
            if not pawn or not pc:return
            hud=pc.call_method('GetHUD');elapsed=time.monotonic()-state['since']
            if state['phase']=='start' and elapsed>.35:
                check('Start screen opens over the map',hud.get_editor_property('MenuState')==0)
                check('Start screen freezes gameplay',unreal.GameplayStatics.is_game_paused(world))
                state['game_time']=unreal.GameplayStatics.get_time_seconds(world)
                transition('start_frozen')
            elif state['phase']=='start_frozen' and elapsed>.4:
                check('Game clock stays frozen on start',abs(unreal.GameplayStatics.get_time_seconds(world)-state['game_time'])<.01)
                hud.call_method('StartGame');transition('playing')
            elif state['phase']=='playing' and elapsed>.3:
                check('Start resumes gameplay',hud.get_editor_property('MenuState')==1 and not unreal.GameplayStatics.is_game_paused(world))
                arm=pawn.get_component_by_class(unreal.SpringArmComponent)
                check('Runtime camera is 1.5 times closer',abs(arm.target_arm_length-1400/1.5)<.1)
                gun=pawn.get_editor_property('EquippedPistol')
                check('Normal starter pickup still supplies one shot',bool(gun) and gun.get_editor_property('Ammo')==1)
                if gun:
                    pixel=unreal.GameplayStatics.project_world_to_screen(pc,pawn.get_actor_location()+unreal.Vector(-250,100,-92.25))
                    pc.set_mouse_location(round(pixel.x),round(pixel.y))
                    gun.call_method('Fire');check('A shot still consumes its sole round',not unreal.SystemLibrary.is_valid(gun) and pawn.get_editor_property('EquippedPistol') is None)
                hud.call_method('TogglePause');state['game_time']=unreal.GameplayStatics.get_time_seconds(world)
                transition('pause')
            elif state['phase']=='pause' and elapsed>.5:
                check('Pause menu freezes clock',hud.get_editor_property('MenuState')==2 and abs(unreal.GameplayStatics.get_time_seconds(world)-state['game_time'])<.01)
                hud.call_method('TogglePause');check('ESC menu action resumes',hud.get_editor_property('MenuState')==1 and not unreal.GameplayStatics.is_game_paused(world))
                for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint').generated_class()):actor.set_editor_property('Enabled',False)
                # Freeze existing enemies only for the overlap/menu fixture.
                for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class()):actor.destroy_actor()
                pawn.set_actor_location(unreal.Vector(340,57750,155),False,True)
                transition('outside_pad')
            elif state['phase']=='outside_pad' and elapsed>.2:
                check('Standing beside the platform does not clear',hud.get_editor_property('MenuState')==1)
                statics=unreal.get_default_object(unreal.GameplayStatics.static_class())
                transform=unreal.Transform(location=unreal.Vector(0,57750,150))
                enemy=statics.call_method('BeginDeferredActorSpawnFromClass',args=(world,unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class(),transform,unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,None,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
                statics.call_method('FinishSpawningActor',args=(enemy,transform,unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT))
                enemy.get_component_by_class(unreal.CharacterMovementComponent).disable_movement();state['enemy']=enemy
                transition('enemy_pad')
            elif state['phase']=='enemy_pad' and elapsed>.2:
                check('An enemy stepping on the platform does not clear',hud.get_editor_property('MenuState')==1)
                state['enemy'].destroy_actor();pawn.set_actor_location(unreal.Vector(0,57750,155),False,True)
                transition('clear')
            elif state['phase']=='clear' and elapsed>.35:
                check('Real player overlap triggers clear',hud.get_editor_property('MenuState')==3)
                check('Clear freezes combat',unreal.GameplayStatics.is_game_paused(world))
                alpha=hud.get_editor_property('MenuFade');check('Clear text fades in gradually',.05<alpha<.9,alpha=alpha)
                state['stamp']=hud.get_editor_property('MenuFadeStart');hud.call_method('ClearGame')
                check('Clear overlap cannot restart the fade',hud.get_editor_property('MenuFadeStart')==state['stamp'])
                transition('clear_complete')
            elif state['phase']=='clear_complete' and elapsed>1.2:
                check('Fade finishes while game is paused',hud.get_editor_property('MenuFade')>.99,alpha=hud.get_editor_property('MenuFade'))
                state['old_pawn']=pawn
                hud.call_method('ReturnToStart');transition('restart')
            elif state['phase']=='restart' and elapsed>.7:
                check('Main menu reopens a fresh level',pawn!=state['old_pawn'] and hud.get_editor_property('MenuState')==0 and unreal.GameplayStatics.is_game_paused(world))
                check('Fresh run clears the reserve',pawn.get_editor_property('QueuedWeaponKind')==-1)
                finish()
            if time.monotonic()-started>120:
                report['error']='PIE acceptance timed out';finish()
        except Exception:
            report['error']=traceback.format_exc();finish()
    started=time.monotonic();write()
    state['handle']=unreal.register_slate_post_tick_callback(tick)
    builtins._ols_course_flow=state

run()
