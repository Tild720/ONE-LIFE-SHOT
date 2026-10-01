"""Editor-only tuning of two existing encounter spawners."""
import json
import traceback
from pathlib import Path
import unreal


def edit():
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    slow = unreal.load_asset('/Game/Enemies/BP_EnemyRunnerSlow').generated_class()
    result = []
    for label, x, y, delay in [('Runner_EndSpawn_1', -260, 1500, 2.0),
                               ('Runner_EndSpawn_2', 260, 1900, 3.5)]:
        actor = next(a for a in actors if a.get_actor_label() == label)
        actor.set_actor_location(unreal.Vector(x, y, 150), False, True)
        actor.set_editor_property('SpawnDelay', delay)
        actor.set_editor_property('MaxAliveEnemies', 2)
        for stage in ['Early', 'Middle', 'Late', 'Final']:
            actor.set_editor_property(stage + 'Interval', 4.0)
            actor.set_editor_property(stage + 'EnemyPool', [slow])
        result.append({'label': label, 'position': [x, y, 150], 'delay': delay})
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    return {'saved': result}


les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
handle = [None]


def tick(dt):
    if les.is_in_play_in_editor():
        return
    unreal.unregister_slate_post_tick_callback(handle[0])
    try:
        result = edit()
    except Exception:
        result = {'error': traceback.format_exc()}
        unreal.log_error(result['error'])
    (Path(unreal.Paths.project_saved_dir()) / 'OneShotEncounterTuning.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')


handle[0] = unreal.register_slate_post_tick_callback(tick)
les.editor_request_end_play()
