"""Tune only existing placed encounter actors after inspecting the real map."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    by_label={a.get_actor_label():a for a in actors}
    expected={'Pistol Target':'BP_TargetActor_C','Dummy_Target':'StaticMeshActor',
              'Gun_Pistol':'StaticMeshActor','Runner_EndPoint':'TargetPoint',
              'Runner_EndSpawn_1':'BP_EnemySpawnPoint_C','Runner_EndSpawn_2':'BP_EnemySpawnPoint_C'}
    for label,cls in expected.items():
        assert label in by_label and by_label[label].get_class().get_name()==cls,(label,cls)
    hidden=[]
    for label in ['Pistol Target','Dummy_Target','Gun_Pistol']:
        actor=by_label[label]
        actor.set_actor_hidden_in_game(True)
        actor.set_actor_enable_collision(False)
        hidden.append(label)
    end=by_label['Runner_EndPoint']; old_end=end.get_actor_location()
    assert abs(old_end.x+10)<.01 and abs(old_end.z-50)<.01,str(old_end)
    end.set_actor_location(unreal.Vector(old_end.x,3850.0,old_end.z),False,True)
    # Keep the intro robot as the first decision. Moving the two existing
    # points forward leaves room to bait a charge after wasting that shot.
    positions={'Runner_EndSpawn_1':1700.0,'Runner_EndSpawn_2':1300.0}
    for label,y in positions.items():
        actor=by_label[label]; position=actor.get_actor_location()
        actor.set_actor_location(unreal.Vector(position.x,y,position.z),False,True)
    delays={'Runner_EndSpawn_1':1.5,'Runner_EndSpawn_2':1.0}
    for label,delay in delays.items(): by_label[label].set_editor_property('SpawnDelay',delay)
    # A second nearby opponent gives the acquired Shotgun a real grouping
    # decision before these points retire. Existing alive caps stay unchanged.
    intervals={'Runner_EndSpawn_1':3.2,'Runner_EndSpawn_2':3.2}
    for label,interval in intervals.items():
        for stage in ['Early','Middle','Late','Final']:
            by_label[label].set_editor_property(stage+'Interval',interval)
    # A committed charge should carry past its locked target and reach a nearby
    # solid wall when baited. The visible lane derives from this same speed.
    assault=unreal.load_asset('/Game/Enemies/BP_EnemyRunnerFast'); assert assault
    compile_blueprint(assault,True)
    unreal.get_default_object(assault.generated_class()).set_editor_property('ChargeSpeed',950.0)
    assert unreal.EditorAssetLibrary.save_loaded_asset(assault,False)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    # Keep the editor-only bootstrap absent from the persisted controller too.
    controller=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller,'EventGraph')
    assert not any(any(p.name=='Command' and 'Tools/Editor-Queue.py' in p.value for p in i.input_pins) for i in BT.get_node_infos(list(ed.list_all_nodes())))
    compile_blueprint(controller,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(controller,False)
    return {'hidden_play_only':hidden,'spawn_delays':delays,'spawn_intervals':intervals,'spawn_y':positions,'assault_charge_speed':950,'end_point_y':3850,'previous_end_point_y':old_end.y,
            'completion':'Existing Complete progress state only; no new victory or checkpoint system'}

run_editor(work,'EncounterClarityPolish.json')
