"""Editor-only readable contact failure for the existing one-shot loop."""
import json
import traceback
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BT
from toolset_registry.helpers import compile_blueprint


def edit():
    char = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
    enemy = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    hud = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_AmmoHUD')
    pickup = unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup')
    names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(char, False)]
    for name, kind in [('Dead', 'bool'), ('RetryDelay', 'float')]:
        if name not in names:
            BT.add_variable(char, name, kind)
        unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(char, name, name == 'RetryDelay')
    compile_blueprint(char)
    default = unreal.get_default_object(char.generated_class())
    default.set_editor_property('Dead', False)
    default.set_editor_property('RetryDelay', 0.55)
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(char, 'EventGraph')

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

    def chain(a, b):
        link(a.find_then_pin(), b.find_execute_pin())

    def call(e, path, **values):
        n = e.add_call_function_node(path)
        assert n, path
        for key, value in values.items():
            assert ip(n, key).set_pin_value(str(value)), (path, key)
        return n

    event = BT.add_event(char, 'FailRun', unreal.IntPoint(1800, 1600))
    assert not event.find_then_pin().list_connected_pins(), 'FailRun already installed'
    dead = ed.add_get_member_variable_node('Dead')
    negate = call(ed, '/Script/Engine.KismetMathLibrary.Not_PreBool')
    link(op(dead, 'Dead'), ip(negate, 'A'))
    branch = ed.add_branch_node()
    link(op(negate), ip(branch, 'Condition'))
    chain(event, branch)
    mark = ed.add_set_member_variable_node('Dead')
    assert ip(mark, 'Dead').set_pin_value('true')
    chain(branch, mark)
    collision = call(ed, '/Script/Engine.Actor.SetActorEnableCollision', bNewActorEnableCollision='false')
    chain(mark, collision)
    pc = call(ed, '/Script/Engine.GameplayStatics.GetPlayerController', PlayerIndex=0)
    disable = call(ed, '/Script/Engine.Actor.DisableInput')
    link(op(pc), ip(disable, 'PlayerController'))
    chain(collision, disable)
    movement = ed.add_get_member_variable_node('CharacterMovement')
    stop = call(ed, '/Script/Engine.CharacterMovementComponent.DisableMovement')
    link(op(movement, 'CharacterMovement'), ip(stop, 'self'))
    chain(disable, stop)
    h = call(ed, '/Script/Engine.PlayerController.GetHUD')
    link(op(pc), ip(h, 'self'))
    hc = ed.create_node_from_name('Utilities|Casting|CastToBP_AmmoHUD', unreal.Vector2D(2400, 1600), [])
    assert hc
    link(op(h), ip(hc, 'Object'))
    chain(stop, hc)
    ammo = ed.add_set_member_variable_node('AmmoLabel', hud.generated_class().get_path_name())
    link(op(hc, 'AsBP Ammo HUD'), ip(ammo, 'self'))
    assert ip(ammo, 'AmmoLabel').set_pin_value('DOWN')
    chain(hc, ammo)
    status = ed.add_set_member_variable_node('StatusLabel', hud.generated_class().get_path_name())
    link(op(hc, 'AsBP Ammo HUD'), ip(status, 'self'))
    assert ip(status, 'StatusLabel').set_pin_value('YOU DIED - RETRYING')
    chain(ammo, status)
    camera_manager = call(ed, '/Script/Engine.GameplayStatics.GetPlayerCameraManager', PlayerIndex=0)
    fade = call(ed, '/Script/Engine.PlayerCameraManager.StartCameraFade', FromAlpha=0,
                ToAlpha=0.65, Duration=0.15, Color='(R=0.3,G=0.02,B=0.02,A=1)',
                bShouldFadeAudio='false', bHoldWhenFinished='true')
    link(op(camera_manager), ip(fade, 'self'))
    chain(status, fade)
    link(op(hc, 'CastFailed'), fade.find_execute_pin())
    delay = call(ed, '/Script/Engine.KismetSystemLibrary.Delay')
    retry = ed.add_get_member_variable_node('RetryDelay')
    link(op(retry, 'RetryDelay'), ip(delay, 'Duration'))
    chain(fade, delay)
    level = call(ed, '/Script/Engine.GameplayStatics.GetCurrentLevelName', bRemovePrefixString='true')
    chain(delay, level)
    name = call(ed, '/Script/Engine.KismetStringLibrary.Conv_StringToName')
    link(op(level), ip(name, 'InString'))
    reopen = call(ed, '/Script/Engine.GameplayStatics.OpenLevel', bAbsolute='true')
    link(op(name), ip(reopen, 'LevelName'))
    chain(level, reopen)
    compile_blueprint(char, True)

    ee = unreal.BlueprintGraphEditor.get_graph_editor_by_name(enemy, 'EventGraph')
    ns = {n.get_name(): n for n in ee.list_all_nodes()}
    contact = ns['K2Node_DynamicCast_0']
    contact.find_then_pin().break_pin_links()
    fail = call(ee, char.generated_class().get_path_name() + ':FailRun')
    link(op(contact, 'AsBP Third Person Character'), ip(fail, 'self'))
    chain(contact, fail)
    ee.remove_nodes([ns[k] for k in ['K2Node_CallFunction_5', 'K2Node_CallFunction_6', 'K2Node_CallFunction_7']])
    compile_blueprint(enemy, True)

    # Returned/floor weapons cannot overwrite the visible failure state.
    pe = unreal.BlueprintGraphEditor.get_graph_editor_by_name(pickup, 'TryAcquire')
    infos = BT.get_node_infos(list(pe.list_all_nodes()))
    cp = next(i.node for i in infos if i.type_id.endswith('|CastToBP_ThirdPersonCharacter'))
    equip = next(i.node for i in infos if i.type_id == '|EquipPistol')
    cp.find_then_pin().break_pin_links()
    player_dead = pe.add_get_member_variable_node('Dead', char.generated_class().get_path_name())
    link(op(cp, 'AsBP Third Person Character'), ip(player_dead, 'self'))
    alive = call(pe, '/Script/Engine.KismetMathLibrary.Not_PreBool')
    link(op(player_dead, 'Dead'), ip(alive, 'A'))
    gate = pe.add_branch_node()
    link(op(alive), ip(gate, 'Condition'))
    chain(cp, gate)
    chain(gate, equip)
    compile_blueprint(pickup, True)
    for bp in [char, enemy, pickup]:
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    return {'saved': [bp.get_path_name() for bp in [char, enemy, pickup]]}


les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
handle = [None]


def after_pie(dt):
    if les.is_in_play_in_editor():
        return
    unreal.unregister_slate_post_tick_callback(handle[0])
    try:
        result = edit()
    except Exception:
        result = {'error': traceback.format_exc()}
        unreal.log_error(result['error'])
    (Path(unreal.Paths.project_saved_dir()) / 'OneShotDeathPolish.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')


handle[0] = unreal.register_slate_post_tick_callback(after_pie)
les.editor_request_end_play()
