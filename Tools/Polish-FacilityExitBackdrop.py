"""Add a visual facility continuation beyond the existing exit rail.

This source imports no content and never runs the blanket facility rebuild.
Only Facility_ExitBackdrop_* StaticMeshActors are authored. They have no
collision and do not change the route, camera, spawns, or deleted user actors.
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import unreal
from CombatAuthoring import BT, run_editor

PREFIX = 'Facility_ExitBackdrop_'
FLOOR_PATH = '/Game/Characters/KayKit/Assets/fbx/Floor'


def xyz(value):
    return [value.x, value.y, value.z]


def rotation_data(value):
    return [value.pitch, value.yaw, value.roll]


def snapshot(actor):
    return {'label': actor.get_actor_label(), 'class': actor.get_class().get_path_name(),
            'position': xyz(actor.get_actor_location()),
            'rotation': rotation_data(actor.get_actor_rotation()),
            'scale': xyz(actor.get_actor_scale3d()),
            'collision': actor.get_actor_enable_collision()}


def bounds_data(actor):
    origin, extent = actor.get_actor_bounds(False)
    return {'origin': xyz(origin), 'extent': xyz(extent),
            'min': [origin.x - extent.x, origin.y - extent.y, origin.z - extent.z],
            'max': [origin.x + extent.x, origin.y + extent.y, origin.z + extent.z]}


def work():
    saved = Path(unreal.Paths.project_saved_dir())
    imported = json.loads((saved / 'FacilityImport.json').read_text(encoding='utf-8'))
    layout = json.loads((saved / 'FacilityLayout.json').read_text(encoding='utf-8'))
    assert not imported.get('error') and not layout.get('error')
    records = {entry['source_name']: entry for entry in imported['meshes']}
    required_names = ['Wall', 'Pillar_A', 'Locker', 'Workbench_Decorated']
    meshes = {name: unreal.load_asset(records[name]['path']) for name in required_names}
    assert all(isinstance(mesh, unreal.StaticMesh) for mesh in meshes.values())
    atlas = unreal.load_asset(imported['material'])
    floor = unreal.load_asset(FLOOR_PATH)
    assert floor and atlas
    subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors = list(subsystem.get_all_level_actors())
    by_label = {actor.get_actor_label(): actor for actor in actors}
    assert 'Facility_ExitRail' in by_label, 'The existing exit rail must remain in place'
    rail = by_label['Facility_ExitRail']
    rail_bounds = bounds_data(rail)
    assert abs(rail_bounds['max'][1] - 4200) < .01, rail_bounds

    # A global package save must not accidentally persist an editor launcher.
    # This guard is read-only: the root owns bootstrap/controller cleanup.
    controller = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    graph = unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller, 'EventGraph')
    assert not any(any(pin.name == 'Command' and 'Editor-Queue.py' in str(pin.value)
                       for pin in info.input_pins)
                   for info in BT.get_node_infos(list(graph.list_all_nodes()))), 'Remove the temporary editor queue launcher before the backdrop save'

    original = {actor.get_path_name(): snapshot(actor) for actor in actors
                if not actor.get_actor_label().startswith(PREFIX)}
    deleted_user_actors_before = {label: label in by_label
                                  for label in ['Runner_IntroEnemy', 'Dummy_Target']}
    component_for = lambda actor: actor.get_component_by_class(unreal.StaticMeshComponent)
    static_actors = [actor for actor in actors if isinstance(actor, unreal.StaticMeshActor)
                     and not actor.get_actor_label().startswith(PREFIX)]
    floor_templates = [actor for actor in static_actors
                       if component_for(actor).get_editor_property('static_mesh') == floor
                       and actor.get_actor_location().y <= 4100]
    assert floor_templates, 'An existing combat floor template is required'
    floor_template = by_label.get('Facility_Floor_R11_C1') or max(
        floor_templates, key=lambda actor: actor.get_actor_location().y)
    assert floor_template in floor_templates
    wall_templates = {}
    for side in ['Left', 'Right']:
        candidates = [actor for actor in static_actors
                      if actor.get_actor_label().startswith('Facility_Wall_' + side + '_')
                      and component_for(actor).get_editor_property('static_mesh') == meshes['Wall']]
        assert candidates, side + ' needs an existing matching wall template'
        wall_templates[side] = max(candidates, key=lambda actor: actor.get_actor_location().y)
    foundation_template = by_label.get('Facility_Substructure')
    assert isinstance(foundation_template, unreal.StaticMeshActor), 'Reuse the existing dark substructure'
    foundation_component = component_for(foundation_template)
    foundation_mesh = foundation_component.get_editor_property('static_mesh')
    assert foundation_mesh
    foundation_material = foundation_component.get_material(0)
    assert foundation_material

    def materials_of(actor):
        component = component_for(actor)
        mesh = component.get_editor_property('static_mesh')
        return [component.get_material(index)
                for index in range(len(mesh.get_editor_property('static_materials')))]

    specs = []
    created = []
    updated = []

    def authored_actor(label, mesh, location, rotation, scale, materials, shadows=True):
        assert label.startswith(PREFIX)
        actor = by_label.get(label)
        if actor is None:
            actor = subsystem.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector())
            assert actor
            created.append(label)
            by_label[label] = actor
        else:
            assert isinstance(actor, unreal.StaticMeshActor), label
            updated.append(label)
        actor.modify()
        actor.set_actor_label(label)
        actor.set_folder_path('Facility/ExitBackdrop')
        actor.set_actor_hidden_in_game(False)
        actor.set_actor_scale3d(unreal.Vector(*scale))
        actor.set_actor_rotation(unreal.Rotator(pitch=rotation[0], yaw=rotation[1], roll=rotation[2]), True)
        actor.set_actor_location(unreal.Vector(*location), False, True)
        component = component_for(actor)
        assert component
        component.modify()
        component.set_static_mesh(mesh)
        component.set_mobility(unreal.ComponentMobility.STATIC)
        component.set_editor_property('override_materials', [])
        for index, material in enumerate(materials):
            if material:
                component.set_material(index, material)
        actor.set_actor_enable_collision(False)
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        component.set_editor_property('generate_overlap_events', False)
        component.set_cast_shadow(shadows)
        bounds = bounds_data(actor)
        assert bounds['min'][1] >= rail_bounds['max'][1] - .01, (label, bounds)
        assert not actor.get_actor_enable_collision()
        assert component.get_collision_enabled() == unreal.CollisionEnabled.NO_COLLISION
        specs.append(actor)
        return actor

    def translated_template(label, template, center_x, center_y, shadows=True):
        bounds = bounds_data(template)
        location = template.get_actor_location()
        translated = [location.x + center_x - bounds['origin'][0],
                      location.y + center_y - bounds['origin'][1], location.z]
        return authored_actor(label, component_for(template).get_editor_property('static_mesh'),
                              translated, rotation_data(template.get_actor_rotation()),
                              xyz(template.get_actor_scale3d()), materials_of(template), shadows)

    def centered_piece(label, mesh, center_x, center_y, bottom_z, scale, yaw, materials, shadows=True):
        local = mesh.get_bounds()
        angle = math.radians(yaw)
        ox, oy = local.origin.x * scale[0], local.origin.y * scale[1]
        rx, ry = math.cos(angle) * ox - math.sin(angle) * oy, math.sin(angle) * ox + math.cos(angle) * oy
        location = [center_x - rx, center_y - ry,
                    bottom_z - (local.origin.z - local.box_extent.z) * scale[2]]
        return authored_actor(label, mesh, location, [0.0, yaw, 0.0], scale, materials, shadows)

    # The first floor/wall bounds begin at Y4200, immediately beyond the rail.
    # Existing transforms and materials preserve the facility's visible seams.
    for row, y in enumerate([4400, 4800, 5200, 5600]):
        for column, x in enumerate([-400, 0, 400]):
            translated_template(f'{PREFIX}Floor_R{row:02d}_C{column}', floor_template,
                                x, y, shadows=False)
        for side in ['Left', 'Right']:
            template = wall_templates[side]
            translated_template(f'{PREFIX}Wall_{side}_{row:02d}', template,
                                bounds_data(template)['origin'][0], y)
    for index, x in enumerate([-400, 0, 400]):
        centered_piece(f'{PREFIX}FarWall_{index}', meshes['Wall'], x, 5827, 50,
                       (1.0, 1.0, 1.0), 180.0, [atlas])
    for side, x, yaw in [('Left', -485, -90.0), ('Right', 485, 90.0)]:
        centered_piece(PREFIX + 'Workbench_' + side, meshes['Workbench_Decorated'],
                       x, 4670, 50, (.65, .65, .65), yaw, [atlas])
        centered_piece(PREFIX + 'Locker_' + side, meshes['Locker'],
                       x, 5190, 50, (.65, .65, .65), yaw, [atlas])
        centered_piece(PREFIX + 'Pillar_' + side, meshes['Pillar_A'],
                       x, 5520, 50, (.7, .7, .7), 0.0, [atlas])
    extent = foundation_mesh.get_bounds().box_extent
    foundation_scale = (2600 / (extent.x * 2), 1600 / (extent.y * 2), 90 / (extent.z * 2))
    centered_piece(PREFIX + 'Substructure', foundation_mesh, 0, 5000, -100,
                   foundation_scale, 0.0, [foundation_material], shadows=False)
    assert len(specs) == 30

    current_actors = list(subsystem.get_all_level_actors())
    current_by_path = {actor.get_path_name(): actor for actor in current_actors}
    for path, before in original.items():
        assert path in current_by_path, 'An original actor was unexpectedly removed: ' + path
        assert snapshot(current_by_path[path]) == before, 'An original actor changed: ' + path
    current_labels = {actor.get_actor_label() for actor in current_actors}
    assert {label: label in current_labels for label in deleted_user_actors_before} == deleted_user_actors_before
    level_saved = bool(unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level())
    assert level_saved, 'Exit backdrop map save failed'
    packages_saved = bool(unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True, True))
    assert packages_saved, 'Exit backdrop external actor package save failed'
    dirty_after = [package.get_path_name() for package in
                   list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()) +
                   list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())]
    assert not [path for path in dirty_after if '/Game/ThirdPerson/' in path or '/Game/__ExternalActors__/' in path], dirty_after
    report_actors = []
    for actor in specs:
        component = component_for(actor)
        entry = snapshot(actor)
        entry.update({'bounds': bounds_data(actor),
                      'mesh': component.get_editor_property('static_mesh').get_path_name(),
                      'materials': [material.get_path_name() if material else None for material in materials_of(actor)],
                      'collision_enabled': str(component.get_collision_enabled())})
        report_actors.append(entry)
    return {'level_saved': level_saved, 'dirty_packages_saved': packages_saved,
            'dirty_after_save': dirty_after, 'created': created, 'updated': updated,
            'actor_count': len(specs), 'actors': report_actors,
            'source_templates': {'floor': floor_template.get_actor_label(),
                                 'walls': {side: actor.get_actor_label() for side, actor in wall_templates.items()},
                                 'substructure': foundation_template.get_actor_label()},
            'deleted_user_actors_presence_unchanged': deleted_user_actors_before,
            'original_actors_unchanged': len(original),
            'preserved': ['Route endpoint Y3850', 'Exit rail Y4180', 'All six spawners',
                          'Fixed camera', 'Existing enemy and weapon gameplay'],
            'purpose': 'Visual facility continuation beyond the existing exit barrier; every authored component has no collision'}


if __name__ == '__main__':
    run_editor(work, 'FacilityExitBackdrop.json')
