"""Apply the user's correction: enemies spawn farther in FRONT of the player."""
import runpy
from pathlib import Path
api=runpy.run_path(str(Path(__file__).with_name('Extend-Course.py')),run_name='course_library')
globals().update({k:v for k,v in api.items() if not k.startswith('__')})
def work():
    bp=unreal.load_asset(SPAWN)
    var(bp,'SpawnAheadDistance','float',1600.0,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'SpawnNext')
    for info in BT.get_node_infos(list(ed.list_all_nodes())):
        if info.type_id=='|GetSpawnBehindDistance':
            old=out(info.node,'SpawnBehindDistance');targets=list(old.list_connected_pins());old.break_pin_links()
            negative=binary(ed,'Multiply_DoubleDouble',v(ed,'SpawnAheadDistance'),-1.0)
            for target in targets:link(negative,target)
            ed.remove_nodes([info.node])
    if 'SpawnBehindDistance' in [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp,False)]:BT.remove_variable(bp,'SpawnBehindDistance')
    compile_blueprint(bp,True);assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for actor in actors:
        if actor.get_class()==bp.generated_class():actor.set_editor_property('SpawnAheadDistance',1600.0)
    cleanup=extend_entry()
    return {'spawn_ahead_cm':1600,'player_relative':'Forward along the course, preserving the point lateral lane and floor height','cleanup':cleanup}
run_editor(work,'CourseSpawnCorrected.json')
