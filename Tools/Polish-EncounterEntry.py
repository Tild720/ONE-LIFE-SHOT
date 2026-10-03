"""Fix encounter entry using the existing starter pickup and enemy logic."""
import sys,builtins
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    enemy=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(enemy,'EventGraph')
    infos=BT.get_node_infos(list(graph.list_all_nodes()))
    nodes={n.get_name():n for n in graph.list_all_nodes()}
    begin=nodes['K2Node_Event_0']
    configure=next(i.node for i in infos if i.type_id.endswith('|ConfigureEnemyAppearance'))
    pulse=next(i.node for i in infos if any(p.name=='FunctionName' and p.value=='EnemyRolePulse' for p in i.input_pins) and i.node.find_output_pin('ReturnValue').is_valid())
    if configure not in [p.get_owning_node() for p in begin.find_then_pin().list_connected_pins()]:
        configure.find_execute_pin().break_pin_links()
        insert_after(graph,begin,configure,pulse)
    val(nodes['K2Node_CallFunction_53'],'bEnabled','true')
    compile_blueprint(enemy,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(enemy,False)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    pickup=next(a for a in actors if a.get_class().get_name()=='BP_PistolPickup_C')
    starts=[a for a in actors if isinstance(a,unreal.PlayerStart)]
    assert len(starts)==1,[(a.get_name(),str(a.get_actor_location())) for a in starts]
    position=starts[0].get_actor_location()
    pickup.set_actor_location(unreal.Vector(position.x,position.y,75),False,True)
    intro=next(a for a in actors if a.get_actor_label()=='Runner_IntroEnemy')
    intro.set_editor_property('MoveSpeed',100.0)
    intro.set_editor_property('CruiseSpeed',100.0)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    hud=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_AmmoHUD')
    event=unreal.BlueprintGraphEditor.get_graph_editor_by_name(hud,'EventGraph')
    guide=next(i.node for i in BT.get_node_infos(list(event.list_all_nodes())) if any(p.name=='Text' and 'WASD MOVE' in str(p.value) for p in i.input_pins))
    val(guide,'Scale',.9)
    compile_blueprint(hud,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(hud,False)
    # Remove the temporary MCP queue launcher from the in-memory controller.
    controller=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    event=unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller,'EventGraph')
    for i in BT.get_node_infos(list(event.list_all_nodes())):
        if any(p.name=='Command' and 'Editor-Queue.py' in str(p.value) for p in i.input_pins):
            previous=list(i.node.find_execute_pin().list_connected_pins())
            following=list(i.node.find_then_pin().list_connected_pins())
            event.remove_nodes([i.node])
            for a in previous:
                for b in following:link(a,b)
    compile_blueprint(controller,True)
    perf=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
    if not hasattr(builtins,'_ols_old_background_throttle'):
        builtins._ols_old_background_throttle=perf.get_editor_property('bThrottleCPUWhenNotForeground')
    perf.set_editor_property('bThrottleCPUWhenNotForeground',False)
    return {'saved':[enemy.get_path_name(),hud.get_path_name(),'Lvl_ThirdPerson'],
            'starter_pickup':str(pickup.get_actor_location()),'intro_initialization':'independent of player spawn order'}
run_editor(work,'EncounterEntryPolish.json')
