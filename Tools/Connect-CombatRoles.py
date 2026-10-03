"""Editor-only shared weapon acquisition and enemy-drop routing."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

CHAR = '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter'
PICK = '/Game/Weapons/Pistol/BP_PistolPickup'
PISTOL = '/Game/Weapons/Pistol/BP_Pistol'
ENEMY = '/Game/Enemies/BP_EnemyStraightRunner'
HUD = '/Game/ThirdPerson/Blueprints/BP_AmmoHUD'

def before(ed, node, first, last=None):
    old = list(node.find_execute_pin().list_connected_pins())
    node.find_execute_pin().break_pin_links()
    for p in old:
        link(p, first.find_execute_pin())
    chain(last or first, node)

def configure_pickup(bp):
    ed = func(bp, 'ConfigurePickup')
    kind = get(ed, 'WeaponKind'); mesh = get(ed, 'PickupMesh')
    previous = ed.find_graph_entry_pin()
    for value, path, scale, rotation in [
        (0, '/Game/Characters/KayKit/Assets/fbx/Gun_Pistol', '(X=0.75,Y=0.75,Z=0.75)', '(Pitch=0,Yaw=0,Roll=0)'),
        (1, '/Game/Characters/KayKit/Assets/fbx/Gun_Rifle', '(X=0.9,Y=0.48,Z=0.85)', '(Pitch=0,Yaw=0,Roll=0)'),
        (2, '/Game/Characters/KayKit/Assets/fbx/Gun_Sniper', '(X=0.75,Y=0.75,Z=0.75)', '(Pitch=0,Yaw=0,Roll=0)'),
        (3, '/Engine/BasicShapes/Cylinder', '(X=0.22,Y=0.22,Z=0.9)', '(Pitch=0,Yaw=0,Roll=90)')]:
        assert unreal.load_asset(path), path
        equal = call(ed, MATH+'EqualEqual_IntInt', B=value); link(out(kind, 'WeaponKind'), inp(equal, 'A'))
        gate = branch(ed, out(equal)); link(previous, gate.find_execute_pin())
        static = call(ed, '/Script/Engine.StaticMeshComponent.SetStaticMesh', NewMesh=path)
        link(out(mesh, 'PickupMesh'), inp(static, 'self')); chain(gate, static)
        resize = call(ed, '/Script/Engine.SceneComponent.SetRelativeScale3D', NewScale3D=scale)
        link(out(mesh, 'PickupMesh'), inp(resize, 'self')); chain(static, resize)
        rotate = call(ed, '/Script/Engine.SceneComponent.K2_SetRelativeRotation', NewRotation=rotation, bSweep='false', bTeleport='true')
        link(out(mesh, 'PickupMesh'), inp(rotate, 'self')); chain(resize, rotate)
        previous = out(gate, 'else')
    compile_blueprint(bp, True)
    for graph_name in ['UserConstructionScript', 'EventGraph']:
        event = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, graph_name)
        infos = BT.get_node_infos(list(event.list_all_nodes()))
        if any(i.type_id.endswith('|ConfigurePickup') for i in infos):
            continue
        origin = next(i.node for i in infos if isinstance(i.node, (unreal.K2Node_FunctionEntry, unreal.K2Node_Event)))
        configure = call(event, 'ConfigurePickup')
        insert_after(event, origin, configure)
    compile_blueprint(bp, True)

def work():
    pistol = unreal.load_asset(PISTOL); character = unreal.load_asset(CHAR)
    pickup = unreal.load_asset(PICK); enemy = unreal.load_asset(ENEMY); hud = unreal.load_asset(HUD)
    pistol_class = pistol.generated_class().get_path_name()
    character_class = character.generated_class().get_path_name()
    pickup_class = pickup.generated_class().get_path_name()
    hud_class = hud.generated_class().get_path_name()
    configure_pickup(pickup)

    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(character, 'EquipPistol')
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    if not any(i.type_id.endswith('|ConfigureWeapon') for i in infos):
        spawn = next(i.node for i in infos if isinstance(i.node, unreal.K2Node_SpawnActorFromClass))
        kind = get(ed, 'NextWeaponKind'); setter = setv(ed, 'WeaponKind', cls=pistol_class)
        link(out(kind, 'NextWeaponKind'), inp(setter, 'WeaponKind')); link(out(spawn), inp(setter, 'self'))
        configure = call(ed, pistol_class+':ConfigureWeapon'); link(out(spawn), inp(configure, 'self'))
        chain(setter, configure); insert_after(ed, spawn, setter, configure)
    compile_blueprint(character, True)

    # Every successful equip updates the HUD, including the initial weapon.
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(character, 'EquipPistol')
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    if not any(i.type_id.endswith('|SetWeaponLabel') for i in infos):
        result = next(i.node for i in infos if isinstance(i.node, unreal.K2Node_FunctionResult))
        gun = get(ed, 'EquippedPistol')
        weapon_name = get(ed, 'WeaponName', pistol_class)
        link(out(gun, 'EquippedPistol'), inp(weapon_name, 'self'))
        controller = call(ed, GAME+'GetPlayerController', PlayerIndex=0)
        hud_ref = call(ed, '/Script/Engine.PlayerController.GetHUD')
        link(out(controller), inp(hud_ref, 'self'))
        cast = ed.create_node_from_name('Utilities|Casting|CastToBP_AmmoHUD', unreal.Vector2D(), [])
        link(out(hud_ref), inp(cast, 'Object'))
        label = setv(ed, 'WeaponLabel', cls=hud_class)
        link(out(cast, 'AsBP Ammo HUD'), inp(label, 'self'))
        link(out(weapon_name, 'WeaponName'), inp(label, 'WeaponLabel'))
        chain(cast, label)
        before(ed, result, cast, label)
        link(out(cast, 'CastFailed'), result.find_execute_pin())
    compile_blueprint(character, True)

    acq = unreal.BlueprintGraphEditor.get_graph_editor_by_name(pickup, 'TryAcquire')
    infos = BT.get_node_infos(list(acq.list_all_nodes()))
    equip = next(i.node for i in infos if i.type_id.endswith('|EquipPistol'))
    if not any(i.type_id.endswith('|SetNextWeaponKind') for i in infos):
        kind = get(acq, 'WeaponKind'); next_kind = setv(acq, 'NextWeaponKind', cls=character_class)
        link(out(kind, 'WeaponKind'), inp(next_kind, 'NextWeaponKind'))
        for p in inp(equip, 'self').list_connected_pins():
            link(p, inp(next_kind, 'self'))
        before(acq, equip, next_kind)
    infos = BT.get_node_infos(list(acq.list_all_nodes()))
    if not any(i.type_id.endswith('|SetWeaponLabel') for i in infos):
        status = next(i.node for i in infos if i.type_id.endswith('|SetStatusLabel'))
        equipped = get(acq, 'EquippedPistol', character_class)
        for p in inp(equip, 'self').list_connected_pins():
            link(p, inp(equipped, 'self'))
        name = get(acq, 'WeaponName', pistol_class); link(out(equipped, 'EquippedPistol'), inp(name, 'self'))
        label = setv(acq, 'WeaponLabel', cls=hud_class); link(out(name, 'WeaponName'), inp(label, 'WeaponLabel'))
        for p in inp(status, 'self').list_connected_pins():
            link(p, inp(label, 'self'))
        insert_after(acq, status, label)
    compile_blueprint(pickup, True)

    die = unreal.BlueprintGraphEditor.get_graph_editor_by_name(enemy, 'Die')
    infos = BT.get_node_infos(list(die.list_all_nodes()))
    if not any(i.type_id.endswith('|SetWeaponKind') for i in infos):
        start = next(i.node for i in infos if i.type_id.endswith('|ReturnToPlayer'))
        kind = get(die, 'WeaponKind'); setter = setv(die, 'WeaponKind', cls=pickup_class)
        link(out(kind, 'WeaponKind'), inp(setter, 'WeaponKind'))
        for p in inp(start, 'self').list_connected_pins():
            link(p, inp(setter, 'self'))
        configure = call(die, pickup_class+':ConfigurePickup')
        for p in inp(start, 'self').list_connected_pins():
            link(p, inp(configure, 'self'))
        chain(setter, configure); before(die, start, setter, configure)
    compile_blueprint(enemy, True)

    # Empty prompts describe the actual recovery route; successful pickup owns READY.
    fire = unreal.BlueprintGraphEditor.get_graph_editor_by_name(pistol, 'Fire')
    for info in BT.get_node_infos(list(fire.list_all_nodes())):
        if info.type_id.endswith('|SetStatusLabel'):
            val(info.node, 'StatusLabel', 'EMPTY - BAIT CHARGER INTO WALL')
    compile_blueprint(pistol, True)
    for bp in [character, pickup, enemy, pistol]:
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False), bp.get_path_name()
    return {'saved': [bp.get_path_name() for bp in [character, pickup, enemy, pistol]], 'weapon_kind_mapping': ['Pistol', 'Shotgun', 'Sniper', 'RPG']}

run_editor(work, 'CombatRouting.json')
