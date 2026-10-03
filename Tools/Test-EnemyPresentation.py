"""Disposable PIE acceptance for enemy poses, attack readability, and recovery.

Run once through the editor queue in a fresh PIE session. Existing encounter
actors are isolated only at runtime. The test drives production warnings and
decision timers, observes actual animation assets, and never saves an asset.
Assault goes through its natural warning/charge/recovery; ranged attacks are
escaped after their warning aim locks. Output: Saved/EnemyPresentationTest.json.
"""
import builtins
import json
import time
from pathlib import Path

import unreal


SESSION_KEY = '_ols_enemy_presentation_qa'
ENEMIES = (
    '/Game/Enemies/BP_EnemyStraightRunner',
    '/Game/Enemies/BP_EnemyRunnerFast',
    '/Game/Enemies/BP_EnemySniper',
    '/Game/Enemies/BP_EnemyRunnerSlow',
)
ANIMS = '/Game/Characters/KayKit/Anims/'


def run():
    if hasattr(builtins, SESSION_KEY):
        unreal.log('ENEMY_PRESENTATION_QA: existing session retained')
        return
    report = {'status': 'running', 'passed': False, 'checks': [], 'samples': [],
              'source': 'Production role timers and actual animation assets; disposable runtime fixture'}
    session = {'handle': None, 'finished': False, 'report': report}
    setattr(builtins, SESSION_KEY, session)
    output = Path(unreal.Paths.project_saved_dir()) / 'EnemyPresentationTest.json'
    wall_start = time.monotonic()
    isolated = []
    spawners = []
    tracked = {}
    state = {'phase': 'startup', 'target': None, 'phase_time': 0.0}
    world = pawn = movement = performance = None
    original_throttle = None
    original_location = original_rotation = None
    baseline = {}
    effect_classes = {}
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

    def phase(name):
        state['phase'] = name
        state['phase_time'] = clock()
        report['phase'] = name
        write()

    def remember(actor):
        if valid(actor):
            tracked[actor.get_path_name()] = actor
        return actor

    def actors(cls):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, cls)) if valid(world) else []

    def effects():
        for name, cls in effect_classes.items():
            for actor in actors(cls):
                if actor.get_path_name() not in baseline.get(name, set()):
                    remember(actor)

    def spawn(cls, position, properties=None, scale=None):
        transform = maths.call_method('MakeTransform', args=(
            position, unreal.Rotator(), scale or unreal.Vector(1.0, 1.0, 1.0)))
        method = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        actor = statics.call_method('BeginDeferredActorSpawnFromClass', args=(
            world, cls, transform, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, method))
        assert valid(actor), 'Runtime presentation actor could not spawn'
        remember(actor)
        for name, value in (properties or {}).items():
            actor.set_editor_property(name, value)
        statics.call_method('FinishSpawningActor', args=(actor, transform, method))
        return actor

    def reset_player():
        movement.stop_movement_immediately()
        pawn.set_actor_location(anchor, False, True)

    def clear_targets():
        effects()
        for path, actor in list(tracked.items()):
            if valid(actor) and actor != state.get('floor'):
                actor.destroy_actor()
                tracked.pop(path, None)
        state['target'] = None
        reset_player()

    def animation(actor):
        mesh = actor.get_editor_property('Mesh')
        instance = mesh.get_anim_instance()
        assert valid(instance), 'Enemy has no live animation instance'
        asset = instance.call_method('GetAnimationAsset')
        return {'asset': asset.get_path_name() if valid(asset) else None,
                'position': float(mesh.call_method('GetPosition')),
                'rate': float(mesh.call_method('GetPlayRate')),
                'length': float(asset.call_method('GetPlayLength')) if valid(asset) else 0.0}

    def sample(actor):
        warning = actor.get_editor_property('TelegraphMesh')
        material = warning.get_material(0)
        tint = material.call_method('K2_GetVectorParameterValue', args=('TracerColor',))
        body = actor.get_editor_property('BodyTint')
        target = actor.get_editor_property('AttackTarget')
        direction = actor.get_editor_property('AttackDirection')
        travel = actor.get_editor_property('TravelDirection')
        forward = actor.get_actor_forward_vector()
        warning_position = warning.get_editor_property('relative_location')
        capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
        capsule_half_height = float(capsule.call_method('GetScaledCapsuleHalfHeight'))
        return {'at': round(clock(), 4), 'phase': state['phase'],
                'kind': int(actor.get_editor_property('WeaponKind')),
                'ai_state': int(actor.get_editor_property('AIState')),
                'pose_mode': int(actor.get_editor_property('EnemyPoseMode')),
                'speed': float(actor.get_editor_property('MoveSpeed')),
                'dead': bool(actor.get_editor_property('Dead')),
                'target': [float(target.x), float(target.y), float(target.z)],
                'direction': [float(direction.x), float(direction.y), float(direction.z)],
                'travel': [float(travel.x), float(travel.y), float(travel.z)],
                'forward': [float(forward.x), float(forward.y), float(forward.z)],
                'remaining': float(actor.get_editor_property('StateEndTime')) - clock(),
                'visible': bool(warning.is_visible()),
                'tint': [float(tint.r), float(tint.g), float(tint.b)],
                'body_tint': [float(body.x), float(body.y), float(body.z)],
                'warning_position': [float(warning_position.x), float(warning_position.y), float(warning_position.z)],
                'warning_absolute_location': bool(warning.get_editor_property('absolute_location')),
                'player_capsule_half_height': capsule_half_height,
                'floor_lift': float(actor.get_editor_property('TelegraphFloorLift')),
                'animation': animation(actor)}

    def is_anim(observation, name):
        path = observation['animation']['asset']
        return path is not None and path.startswith(ANIMS + name + '.')

    def tint_matches_multiplier(observation, multiplier):
        return all(abs(actual - base * multiplier) < .01
                   for actual, base in zip(observation['tint'], observation['body_tint']))

    def check_early_role_color(label, observation):
        body = observation['body_tint']
        dominant = max(range(3), key=lambda i: body[i])
        gain = observation['tint'][dominant] / body[dominant] if body[dominant] > .001 else 0
        same_hue = all(abs(actual - base * gain) < .01
                       for actual, base in zip(observation['tint'], body))
        check(label + '_early_warning_keeps_visible_role_color',
              same_hue and .99 <= gain <= 2.05,
              actual=observation['tint'], role_color=body, gain=gain)

    def check_locked_role_color(label, observation):
        check(label + '_settled_final_lock_has_expected_four_times_role_tint',
              observation['ai_state'] == 1 and observation['visible']
              and tint_matches_multiplier(observation, 4.0),
              actual=observation['tint'], expected=[v * 4 for v in observation['body_tint']],
              remaining=observation['remaining'])

    def check_grounded_warning(label, observation):
        actual = observation['warning_position'][2]
        expected = observation['target'][2] - observation['player_capsule_half_height'] + observation['floor_lift']
        check(label + '_warning_plane_stays_above_floor_at_player_foot_height',
              observation['ai_state'] == 1 and observation['visible']
              and observation['warning_absolute_location'] and abs(actual - expected) < .001
              and actual >= 50.0 - .001 and abs(observation['floor_lift'] - 3.0) < .001,
              actual_height=actual, expected_height=expected, fixture_floor_surface=50.0,
              target_height=observation['target'][2], player_capsule_half_height=observation['player_capsule_half_height'],
              configured_floor_lift=observation['floor_lift'])

    def assert_cache_progress(name, before, after):
        first = before['animation']
        second = after['animation']
        length = second['length']
        elapsed = after['at'] - before['at']
        advance = (second['position'] - first['position']) % length if length > 0 else 0.0
        expected = elapsed * second['rate']
        # This samples well below a full loop, so an animation replayed every
        # .1-second AI pulse cannot make the expected .25-second progression.
        check(name, first['asset'] == second['asset'] and expected > .15
              and abs(advance - expected) < .12,
              advance=advance, expected=expected, elapsed=elapsed,
              start_position=first['position'], end_position=second['position'])

    def cleanup():
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        if valid(world):
            effects()
        for actor in list(tracked.values()):
            if valid(actor):
                actor.destroy_actor()
        for actor, saved in isolated:
            if valid(actor):
                actor.set_editor_property('MoveSpeed', saved['speed'])
                actor.set_actor_enable_collision(saved['collision'])
                actor.set_actor_tick_enabled(saved['tick'])
                if saved['timer']:
                    system.call_method('K2_SetTimer', args=(actor, 'EnemyRolePulse', .1, True, True, 0.0, 0.0))
        for actor, enabled in spawners:
            if valid(actor):
                actor.set_editor_property('Enabled', enabled)
        if valid(pawn) and not pawn.get_editor_property('Dead') and original_location is not None:
            movement.stop_movement_immediately()
            pawn.set_actor_location(original_location, False, True)
            pawn.set_actor_rotation(original_rotation, True)
        if valid(performance) and original_throttle is not None:
            performance.set_editor_property('bThrottleCPUWhenNotForeground', original_throttle)
        report['cleanup'] = 'Runtime actors removed; encounter and background throttle restored; restart PIE to reset transient inventory'

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
            unreal.log_error('ENEMY_PRESENTATION_QA: ' + str(error))
        write()

    session['cancel'] = lambda: finish('Explicitly cancelled')

    try:
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        maths = unreal.get_default_object(unreal.MathLibrary.static_class())
        system = unreal.get_default_object(unreal.SystemLibrary.static_class())
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert valid(world), 'Start a fresh PIE session for presentation QA'
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        assert valid(pawn) and not pawn.get_editor_property('Dead'), 'Presentation QA requires a living local player'
        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        assert valid(movement)
        performance = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
        original_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
        performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
        original_location = pawn.get_actor_location()
        original_rotation = pawn.get_actor_rotation()
        anchor = unreal.Vector(20000.0, 20000.0, 142.25)
        classes = [unreal.load_asset(path).generated_class() for path in ENEMIES]
        spawner_class = unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint').generated_class()
        effect_classes = {name: unreal.load_asset(path).generated_class() for name, path in {
            'pickup': '/Game/Weapons/Pistol/BP_PistolPickup',
            'gun': '/Game/Weapons/Pistol/BP_Pistol',
            'bullet': '/Game/Weapons/Pistol/BP_BulletProjectile'}.items()}
        baseline = {name: {a.get_path_name() for a in actors(cls)} for name, cls in effect_classes.items()}
        for actor in actors(spawner_class):
            spawners.append((actor, actor.get_editor_property('Enabled')))
            actor.set_editor_property('Enabled', False)
        for actor in actors(classes[0]):
            isolated.append((actor, {'speed': actor.get_editor_property('MoveSpeed'),
                'collision': actor.get_actor_enable_collision(), 'tick': actor.is_actor_tick_enabled(),
                'timer': bool(system.call_method('K2_IsTimerActive', args=(actor, 'EnemyRolePulse')))}))
            actor.set_editor_property('MoveSpeed', 0.0)
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
        state['floor'] = floor
        reset_player()
        duration = unreal.get_default_object(effect_classes['pickup']).get_editor_property('ReturnDuration')
        check('weapon_return_restored_to_tense_point_55_seconds', abs(float(duration) - .55) < .001,
              actual=float(duration))
        state['target'] = spawn(classes[0], anchor + unreal.Vector(0, 1500, 0))
        phase('basic_pose')

        def tick(_dt):
            try:
                assert time.monotonic() - wall_start < 40.0, 'Enemy presentation QA timed out'
                assert valid(world) and valid(pawn) and not pawn.get_editor_property('Dead'), 'Unexpected player death/world change'
                age = clock() - state['phase_time']
                name = state['phase']
                target = state['target']
                observation = sample(target) if valid(target) else None
                if observation is not None:
                    report['samples'].append(observation)
                if name == 'basic_pose':
                    if age < .2:
                        return
                    if 'first_pose' not in state:
                        check('basic_cruise_uses_actual_run_animation', is_anim(observation, 'A_Dummy_Run')
                              and observation['pose_mode'] == 2 and observation['speed'] > 0,
                              actual=observation)
                        state['first_pose'] = observation
                        return
                    if observation['at'] - state['first_pose']['at'] < .25:
                        return
                    assert_cache_progress('stable_pose_keeps_animation_progress_between_ai_pulses', state.pop('first_pose'), observation)
                    movement.stop_movement_immediately()
                    pawn.set_actor_location(anchor + unreal.Vector(250, 0, 0), False, True)
                    phase('basic_facing')
                    return
                if name == 'basic_facing':
                    if age < .15:
                        return
                    travel = observation['travel']
                    forward = observation['forward']
                    travel_length = (travel[0] ** 2 + travel[1] ** 2) ** .5
                    forward_length = (forward[0] ** 2 + forward[1] ** 2) ** .5
                    dot = ((travel[0] * forward[0] + travel[1] * forward[1]) /
                           (travel_length * forward_length)) if travel_length * forward_length > .001 else 0
                    check('basic_body_turns_to_updated_player_direction_without_sliding',
                          travel[0] > .1 and dot > .995 and is_anim(observation, 'A_Dummy_Run'),
                          actual=observation, forward_travel_alignment=dot)
                    clear_targets()
                    state['target'] = spawn(classes[1], anchor + unreal.Vector(0, 650, 0))
                    state['assault'] = {'warning': None, 'locked': None, 'locked_tint': None, 'charge': None, 'recovery': None}
                    phase('assault_cycle')
                    return
                if name == 'assault_cycle':
                    cycle = state['assault']
                    if observation['ai_state'] == 1 and cycle['warning'] is None:
                        cycle['warning'] = observation
                        check('assault_natural_warning_stops_and_uses_idle', observation['visible']
                              and observation['speed'] == 0 and is_anim(observation, 'A_Dummy_Idle'), actual=observation)
                        check_early_role_color('assault', observation)
                        check_grounded_warning('assault_early', observation)
                    if observation['ai_state'] == 1 and cycle['locked'] is None and observation['remaining'] <= float(target.get_editor_property('WarningLockLeadTime')):
                        cycle['locked'] = observation
                        movement.stop_movement_immediately()
                        pawn.set_actor_location(anchor + unreal.Vector(350, 0, 0), False, True)
                    if observation['ai_state'] == 1 and cycle['locked'] is not None and cycle['locked_tint'] is None and observation['at'] - cycle['locked']['at'] >= .12:
                        cycle['locked_tint'] = observation
                        check_locked_role_color('assault', observation)
                        check_grounded_warning('assault_locked', observation)
                    if target.get_editor_property('ChargeActive') and cycle['charge'] is None:
                        cycle['charge'] = observation
                        check('assault_committed_charge_uses_fast_run', observation['ai_state'] == 2
                              and is_anim(observation, 'A_Dummy_Run') and observation['animation']['rate'] > 1.1
                              and not observation['visible'], actual=observation)
                        check('assault_does_not_retarget_after_final_commitment', cycle['locked'] is not None
                              and all(abs(a-b) < .001 for a,b in zip(cycle['locked']['direction'], observation['direction'])),
                              locked=cycle['locked'], charge=observation)
                        if cycle['locked_tint'] is None:
                            check('assault_settled_final_lock_has_expected_four_times_role_tint', False,
                                  error='No settled final-lock sample before charge')
                    if observation['ai_state'] == 3 and cycle['recovery'] is None:
                        cycle['recovery'] = observation
                        check('assault_after_charge_has_visible_idle_recovery', observation['speed'] == 0
                              and is_anim(observation, 'A_Dummy_Idle') and not target.get_editor_property('ChargeActive'),
                              actual=observation)
                    if cycle['recovery'] is not None and observation['ai_state'] == 0:
                        windup = float(target.get_editor_property('ChargeWindup'))
                        charge = float(target.get_editor_property('ChargeDuration'))
                        recovery = float(target.get_editor_property('RecoveryDuration'))
                        check('assault_warning_charge_and_recovery_follow_editable_timing',
                              cycle['warning'] is not None and cycle['charge'] is not None
                              and abs(cycle['charge']['at'] - cycle['warning']['at'] - windup) < .22
                              and abs(cycle['recovery']['at'] - cycle['charge']['at'] - charge) < .22
                              and abs(observation['at'] - cycle['recovery']['at'] - recovery) < .22,
                              cycle=cycle, end=observation, configured=[windup, charge, recovery])
                        check('assault_can_be_sidestepped_without_player_death', not pawn.get_editor_property('Dead'))
                        clear_targets()
                        state['ranged_kind'] = 3
                        phase('ranged_setup')
                    elif age > 7:
                        raise AssertionError('Assault did not complete natural warning/charge/recovery')
                    return
                if name == 'ranged_setup':
                    kind = state['ranged_kind']
                    state['target'] = spawn(classes[kind], anchor + unreal.Vector(0, 650, 0))
                    target = state['target']
                    system.call_method('K2_ClearTimer', args=(target, 'EnemyRolePulse'))
                    state['ranged'] = {'first': None, 'late': None, 'locked': None, 'locked_tint': None, 'flash': None, 'hidden': None}
                    target.call_method('BeginBlastWarning' if kind == 3 else 'BeginSniperWarning')
                    system.call_method('K2_SetTimer', args=(target, 'EnemyRolePulse', .1, True, True, 0.0, 0.0))
                    phase('ranged_cycle')
                    return
                if name == 'ranged_cycle':
                    cycle = state['ranged']
                    kind = state['ranged_kind']
                    label = 'heavy' if kind == 3 else 'sniper'
                    if observation['ai_state'] == 1 and age >= .12:
                        if cycle['first'] is None:
                            cycle['first'] = observation
                            check(label + '_warning_uses_idle_and_visible_locked_shape',
                                  observation['visible'] and observation['speed'] == 0
                                  and is_anim(observation, 'A_Dummy_Idle'), actual=observation)
                            check_early_role_color(label, observation)
                            check_grounded_warning(label + '_early', observation)
                            movement.stop_movement_immediately()
                            pawn.set_actor_location(anchor + unreal.Vector(80, 0, 0), False, True)
                        elif age >= .55:
                            cycle['late'] = observation
                        if cycle['locked'] is None and observation['remaining'] <= float(target.get_editor_property('WarningLockLeadTime')):
                            cycle['locked'] = observation
                            check(label + '_early_windup_tracks_player_before_commitment',
                                  abs(observation['target'][0] - anchor.x - 80) < 2,
                                  initial=cycle['first']['target'], locked=observation['target'])
                            movement.stop_movement_immediately()
                            pawn.set_actor_location(anchor + unreal.Vector(530 if kind == 3 else 280, 0, 0), False, True)
                        if cycle['locked'] is not None and cycle['locked_tint'] is None and observation['at'] - cycle['locked']['at'] >= .12:
                            cycle['locked_tint'] = observation
                            check_locked_role_color(label, observation)
                            check_grounded_warning(label + '_locked', observation)
                    if observation['ai_state'] == 2 and observation['visible'] and cycle['flash'] is None:
                        cycle['flash'] = observation
                        check(label + '_actual_discharge_has_distinct_visible_flash',
                              cycle['first'] is not None and sum(abs(a-b) for a,b in zip(observation['tint'], cycle['first']['tint'])) > .1,
                              actual=observation, warning=cycle['first'])
                        check(label + '_discharge_flash_has_expected_eight_times_role_tint',
                              tint_matches_multiplier(observation, 8.0), actual=observation['tint'],
                              expected=[v * 8 for v in observation['body_tint']])
                        if cycle['locked_tint'] is None:
                            check(label + '_settled_final_lock_has_expected_four_times_role_tint', False,
                                  error='No settled final-lock sample before discharge')
                        check(label + '_final_warning_remains_locked_through_discharge',
                              cycle['locked'] is not None
                              and all(abs(a-b) < .001 for a,b in zip(cycle['locked']['target'], observation['target']))
                              and all(abs(a-b) < .001 for a,b in zip(cycle['locked']['direction'], observation['direction'])),
                              locked=cycle['locked'], fired=observation)
                        if cycle['late'] is not None:
                            check(label + '_warning_brightens_before_discharge',
                                  sum(cycle['late']['tint']) > sum(cycle['first']['tint']) + .05,
                                  early=cycle['first']['tint'], late=cycle['late']['tint'])
                        else:
                            check(label + '_warning_brightens_before_discharge', False, error='No later windup sample')
                    if observation['ai_state'] == 2 and not observation['visible'] and cycle['flash'] is not None and cycle['hidden'] is None:
                        cycle['hidden'] = observation
                        delay = observation['at'] - cycle['flash']['at']
                        check(label + '_discharge_flash_clears_promptly', .07 <= delay < .35, elapsed=delay)
                        # After testing the real near-miss, prevent an immediate
                        # second warning so the ready locomotion can be sampled.
                        movement.stop_movement_immediately()
                        pawn.set_actor_location(anchor + unreal.Vector(1500 if kind == 3 else 3000, 0, 0), False, True)
                    if cycle['hidden'] is not None and observation['ai_state'] == 0:
                        check(label + '_locked_warning_is_escapable', not pawn.get_editor_property('Dead'))
                        # The role pulse updates animation just after the state
                        # transition; give it one full decision interval.
                        state['ready_seen'] = clock()
                        phase('ranged_ready')
                    elif age > 5:
                        raise AssertionError(label + ' did not warn, discharge, hide and recover')
                    return
                if name == 'ranged_ready':
                    if age < .12:
                        return
                    kind = state['ranged_kind']
                    check(('heavy' if kind == 3 else 'sniper') + '_recovery_restores_correct_pose',
                          is_anim(observation, 'A_Dummy_Walk' if kind == 3 else 'A_Dummy_Idle'), actual=observation)
                    clear_targets()
                    if kind == 3:
                        state['ranged_kind'] = 2
                        phase('ranged_setup')
                    else:
                        target = spawn(classes[2], anchor + unreal.Vector(0, 650, 0))
                        state['target'] = target
                        target.call_method('BeginSniperWarning')
                        phase('death_during_warning')
                    return
                if name == 'death_during_warning':
                    if age < .2:
                        return
                    check('death_fixture_is_in_active_visible_warning', observation['ai_state'] == 1 and observation['visible'])
                    expected = target.get_editor_property('DeathAnimation').get_path_name()
                    target.call_method('Die')
                    observation = sample(target)
                    check('death_immediately_removes_attack_warning', observation['dead'] and not observation['visible'], actual=observation)
                    check('death_plays_actual_death_animation_instead_of_cached_pose', observation['animation']['asset'] == expected,
                          actual=observation['animation']['asset'], expected=expected)
                    check('death_stops_enemy_decision_timer', not system.call_method('K2_IsTimerActive', args=(target, 'EnemyRolePulse')))
                    state['death_animation'] = expected
                    phase('death_cleanup_wait')
                    return
                if name == 'death_cleanup_wait':
                    if observation is not None:
                        assert not observation['visible'], 'Attack warning became visible again after death'
                        assert observation['animation']['asset'] == state['death_animation'], 'Pose update replaced death animation'
                    if age < .45:
                        return
                    check('dead_enemy_cannot_restore_warning_or_locomotion', observation is None or
                          (not observation['visible'] and observation['animation']['asset'] == state['death_animation']))
                    finish()
            except Exception as error:
                finish(error)

        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
