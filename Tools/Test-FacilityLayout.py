"""Runtime acceptance for the authored facility in a fresh PIE session.

Uses actual CharacterMovement, the saved route geometry, and production
SpawnNext timers. One initial position reset starts the route; every accepted
passage afterwards uses AddMovementInput. Enemies are frozen only at runtime
to isolate traversal, while actual spawn owners and retirement remain intact.
No asset is saved, no inventory/death value is written, and no target is added.
Restart PIE after this test: passed spawn points intentionally remain retired.
Output: Saved/FacilityLayoutTest.json.
"""
import builtins
import json
import math
import time
from pathlib import Path

import unreal


SESSION_KEY = '_ols_facility_layout_qa'
SPAWNER_PATH = '/Game/Enemies/BP_EnemySpawnPoint'
ENEMY_PATH = '/Game/Enemies/BP_EnemyStraightRunner'
PROGRESS_PATH = '/Game/Runner/BP_RunnerProgress'
HUD_PATH = '/Game/ThirdPerson/Blueprints/BP_AmmoHUD'
WIDGET_PATH = '/Game/UI/WBP_RunnerProgress'


def run():
    prior = getattr(builtins, SESSION_KEY, None)
    if prior and not prior.get('finished', False):
        unreal.log('FACILITY_LAYOUT_QA: an acceptance run is already active')
        return
    saved_dir = Path(unreal.Paths.project_saved_dir())
    output = saved_dir / 'FacilityLayoutTest.json'
    report = {'status': 'running', 'passed': False, 'checks': [], 'samples': [],
              'source': 'Actual saved map, production CharacterMovement and SpawnNext timers',
              'limitations': 'Enemy Tick, collision and role timers isolated; physical keyboard, subjective readability and collision-free visual occlusion require viewport review'}
    session = {'handle': None, 'finished': False}
    setattr(builtins, SESSION_KEY, session)
    wall_start = time.monotonic()
    world = pawn = movement = performance = statics = system = None
    original_location = original_rotation = original_throttle = None
    frozen = {}
    observed_owners = {}
    retired_counts = {}
    retirement_violations = []
    state = {'phase': 'settle', 'started': None, 'index': 0,
             'last_sample': -1.0, 'leg_start': None, 'leg_time': None}

    def valid(obj):
        try:
            return obj is not None and unreal.SystemLibrary.is_valid(obj)
        except Exception:
            return False

    def xyz(vector):
        return [round(vector.x, 3), round(vector.y, 3), round(vector.z, 3)]

    def clock():
        return float(statics.call_method('GetTimeSeconds', args=(world,)))

    def write():
        report['wall_elapsed'] = round(time.monotonic() - wall_start, 3)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def check(name, condition, **evidence):
        report['checks'].append({'name': name, 'passed': bool(condition), **evidence})
        write()

    def actors(cls):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, cls))

    def trace_evidence(cover, trace_start, trace_end, ignored, profile=None):
        # Editor mesh-shape counting is intentionally prohibited during PIE.
        # Query the active physics scene instead. Camera is a real trace
        # channel; Pawn is an object channel queried through its existing
        # built-in collision profile, not an invalid TraceTypeQuery mapping.
        arguments = (world, trace_start, trace_end,
                     profile if profile is not None else unreal.TraceTypeQuery.TRACE_TYPE_QUERY2,
                     False, ignored, unreal.DrawDebugTrace.NONE, True,
                     unreal.LinearColor(0, 0, 0, 0), unreal.LinearColor(0, 0, 0, 0), 0.0)
        result = (unreal.SystemLibrary.line_trace_single_by_profile(*arguments) if profile is not None
                  else unreal.SystemLibrary.line_trace_single(*arguments))
        values = result if isinstance(result, (tuple, list)) else [result]
        hit = next((item for item in values if isinstance(item, unreal.HitResult)), None)
        if hit is None:
            return {'blocking': False, 'exact_cover': False, 'hit_actor': None,
                    'start': xyz(trace_start), 'end': xyz(trace_end)}
        broken = statics.call_method('BreakHitResult', args=(hit,))
        hit_actor = next((item for item in broken if isinstance(item, unreal.Actor)), None)
        return {'blocking': bool(broken[0]), 'exact_cover': hit_actor == cover,
                'hit_actor': hit_actor.get_path_name() if valid(hit_actor) else None,
                'start': xyz(trace_start), 'end': xyz(trace_end)}

    def isolate_actual_enemies():
        for enemy in actors(enemy_class):
            key = enemy.get_path_name()
            owner = enemy.call_method('GetOwner')
            if valid(owner) and owner in spawners:
                observed_owners.setdefault(owner.get_path_name(), set()).add(key)
            if key in frozen:
                continue
            frozen[key] = (enemy, {
                'collision': enemy.get_actor_enable_collision(),
                'tick': enemy.is_actor_tick_enabled(),
                'timer': bool(system.call_method('K2_IsTimerActive', args=(enemy, 'EnemyRolePulse')))})
            enemy.set_actor_enable_collision(False)
            enemy.set_actor_tick_enabled(False)
            system.call_method('K2_ClearTimer', args=(enemy, 'EnemyRolePulse'))

    def observe_retirement():
        for point in spawners:
            key = point.get_path_name()
            count = len(observed_owners.get(key, set()))
            retired = bool(point.get_editor_property('SpawnRetired'))
            if key not in retired_counts and retired:
                retired_counts[key] = count
            elif key in retired_counts and (not retired or count != retired_counts[key]):
                retirement_violations.append({'point': key, 'before': retired_counts[key],
                                              'after': count, 'retired': retired})

    def sample():
        position = pawn.get_actor_location()
        rotation = camera.get_camera_rotation()
        feet_z = position.z - float(capsule.call_method('GetScaledCapsuleHalfHeight'))
        row = {'at': round(clock(), 3), 'phase': state['phase'], 'player': xyz(position),
               'feet_z': round(feet_z, 3), 'camera': [rotation.pitch, rotation.yaw, rotation.roll],
               'speed': round(pawn.get_velocity().length(), 3),
               'progress': round(float(progress.get_editor_property('Progress')), 4),
               'retired': sum(bool(p.get_editor_property('SpawnRetired')) for p in spawners)}
        report['samples'].append(row)
        write()

    def cleanup():
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        for enemy, before in frozen.values():
            if valid(enemy):
                enemy.set_actor_enable_collision(before['collision'])
                enemy.set_actor_tick_enabled(before['tick'])
                if before['timer'] and not enemy.get_editor_property('Dead'):
                    system.call_method('K2_SetTimer', args=(enemy, 'EnemyRolePulse', .1, True, True, 0.0, 0.0))
        if valid(pawn) and not pawn.get_editor_property('Dead') and original_location is not None:
            movement.stop_movement_immediately()
            pawn.set_actor_location(original_location, False, True)
            pawn.set_actor_rotation(original_rotation, True)
            if valid(progress):
                progress.call_method('UpdateProgress')
        if valid(performance) and original_throttle is not None:
            performance.set_editor_property('bThrottleCPUWhenNotForeground', original_throttle)
        report['cleanup'] = 'Player and enemy runtime isolation restored; no saved asset changed. Restart PIE to reset legitimately retired map spawners.'

    def finish(error=None):
        if session['finished']:
            return
        session['finished'] = True
        try:
            cleanup()
        except Exception as failure:
            report['cleanup_error'] = str(failure)
            error = error or failure
        report['status'] = 'complete'
        report['passed'] = error is None and bool(report['checks']) and all(c['passed'] for c in report['checks'])
        if error is not None:
            report['error'] = str(error)
            unreal.log_error('FACILITY_LAYOUT_QA: ' + str(error))
        write()

    session['cancel'] = lambda: finish('Explicitly cancelled')
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert valid(world), 'Start a fresh PIE session before facility acceptance'
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        system = unreal.get_default_object(unreal.SystemLibrary.static_class())
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        assert valid(pawn) and valid(controller) and not pawn.get_editor_property('Dead'), 'Living local player required'
        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
        assert valid(movement) and valid(capsule)
        enemy_class = unreal.load_asset(ENEMY_PATH).generated_class()
        spawners = actors(unreal.load_asset(SPAWNER_PATH).generated_class())
        managers = actors(unreal.load_asset(PROGRESS_PATH).generated_class())
        assert len(managers) == 1, 'Map must have one route/HUD owner'
        progress = managers[0]
        start = progress.get_editor_property('StartPoint')
        end = progress.get_editor_property('EndPoint')
        assert valid(start) and valid(end), 'Actual route endpoints must be assigned'
        start_pos, end_pos = start.get_actor_location(), end.get_actor_location()
        camera = unreal.GameplayStatics.get_player_camera_manager(world, 0)
        initial_camera = camera.get_camera_rotation()
        original_location, original_rotation = pawn.get_actor_location(), pawn.get_actor_rotation()
        performance = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
        original_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
        performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
        manifest = saved_dir / 'FacilityLayout.json'
        layout = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
        assert not layout.get('error'), 'Facility authoring report contains an error; finish/save the map before acceptance'
        crossover_values = layout.get('course', {}).get('safe_crossover_y',
            layout.get('qa_crossovers', layout.get('crossovers', [450, 1050, 2100, 3200])))
        crossovers = [float(p['y'] if isinstance(p, dict) else p) for p in crossover_values]
        assert len(crossovers) >= 3 and all(100 < y < 3700 for y in crossovers)
        report['configuration'] = {'manifest': str(manifest) if manifest.is_file() else None,
            'crossovers': crossovers, 'side_sample_x': 260, 'route_start': xyz(start_pos),
            'route_end': xyz(end_pos), 'walking_floor_top': 50, 'spawner_count': len(spawners)}
        check('saved_route_has_intended_straight_endpoints', abs(start_pos.y) < 1.0
              and abs(end_pos.y - 3850.0) < 1.0 and abs(start_pos.x - end_pos.x) < 1.0,
              start=xyz(start_pos), end=xyz(end_pos))
        check('actual_map_uses_six_existing_spawner_instances', len(spawners) == 6,
              points=[p.get_path_name() for p in spawners])
        check('fresh_map_spawners_begin_unretired', all(not p.get_editor_property('SpawnRetired') for p in spawners))
        hud = controller.get_hud()
        check('existing_ammo_hud_is_the_active_local_hud', valid(hud)
              and hud.get_class() == unreal.load_asset(HUD_PATH).generated_class())
        widgets = [p.get_editor_property('ProgressHUD') for p in managers]
        active = [w for w in widgets if valid(w) and w.call_method('IsInViewport')]
        check('one_existing_progress_widget_has_one_route_owner', len(active) == 1
              and active[0].get_class() == unreal.load_asset(WIDGET_PATH).generated_class()
              and active[0].call_method('GetOwningPlayer') == controller,
              widget_paths=[w.get_path_name() for w in active])
        if active:
            visibility = active[0].call_method('GetVisibility')
            check('progress_ui_does_not_capture_mouse_input', visibility in (
                unreal.SlateVisibility.HIT_TEST_INVISIBLE, unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE),
                visibility=str(visibility))
        cover_class = unreal.StaticMeshActor.static_class()
        cover_actors = [a for a in actors(cover_class) if a.get_actor_label().startswith('Facility_Cover_')]
        check('authored_map_has_real_bait_or_cover_geometry', bool(cover_actors),
              labels=[a.get_actor_label() for a in cover_actors])
        for cover in cover_actors:
            component = cover.get_component_by_class(unreal.StaticMeshComponent)
            responses = {name: str(component.get_collision_response_to_channel(channel)) for name, channel in (
                ('Pawn', unreal.CollisionChannel.ECC_PAWN), ('Bullet', unreal.CollisionChannel.ECC_BULLET),
                ('Camera', unreal.CollisionChannel.ECC_CAMERA))}
            origin, extent = cover.get_actor_bounds(True)
            half_width = max(float(extent.x) + 20.0, 40.0)
            shot_height = float(original_location.z)
            trace_start = unreal.Vector(origin.x - half_width, origin.y, shot_height)
            trace_end = unreal.Vector(origin.x + half_width, origin.y, shot_height)
            ignored = [pawn] + actors(enemy_class)
            camera_trace = trace_evidence(cover, trace_start, trace_end, ignored)
            pawn_trace = trace_evidence(cover, trace_start, trace_end, ignored, 'Pawn')
            check('solid_cover_channels_' + cover.get_actor_label(),
                  component.get_collision_enabled() != unreal.CollisionEnabled.NO_COLLISION
                  and camera_trace['blocking'] and camera_trace['exact_cover']
                  and pawn_trace['blocking'] and pawn_trace['exact_cover']
                  and all(component.get_collision_response_to_channel(channel) == unreal.CollisionResponseType.ECR_BLOCK
                          for channel in (unreal.CollisionChannel.ECC_PAWN, unreal.CollisionChannel.ECC_BULLET,
                                          unreal.CollisionChannel.ECC_CAMERA)), responses=responses,
                  camera_trace=camera_trace, pawn_profile_trace=pawn_trace,
                  collision_readiness='Actual simple physics query at shot height; saved shape counts validated separately by editor persistence audit')
        pickup_defaults = unreal.get_default_object(unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup').generated_class())
        check('point_55_return_tension_is_preserved', abs(float(pickup_defaults.get_editor_property('ReturnDuration')) - .55) < .001)
        isolate_actual_enemies()
        movement.stop_movement_immediately()
        pawn.set_actor_location(unreal.Vector(start_pos.x, 100, original_location.z), False, True)
        state['started'] = clock()
        waypoints = []
        for index, y in enumerate(sorted(crossovers)):
            waypoints.extend([(f'forward_bay_{index}', 0.0, y), (f'left_bay_{index}', -260.0, y),
                              (f'cross_bay_{index}', 260.0, y), (f'center_bay_{index}', 0.0, y)])
        waypoints.extend([('forward_end', 0.0, 3700.0), ('retreat_all_bays', 0.0, 100.0)])

        def tick(_dt):
            try:
                assert time.monotonic() - wall_start < 65.0, 'Facility route acceptance timed out'
                assert valid(world) and valid(pawn) and not pawn.get_editor_property('Dead'), 'World or player changed during isolated movement acceptance'
                isolate_actual_enemies()
                observe_retirement()
                now = clock()
                if now - state['last_sample'] >= .08:
                    state['last_sample'] = now
                    sample()
                if state['phase'] == 'settle':
                    if now - state['started'] < .25:
                        return
                    state['phase'] = 'move'
                if state['index'] >= len(waypoints):
                    rows = report['samples']
                    # PlayerStart may begin a few units above the floor.
                    # Assess the traversed route after the settle phase,
                    # preserving those startup samples as separate evidence.
                    floor_values = [row['feet_z'] for row in rows if row['phase'] != 'settle']
                    check('continuous_route_and_crossovers_never_fall_or_climb_decor', all(49.0 <= z <= 57.0 for z in floor_values),
                          minimum_foot_z=min(floor_values), maximum_foot_z=max(floor_values))
                    def angle_error(a, b):
                        return abs(((a - b + 180.0) % 360.0) - 180.0)
                    check('camera_keeps_fixed_quarter_view_during_all_passages', all(
                        angle_error(row['camera'][0], initial_camera.pitch) < .2
                        and angle_error(row['camera'][1], initial_camera.yaw) < .2
                        and angle_error(row['camera'][2], initial_camera.roll) < .2 for row in rows)
                        and angle_error(initial_camera.pitch, -55.0) < .2
                        and angle_error(initial_camera.yaw, 90.0) < .2,
                        first_camera=[initial_camera.pitch, initial_camera.yaw, initial_camera.roll])
                    for point in spawners:
                        check('actual_passed_point_stays_retired_' + point.get_name(),
                              point.get_editor_property('SpawnRetired')
                              and not point.get_editor_property('SpawnWindowOpen')
                              and not system.call_method('K2_IsTimerActive', args=(point, 'SpawnNext')),
                              location=xyz(point.get_actor_location()),
                              actual_owned_spawns=len(observed_owners.get(point.get_path_name(), set())))
                    check('retreat_adds_no_new_enemy_from_passed_points', not retirement_violations,
                          violations=retirement_violations)
                    check('traversal_observed_actual_owner_linked_map_spawns', sum(len(v) for v in observed_owners.values()) > 0,
                          observed_counts={key: len(value) for key, value in observed_owners.items()})
                    check('layout_movement_reaches_end_and_retreats_without_teleports', state['index'] == len(waypoints),
                          accepted_passages=len(waypoints), final_position=xyz(pawn.get_actor_location()))
                    finish()
                    return
                name, x, y = waypoints[state['index']]
                if state['leg_start'] is None:
                    state['leg_start'] = pawn.get_actor_location()
                    state['leg_time'] = now
                    state['phase'] = name
                position = pawn.get_actor_location()
                dx, dy = start_pos.x + x - position.x, y - position.y
                remaining = math.hypot(dx, dy)
                if remaining < 24.0:
                    movement.stop_movement_immediately()
                    travel = position - state['leg_start']
                    check('real_character_movement_' + name, math.hypot(travel.x, travel.y) > 100.0,
                          start=xyz(state['leg_start']), end=xyz(position),
                          duration=round(now - state['leg_time'], 3), remaining=round(remaining, 3))
                    state['index'] += 1
                    state['leg_start'] = None
                    return
                elapsed = now - state['leg_time']
                expected = math.hypot(start_pos.x + x - state['leg_start'].x, y - state['leg_start'].y) / 150.0 + 2.0
                assert elapsed < expected, 'Blocked actual passage ' + name + ' at ' + str(xyz(position))
                pawn.add_movement_input(unreal.Vector(dx / remaining, dy / remaining, 0), 1.0, False)
            except Exception as error:
                finish(error)

        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
