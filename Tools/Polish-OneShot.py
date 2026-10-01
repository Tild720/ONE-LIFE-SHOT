"""Editor-only core-loop polish, launched through temporary Unreal MCP harness.

All assets are modified by Unreal Editor APIs. No runtime Python dependency.
"""
import json
import traceback
from pathlib import Path
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BT
from toolset_registry.helpers import compile_blueprint
unreal.EditorPythonScripting.set_keep_python_script_alive(True)

CHAR = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'
PICK = '/Game/Weapons/Pistol/BP_PistolPickup'
ENEMY = '/Game/Enemies/BP_EnemyStraightRunner'
HUD = '/Game/ThirdPerson/Blueprints/BP_AmmoHUD'
SYS = '/Script/Engine.KismetSystemLibrary.'
MATH = '/Script/Engine.KismetMathLibrary.'
ACT = '/Script/Engine.Actor.'
GAME = '/Script/Engine.GameplayStatics.'


def inp(node, name):
    p = node.find_input_pin(name)
    assert p.is_valid(), (node.get_name(), name)
    return p


def out(node, name='ReturnValue'):
    p = node.find_output_pin(name)
    assert p.is_valid(), (node.get_name(), name)
    return p


def link(a, b):
    assert a.try_create_connection(b), (str(a), str(b))


def val(node, name, value):
    assert inp(node, name).set_pin_value(str(value)), (node.get_name(), name, value)


def call(ed, path, **values):
    unreal.log('ONE_SHOT_EDIT node ' + path)
    n = ed.add_call_function_node(path)
    assert n, path
    for name, value in values.items():
        if not inp(n, name).set_pin_value(str(value)):
            # Promotable math operators initially have wildcard pins.
            if isinstance(value, (float, int)):
                kind = 'MakeLiteralInt' if '_IntInt' in path else 'MakeLiteralDouble'
                literal = ed.add_call_function_node(SYS + kind)
                val(literal, 'Value', value)
                link(out(literal), inp(n, name))
            elif str(value).startswith('(X='):
                components = str(value).strip('()').split(',')
                literal = ed.add_call_function_node(MATH + 'MakeVector')
                for component in components:
                    key, number = component.split('=')
                    val(literal, key, number)
                link(out(literal), inp(n, name))
            else:
                raise AssertionError((path, name, value))
    return n


def chain(a, b):
    link(a.find_then_pin(), b.find_execute_pin())


def get(ed, name, cls=''):
    n = ed.add_get_member_variable_node(name, cls)
    assert n, name
    return n


def setv(ed, name, value=None, cls=''):
    n = ed.add_set_member_variable_node(name, cls)
    assert n, name
    if value is not None:
        val(n, name, value)
    return n


def branch(ed, source):
    n = ed.add_branch_node()
    link(source, inp(n, 'Condition'))
    return n


def var(bp, name, kind, default, editable=False):
    names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)]
    if name not in names:
        BT.add_variable(bp, name, kind)
    unreal.BlueprintEditorLibrary.set_blueprint_variable_instance_editable(bp, name, editable)
    unreal.BlueprintEditorLibrary.set_blueprint_variable_category(bp, name, 'One Shot')
    compile_blueprint(bp)
    unreal.get_default_object(bp.generated_class()).set_editor_property(name, default)


def func(bp, name):
    graph = BT.add_function_graph(bp, name)
    ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
    ed.remove_nodes([n for n in ed.list_all_nodes() if not isinstance(n, unreal.K2Node_FunctionEntry)])
    return ed


def cast(ed, kind):
    n = ed.create_node_from_name('Utilities|Casting|CastTo' + kind,
                                unreal.Vector2D(300, 100), [])
    assert n, kind
    return n


def selfpin(ed):
    # UObject self defaults on member functions; timer's Object requires an explicit self.
    ids = [s for s in ed.list_available_nodes([]) if s == 'Variables|셀프레퍼런스가져오기' or s.endswith('|Getareferencetoself')]
    assert ids, 'Self node type not found'
    n = ed.create_node_from_name(ids[0], unreal.Vector2D(0, 400), [])
    assert n, 'self node'
    return out(n, 'self')


def timer(ed, name, interval, looping=True):
    n = call(ed, SYS + 'K2_SetTimer', FunctionName=name, Time=interval,
             bLooping='true' if looping else 'false', bMaxOncePerFrame='true')
    link(selfpin(ed), inp(n, 'Object'))
    return n


def hudset(ed, tail, ammo=None, status=None):
    pc = call(ed, GAME + 'GetPlayerController', PlayerIndex=0)
    gh = call(ed, '/Script/Engine.PlayerController.GetHUD')
    link(out(pc), inp(gh, 'self'))
    c = cast(ed, 'BP_AmmoHUD')
    link(out(gh), inp(c, 'Object'))
    chain(tail, c)
    end = c
    for name, value in [('AmmoLabel', ammo), ('StatusLabel', status)]:
        if value is None:
            continue
        s = setv(ed, name, value, unreal.load_asset(HUD).generated_class().get_path_name())
        link(out(c, 'AsBP Ammo HUD'), inp(s, 'self'))
        chain(end, s)
        end = s
    return end, c


def do_polish():
    hud = unreal.load_asset(HUD)
    hed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(hud, 'EventGraph')
    # Remove our previous status/hint drawings, retaining original node names 0..8.
    original_draw = {'K2Node_CallFunction_' + str(i) for i in range(9)}
    hed.remove_nodes([i.node for i in BT.get_node_infos(list(hed.list_all_nodes()))
                      if i.type_id.endswith('|DrawText') and i.node.get_name() not in original_draw])
    hed.remove_nodes([i.node for i in BT.get_node_infos(list(hed.list_all_nodes()))
                      if i.type_id == '|DrawOneShotStatus'])
    if 'DrawOneShotStatus' in [g.get_name() for g in unreal.BlueprintEditorLibrary.list_graphs(hud)]:
        previous = unreal.BlueprintGraphEditor.get_graph_editor_by_name(hud, 'DrawOneShotStatus')
        for name in ['X', 'Y', 'X1', 'Y1']:
            previous.remove_graph_input_parameter(name)
    var(hud, 'StatusLabel', 'string', 'EMPTY - FIND A WEAPON', True)
    hed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(hud, 'EventGraph')
    nodes = {n.get_name(): n for n in hed.list_all_nodes()}
    # Extend the existing panel instead of creating another HUD/widget.
    for key in ['K2Node_CallFunction_0', 'K2Node_CallFunction_1', 'K2Node_CallFunction_3']:
        val(nodes[key], 'ScreenH', 140)
    for info in BT.get_node_infos(list(hed.list_all_nodes())):
        if info.type_id.endswith('float-float'):
            for p in info.input_pins:
                if p.name == 'B' and p.value == '108':
                    val(info.node, 'B', 140)
    status = call(hed, '/Script/Engine.HUD.DrawText', TextColor='(R=1,G=0.8,B=0.35,A=1)',
                  Font='/Engine/EngineFonts/Roboto.Roboto', Scale=0.8, bScalePosition='false')
    label = get(hed, 'StatusLabel')
    link(out(label, 'StatusLabel'), inp(status, 'Text'))
    terminal = nodes['K2Node_CallFunction_8']
    terminal.find_then_pin().break_pin_links()
    chain(terminal, status)
    link(out(nodes['K2Node_PromotableOperator_20']), inp(status, 'ScreenX'))
    y = call(hed, MATH + 'Add_DoubleDouble', B=18)
    link(out(nodes['K2Node_PromotableOperator_21']), inp(y, 'A'))
    link(out(y), inp(status, 'ScreenY'))
    hint = call(hed, '/Script/Engine.HUD.DrawText', Text='WASD MOVE   MOUSE AIM   LMB FIRE   R RETRY',
                TextColor='(R=0.65,G=0.78,B=0.8,A=1)', ScreenX=20, ScreenY=64,
                Font='/Engine/EngineFonts/Roboto.Roboto', Scale=0.85, bScalePosition='false')
    chain(status, hint)
    compile_blueprint(hud, True)

    pickup = unreal.load_asset(PICK)
    for name, kind, default, edit in [
        ('ReturnDuration', 'float', 0.55, True), ('Returning', 'bool', False, False),
        ('ReturnStart', 'Vector', unreal.Vector(), False), ('ReturnStartTime', 'float', 0.0, False)]:
        var(pickup, name, kind, default, edit)
    unreal.get_default_object(pickup.generated_class()).set_editor_property('PickupRadius', 180.0)
    ped = unreal.BlueprintGraphEditor.get_graph_editor_by_name(pickup, 'EventGraph')
    pnodes = {n.get_name(): n for n in ped.list_all_nodes()}
    # Move acquisition into one function shared by floor overlap and returning drops.
    original = ['K2Node_CallFunction_0', 'K2Node_IfThenElse_0', 'K2Node_CallFunction_1',
                'K2Node_CallFunction_4', 'K2Node_CallFunction_5', 'K2Node_DynamicCast_2',
                'K2Node_VariableSet_1']
    if 'TryAcquire' not in [g.get_name() for g in unreal.BlueprintEditorLibrary.list_graphs(pickup)]:
        ped.remove_nodes([pnodes[k] for k in original if k in pnodes])
    else:
        ped.remove_nodes([i.node for i in BT.get_node_infos(list(ped.list_all_nodes()))
                          if i.type_id == '|TryAcquire' or
                          any(p.name == 'FunctionName' and p.value == 'TryAcquire' for p in i.input_pins)])
    acq = func(pickup, 'TryAcquire')
    ret = get(acq, 'Returning')
    nt = call(acq, MATH + 'Not_PreBool')
    link(out(ret, 'Returning'), inp(nt, 'A'))
    guard = branch(acq, out(nt))
    link(acq.find_graph_entry_pin(), guard.find_execute_pin())
    player = call(acq, GAME + 'GetPlayerPawn', PlayerIndex=0)
    valid = call(acq, SYS + 'IsValid')
    link(out(player), inp(valid, 'Object'))
    vg = branch(acq, out(valid))
    chain(guard, vg)
    distance = call(acq, ACT + 'GetDistanceTo')
    link(out(player), inp(distance, 'OtherActor'))
    le = call(acq, MATH + 'LessEqual_DoubleDouble')
    link(out(distance), inp(le, 'A'))
    radius = get(acq, 'PickupRadius')
    link(out(radius, 'PickupRadius'), inp(le, 'B'))
    close = branch(acq, out(le))
    chain(vg, close)
    cp = cast(acq, 'BP_ThirdPersonCharacter')
    link(out(player), inp(cp, 'Object'))
    chain(close, cp)
    equip = call(acq, unreal.load_asset(CHAR).generated_class().get_path_name() + ':EquipPistol')
    link(out(cp, 'AsBP Third Person Character'), inp(equip, 'self'))
    chain(cp, equip)
    ok = branch(acq, out(equip, 'Success'))
    chain(equip, ok)
    # Update UI before DestroyActor, then leave failed acquisition on the floor.
    tail, hc = hudset(acq, ok, '1/1', 'READY - CHOOSE YOUR TARGET')
    destroy = call(acq, ACT + 'K2_DestroyActor')
    chain(tail, destroy)
    link(out(hc, 'CastFailed'), destroy.find_execute_pin())
    compile_blueprint(pickup, True)
    overlap_acq = call(ped, 'TryAcquire')
    chain(pnodes['K2Node_DynamicCast_0'], overlap_acq)
    bp_acq = timer(ped, 'TryAcquire', 0.15)
    link(pnodes['K2Node_Event_0'].find_then_pin(), bp_acq.find_execute_pin())

    # Enemy drops travel visibly for a tunable interval. Ammo changes only in TryAcquire.
    start = func(pickup, 'ReturnToPlayer')
    returning = setv(start, 'Returning', 'true')
    link(start.find_graph_entry_pin(), returning.find_execute_pin())
    loc = call(start, ACT + 'K2_GetActorLocation')
    s = setv(start, 'ReturnStart')
    link(out(loc), inp(s, 'ReturnStart'))
    chain(returning, s)
    now = call(start, SYS + 'GetGameTimeInSeconds')
    st = setv(start, 'ReturnStartTime')
    link(out(now), inp(st, 'ReturnStartTime'))
    chain(s, st)
    t = timer(start, 'UpdateReturn', 0.02)
    chain(st, t)
    compile_blueprint(pickup)
    upd = func(pickup, 'UpdateReturn')
    pp = call(upd, GAME + 'GetPlayerPawn', PlayerIndex=0)
    iv = call(upd, SYS + 'IsValid')
    link(out(pp), inp(iv, 'Object'))
    b = branch(upd, out(iv))
    link(upd.find_graph_entry_pin(), b.find_execute_pin())
    clock = call(upd, SYS + 'GetGameTimeInSeconds')
    sub = call(upd, MATH + 'Subtract_DoubleDouble')
    link(out(clock), inp(sub, 'A'))
    stamp = get(upd, 'ReturnStartTime')
    link(out(stamp, 'ReturnStartTime'), inp(sub, 'B'))
    div = call(upd, MATH + 'Divide_DoubleDouble')
    link(out(sub), inp(div, 'A'))
    duration = get(upd, 'ReturnDuration')
    bounded = call(upd, MATH + 'FClamp', Min=0.1, Max=2.0)
    link(out(duration, 'ReturnDuration'), inp(bounded, 'Value'))
    link(out(bounded), inp(div, 'B'))
    alpha = call(upd, MATH + 'FClamp', Min=0, Max=1)
    link(out(div), inp(alpha, 'Value'))
    origin = get(upd, 'ReturnStart')
    target = call(upd, ACT + 'K2_GetActorLocation')
    link(out(pp), inp(target, 'self'))
    offset = call(upd, MATH + 'Subtract_VectorVector', B='(X=0,Y=0,Z=55)')
    link(out(target), inp(offset, 'A'))
    lerp = call(upd, MATH + 'VLerp')
    link(out(origin, 'ReturnStart'), inp(lerp, 'A'))
    link(out(offset), inp(lerp, 'B'))
    link(out(alpha), inp(lerp, 'Alpha'))
    move = call(upd, ACT + 'K2_SetActorLocation', bSweep='false', bTeleport='true')
    link(out(lerp), inp(move, 'NewLocation'))
    chain(b, move)
    done = call(upd, MATH + 'GreaterEqual_DoubleDouble', B=1)
    link(out(alpha), inp(done, 'A'))
    arrived = branch(upd, out(done))
    chain(move, arrived)
    clear = call(upd, SYS + 'K2_ClearTimer', FunctionName='UpdateReturn')
    link(selfpin(upd), inp(clear, 'Object'))
    chain(arrived, clear)
    finish = setv(upd, 'Returning', 'false')
    chain(clear, finish)
    take = call(upd, 'TryAcquire')
    chain(finish, take)
    abort = call(upd, SYS + 'K2_ClearTimer', FunctionName='UpdateReturn')
    link(selfpin(upd), inp(abort, 'Object'))
    link(out(b, 'else'), abort.find_execute_pin())
    stopped = setv(upd, 'Returning', 'false')
    chain(abort, stopped)
    compile_blueprint(pickup, True)

    enemy = unreal.load_asset(ENEMY)
    die = unreal.BlueprintGraphEditor.get_graph_editor_by_name(enemy, 'Die')
    ns = {n.get_name(): n for n in die.list_all_nodes()}
    spawn = ns['K2Node_SpawnActorFromClass_1']
    continuation = list(spawn.find_then_pin().list_connected_pins())
    spawn.find_then_pin().break_pin_links()
    is_spawned = call(die, SYS + 'IsValid')
    link(out(spawn), inp(is_spawned, 'Object'))
    spawned_guard = branch(die, out(is_spawned))
    chain(spawn, spawned_guard)
    return_call = call(die, pickup.generated_class().get_path_name() + ':ReturnToPlayer')
    link(out(spawn), inp(return_call, 'self'))
    chain(spawned_guard, return_call)
    for p in continuation:
        link(return_call.find_then_pin(), p)
        link(out(spawned_guard, 'else'), p)
    compile_blueprint(enemy, True)

    character = unreal.load_asset(CHAR)
    arm = unreal.load_object(None, CHAR + '.BP_ThirdPersonCharacter_C:SpringArmComponent_0__A9892D03')
    assert isinstance(arm, unreal.SpringArmComponent)
    arm.set_editor_property('relative_rotation', unreal.Rotator(pitch=-55, yaw=90, roll=0))
    arm.set_editor_property('target_arm_length', 1400.0)
    arm.set_editor_property('target_offset', unreal.Vector(0, 220, 0))
    arm.set_editor_property('do_collision_test', False)
    arm.set_editor_property('absolute_rotation', True)
    compile_blueprint(character, True)

    # Add state text to the existing pistol's successful-shot HUD update.
    pistol = unreal.load_asset('/Game/Weapons/Pistol/BP_Pistol')
    for graph in unreal.BlueprintEditorLibrary.list_graphs(pistol):
        ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
        for info in BT.get_node_infos(list(ed.list_all_nodes())):
            if info.type_id == '|SetAmmoLabel':
                old = info.node
                status_node = setv(ed, 'StatusLabel', 'EMPTY - DODGE / GET A WEAPON', hud.generated_class().get_path_name())
                for source in inp(old, 'self').list_connected_pins():
                    link(source, inp(status_node, 'self'))
                nxt = list(old.find_then_pin().list_connected_pins())
                old.find_then_pin().break_pin_links()
                chain(old, status_node)
                for p in nxt:
                    link(status_node.find_then_pin(), p)
    compile_blueprint(pistol, True)
    for bp in [hud, pickup, enemy, character, pistol]:
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False), bp.get_path_name()
    return {'saved': [bp.get_path_name() for bp in [hud, pickup, enemy, character, pistol]]}


les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
handle = [None]


def after_pie(dt):
    if les.is_in_play_in_editor():
        return
    unreal.unregister_slate_post_tick_callback(handle[0])
    try:
        result = do_polish()
    except Exception:
        result = {'error': traceback.format_exc()}
        unreal.log_error(result['error'])
    (Path(unreal.Paths.project_saved_dir()) / 'OneShotPolish.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')


handle[0] = unreal.register_slate_post_tick_callback(after_pie)
les.editor_request_end_play()
