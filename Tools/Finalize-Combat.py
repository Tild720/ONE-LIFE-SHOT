"""Scoped editor-managed persistence and final combat cleanup."""
import sys
import builtins
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    enemy = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    assert enemy
    appearance = unreal.BlueprintGraphEditor.get_graph_editor_by_name(enemy, 'ConfigureEnemyAppearance')
    rotations = 0
    for info in BT.get_node_infos(list(appearance.list_all_nodes())):
        for pin in info.input_pins:
            if pin.name == 'NewRotation' and 'Pitch=90' in str(pin.value):
                val(info.node, 'NewRotation', '(Pitch=0,Yaw=0,Roll=90)')
                rotations += 1
    die = unreal.BlueprintGraphEditor.get_graph_editor_by_name(enemy, 'Die')
    infos = BT.get_node_infos(list(die.list_all_nodes()))
    if not any(i.type_id.endswith('|HideTelegraph') for i in infos):
        dead = next(i.node for i in infos if i.type_id.endswith('|SetDead'))
        hide = call(die, 'HideTelegraph')
        clear = call(die, SYS+'K2_ClearTimer', FunctionName='EnemyRolePulse')
        link(selfpin(die), inp(clear, 'Object'))
        chain(hide, clear)
        insert_after(die, dead, hide, clear)
    compile_blueprint(enemy, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(enemy, False)

    paths = ['/Game/Characters/KayKit/Assets/fbx/Gun_Pistol',
             '/Game/Characters/KayKit/Assets/fbx/Gun_Rifle',
             '/Game/Characters/KayKit/Assets/fbx/Gun_Sniper']
    source = unreal.load_asset(paths[0])
    reference = source.find_socket('Muzzle').get_editor_property('relative_location')
    axis = 'x' if abs(reference.x) > abs(reference.y) else 'y'
    direction = 1 if getattr(reference, axis) >= 0 else -1
    sockets = {}
    for path in paths:
        mesh = unreal.load_asset(path)
        assert mesh, path
        socket = mesh.find_socket('Muzzle')
        if socket is None:
            bounds = mesh.get_bounding_box()
            center = (bounds.min + bounds.max) * .5
            position = unreal.Vector(center.x, center.y, bounds.min.z + (bounds.max.z-bounds.min.z)*.78)
            setattr(position, axis, getattr(bounds.max if direction > 0 else bounds.min, axis)+direction)
            socket = unreal.new_object(unreal.StaticMeshSocket, outer=mesh, name='Muzzle')
            socket.set_editor_property('socket_name', 'Muzzle')
            socket.set_editor_property('relative_location', position)
            socket.set_editor_property('relative_rotation', unreal.Rotator())
            socket.set_editor_property('relative_scale', unreal.Vector(1,1,1))
            mesh.add_socket(socket)
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False)
        sockets[path] = str(socket.get_editor_property('relative_location'))

    compiled = []
    for path in ['/Game/Enemies/BP_EnemyRunnerFast', '/Game/Enemies/BP_EnemyRunnerSlow',
                 '/Game/Enemies/BP_EnemySniper', '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter',
                 '/Game/ThirdPerson/Blueprints/BP_AmmoHUD', '/Game/Weapons/Pistol/BP_Pistol',
                 '/Game/Weapons/Pistol/BP_PistolPickup', '/Game/Weapons/Pistol/BP_BulletProjectile']:
        bp = unreal.load_asset(path)
        assert bp, path
        compile_blueprint(bp, True)
        compiled.append(path)

    # Remove only the unsaved queue bootstrap node; keep the runtime queue alive.
    ctrl = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    graph = unreal.BlueprintGraphEditor.get_graph_editor_by_name(ctrl, 'EventGraph')
    for info in BT.get_node_infos(list(graph.list_all_nodes())):
        if any(p.name == 'Command' and 'Editor-Queue.py' in str(p.value) for p in info.input_pins):
            previous = list(info.node.find_execute_pin().list_connected_pins())
            following = list(info.node.find_then_pin().list_connected_pins())
            graph.remove_nodes([info.node])
            for a in previous:
                for b in following:
                    link(a,b)
    compile_blueprint(ctrl, True)
    perf = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
    builtins._ols_old_background_throttle = perf.get_editor_property('bThrottleCPUWhenNotForeground')
    perf.set_editor_property('bThrottleCPUWhenNotForeground', False)
    return {'compiled': compiled, 'saved_enemy': enemy.get_path_name(), 'heavy_rotations_fixed': rotations,
            'saved_muzzle_sockets': sockets, 'temporary_bootstrap_removed': True}

run_editor(work, 'CombatFinalize.json')
