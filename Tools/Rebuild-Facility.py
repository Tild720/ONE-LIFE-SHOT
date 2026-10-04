"""Author the existing level as a compact KayKit robotics facility.

Editor managed actors and assets only. Importing this module is read-only;
the root editor queue calls its main entry after inspecting FacilityImport.json.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from CombatAuthoring import BT, compile_blueprint, link, run_editor

ROOT = '/Game/LevelPrototyping/KayKit'
FLOOR = '/Game/Characters/KayKit/Assets/fbx/Floor'
FLAT_PARENT = '/Game/LevelPrototyping/Materials/M_FlatCol'
SPAWNER = '/Game/Enemies/BP_EnemySpawnPoint'
ROLE_PATHS = {
    'basic': '/Game/Enemies/BP_EnemyStraightRunner',
    'assault': '/Game/Enemies/BP_EnemyRunnerFast',
    'heavy': '/Game/Enemies/BP_EnemyRunnerSlow',
    'sniper': '/Game/Enemies/BP_EnemySniper',
}
PALETTE = {
    'Floor': (0.18, 0.195, 0.215, 1.0),
    'FloorDark': (0.125, 0.14, 0.16, 1.0),
    'Trim': (0.095, 0.11, 0.13, 1.0),
    'PaintAmber': (0.55, 0.25, 0.055, 1.0),
    'PaintWhite': (0.36, 0.385, 0.41, 1.0),
}
BAYS = [
    {'number': '01', 'title': 'RESEARCH', 'start_y': -600, 'end_y': 600, 'label_y': 170},
    {'number': '02', 'title': 'ASSEMBLY', 'start_y': 600, 'end_y': 1650, 'label_y': 980},
    {'number': '03', 'title': 'SECURITY', 'start_y': 1650, 'end_y': 2700, 'label_y': 2070},
    {'number': '04', 'title': 'CORE', 'start_y': 2700, 'end_y': 4200, 'label_y': 3020},
]


def vec(values):
    return unreal.Vector(*values)


def xyz(value):
    return [value.x, value.y, value.z]


def rot(values):
    pitch, yaw, roll = values
    return unreal.Rotator(pitch=pitch, yaw=yaw, roll=roll)


def bounds_data(actor):
    origin, extent = actor.get_actor_bounds(False)
    return {'origin': xyz(origin), 'extent': xyz(extent),
            'min': [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z],
            'max': [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]}


def material_instances():
    parent = unreal.load_asset(FLAT_PARENT)
    assert isinstance(parent, unreal.Material), FLAT_PARENT
    library = unreal.MaterialEditingLibrary
    assert {'Base Color'} <= {str(v) for v in library.get_vector_parameter_names(parent)}
    assert {'Metallic', 'Roughness'} <= {str(v) for v in library.get_scalar_parameter_names(parent)}
    result = {}
    for suffix, color in PALETTE.items():
        name = 'MI_Facility' + suffix
        path = ROOT + '/Materials/' + name
        material = unreal.load_asset(path)
        if material is None:
            material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                name, ROOT + '/Materials', unreal.MaterialInstanceConstant,
                unreal.MaterialInstanceConstantFactoryNew())
        assert isinstance(material, unreal.MaterialInstanceConstant), path
        material.modify()
        library.set_material_instance_parent(material, parent)
        # UE5.8 native setters perform the update but return their untouched
        # bResult=false variable. Read the resulting parameters to verify them.
        library.set_material_instance_vector_parameter_value(material, 'Base Color', unreal.LinearColor(*color))
        library.set_material_instance_scalar_parameter_value(material, 'Metallic', 0.1)
        library.set_material_instance_scalar_parameter_value(material, 'Roughness', 0.82)
        library.update_material_instance(material)
        actual_color = library.get_material_instance_vector_parameter_value(material, 'Base Color')
        assert all(abs(actual - expected) < .00001
                   for actual, expected in zip([actual_color.r, actual_color.g, actual_color.b, actual_color.a], color)), path
        assert abs(library.get_material_instance_scalar_parameter_value(material, 'Metallic') - .1) < .00001, path
        assert abs(library.get_material_instance_scalar_parameter_value(material, 'Roughness') - .82) < .00001, path
        assert unreal.EditorAssetLibrary.save_loaded_asset(material, False), path
        result[suffix] = material
    return result


def strip_bootstrap():
    controller = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    assert controller
    editor = unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller, 'EventGraph')
    removed = []
    for info in BT.get_node_infos(list(editor.list_all_nodes())):
        if not any(pin.name == 'Command' and 'Editor-Queue.py' in str(pin.value)
                   for pin in info.input_pins):
            continue
        node = info.node
        previous = list(node.find_execute_pin().list_connected_pins())
        following = list(node.find_then_pin().list_connected_pins())
        removed.append(node.get_name())
        editor.remove_nodes([node])
        for source in previous:
            for target in following:
                link(source, target)
    compile_blueprint(controller, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(controller, False)
    assert not any(any(pin.name == 'Command' and 'Editor-Queue.py' in str(pin.value)
                       for pin in info.input_pins)
                   for info in BT.get_node_infos(list(editor.list_all_nodes())))
    return removed


def ensure_facility_collisions(meshes):
    """Verify actual shapes, including convex shapes omitted by simple count."""
    editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    report = []
    for name in ['Wall', 'Wall_Decorated', 'Pillar_A', 'Locker',
                 'Barrel_A', 'Barrel_B', 'Barrel_C']:
        mesh = meshes[name]
        assert mesh.get_path_name().startswith(ROOT + '/Meshes/'), 'Do not change shared meshes outside this facility import'
        simple = editor.get_simple_collision_count(mesh)
        convex = editor.get_convex_collision_count(mesh)
        assert simple >= 0 and convex >= 0, name
        generated = False
        if simple + convex == 0:
            shape = (unreal.ScriptCollisionShapeType.NDOP26 if name.startswith('Barrel')
                     else unreal.ScriptCollisionShapeType.BOX)
            mesh.modify()
            assert editor.add_simple_collisions(mesh, shape) >= 0, name
            generated = True
        simple = editor.get_simple_collision_count(mesh)
        convex = editor.get_convex_collision_count(mesh)
        assert simple + convex > 0, name
        assert unreal.EditorAssetLibrary.save_loaded_asset(mesh, False), mesh.get_path_name()
        report.append({'mesh': mesh.get_path_name(), 'simple_count': simple,
                       'convex_count': convex, 'generated': generated,
                       'complexity': str(editor.get_collision_complexity(mesh))})
    # A convex hull across an open window would create a hidden solid sheet.
    # These static perimeter frames use their real triangles for all queries.
    window = meshes['Wall_Window_Open']
    assert window.get_path_name().startswith(ROOT + '/Meshes/')
    body = window.get_editor_property('body_setup')
    if body is None:
        assert editor.add_simple_collisions(window, unreal.ScriptCollisionShapeType.BOX) >= 0
        body = window.get_editor_property('body_setup')
    assert body
    window.modify()
    body.modify()
    body.set_editor_property('collision_trace_flag', unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    # This native editor call removes convex/primitive hulls, rebuilds the mesh,
    # and refreshes placed physics components with the new per-triangle policy.
    assert editor.remove_collisions(window)
    assert editor.get_collision_complexity(window) == unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    assert unreal.EditorAssetLibrary.save_loaded_asset(window, False), window.get_path_name()
    report.append({'mesh': window.get_path_name(),
                   'simple_count': editor.get_simple_collision_count(window),
                   'convex_count': editor.get_convex_collision_count(window),
                   'complexity': str(editor.get_collision_complexity(window)),
                   'policy': 'Visible window frame triangles; the window opening remains open'})
    return report


def work():
    saved = Path(unreal.Paths.project_saved_dir())
    manifest = json.loads((saved / 'FacilityImport.json').read_text(encoding='utf-8'))
    assert not manifest.get('error') and not manifest.get('skipped'), manifest
    records = {entry['source_name']: entry for entry in manifest['meshes']}
    meshes = {name: unreal.load_asset(entry['path']) for name, entry in records.items()}
    assert all(isinstance(mesh, unreal.StaticMesh) for mesh in meshes.values())
    floor = unreal.load_asset(FLOOR)
    cube = unreal.load_asset('/Engine/BasicShapes/Cube')
    atlas = unreal.load_asset(manifest['material'])
    assert floor and cube and atlas
    floor_bounds = floor.get_bounds()
    assert abs(floor_bounds.box_extent.x * 2 - 400) < 0.01
    assert abs(floor_bounds.box_extent.z * 2 - 50) < 0.01
    role_classes = {name: unreal.load_asset(path).generated_class()
                    for name, path in ROLE_PATHS.items()}
    spawner_bp = unreal.load_asset(SPAWNER)
    assert spawner_bp
    compile_blueprint(spawner_bp, True)
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    by_label = {actor.get_actor_label(): actor for actor in actors}
    required = ['Runner_StartPoint', 'Runner_EndPoint', 'Runner_ProgressManager',
                'Runner_IntroEnemy', 'PlayerStart', 'Runner_EndSpawn_1',
                'Runner_EndSpawn_2', 'Runner_EndSpawn_3', 'Runner_EndSpawn_4']
    assert all(label in by_label for label in required), required
    assert all(by_label[label].get_class() == spawner_bp.generated_class()
               for label in required if 'EndSpawn' in label)
    removed_bootstrap = strip_bootstrap()
    materials = material_instances()
    collision_assets = ensure_facility_collisions(meshes)
    changed = []
    deleted = []
    created = []
    old_geometry = []
    geometry_pool = []
    # Reuse the existing StaticMeshActor instances before creating extra pieces.
    # All obsolete tail tiles and geometric walls are removed through Editor.
    for actor in actors:
        label = actor.get_actor_label()
        if isinstance(actor, unreal.StaticMeshActor):
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            mesh = component.get_editor_property('static_mesh')
            if label.startswith('Facility_') or label.startswith('RunnerWall_') or (
                    mesh == floor and (label.startswith('RunnerFloor_') or label.startswith('Floor'))):
                old_geometry.append({'label': label, 'bounds': bounds_data(actor)})
                geometry_pool.append(actor)
        elif label.startswith('Facility_') and isinstance(actor, unreal.TextRenderActor):
            assert subsystem.destroy_actor(actor)
            deleted.append(label)
    geometry_pool.sort(key=lambda actor: (actor.get_actor_location().y,
                                         actor.get_actor_location().x, actor.get_actor_label()))

    def identity(actor, label, folder):
        actor.modify()
        actor.set_actor_label(label)
        actor.set_folder_path('Facility/' + folder)
        actor.set_actor_hidden_in_game(False)

    def static(label, mesh, center_x, center_y, bottom_z=50.0,
               scale=(1.0, 1.0, 1.0), yaw=0.0, material=None,
               collision=False, folder='Props'):
        if geometry_pool:
            actor = geometry_pool.pop(0)
        else:
            actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
            assert actor, label
            created.append(label)
        identity(actor, label, folder)
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        assert component
        component.modify()
        component.set_static_mesh(mesh)
        component.set_mobility(unreal.ComponentMobility.STATIC)
        component.set_editor_property('override_materials', [])
        if material:
            for index in range(len(mesh.get_editor_property('static_materials'))):
                component.set_material(index, material)
        # Center each mesh in X/Y and place its actual lower bound on the floor.
        # Barrels are center-pivoted, whereas walls/furniture are bottom-pivoted.
        local = mesh.get_bounds()
        radians = math.radians(yaw)
        ox, oy = local.origin.x * scale[0], local.origin.y * scale[1]
        rx = math.cos(radians) * ox - math.sin(radians) * oy
        ry = math.sin(radians) * ox + math.cos(radians) * oy
        min_z = local.origin.z - local.box_extent.z
        actor.set_actor_scale3d(vec(scale))
        actor.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0), True)
        actor.set_actor_location(unreal.Vector(center_x - rx, center_y - ry,
                                              bottom_z - min_z * scale[2]), False, True)
        actor.set_actor_enable_collision(collision)
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS
                                        if collision else unreal.CollisionEnabled.NO_COLLISION)
        if collision:
            component.set_collision_profile_name('BlockAll')
            component.set_collision_object_type(unreal.CollisionChannel.ECC_WORLD_STATIC)
            # RPG radial damage uses Camera for solid-cover occlusion. The
            # camera boom already disables collision, so Camera must block here.
            for channel in [unreal.CollisionChannel.ECC_CAMERA,
                            unreal.CollisionChannel.ECC_BULLET,
                            unreal.CollisionChannel.ECC_PAWN]:
                component.set_collision_response_to_channel(channel, unreal.CollisionResponseType.ECR_BLOCK)
        component.set_cast_shadow(collision and folder not in ['Floors', 'Paint'])
        changed.append(actor)
        return actor

    def box(label, x, y, bottom_z, size, material, collision=False, folder='Paint'):
        extent = cube.get_bounds().box_extent
        scale = (size[0] / (extent.x * 2), size[1] / (extent.y * 2),
                 size[2] / (extent.z * 2))
        return static(label, cube, x, y, bottom_z, scale=scale,
                      material=material, collision=collision, folder=folder)

    def prop(label, name, x, y, uniform=1.0, yaw=0.0, collision=False,
             height_scale=None, folder='Props'):
        scale = (uniform, uniform, uniform if height_scale is None else height_scale)
        return static(label, meshes[name], x, y, scale=scale, yaw=yaw,
                      material=atlas, collision=collision, folder=folder)

    def text(label, value, position, rotation, size, folder='Signage'):
        actor = subsystem.spawn_actor_from_class(unreal.TextRenderActor, vec(position), rot(rotation))
        assert actor
        identity(actor, label, folder)
        actor.set_actor_enable_collision(False)
        component = actor.get_component_by_class(unreal.TextRenderComponent)
        assert component and component.get_editor_property('font'), 'Use the existing default TextRender font only'
        component.set_text(value)
        component.set_world_size(size)
        component.set_horizontal_alignment(unreal.HorizTextAligment.EHTA_CENTER)
        component.set_vertical_alignment(unreal.VerticalTextAligment.EVRTA_TEXT_CENTER)
        component.set_text_render_color(unreal.Color(157, 169, 182, 255))
        component.set_cast_shadow(False)
        created.append(label)
        changed.append(actor)
        return actor

    # Twelve rows, no gaps, no 150m tail. All collision floors have the same Z50.
    for row, y in enumerate(range(-400, 4001, 400)):
        bay_index = next(i for i, bay in enumerate(BAYS) if bay['start_y'] <= y < bay['end_y'])
        material = materials['FloorDark' if bay_index in [1, 3] else 'Floor']
        for column, x in enumerate([-400, 0, 400]):
            static(f'Facility_Floor_R{row:02d}_C{column}', floor, x, y, bottom_z=0,
                   material=material, collision=True, folder='Floors')

    # Perimeter panels carry the visual and physical boundary themselves. No
    # invisible old cube barriers survive behind the newly authored walls.
    for side, x, yaw in [('Left', -630, -90), ('Right', 630, 90)]:
        for index, y in enumerate(range(-400, 4001, 400)):
            name = 'Wall_Window_Open' if index in [1, 4, 7, 10] else (
                   'Wall_Decorated' if index in [2, 5, 8, 11] else 'Wall')
            static(f'Facility_Wall_{side}_{index:02d}', meshes[name], x, y,
                   yaw=yaw, material=atlas, collision=True, folder='Walls')
    for index, x in enumerate([-400, 0, 400]):
        static(f'Facility_Wall_Back_{index}', meshes['Wall'], x, -630,
               material=atlas, collision=True, folder='Walls')
    # The camera-facing exit boundary is a visible low rail, with no overhead
    # portal or transverse wall hiding the final combat group.
    box('Facility_ExitRail', 0, 4180, 50, (1260, 40, 100), materials['Trim'], True, 'Walls')

    for bay in BAYS:
        y = bay['label_y']
        text('Facility_Sign_' + bay['number'], bay['number'] + '  ' + bay['title'],
             (597, y, 218), (0, 180, 0), 34)
        text('Facility_Number_' + bay['number'], bay['number'],
             (-490, y, 51.2), (90, -30, 0), 78)
    text('Facility_ExitText', 'EXIT', (0, 3900, 51.4), (90, -30, 0), 68)
    for index, y in enumerate([600, 1650, 2700]):
        for side, x in [('Left', -480), ('Right', 480)]:
            prop(f'Facility_Gate_{index}_{side}', 'Pillar_A', x, y,
                 height_scale=0.39, collision=True, folder='Walls')
            box(f'Facility_Threshold_{index}_{side}', x, y, 50.12,
                (230, 12, 0.25), materials['PaintAmber'])
    for side, x in [('Left', -562), ('Right', 562)]:
        box('Facility_EdgeStripe_' + side, x, 1800, 50.12,
            (5, 4750, 0.25), materials['PaintAmber'])
    box('Facility_Substructure', 0, 1800, -100, (2600, 5000, 90),
        materials['Trim'], collision=False, folder='Substructure')

    # Purposeful side workstations, assembled equipment, sentry alcoves, then
    # grouped core canisters. Gameplay cover leaves central X±280 unobstructed.
    prop('Facility_Lab_Workbench', 'Workbench_Decorated', 510, 145, .55, 90)
    prop('Facility_Lab_LockerA', 'Locker', 515, 340, .6, 90)
    prop('Facility_Lab_LockerB', 'Locker', 515, 425, .6, 90)
    prop('Facility_Lab_Table', 'table_medium_Decorated', -495, 130, .7, -90)
    prop('Facility_Lab_Box', 'Box_A', -490, 245, .65, -18)
    prop('Facility_Assembly_Workbench', 'Workbench_Decorated', 510, 1040, .65, 90)
    prop('Facility_Assembly_Table', 'table_medium_Decorated', 510, 1410, .6, 90)
    prop('Facility_Assembly_CanisterA', 'Barrel_B', -520, 1160, .72)
    prop('Facility_Assembly_CanisterB', 'Barrel_A', -520, 1250, .72)
    prop('Facility_Assembly_BoxA', 'Box_A', -510, 1460, .9, -12)
    prop('Facility_Assembly_BoxB', 'Box_A', -475, 1490, .7, 7)
    prop('Facility_Cover_AssemblyBarrel', 'Barrel_B', -420, 1330, 1.1,
         collision=True, folder='Cover')
    prop('Facility_Cover_AssemblyPillar', 'Pillar_A', 420, 1500, 1.0,
         collision=True, height_scale=.44, folder='Cover')
    prop('Facility_Security_LockerA', 'Locker_Decorated', 510, 2160, .6, 90)
    prop('Facility_Security_LockerB', 'Locker', 510, 2250, .6, 90)
    prop('Facility_Cover_SecurityLocker', 'Locker', -420, 1930, .55, -90,
         collision=True, folder='Cover')
    prop('Facility_Cover_SecurityPillar', 'Pillar_A', 420, 2460, 1.3,
         collision=True, height_scale=.44, folder='Cover')
    prop('Facility_Core_CanisterA', 'Barrel_C', -520, 3030, .8)
    prop('Facility_Core_CanisterB', 'Barrel_C', -520, 3130, .8)
    prop('Facility_Core_CanisterC', 'Barrel_A', 520, 2950, .75)
    prop('Facility_Core_CanisterD', 'Barrel_B', 520, 3060, .75)
    prop('Facility_Core_Terminal', 'Workbench_Decorated', 510, 3520, .55, 90)
    prop('Facility_Core_ColumnA', 'Pillar_B', -520, 3750, .9, height_scale=.50)
    prop('Facility_Core_ColumnB', 'Pillar_B', 520, 3750, .9, height_scale=.50)
    prop('Facility_Cover_CoreBarrelLeft', 'Barrel_C', -420, 2820, 1.4,
         collision=True, folder='Cover')
    prop('Facility_Cover_CoreBarrelRight', 'Barrel_B', 420, 3370, 1.4,
         collision=True, folder='Cover')

    for actor in geometry_pool:
        deleted.append(actor.get_actor_label())
        assert subsystem.destroy_actor(actor)
    for label in ['Pistol Target', 'Dummy_Target', 'Gun_Pistol']:
        actor = by_label.get(label)
        if actor:
            actor.modify()
            actor.set_actor_hidden_in_game(True)
            actor.set_actor_enable_collision(False)

    progress = by_label['Runner_ProgressManager']
    start = by_label['Runner_StartPoint']
    end = by_label['Runner_EndPoint']
    for actor, position in [(start, (0, 0, 50)), (end, (0, 3850, 50)),
                            (by_label['PlayerStart'], (0, 0, 142.25)),
                            (by_label['Runner_IntroEnemy'], (0, 550, 142.25))]:
        actor.modify()
        actor.set_actor_location(vec(position), False, True)
    by_label['PlayerStart'].set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=90.0, roll=0.0), True)
    progress.modify()
    progress.set_editor_property('StartPoint', start)
    progress.set_editor_property('EndPoint', end)
    intro = by_label['Runner_IntroEnemy']
    intro.set_editor_property('CruiseSpeed', 100.0)
    pickups = [actor for actor in actors if actor.get_class().get_name() == 'BP_PistolPickup_C']
    assert len(pickups) == 1, 'Reuse the single existing starter pickup'
    pickups[0].modify()
    pickups[0].set_actor_location(unreal.Vector(0, 0, 75), False, True)
    pickups[0].set_actor_hidden_in_game(False)
    pickups[0].set_actor_enable_collision(True)
    pickups[0].set_editor_property('WeaponKind', 0)

    spawn_settings = [
        ('Runner_EndSpawn_1', 'basic', 0, 1050, 1600, 1.6, 3.6, 2),
        ('Runner_EndSpawn_2', 'assault', -220, 1550, 1500, 1.1, 4.0, 2),
        ('Runner_EndSpawn_3', 'heavy', 150, 3050, 1350, 1.2, 5.0, 1),
        ('Runner_EndSpawn_4', 'sniper', -200, 2350, 1500, 1.0, 5.0, 1),
        ('Facility_CoreSpawn_Basic', 'basic', 170, 3450, 1000, 1.6, 5.0, 1),
        ('Facility_CoreSpawn_Assault', 'assault', -170, 3570, 1100, 2.2, 5.0, 1),
    ]
    spawn_report = []
    for label, role, x, y, activation, delay, interval, cap in spawn_settings:
        actor = by_label.get(label)
        created_spawner = actor is None
        if created_spawner:
            actor = subsystem.spawn_actor_from_class(spawner_bp.generated_class(), unreal.Vector(x, y, 150))
            assert actor
        assert actor.get_class() == spawner_bp.generated_class()
        before_pool = [cls.get_path_name() for cls in actor.get_editor_property('EarlyEnemyPool')]
        identity(actor, label, 'Spawns')
        actor.set_actor_location(unreal.Vector(x, y, 150), False, True)
        actor.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=-90.0, roll=0.0), True)
        actor.set_editor_property('ProgressManager', progress)
        actor.set_editor_property('Enabled', True)
        actor.set_editor_property('SpawnActivationDistance', activation)
        actor.set_editor_property('SpawnMinimumAhead', 250.0)
        actor.set_editor_property('SpawnDelay', delay)
        actor.set_editor_property('MaxAliveEnemies', cap)
        actor.set_editor_property('UseSpawnSpeedOverride', False)
        for stage in ['Early', 'Middle', 'Late', 'Final']:
            actor.set_editor_property(stage + 'Interval', interval)
            actor.set_editor_property(stage + 'EnemyPool', [role_classes[role]])
        spawn_report.append({'label': label, 'role': role, 'enemy_class': role_classes[role].get_path_name(),
                             'position': [x, y, 150], 'activation': activation,
                             'delay': delay, 'interval': interval, 'max_alive': cap,
                             'created_instance': created_spawner, 'previous_pool': before_pool})

    # Existing broad light remains sufficient for reading targets and fields;
    # no animated lamps, local light carpet, new post-process, or camera changes.
    lighting = []
    for label, cls, intensity in [('DirectionalLight', unreal.DirectionalLightComponent, 3.0),
                                  ('SkyLight', unreal.SkyLightComponent, .8)]:
        actor = by_label.get(label)
        if actor:
            actor.modify()
            component = actor.get_component_by_class(cls)
            assert component
            component.modify()
            component.set_intensity(intensity)
            component.set_light_color(unreal.LinearColor(.94, .97, 1.0, 1.0))
            lighting.append({'label': label, 'intensity': intensity})

    cover = [actor for actor in changed if actor.get_actor_label().startswith('Facility_Cover_')]
    assert len(cover) == 6
    for actor in cover:
        bounds = bounds_data(actor)
        assert bounds['max'][0] < -280 or bounds['min'][0] > 280, bounds
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        mesh = component.get_editor_property('static_mesh')
        collision_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        assert (collision_editor.get_simple_collision_count(mesh) +
                collision_editor.get_convex_collision_count(mesh)) > 0, actor.get_actor_label()
        for channel in [unreal.CollisionChannel.ECC_CAMERA,
                        unreal.CollisionChannel.ECC_BULLET,
                        unreal.CollisionChannel.ECC_PAWN]:
            assert component.get_collision_response_to_channel(channel) == unreal.CollisionResponseType.ECR_BLOCK, actor.get_actor_label()
    level_saved = bool(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level())
    assert level_saved, 'The map package did not save'
    dirty_before = [package.get_path_name() for package in
                    list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()) +
                    list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
    dirty_saved = bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True))
    assert dirty_saved, 'Map and external actor package save failed'
    dirty_after = [package.get_path_name() for package in
                   list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()) +
                   list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
    assert not [path for path in dirty_after if '/Game/ThirdPerson/' in path or '/Game/__ExternalActors__/' in path], dirty_after
    layout = []
    for actor in changed:
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        rotation = actor.get_actor_rotation()
        entry = {'label': actor.get_actor_label(), 'class': actor.get_class().get_path_name(),
                 'position': xyz(actor.get_actor_location()), 'scale': xyz(actor.get_actor_scale3d()),
                 'rotation': [rotation.pitch, rotation.yaw, rotation.roll],
                 'collision': actor.get_actor_enable_collision(), 'bounds': bounds_data(actor)}
        if component:
            mesh = component.get_editor_property('static_mesh')
            entry['mesh'] = mesh.get_path_name()
            entry['collision_enabled'] = str(component.get_collision_enabled())
            entry['camera_collision'] = str(component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA))
            entry['bullet_collision'] = str(component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_BULLET))
            entry['pawn_collision'] = str(component.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN))
            entry['materials'] = [material.get_path_name() if material else None
                                  for material in component.get_editor_property('override_materials')]
        else:
            text_component = actor.get_component_by_class(unreal.TextRenderComponent)
            entry['font'] = text_component.get_editor_property('font').get_path_name()
            entry['text'] = str(text_component.get_editor_property('text'))
        layout.append(entry)
    return {'level_saved': level_saved, 'dirty_packages_saved': dirty_saved,
            'dirty_before_save': dirty_before, 'dirty_after_save': dirty_after,
            'bootstrap_nodes_removed': removed_bootstrap, 'old_geometry': old_geometry,
            'deleted_actor_labels': deleted, 'created_actor_labels': created,
            'bay_layout': BAYS, 'actors': layout, 'spawners': spawn_report,
            'course': {'start': [0, 0, 50], 'end': [0, 3850, 50],
                       'floor_top': 50, 'central_clear_half_width': 280,
                       'safe_crossover_y': [450, 1050, 2100, 3200]},
            'starter_pickup': pickups[0].get_actor_label(), 'intro_enemy_y': 550,
            'palette_materials': {name: material.get_path_name() for name, material in materials.items()},
            'lighting': lighting, 'camera_changed': False, 'collision_assets': collision_assets,
            'note': 'Existing six spawner instances use the same retirement window; no new enemy classes or encounter runtime was added.'}


if __name__ == '__main__':
    run_editor(work, 'FacilityLayout.json')
