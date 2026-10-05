"""Arm a disposable QA script before PIE, after the player and viewport exist."""
import builtins
import json
import runpy
from pathlib import Path
import unreal

root = Path(__file__).resolve().parents[1]
command = json.loads((root / 'One_life_Shot/Saved/EditorCommand.json').read_text(encoding='utf-8'))
script = command.get('play_script', 'Tools/Test-WeaponQueue.py')
target = (root / script).resolve()
assert target.is_relative_to(root / 'Tools') and target.is_file()
perf = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
if not hasattr(builtins, '_ols_old_background_throttle'):
    builtins._ols_old_background_throttle = perf.get_editor_property('bThrottleCPUWhenNotForeground')
perf.set_editor_property('bThrottleCPUWhenNotForeground', False)
for key in ['_ols_weapon_queue_qa', '_combat_roles_qa_session']:
    old = builtins.__dict__.get(key)
    assert old is None or old.get('finished'), 'Do not interrupt an active acceptance run: ' + key
    builtins.__dict__.pop(key, None)
handle = [None]

def ready(_dt):
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
    if not world:
        return
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    if not pawn or not controller or pawn.get_editor_property('Dead'):
        return
    unreal.unregister_slate_post_tick_callback(handle[0])
    runpy.run_path(str(target), run_name='__main__')

handle[0] = unreal.register_slate_post_tick_callback(ready)
(Path(unreal.Paths.project_saved_dir()) / 'PlayQAArmed.json').write_text(json.dumps({'script': script, 'armed': True}))
