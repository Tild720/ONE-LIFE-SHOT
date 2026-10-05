"""Editor-managed current + reserve FIFO; each weapon still supplies one shot."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

CHAR = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'
GUN = '/Game/Weapons/Pistol/BP_Pistol'
PICKUP = '/Game/Weapons/Pistol/BP_PistolPickup'
HUD = '/Game/ThirdPerson/Blueprints/BP_AmmoHUD'


def editor(bp, graph):
    return unreal.BlueprintGraphEditor.get_graph_editor(BT.get_graph(bp, graph))


def node(ed, name):
    return next(n for n in ed.list_all_nodes() if n.get_name() == name)


def entry(ed):
    return next(n for n in ed.list_all_nodes() if isinstance(n, unreal.K2Node_FunctionEntry))


def method(ed, bp, name):
    return call(ed, bp.generated_class().get_path_name() + ':' + name)


def cast(ed, name, source):
    n = ed.create_node_from_name('Utilities|Casting|CastTo' + name, unreal.Vector2D(), [])
    assert n, name
    link(source, inp(n, 'Object'))
    pin_name = next(p.name for p in BT.get_node_infos([n])[0].output_pins if p.name.startswith('As'))
    return n, out(n, pin_name)


def prop(ed, name, owner, cls):
    n = get(ed, name, cls)
    link(owner, inp(n, 'self'))
    return out(n, name)


def valid(ed, source):
    n = call(ed, SYS + 'IsValid')
    link(source, inp(n, 'Object'))
    return out(n)


def equal(ed, source, number):
    n = call(ed, MATH + 'EqualEqual_IntInt', B=number)
    link(source, inp(n, 'A'))
    return out(n)


def select_string(ed, condition, yes, no):
    n = call(ed, MATH + 'SelectString', A=yes, B=no)
    link(condition, inp(n, 'bPickA'))
    return out(n)


def label(ed, kind):
    text = 'EMPTY'
    for i, name in reversed(list(enumerate(['PISTOL', 'SHOTGUN', 'SNIPER', 'RPG']))):
        n = call(ed, MATH + 'SelectString', A=name)
        if hasattr(text, 'is_valid'):
            link(text, inp(n, 'B'))
        else:
            val(n, 'B', text)
        link(equal(ed, kind, i), inp(n, 'bPickA'))
        text = out(n)
    return text


def hud_set(ed, hud, name, value, cls):
    n = setv(ed, name, cls=cls)
    link(hud, inp(n, 'self'))
    if hasattr(value, 'is_valid'):
        link(value, inp(n, name))
    else:
        val(n, name, value)
    return n


def refresh(bp, hud_bp, gun_bp):
    ed = func(bp, 'RefreshWeaponSlotsHUD')
    pc = call(ed, GAME + 'GetPlayerController', PlayerIndex=0)
    h = call(ed, '/Script/Engine.PlayerController.GetHUD')
    link(out(pc), inp(h, 'self'))
    c, hp = cast(ed, 'BP_AmmoHUD', out(h))
    chain(entry(ed), c)
    dead = branch(ed, out(get(ed, 'Dead'), 'Dead'))
    chain(c, dead)
    hc = hud_bp.generated_class().get_path_name()
    reserve = hud_set(ed, hp, 'ReserveWeaponLabel', label(ed, out(get(ed, 'QueuedWeaponKind'), 'QueuedWeaponKind')), hc)
    link(out(dead, 'else'), reserve.find_execute_pin())
    current = out(get(ed, 'EquippedPistol'), 'EquippedPistol')
    has = branch(ed, valid(ed, current))
    chain(reserve, has)
    alive_nodes = [hud_set(ed, hp, 'AmmoLabel', '1/1', hc),
                   hud_set(ed, hp, 'WeaponLabel', prop(ed, 'WeaponName', current, gun_bp.generated_class().get_path_name()), hc),
                   hud_set(ed, hp, 'StatusLabel', 'READY', hc)]
    empty_nodes = [hud_set(ed, hp, 'AmmoLabel', '0/1', hc),
                   hud_set(ed, hp, 'WeaponLabel', 'NO WEAPON', hc),
                   hud_set(ed, hp, 'StatusLabel', 'EMPTY - BAIT CHARGER INTO WALL', hc)]
    dead_nodes = [hud_set(ed, hp, 'ReserveWeaponLabel', 'EMPTY', hc),
                  hud_set(ed, hp, 'AmmoLabel', 'DOWN', hc),
                  hud_set(ed, hp, 'StatusLabel', 'YOU DIED  -  R TO RETRY', hc)]
    link(out(has, 'then'), alive_nodes[0].find_execute_pin())
    link(out(has, 'else'), empty_nodes[0].find_execute_pin())
    link(out(dead, 'then'), dead_nodes[0].find_execute_pin())
    for seq in [alive_nodes, empty_nodes, dead_nodes]:
        for a, b in zip(seq, seq[1:]):
            chain(a, b)


def object_function(bp, name, argument, gun_bp):
    ed = func(bp, name)
    if not entry(ed).find_output_pin(argument).is_valid():
        BT.add_object_function_param(BT.get_graph(bp, name), argument, gun_bp.generated_class(), True)
    return ed, out(entry(ed), argument)


def advance(bp, gun_bp):
    ed, fired = object_function(bp, 'AdvanceWeaponQueue', 'FiredWeapon', gun_bp)
    guard = branch(ed, valid(ed, fired))
    chain(entry(ed), guard)
    same = call(ed, MATH + 'EqualEqual_ObjectObject')
    link(fired, inp(same, 'A'))
    link(out(get(ed, 'EquippedPistol'), 'EquippedPistol'), inp(same, 'B'))
    identity = branch(ed, out(same))
    link(out(guard, 'then'), identity.find_execute_pin())
    spent = branch(ed, equal(ed, prop(ed, 'Ammo', fired, gun_bp.generated_class().get_path_name()), 0))
    link(out(identity, 'then'), spent.find_execute_pin())
    neg = call(ed, MATH + 'Not_PreBool')
    link(out(get(ed, 'Dead'), 'Dead'), inp(neg, 'A'))
    living = branch(ed, out(neg))
    link(out(spent, 'then'), living.find_execute_pin())
    clear = setv(ed, 'EquippedPistol')
    link(out(living, 'then'), clear.find_execute_pin())
    destroy = call(ed, ACT + 'K2_DestroyActor')
    link(fired, inp(destroy, 'self'))
    chain(clear, destroy)
    queued = out(get(ed, 'QueuedWeaponKind'), 'QueuedWeaponKind')
    has_next = call(ed, MATH + 'InRange_IntInt', Min=0, Max=3, InclusiveMin='true', InclusiveMax='true')
    link(queued, inp(has_next, 'Value'))
    promote = branch(ed, out(has_next))
    chain(destroy, promote)
    incoming = setv(ed, 'NextWeaponKind')
    link(queued, inp(incoming, 'NextWeaponKind'))
    link(out(promote, 'then'), incoming.find_execute_pin())
    pop = setv(ed, 'QueuedWeaponKind', -1)
    chain(incoming, pop)
    equip = method(ed, bp, 'EquipPistol')
    chain(pop, equip)
    update = method(ed, bp, 'RefreshWeaponSlotsHUD')
    link(out(promote, 'else'), update.find_execute_pin())


def clear_queue(bp, gun_bp):
    ed, current = object_function(bp, 'ClearWeaponQueue', 'CurrentWeapon', gun_bp)
    clear = setv(ed, 'EquippedPistol')
    chain(entry(ed), clear)
    pop = setv(ed, 'QueuedWeaponKind', -1)
    chain(clear, pop)
    has = branch(ed, valid(ed, current))
    chain(pop, has)
    destroy = call(ed, ACT + 'K2_DestroyActor')
    link(current, inp(destroy, 'self'))
    link(out(has, 'then'), destroy.find_execute_pin())
    update = method(ed, bp, 'RefreshWeaponSlotsHUD')
    chain(destroy, update)
    link(out(has, 'else'), update.find_execute_pin())


def splice_equip(bp):
    ed = editor(bp, 'EquipPistol')
    original = node(ed, 'K2Node_IfThenElse_0')
    ent = entry(ed)
    ent.find_then_pin().break_pin_links()
    neg = call(ed, MATH + 'Not_PreBool')
    link(out(get(ed, 'Dead'), 'Dead'), inp(neg, 'A'))
    living = branch(ed, out(neg))
    chain(ent, living)
    kind = out(get(ed, 'NextWeaponKind'), 'NextWeaponKind')
    range_check = call(ed, MATH + 'InRange_IntInt', Min=0, Max=3, InclusiveMin='true', InclusiveMax='true')
    link(kind, inp(range_check, 'Value'))
    valid_kind = branch(ed, out(range_check))
    link(out(living, 'then'), valid_kind.find_execute_pin())
    link(out(valid_kind, 'then'), original.find_execute_pin())
    loaded = node(ed, 'K2Node_IfThenElse_2')
    out(loaded, 'else').break_pin_links()
    room = branch(ed, equal(ed, out(get(ed, 'QueuedWeaponKind'), 'QueuedWeaponKind'), -1))
    link(out(loaded, 'else'), room.find_execute_pin())
    reserve = setv(ed, 'QueuedWeaponKind')
    link(kind, inp(reserve, 'QueuedWeaponKind'))
    link(out(room, 'then'), reserve.find_execute_pin())
    reserved_refresh = method(ed, bp, 'RefreshWeaponSlotsHUD')
    chain(reserve, reserved_refresh)
    success = node(ed, 'K2Node_FunctionResult_0')
    chain(reserved_refresh, success)
    old_hud = node(ed, 'K2Node_VariableSet_2')
    old_hud.find_then_pin().break_pin_links()
    updated = method(ed, bp, 'RefreshWeaponSlotsHUD')
    chain(old_hud, updated)
    chain(updated, success)
    failed_cast = out(node(ed, 'K2Node_DynamicCast_0'), 'CastFailed')
    failed_cast.break_pin_links()
    link(failed_cast, updated.find_execute_pin())


def splice_fire(gun_bp, char_bp):
    ed = editor(gun_bp, 'Fire')
    owner = call(ed, ACT + 'GetOwner')
    c, cp = cast(ed, 'BP_ThirdPersonCharacter', out(owner))
    old_tail = node(ed, 'K2Node_VariableSet_2')
    old_tail.find_then_pin().break_pin_links()
    chain(old_tail, c)
    cast_fail = out(node(ed, 'K2Node_DynamicCast_0'), 'CastFailed')
    cast_fail.break_pin_links()
    link(cast_fail, c.find_execute_pin())
    advance_call = method(ed, char_bp, 'AdvanceWeaponQueue')
    link(cp, inp(advance_call, 'self'))
    link(selfpin(ed), inp(advance_call, 'FiredWeapon'))
    chain(c, advance_call)


def splice_pickup(bp):
    ed = editor(bp, 'TryAcquire')
    ent = entry(ed)
    ent.find_then_pin().break_pin_links()
    neg = call(ed, MATH + 'Not_PreBool')
    link(out(get(ed, 'Consumed'), 'Consumed'), inp(neg, 'A'))
    once = branch(ed, out(neg))
    chain(ent, once)
    link(out(once, 'then'), node(ed, 'K2Node_IfThenElse_8').find_execute_pin())
    success = node(ed, 'K2Node_IfThenElse_11')
    out(success, 'then').break_pin_links()
    consumed = setv(ed, 'Consumed', 'true')
    link(out(success, 'then'), consumed.find_execute_pin())
    destroy = node(ed, 'K2Node_CallFunction_23')
    destroy.find_execute_pin().break_pin_links()
    chain(consumed, destroy)


def splice_death(bp):
    ed = editor(bp, 'EventGraph')
    clear = method(ed, bp, 'ClearWeaponQueue')
    link(out(get(ed, 'EquippedPistol'), 'EquippedPistol'), inp(clear, 'CurrentWeapon'))
    insert_after(ed, node(ed, 'K2Node_VariableSet_0'), clear)


def work():
    char, gun, pickup, hud = [unreal.load_asset(p) for p in [CHAR, GUN, PICKUP, HUD]]
    assert all([char, gun, pickup, hud])
    command = json.loads((Path(unreal.Paths.project_saved_dir()) / 'EditorCommand.json').read_text(encoding='utf-8'))
    if command.get('hud_only'):
        refresh(char, hud, gun)
        compile_blueprint(char, True)
        assert unreal.EditorAssetLibrary.save_loaded_asset(char, False)
        return {'hud_labels': 'Existing 1/1 and 0/1 contract preserved', 'saved': CHAR}
    # A completed install must not splice a second death or fire callback.
    infos = BT.get_node_infos(list(editor(gun, 'Fire').list_all_nodes()))
    if any('AdvanceWeaponQueue' in i.type_id.replace(' ', '') for i in infos):
        for bp in [char, gun, pickup, hud]:
            compile_blueprint(bp, True)
        return {'already_installed': True, 'slots': 2, 'assets': [CHAR, GUN, PICKUP, HUD]}
    var(char, 'QueuedWeaponKind', 'int', -1)
    var(hud, 'ReserveWeaponLabel', 'string', 'EMPTY')
    var(pickup, 'Consumed', 'bool', False)
    refresh(char, hud, gun)
    compile_blueprint(char)
    advance(char, gun)
    clear_queue(char, gun)
    compile_blueprint(char)
    splice_equip(char)
    compile_blueprint(char)
    splice_fire(gun, char)
    splice_pickup(pickup)
    splice_death(char)
    results = {}
    for bp in [char, gun, pickup, hud]:
        compile_blueprint(bp, True)
        results[bp.get_name()] = 'passed'
    unreal.get_default_object(char.generated_class()).set_editor_property('QueuedWeaponKind', -1)
    unreal.get_default_object(hud.generated_class()).set_editor_property('ReserveWeaponLabel', 'EMPTY')
    cdo = unreal.get_default_object(pickup.generated_class())
    cdo.set_editor_property('Consumed', False)
    assert abs(cdo.get_editor_property('ReturnDuration') - .55) < .001
    for bp in [char, gun, pickup, hud]:
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    return {'compiled': results, 'slots': 2, 'reserve_default': -1,
            'return_duration': cdo.get_editor_property('ReturnDuration'),
            'assets': [CHAR, GUN, PICKUP, HUD]}


run_editor(work, 'WeaponQueueImplementation.json')
