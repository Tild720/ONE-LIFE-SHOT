"""Tune the four inspected encounter spawners and player movement in editor."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    paths = ['/Game/Enemies/BP_EnemyStraightRunner', '/Game/Enemies/BP_EnemyRunnerFast',
             '/Game/Enemies/BP_EnemyRunnerSlow', '/Game/Enemies/BP_EnemySniper']
    classes = [unreal.load_asset(path).generated_class() for path in paths]
    result = []
    for label, x, y, delay, interval, count, role in [
        ('Runner_EndSpawn_1', -260, 1300, 3.0, 6.0, 2, 0),
        ('Runner_EndSpawn_2', 260, 1700, 5.0, 7.0, 2, 1),
        ('Runner_EndSpawn_3', -260, 2400, 12.0, 12.0, 1, 2),
        ('Runner_EndSpawn_4', 260, 3000, 18.0, 14.0, 1, 3)]:
        actor = next(a for a in actors if a.get_actor_label() == label)
        actor.set_actor_location(unreal.Vector(x,y,150), False, True)
        actor.set_editor_property('SpawnDelay', delay)
        actor.set_editor_property('MaxAliveEnemies', count)
        actor.set_editor_property('UseSpawnSpeedOverride', False)
        for stage in ['Early','Middle','Late','Final']:
            actor.set_editor_property(stage+'EnemyPool', [classes[role]])
            actor.set_editor_property(stage+'Interval', interval)
        result.append({'label':label,'role':paths[role],'delay':delay,'interval':interval,'max_alive':count})
    intro = next(a for a in actors if a.get_actor_label() == 'Runner_IntroEnemy')
    intro.set_editor_property('CruiseSpeed', 100.0)
    bp = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
    cdo = unreal.get_default_object(bp.generated_class())
    cdo.get_component_by_class(unreal.CharacterMovementComponent).set_editor_property('max_walk_speed',600.0)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    return {'spawners':result,'walk_speed':600,'dodge_speed':1100,'intro_cruise_speed':100}

run_editor(work,'CombatEncounterTuning.json')
