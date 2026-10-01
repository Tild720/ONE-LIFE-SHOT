"""Editor-only opt-in use of the existing SpawnSpeed tuning value."""
import json
import traceback
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BT
from toolset_registry.helpers import compile_blueprint


def edit():
    bp = unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint')
    names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)]
    if 'UseSpawnSpeedOverride' not in names:
        BT.add_variable(bp, 'UseSpawnSpeedOverride', 'bool')
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, 'UseSpawnSpeedOverride', True)
    compile_blueprint(bp)
    unreal.get_default_object(bp.generated_class()).set_editor_property('UseSpawnSpeedOverride', False)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'SpawnNext')
    ns = {n.get_name(): n for n in ed.list_all_nodes()}
    terminal = ns['K2Node_CallFunction_31']
    assert not terminal.find_then_pin().list_connected_pins(), 'Speed override already installed'

    def ip(n, name):
        p = n.find_input_pin(name)
        assert p.is_valid(), (n.get_name(), name)
        return p

    def op(n, name='ReturnValue'):
        p = n.find_output_pin(name)
        assert p.is_valid(), (n.get_name(), name)
        return p

    def link(a, b):
        assert a.try_create_connection(b)

    flag = ed.add_get_member_variable_node('UseSpawnSpeedOverride')
    gate = ed.add_branch_node()
    link(op(flag, 'UseSpawnSpeedOverride'), ip(gate, 'Condition'))
    link(terminal.find_then_pin(), gate.find_execute_pin())
    cast = ed.create_node_from_name('Utilities|Casting|CastToBP_EnemyStraightRunner', unreal.Vector2D(2200, 1600), [])
    assert cast
    link(op(ns['K2Node_SpawnActorFromClass_1']), ip(cast, 'Object'))
    link(gate.find_then_pin(), cast.find_execute_pin())
    enemy = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    setter = ed.add_set_member_variable_node('MoveSpeed', enemy.generated_class().get_path_name())
    link(op(cast, 'AsBP Enemy Straight Runner'), ip(setter, 'self'))
    speed = ed.add_get_member_variable_node('SpawnSpeed')
    clamp = ed.add_call_function_node('/Script/Engine.KismetMathLibrary.FClamp')
    assert ip(clamp, 'Min').set_pin_value('100')
    assert ip(clamp, 'Max').set_pin_value('2000')
    link(op(speed, 'SpawnSpeed'), ip(clamp, 'Value'))
    link(op(clamp), ip(setter, 'MoveSpeed'))
    link(cast.find_then_pin(), setter.find_execute_pin())
    compile_blueprint(bp, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    for a in actors:
        if a.get_actor_label() in ['Runner_EndSpawn_1', 'Runner_EndSpawn_2']:
            a.set_editor_property('UseSpawnSpeedOverride', True)
            a.set_editor_property('SpawnSpeed', 300.0)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    return {'saved': bp.get_path_name(), 'first_encounter_speed': 300.0}


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
    (Path(unreal.Paths.project_saved_dir()) / 'OneShotSpawnSpeed.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')


handle[0] = unreal.register_slate_post_tick_callback(tick)
les.editor_request_end_play()
