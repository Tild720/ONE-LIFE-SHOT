"""Make the existing charge recovery opportunity earlier and readable."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    bp=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    material='/Game/Enemies/Materials/M_EnemyRed'
    assert unreal.load_asset(material)
    graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'ConfigureEnemyAppearance')
    infos=BT.get_node_infos(list(graph.list_all_nodes()))
    if not any(i.type_id.endswith('|SetMaterial') for i in infos):
        start=list(graph.find_graph_entry_pin().list_connected_pins())
        graph.find_graph_entry_pin().break_pin_links()
        assign=call(graph,'/Script/Engine.PrimitiveComponent.SetMaterial',ElementIndex=0,Material=material)
        link(out(get(graph,'Mesh'),'Mesh'),inp(assign,'self'))
        link(graph.find_graph_entry_pin(),assign.find_execute_pin())
        for p in start:link(assign.find_then_pin(),p)
    compile_blueprint(bp,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    assault=unreal.load_asset('/Game/Enemies/BP_EnemyRunnerFast')
    cdo=unreal.get_default_object(assault.generated_class())
    cdo.set_editor_property('ChargeWindup',.65)
    cdo.set_editor_property('ChargeDuration',.85)
    compile_blueprint(assault,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(assault,False)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    spawner=next(a for a in actors if a.get_actor_label()=='Runner_EndSpawn_2')
    spawner.set_actor_location(unreal.Vector(260,1000,150),False,True)
    spawner.set_editor_property('SpawnDelay',2.5)
    basic=next(a for a in actors if a.get_actor_label()=='Runner_EndSpawn_1')
    basic.set_editor_property('SpawnDelay',5.0)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    return {'saved':[bp.get_path_name(),assault.get_path_name(),'Lvl_ThirdPerson'],
            'charge_windup':cdo.get_editor_property('ChargeWindup'),'charge_duration':cdo.get_editor_property('ChargeDuration'),
            'assault_spawn_delay':2.5,'assault_spawn_position':[260,1000,150]}
run_editor(work,'EnemyPressurePolish.json')
