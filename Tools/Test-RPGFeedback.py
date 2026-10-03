"""Disposable PIE regression for the production RPG impact feedback.

The fixture calls the real projectile Detonate against a real enemy cluster.
No inventory/Ammo writes, direct enemy Die calls, saved assets, or UI controls.
Damage/cover/one-shot Fire are also covered by Test-CombatRoles.py. This shorter
test follows ground-wave progress, core visibility, drops, and effect lifetime.
Output: Saved/RPGFeedbackTest.json.
"""
import ast
import builtins
import json
import math
import time
from pathlib import Path

import unreal


SESSION_KEY = '_ols_rpg_feedback_qa'
ENEMY_PATHS = (
    '/Game/Enemies/BP_EnemyStraightRunner',
    '/Game/Enemies/BP_EnemyRunnerFast',
    '/Game/Enemies/BP_EnemySniper',
)


def run():
    previous = getattr(builtins, SESSION_KEY, None)
    if previous and not previous.get('finished', False):
        unreal.log('RPG_FEEDBACK_QA: a test is already running')
        return
    report = {'status': 'running', 'passed': False, 'checks': [], 'samples': [],
              'source': 'Production projectile Detonate and real enemy drops; isolated runtime fixture'}
    session = {'handle': None, 'finished': False, 'report': report}
    setattr(builtins, SESSION_KEY, session)
    output = Path(unreal.Paths.project_saved_dir()) / 'RPGFeedbackTest.json'
    wall_start = time.monotonic()
    tracked = {}
    isolated = []
    spawners = []
    baseline = {}
    classes = {}
    state = {'core_checked': False, 'last_sample': -1.0, 'projectile': None}
    world = pawn = movement = performance = None
    original_throttle = original_location = original_rotation = None
    statics = maths = system = None

    def valid(obj):
        return obj is not None and unreal.SystemLibrary.is_valid(obj)

    def clock():
        return float(statics.call_method('GetTimeSeconds', args=(world,))) if valid(world) else 0.0

    def write():
        report['wall_elapsed'] = round(time.monotonic() - wall_start, 3)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def check(name, condition, **evidence):
        report['checks'].append({'name': name, 'passed': bool(condition), **evidence})
        write()

    def remember(actor):
        if valid(actor):
            tracked[actor.get_path_name()] = actor
        return actor

    def actors(name):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, classes[name])) if valid(world) else []

    def collect_effects():
        if not valid(world):
            return
        for name in ('pickup', 'gun', 'bullet', 'bits'):
            for actor in actors(name):
                if actor.get_path_name() not in baseline[name]:
                    remember(actor)

    def drops():
        return [remember(actor) for actor in actors('pickup')
                if actor.get_path_name() not in baseline['pickup']]

    def spawn(cls, location, properties=None, scale=None):
        transform = maths.call_method('MakeTransform', args=(
            location, unreal.Rotator(), scale or unreal.Vector(1, 1, 1)))
        method = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        actor = statics.call_method('BeginDeferredActorSpawnFromClass', args=(
            world, cls, transform, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, method))
        assert valid(actor), 'Runtime RPG fixture could not spawn'
        remember(actor)
        for name, value in (properties or {}).items():
            actor.set_editor_property(name, value)
        statics.call_method('FinishSpawningActor', args=(actor, transform, method))
        return actor

    def freeze_enemy(actor):
        actor.set_actor_tick_enabled(False)
        system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))
        return actor

    def scalar(material, name):
        return float(material.call_method('K2_GetScalarParameterValue', args=(name,)))

    def base_material(material):
        current = material
        for _ in range(8):
            if isinstance(current, unreal.Material):
                return current
            current = current.get_editor_property('parent')
        raise AssertionError('RPG ring material parent chain did not reach a Material')

    def sample(projectile):
        ring = projectile.get_editor_property('ExplosionRing')
        core = projectile.get_editor_property('ExplosionSphere')
        flare = projectile.get_editor_property('ExplosionFlare')
        material = ring.get_material(0)
        flare_material = flare.get_material(0)
        position = ring.call_method('K2_GetComponentLocation')
        flare_position = flare.call_method('K2_GetComponentLocation')
        flare_normal = flare.get_up_vector()
        camera_direction = state['camera_at_detonation'] - flare_position
        camera_distance = math.sqrt(camera_direction.x ** 2 + camera_direction.y ** 2 + camera_direction.z ** 2)
        facing_dot = ((flare_normal.x * camera_direction.x + flare_normal.y * camera_direction.y
                       + flare_normal.z * camera_direction.z) / max(camera_distance, .001))
        scale = ring.get_editor_property('relative_scale3d')
        flare_scale = flare.get_editor_property('relative_scale3d')
        core_scale = core.get_editor_property('relative_scale3d')
        core_radius = max(abs(core_scale.x), abs(core_scale.y), abs(core_scale.z)) * 50.0
        age = clock() - state['detonation_time']
        observation = {'at': round(age, 5), 'progress': scalar(material, 'EffectProgress'),
                       'mode': scalar(material, 'ShapeMode'), 'opacity': scalar(material, 'Opacity'),
                       'ring_world': [position.x, position.y, position.z],
                       'ring_scale': [scale.x, scale.y, scale.z],
                       'ring_visible': bool(ring.is_visible()),
                       'flare_visible': bool(flare.is_visible()),
                       'flare_mode': scalar(flare_material, 'ShapeMode'),
                       'flare_progress': scalar(flare_material, 'EffectProgress'),
                       'flare_opacity': scalar(flare_material, 'Opacity'),
                       'flare_world': [flare_position.x, flare_position.y, flare_position.z],
                       'flare_scale': [flare_scale.x, flare_scale.y, flare_scale.z],
                       'flare_radius': max(abs(flare_scale.x), abs(flare_scale.y)) * 50.0,
                       'flare_facing_dot': facing_dot,
                       'core_visible': bool(core.is_visible()), 'core_radius': core_radius,
                       'camera_yaw': float(camera.get_camera_rotation().yaw),
                       'drops': len(drops())}
        report['samples'].append(observation)
        write()
        return observation

    def cleanup():
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        if valid(world):
            collect_effects()
        for actor in list(tracked.values()):
            if valid(actor):
                actor.destroy_actor()
        for actor, saved in isolated:
            if valid(actor):
                actor.set_actor_enable_collision(saved['collision'])
                actor.set_actor_tick_enabled(saved['tick'])
                if saved['timer']:
                    system.call_method('K2_SetTimer', args=(actor, 'EnemyRolePulse', .1, True, True, 0.0, 0.0))
        if valid(pawn) and not pawn.get_editor_property('Dead') and original_location is not None:
            movement.stop_movement_immediately()
            pawn.set_actor_location(original_location, False, True)
            pawn.set_actor_rotation(original_rotation, True)
        # Fixture teleports can update the real runner's transient progress.
        if valid(world):
            progress_cls = unreal.load_asset('/Game/Runner/BP_RunnerProgress').generated_class()
            for actor in unreal.GameplayStatics.get_all_actors_of_class(world, progress_cls):
                actor.call_method('UpdateProgress')
        for actor, enabled in spawners:
            if valid(actor):
                actor.set_editor_property('Enabled', enabled)
        if valid(performance) and original_throttle is not None:
            performance.set_editor_property('bThrottleCPUWhenNotForeground', original_throttle)
        report['cleanup'] = 'Runtime actors removed; encounter, player, progress, and background throttle restored'

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
            unreal.log_error('RPG_FEEDBACK_QA: ' + str(error))
        write()

    session['cancel'] = lambda: finish('Explicitly cancelled')

    try:
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        maths = unreal.get_default_object(unreal.MathLibrary.static_class())
        system = unreal.get_default_object(unreal.SystemLibrary.static_class())
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert valid(world), 'Start a fresh PIE session for RPG feedback QA'
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        assert valid(pawn) and not pawn.get_editor_property('Dead'), 'RPG QA requires a living player'
        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        assert valid(movement)
        performance = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
        original_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
        performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
        original_location = pawn.get_actor_location()
        original_rotation = pawn.get_actor_rotation()
        anchor = unreal.Vector(20000, 20000, 142.25)
        classes = {name: unreal.load_asset(path).generated_class() for name, path in {
            'enemy': ENEMY_PATHS[0], 'pickup': '/Game/Weapons/Pistol/BP_PistolPickup',
            'gun': '/Game/Weapons/Pistol/BP_Pistol',
            'bullet': '/Game/Weapons/Pistol/BP_BulletProjectile',
            'bits': '/Game/Weapons/Pistol/BP_PistolImpactBits'}.items()}
        baseline = {name: {a.get_path_name() for a in actors(name)}
                    for name in ('pickup', 'gun', 'bullet', 'bits')}
        spawner_cls = unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint').generated_class()
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, spawner_cls):
            spawners.append((actor, actor.get_editor_property('Enabled')))
            actor.set_editor_property('Enabled', False)
        for actor in actors('enemy'):
            isolated.append((actor, {'collision': actor.get_actor_enable_collision(),
                                    'tick': actor.is_actor_tick_enabled(),
                                    'timer': bool(system.call_method('K2_IsTimerActive', args=(actor, 'EnemyRolePulse')))}))
            actor.set_actor_enable_collision(False)
            actor.set_actor_tick_enabled(False)
            system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))
        floor = spawn(unreal.StaticMeshActor.static_class(), anchor + unreal.Vector(0, 0, -anchor.z),
                      scale=unreal.Vector(120, 120, 1))
        component = floor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        assert component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        component.set_collision_profile_name('BlockAll')
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        movement.stop_movement_immediately()
        pawn.set_actor_location(anchor, False, True)
        camera = unreal.GameplayStatics.get_player_camera_manager(world, 0)
        initial_yaw = float(camera.get_camera_rotation().yaw)
        impact = anchor + unreal.Vector(0, 1500, 0)
        offsets = (unreal.Vector(0, 120, 0), unreal.Vector(200, 100, 0), unreal.Vector(-180, 160, 0))
        targets = [freeze_enemy(spawn(unreal.load_asset(path).generated_class(), impact + offset))
                   for path, offset in zip(ENEMY_PATHS, offsets)]
        outsider = freeze_enemy(spawn(classes['enemy'], impact + unreal.Vector(700, 0, 0)))
        projectile = spawn(classes['bullet'], impact, {'WeaponKind': 3})
        state['projectile'] = projectile
        projectile.get_editor_property('ProjectileMovement').call_method('StopMovementImmediately')
        projectile.set_actor_tick_enabled(False)
        radius = float(projectile.get_editor_property('BlastRadius'))
        duration = float(projectile.get_editor_property('ExplosionVisualDuration'))
        core_duration = float(projectile.get_editor_property('ExplosionCoreDuration'))
        core_max_radius = float(projectile.get_editor_property('ExplosionCoreRadius'))
        flare_max_radius = float(projectile.get_editor_property('ExplosionFlareRadius'))
        capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
        expected_ground = pawn.get_actor_location().z - float(capsule.call_method('GetScaledCapsuleHalfHeight')) + 3.0
        report['configuration'] = {'blast_radius': radius, 'wave_duration': duration,
                                   'core_duration': core_duration, 'core_radius': core_max_radius,
                                   'flare_radius': flare_max_radius,
                                   'expected_ground_z': expected_ground}
        state['camera_at_detonation'] = camera.get_camera_location()
        projectile.call_method('Detonate')
        state['detonation_time'] = float(projectile.get_editor_property('ExplosionStartTime'))
        collect_effects()
        check('one_production_rpg_detonation_defeats_cluster', all(a.get_editor_property('Dead') for a in targets))
        check('one_production_rpg_detonation_preserves_outside_target', not outsider.get_editor_property('Dead'))
        actual_drops = drops()
        check('cluster_drops_each_defeated_enemy_weapon',
              len(actual_drops) == 3 and sorted(int(a.get_editor_property('WeaponKind')) for a in actual_drops) == [0, 1, 2],
              kinds=[int(a.get_editor_property('WeaponKind')) for a in actual_drops])
        ring = projectile.get_editor_property('ExplosionRing')
        core = projectile.get_editor_property('ExplosionSphere')
        flare = projectile.get_editor_property('ExplosionFlare')
        assert valid(ring) and valid(core) and valid(flare), 'Detonate must create wave, small core, and impact flare'
        check('ground_wave_uses_flat_plane_mesh',
              ring.get_editor_property('static_mesh').get_path_name() == '/Engine/BasicShapes/Plane.Plane')
        check('ground_wave_has_no_collision', ring.call_method('GetCollisionEnabled') == unreal.CollisionEnabled.NO_COLLISION)
        check('impact_core_has_no_collision', core.call_method('GetCollisionEnabled') == unreal.CollisionEnabled.NO_COLLISION)
        check('impact_flare_has_no_collision', flare.call_method('GetCollisionEnabled') == unreal.CollisionEnabled.NO_COLLISION)
        check('impact_flare_uses_flat_plane_mesh',
              flare.get_editor_property('static_mesh').get_path_name() == '/Engine/BasicShapes/Plane.Plane')
        material = ring.get_material(0)
        base = base_material(material)
        check('ground_wave_material_is_translucent', base.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_TRANSLUCENT,
              material=base.get_path_name(), blend_mode=str(base.get_editor_property('blend_mode')))
        check('ground_wave_material_keeps_depth_test', not base.get_editor_property('disable_depth_test'))
        flare_base = base_material(flare.get_material(0))
        check('impact_flare_reuses_shared_translucent_material',
              flare_base == base and flare_base.get_editor_property('blend_mode') == unreal.BlendMode.BLEND_TRANSLUCENT,
              material=flare_base.get_path_name())
        first = sample(projectile)
        check('ground_wave_selects_shader_shockwave_mode_2', abs(first['mode'] - 2.0) < .001, actual=first['mode'])
        check('ground_wave_has_visible_bounded_opacity', .8 <= first['opacity'] <= 1.0, actual=first['opacity'])
        check('impact_flare_selects_fire_and_sparks_mode_3', abs(first['flare_mode'] - 3.0) < .001,
              actual=first['flare_mode'])
        check('impact_flare_has_visible_bounded_opacity', .8 <= first['flare_opacity'] <= 1.0,
              actual=first['flare_opacity'])
        check('impact_flare_starts_visible_and_bounded', first['flare_visible']
              and abs(first['flare_radius'] - flare_max_radius) < .01
              and flare_max_radius < radius,
              actual_radius=first['flare_radius'], configured_radius=flare_max_radius, blast_radius=radius)
        check('impact_flare_faces_actual_camera_at_detonation', first['flare_facing_dot'] >= .99,
              normal_to_camera_dot=first['flare_facing_dot'])
        check('impact_flare_is_at_actual_projectile_impact',
              all(abs(actual - expected) < .01 for actual, expected in zip(
                  first['flare_world'], (impact.x, impact.y, impact.z))), actual=first['flare_world'])
        check('ground_wave_centers_at_impact_xy_and_ground_plus_3',
              abs(first['ring_world'][0] - impact.x) < .01
              and abs(first['ring_world'][1] - impact.y) < .01
              and abs(first['ring_world'][2] - expected_ground) < .01,
              actual=first['ring_world'], expected=[impact.x, impact.y, expected_ground])
        check('ground_wave_footprint_matches_gameplay_blast_radius',
              abs(first['ring_scale'][0] * 50.0 - radius) < .01
              and abs(first['ring_scale'][1] * 50.0 - radius) < .01,
              scale=first['ring_scale'], blast_radius=radius)
        check('impact_core_stays_small_at_burst_start', first['core_visible'] and first['core_radius'] <= core_max_radius + .01,
              actual_radius=first['core_radius'], configured_radius=core_max_radius)
        check('projectile_is_armed_as_completed_once', bool(projectile.get_editor_property('ExplosionDone')))
        initial_ring, initial_core, initial_flare = ring, core, flare
        before_repeat_progress = first['progress']
        projectile.call_method('Detonate')
        projectile.call_method('Detonate')
        check('repeat_detonate_keeps_same_effect_components',
              projectile.get_editor_property('ExplosionRing') == initial_ring
              and projectile.get_editor_property('ExplosionSphere') == initial_core
              and projectile.get_editor_property('ExplosionFlare') == initial_flare)
        check('repeat_detonate_keeps_same_matching_drops', len(drops()) == 3)
        check('repeat_detonate_does_not_reset_effect_progress',
              scalar(material, 'EffectProgress') + .001 >= before_repeat_progress)
        # Record the reviewed shader branch as evidence; runtime checks follow
        # its input progress rather than duplicating its pixel math in a test.
        source_path = Path(__file__).resolve().parent / 'Author-CombatFieldMaterial.py'
        source_tree = ast.parse(source_path.read_text(encoding='utf-8'))
        shader = next(ast.literal_eval(node.value) for node in source_tree.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'FIELD_SHADER' for target in node.targets))
        report['shader_source_review'] = {'path': str(source_path), 'modes': [2, 3],
            'reviewed_lines': [line.strip() for line in shader.splitlines()
                               if 'waveRadius' in line or 'fade =' in line or 'float alpha =' in line
                               or 'plumeRadius' in line or 'sparkRadius' in line],
            'interpretation': 'Thin ground wave and small fire/sparks flare fade through shared EffectProgress; flare fully fades at progress .68'}
        check('pickup_return_tension_is_preserved',
              abs(float(unreal.get_default_object(classes['pickup']).get_editor_property('ReturnDuration')) - .55) < .001)
        state['last_valid_time'] = 0.0

        def tick(_dt):
            try:
                assert time.monotonic() - wall_start < 12.0, 'RPG feedback QA timed out'
                assert valid(world) and valid(pawn) and not pawn.get_editor_property('Dead'), 'Unexpected player death/world change'
                collect_effects()
                age = clock() - state['detonation_time']
                if valid(projectile):
                    state['last_valid_time'] = age
                    if age - state['last_sample'] >= .01:
                        state['last_sample'] = age
                        current = sample(projectile)
                    else:
                        current = report['samples'][-1]
                    if age >= core_duration + .045 and not state['core_checked']:
                        state['core_checked'] = True
                        check('small_impact_core_hides_after_short_burst', not current['core_visible'],
                              sampled_at=current['at'], core_duration=core_duration)
                        check('returning_weapon_meshes_stay_visible_during_ground_wave',
                              len(drops()) == 3 and all(a.get_editor_property('PickupMesh').is_visible() for a in drops()),
                              sampled_at=current['at'], drop_count=len(drops()))
                    if age > duration + .30:
                        finish('RPG feedback actor outlived its short cleanup window')
                else:
                    samples = report['samples']
                    progress_values = [row['progress'] for row in samples]
                    check('ground_wave_progress_advances_monotonically_for_shader_fade',
                          len(progress_values) >= 5
                          and all(right + .002 >= left for left, right in zip(progress_values, progress_values[1:]))
                          and progress_values[-1] >= .95,
                          sample_count=len(progress_values), first=progress_values[0], last=progress_values[-1])
                    check('ground_wave_scale_does_not_grow_beyond_blast_boundary', all(
                        abs(row['ring_scale'][0] * 50.0 - radius) < .01
                        and abs(row['ring_scale'][1] * 50.0 - radius) < .01 for row in samples))
                    check('impact_flare_stays_within_small_configured_radius', all(
                        row['flare_radius'] <= flare_max_radius + .01 for row in samples),
                        maximum_radius=max(row['flare_radius'] for row in samples), configured_radius=flare_max_radius)
                    check('impact_flare_tracks_same_progress_as_ground_wave', all(
                        abs(row['flare_progress'] - row['progress']) < .002 for row in samples))
                    check('impact_flare_reaches_shader_fade_completion_before_cleanup',
                          any(row['flare_progress'] >= .68 for row in samples))
                    check('impact_flare_remains_facing_captured_impact_camera',
                          all(row['flare_facing_dot'] >= .99 for row in samples))
                    check('all_feedback_components_hide_before_actor_cleanup',
                          not samples[-1]['ring_visible'] and not samples[-1]['core_visible']
                          and not samples[-1]['flare_visible'], final_sample_at=samples[-1]['at'])
                    check('impact_flare_is_removed_with_projectile_cleanup', not valid(initial_flare))
                    check('core_never_becomes_large_opaque_blast_ball', all(
                        row['core_radius'] <= core_max_radius + .01 for row in samples),
                        maximum_radius=max(row['core_radius'] for row in samples))
                    check('camera_stays_fixed_during_explosion_feedback', all(
                        abs(((row['camera_yaw'] - initial_yaw + 180.0) % 360.0) - 180.0) < .001 for row in samples),
                        initial_yaw=initial_yaw)
                    check('short_burst_visibility_was_sampled', state['core_checked'])
                    check('feedback_actor_cleans_up_after_point_42_seconds',
                          duration <= state['last_valid_time'] <= duration + .16
                          and duration + .03 <= age <= duration + .18,
                          last_valid_at=state['last_valid_time'], destroyed_observed_at=age,
                          configured_wave_duration=duration)
                    check('feedback_cleanup_preserves_matching_weapon_drops',
                          len(drops()) == 3 and all(a.get_editor_property('PickupMesh').is_visible() for a in drops()))
                    finish()
            except Exception as error:
                finish(error)

        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
