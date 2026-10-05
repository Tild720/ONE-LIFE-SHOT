"""Read-only editor audit after reloading the saved Lvl_ThirdPerson.

Inspects persisted endpoints, existing spawn Blueprint instances, geometry,
collision responses and single progress/HUD ownership. Does not compile,
spawn, reposition, hide, delete or save anything. Root should stop PIE and
reload the level before executing this script through the editor queue.
Output: Saved/FacilityPersistenceAudit.json.
"""
import json
from pathlib import Path

import unreal


def run():
    output = Path(unreal.Paths.project_saved_dir()) / 'FacilityPersistenceAudit.json'
    report = {'status': 'complete', 'passed': False, 'read_only': True,
              'source': 'Editor actors loaded from saved map after root reload',
              'checks': [], 'geometry': [], 'spawners': [], 'legacy_collision': [],
              'background_geometry': []}

    def valid(obj):
        return obj is not None and unreal.SystemLibrary.is_valid(obj)

    def xyz(vector):
        return [round(vector.x, 3), round(vector.y, 3), round(vector.z, 3)]

    def check(name, condition, **evidence):
        report['checks'].append({'name': name, 'passed': bool(condition), **evidence})

    def collision_on(component):
        return component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION

    try:
        subsystem = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        game = subsystem.get_game_world()
        assert not valid(game), 'Stop PIE and reload the persisted level before this read-only audit'
        world = subsystem.get_editor_world()
        assert valid(world), 'No loaded editor world'
        report['world'] = world.get_path_name()
        check('existing_gameplay_map_remains_loaded', 'Lvl_ThirdPerson' in report['world'])
        actors = list(unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors())
        progress_class = unreal.load_asset('/Game/Runner/BP_RunnerProgress').generated_class()
        spawner_class = unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint').generated_class()
        managers = [a for a in actors if a.get_class() == progress_class]
        spawners = [a for a in actors if a.get_class() == spawner_class]
        check('one_persisted_route_and_progress_hud_owner', len(managers) == 1,
              labels=[a.get_actor_label() for a in managers])
        assert len(managers) == 1, 'A single assigned route manager is required'
        manager = managers[0]
        start, end = manager.get_editor_property('StartPoint'), manager.get_editor_property('EndPoint')
        assert valid(start) and valid(end), 'Persisted route lost an endpoint reference'
        start_pos, end_pos = start.get_actor_location(), end.get_actor_location()
        report['endpoints'] = {'start': {'label': start.get_actor_label(), 'position': xyz(start_pos)},
                               'end': {'label': end.get_actor_label(), 'position': xyz(end_pos)}}
        check('persisted_route_starts_at_zero_and_ends_at_3850', abs(start_pos.y) < 1.0
              and abs(end_pos.y - 3850.0) < 1.0 and abs(start_pos.x - end_pos.x) < 1.0,
              start=xyz(start_pos), end=xyz(end_pos))
        check('six_persisted_spawners_reuse_existing_blueprint', len(spawners) == 6,
              count=len(spawners))
        expected_y = [1050, 1550, 2350, 3050, 3450, 3570]
        actual_y = sorted(a.get_actor_location().y for a in spawners)
        check('persisted_spawn_points_follow_authored_bay_order', len(actual_y) == len(expected_y)
              and all(abs(a - b) < 1.0 for a, b in zip(actual_y, expected_y)),
              expected=expected_y, actual=actual_y)
        for actor in spawners:
            row = {'label': actor.get_actor_label(), 'location': xyz(actor.get_actor_location()),
                   'enabled': bool(actor.get_editor_property('Enabled')),
                   'progress_reference': actor.get_editor_property('ProgressManager') == manager,
                   'retired': bool(actor.get_editor_property('SpawnRetired')),
                   'open': bool(actor.get_editor_property('SpawnWindowOpen')),
                   'activation_distance': float(actor.get_editor_property('SpawnActivationDistance')),
                   'minimum_ahead': float(actor.get_editor_property('SpawnMinimumAhead')),
                   'delay': float(actor.get_editor_property('SpawnDelay'))}
            report['spawners'].append(row)
            check('persisted_spawn_configuration_' + row['label'], row['enabled'] and row['progress_reference']
                  and not row['retired'] and not row['open']
                  and row['activation_distance'] > row['minimum_ahead'] > 0.0, **row)
        geometry = [a for a in actors if a.get_actor_label().startswith('Facility_')
                    and a.get_component_by_class(unreal.StaticMeshComponent) is not None]
        check('authored_facility_mesh_geometry_is_persisted', len(geometry) >= 20,
              count=len(geometry))
        manifest = Path(unreal.Paths.project_saved_dir()) / 'FacilityLayout.json'
        layout = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
        assert not layout.get('error'), 'Facility authoring report contains an error'
        expected_meshes = {entry['label']: entry['mesh'] for entry in layout.get('actors', [])
                           if entry.get('mesh') and entry['label'].startswith('Facility_')}
        covers = []
        for actor in geometry:
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            mesh = component.get_editor_property('static_mesh')
            row = {'label': actor.get_actor_label(), 'location': xyz(actor.get_actor_location()),
                   'mesh': mesh.get_path_name() if valid(mesh) else None,
                   'collision': str(component.get_collision_enabled()),
                   'mobility': str(component.get_editor_property('mobility'))}
            report['geometry'].append(row)
            if row['label'].startswith('Facility_Cover_'):
                covers.append(actor)
                mesh_editor = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
                simple_count = int(mesh_editor.get_simple_collision_count(mesh))
                convex_count = int(mesh_editor.get_convex_collision_count(mesh))
                check('persisted_real_cover_channels_' + row['label'], simple_count + convex_count > 0 and collision_on(component)
                      and all(component.get_collision_response_to_channel(channel) == unreal.CollisionResponseType.ECR_BLOCK
                              for channel in (unreal.CollisionChannel.ECC_PAWN, unreal.CollisionChannel.ECC_BULLET,
                                              unreal.CollisionChannel.ECC_CAMERA)), simple_collision_shapes=simple_count,
                      convex_collision_shapes=convex_count, **row)
        check('authored_cover_and_assault_bait_survive_reload', bool(covers),
              labels=[a.get_actor_label() for a in covers])
        missing_meshes = [row for row in report['geometry'] if row['mesh'] is None]
        check('persisted_geometry_keeps_actual_mesh_assignments', not missing_meshes, missing=missing_meshes)
        if expected_meshes:
            loaded_meshes = {row['label']: row['mesh'] for row in report['geometry']}
            mismatches = {label: {'expected': mesh, 'loaded': loaded_meshes.get(label)}
                          for label, mesh in expected_meshes.items() if loaded_meshes.get(label) != mesh}
            check('every_authored_mesh_actor_survives_saved_map_reload', not mismatches,
                  authored_mesh_count=len(expected_meshes), loaded_mesh_count=len(loaded_meshes),
                  mismatches=mismatches)
        for actor in actors:
            # Inspect only old StaticMesh geometry; markers, managers, and
            # gameplay Blueprint capsules are not old corridor construction.
            if actor.get_actor_label().startswith('Facility_') or not isinstance(actor, unreal.StaticMeshActor):
                continue
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            if not valid(component):
                continue
            mesh = component.get_editor_property('static_mesh')
            if valid(mesh) and mesh.get_path_name() == '/Engine/EngineSky/SM_SkySphere.SM_SkySphere':
                # This exact asset was verified in FacilityInventory. A
                # background dome is not a leftover corridor floor/wall.
                # Record it explicitly instead of ignoring labels containing
                # "sky", which could accidentally hide real construction.
                report['background_geometry'].append({'label': actor.get_actor_label(),
                    'mesh': mesh.get_path_name(), 'actor_collision': actor.get_actor_enable_collision(),
                    'component_collision': str(component.get_collision_enabled()),
                    'responses': {name: str(component.get_collision_response_to_channel(channel))
                        for name, channel in (('Pawn', unreal.CollisionChannel.ECC_PAWN),
                                              ('Bullet', unreal.CollisionChannel.ECC_BULLET),
                                              ('Camera', unreal.CollisionChannel.ECC_CAMERA))}})
                continue
            if not actor.get_actor_enable_collision() or not collision_on(component):
                continue
            origin, extent = actor.get_actor_bounds(True)
            maximum_y = origin.y + extent.y
            if maximum_y > 3955.0:
                report['legacy_collision'].append({'label': actor.get_actor_label(),
                    'origin': xyz(origin), 'extent': xyz(extent), 'maximum_y': maximum_y})
        check('old_corridor_tail_has_no_remaining_collision_past_3950', not report['legacy_collision'],
              offenders=report['legacy_collision'])
        controller_bp = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
        from editor_toolset.toolsets.blueprint import BlueprintTools as BT
        graph = unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller_bp, 'EventGraph')
        queue_nodes = [info.node.get_name() for info in BT.get_node_infos(list(graph.list_all_nodes()))
                       if any(pin.name == 'Command' and 'Tools/Editor-Queue.py' in pin.value for pin in info.input_pins)]
        check('persisted_controller_contains_no_temporary_queue_launcher', not queue_nodes, nodes=queue_nodes)
        pickup = unreal.get_default_object(unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup').generated_class())
        check('saved_weapon_return_duration_stays_point_55', abs(float(pickup.get_editor_property('ReturnDuration')) - .55) < .001)
        report['passed'] = bool(report['checks']) and all(c['passed'] for c in report['checks'])
    except Exception as error:
        report['error'] = str(error)
        unreal.log_error('FACILITY_PERSISTENCE_AUDIT: ' + str(error))
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')


run()
