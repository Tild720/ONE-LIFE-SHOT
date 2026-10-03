"""Disposable PIE acceptance for forward-only encounter spawning.

Run through the editor queue in a fresh PIE session. This observes real enemies
created by BP_EnemySpawnPoint's existing SpawnNext timer and their Owner. Only
temporary runtime track points, a progress manager, and spawners are added.
No asset is saved, no inventory is written, and existing pursuers are not killed.
Output: Saved/SpawnProgressTest.json.
"""
import builtins
import json
import time
from pathlib import Path

import unreal


SESSION_KEY = '_ols_spawn_progress_qa'


def run():
    previous = getattr(builtins, SESSION_KEY, None)
    if previous and not previous.get('finished', False):
        unreal.log('SPAWN_PROGRESS_QA: a test is already running')
        return
    report = {'status': 'running', 'passed': False, 'checks': [], 'samples': [],
              'source': 'Production SpawnNext timer and real spawned enemy Owner; temporary runtime track'}
    session = {'handle': None, 'finished': False, 'report': report}
    setattr(builtins, SESSION_KEY, session)
    output = Path(unreal.Paths.project_saved_dir()) / 'SpawnProgressTest.json'
    wall_start = time.monotonic()
    state = {'phase': 'startup', 'phase_time': 0.0, 'point': None}
    tracked = {}
    owned_enemies = {}
    isolated = []
    original_spawners = []
    original_progress = []
    points = []
    effect_classes = {}
    baseline = {}
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

    def spawn(cls, location, properties=None, scale=None):
        transform = maths.call_method('MakeTransform', args=(
            location, unreal.Rotator(), scale or unreal.Vector(1, 1, 1)))
        method = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        actor = statics.call_method('BeginDeferredActorSpawnFromClass', args=(
            world, cls, transform, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, method))
        assert valid(actor), 'Runtime spawn-progress fixture could not spawn'
        remember(actor)
        for name, value in (properties or {}).items():
            actor.set_editor_property(name, value)
        statics.call_method('FinishSpawningActor', args=(actor, transform, method))
        return actor

    def owned(point):
        return [actor for actor in actors(enemy_class)
                if actor.call_method('GetOwner') == point]

    def observe_spawns():
        # Freeze each actual pursuer after its production spawn. This preserves
        # its life/Owner while preventing fixture teleports from causing contact.
        for point in points:
            if not valid(point):
                continue
            for actor in owned(point):
                path = actor.get_path_name()
                remember(actor)
                if path not in owned_enemies:
                    owned_enemies[path] = actor
                    actor.set_actor_enable_collision(False)
                    actor.set_actor_tick_enabled(False)
                    system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))
        for name, cls in effect_classes.items():
            for actor in actors(cls):
                if actor.get_path_name() not in baseline[name]:
                    remember(actor)

    def set_player(location):
        movement.stop_movement_immediately()
        pawn.set_actor_location(location, False, True)

    def new_point(location):
        properties = {'ProgressManager': progress, 'SpawnDelay': 0.05,
                      'MaxAliveEnemies': 2, 'EnemyLifetime': 90.0,
                      'UseSpawnSpeedOverride': False}
        for name in ('Early', 'Middle', 'Late', 'Final'):
            properties[name + 'EnemyPool'] = [enemy_class]
            properties[name + 'Interval'] = .35
        point = spawn(spawner_class, location, properties)
        points.append(point)
        state['point'] = point
        return point

    def sample(label, point):
        player_position = pawn.get_actor_location()
        spawn_position = point.get_actor_location()
        observation = {'at': round(clock(), 3), 'label': label,
                       'player': [player_position.x, player_position.y, player_position.z],
                       'spawn': [spawn_position.x, spawn_position.y, spawn_position.z],
                       'open': bool(point.get_editor_property('SpawnWindowOpen')),
                       'retired': bool(point.get_editor_property('SpawnRetired')),
                       'timer_active': bool(system.call_method('K2_IsTimerActive', args=(point, 'SpawnNext'))),
                       'owned_count': len(owned(point))}
        report['samples'].append(observation)
        write()
        return observation

    def retire_checks(label, point):
        observation = sample(label, point)
        check(label + '_retires', observation['retired'], **observation)
        check(label + '_closes_spawn_window', not observation['open'], **observation)
        check(label + '_stops_existing_spawn_timer', not observation['timer_active'], **observation)
        return observation

    def cleanup():
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        if valid(world):
            observe_spawns()
        # EndPlay of the temporary progress manager removes its temporary HUD.
        for actor in list(tracked.values()):
            if valid(actor):
                actor.destroy_actor()
        if valid(pawn) and not pawn.get_editor_property('Dead') and original_location is not None:
            movement.stop_movement_immediately()
            pawn.set_actor_location(original_location, False, True)
            pawn.set_actor_rotation(original_rotation, True)
            for actor in original_progress:
                if valid(actor):
                    actor.call_method('UpdateProgress')
        for actor, saved in isolated:
            if valid(actor):
                actor.set_actor_enable_collision(saved['collision'])
                actor.set_actor_tick_enabled(saved['tick'])
                if saved['timer']:
                    system.call_method('K2_SetTimer', args=(actor, 'EnemyRolePulse', .1, True, True, 0.0, 0.0))
        for actor, enabled in original_spawners:
            if valid(actor):
                actor.set_editor_property('Enabled', enabled)
        if valid(performance) and original_throttle is not None:
            performance.set_editor_property('bThrottleCPUWhenNotForeground', original_throttle)
        report['cleanup'] = 'Runtime fixture removed; original encounter and background throttle restored'

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
            unreal.log_error('SPAWN_PROGRESS_QA: ' + str(error))
        write()

    session['cancel'] = lambda: finish('Explicitly cancelled')

    try:
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        maths = unreal.get_default_object(unreal.MathLibrary.static_class())
        system = unreal.get_default_object(unreal.SystemLibrary.static_class())
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        assert valid(world), 'Start a fresh PIE session for spawn-progress QA'
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        assert valid(pawn) and not pawn.get_editor_property('Dead'), 'Spawn QA requires a living player'
        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        assert valid(movement)
        performance = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
        original_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
        performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
        original_location = pawn.get_actor_location()
        original_rotation = pawn.get_actor_rotation()
        anchor = unreal.Vector(20000, 20000, 142.25)
        enemy_class = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class()
        spawner_class = unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint').generated_class()
        progress_class = unreal.load_asset('/Game/Runner/BP_RunnerProgress').generated_class()
        effect_classes = {name: unreal.load_asset(path).generated_class() for name, path in {
            'pickup': '/Game/Weapons/Pistol/BP_PistolPickup',
            'gun': '/Game/Weapons/Pistol/BP_Pistol',
            'bullet': '/Game/Weapons/Pistol/BP_BulletProjectile'}.items()}
        baseline = {name: {a.get_path_name() for a in actors(cls)} for name, cls in effect_classes.items()}
        for actor in actors(spawner_class):
            original_spawners.append((actor, actor.get_editor_property('Enabled')))
            actor.set_editor_property('Enabled', False)
        original_progress = actors(progress_class)
        for actor in actors(enemy_class):
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
        set_player(anchor)
        start = spawn(unreal.TargetPoint.static_class(), anchor + unreal.Vector(0, -1000, -92.25))
        end = spawn(unreal.TargetPoint.static_class(), anchor + unreal.Vector(0, 10000, -92.25))
        progress = spawn(progress_class, anchor + unreal.Vector(-3000, 0, 0),
                         {'StartPoint': start, 'EndPoint': end})
        defaults = unreal.get_default_object(spawner_class)
        activation = float(defaults.get_editor_property('SpawnActivationDistance'))
        minimum = float(defaults.get_editor_property('SpawnMinimumAhead'))
        assert activation > minimum > 0.0, 'Spawn window must have positive ordered distances'
        report['configuration'] = {'activation_distance': activation, 'minimum_ahead': minimum}
        check('new_spawner_default_is_not_retired', not defaults.get_editor_property('SpawnRetired'))
        duration = float(unreal.get_default_object(effect_classes['pickup']).get_editor_property('ReturnDuration'))
        check('weapon_return_preserves_point_55_seconds', abs(duration - .55) < .001, actual=duration)
        first = new_point(anchor + unreal.Vector(0, (activation + minimum) / 2, 0))
        phase('ahead_wait')

        def tick(_dt):
            try:
                assert time.monotonic() - wall_start < 25.0, 'Spawn progress QA timed out'
                assert valid(world) and valid(pawn) and not pawn.get_editor_property('Dead'), 'Unexpected player death/world change'
                observe_spawns()
                age = clock() - state['phase_time']
                name = state['phase']
                point = state['point']
                if name == 'ahead_wait' and age >= .8:
                    observation = sample('ahead', point)
                    check('forward_point_creates_real_owned_enemy_by_timer', observation['owned_count'] > 0, **observation)
                    check('forward_point_opens_window', observation['open'] and not observation['retired'], **observation)
                    check('existing_per_point_alive_cap_is_preserved', observation['owned_count'] <= 2, **observation)
                    state['survivors'] = list(owned(point))
                    state['count_before_retire'] = len(state['survivors'])
                    set_player(point.get_actor_location() - unreal.Vector(0, minimum / 2, 0))
                    phase('near_retire_wait')
                elif name == 'near_retire_wait' and age >= .8:
                    observation = retire_checks('near_point', point)
                    check('near_point_adds_no_surprise_enemy', observation['owned_count'] == state['count_before_retire'], **observation)
                    check('retirement_preserves_existing_pursuers', bool(state['survivors']) and all(
                        valid(a) and not a.get_editor_property('Dead') for a in state['survivors']))
                    set_player(anchor)
                    point.call_method('SpawnNext')
                    phase('retreat_wait')
                elif name == 'retreat_wait' and age >= .8:
                    observation = sample('retreat_after_retire', point)
                    check('retreat_does_not_reactivate_passed_point', observation['retired'] and not observation['open'], **observation)
                    check('retreat_and_direct_spawnnext_add_no_enemy', observation['owned_count'] == state['count_before_retire'], **observation)
                    check('retreat_keeps_spawn_timer_stopped', not observation['timer_active'], **observation)
                    new_point(anchor + unreal.Vector(0, minimum / 2, 0))
                    phase('initial_near_wait')
                elif name == 'initial_near_wait' and age >= .6:
                    observation = retire_checks('initial_near', point)
                    check('initial_near_point_never_spawns', observation['owned_count'] == 0, **observation)
                    new_point(anchor - unreal.Vector(0, 600, 0))
                    phase('initial_behind_wait')
                elif name == 'initial_behind_wait' and age >= .6:
                    observation = retire_checks('initial_behind', point)
                    check('initial_behind_point_never_spawns', observation['owned_count'] == 0, **observation)
                    new_point(anchor + unreal.Vector(0, activation + 600, 0))
                    phase('far_wait')
                elif name == 'far_wait' and age >= .8:
                    observation = sample('far', point)
                    check('distant_point_stays_dormant', observation['owned_count'] == 0 and not observation['open'], **observation)
                    check('distant_point_remains_available_when_approached', not observation['retired'] and observation['timer_active'], **observation)
                    set_player(point.get_actor_location() - unreal.Vector(0, minimum + 500, 0))
                    phase('far_approach_wait')
                elif name == 'far_approach_wait' and age >= .8:
                    observation = sample('far_approached', point)
                    check('approaching_dormant_point_creates_real_owned_enemy', observation['owned_count'] > 0, **observation)
                    check('approached_point_opens_without_retiring', observation['open'] and not observation['retired'], **observation)
                    set_player(anchor)
                    start.set_actor_location(anchor + unreal.Vector(-1000, 0, -92.25), False, True)
                    end.set_actor_location(anchor + unreal.Vector(10000, 0, -92.25), False, True)
                    progress.call_method('UpdateProgress')
                    # Behind in world Y, ahead along the actual rotated track.
                    new_point(anchor + unreal.Vector((activation + minimum) / 2, -800, 0))
                    phase('rotated_ahead_wait')
                elif name == 'rotated_ahead_wait' and age >= .8:
                    observation = sample('rotated_ahead', point)
                    check('rotated_track_spawns_ahead_despite_lower_world_y',
                          observation['owned_count'] > 0 and observation['spawn'][1] < observation['player'][1], **observation)
                    check('rotated_track_window_follows_start_to_end_direction', observation['open'] and not observation['retired'], **observation)
                    state['rotated_count'] = observation['owned_count']
                    set_player(point.get_actor_location() + unreal.Vector(minimum + 100, 800, 0))
                    phase('rotated_pass_wait')
                elif name == 'rotated_pass_wait' and age >= .8:
                    observation = retire_checks('rotated_pass', point)
                    check('rotated_pass_adds_no_enemy', observation['owned_count'] == state['rotated_count'], **observation)
                    state['retired_point'] = point
                    set_player(anchor)
                    new_point(point.get_actor_location())
                    phase('fresh_point_wait')
                elif name == 'fresh_point_wait' and age >= .8:
                    observation = sample('fresh_instance', point)
                    check('new_runtime_spawner_instance_resets_retirement',
                          observation['owned_count'] > 0 and observation['open'] and not observation['retired'], **observation)
                    old = sample('prior_retired_instance', state['retired_point'])
                    check('old_instance_stays_retired_while_new_instance_operates', old['retired'] and not old['open'], **old)
                    finish()
            except Exception as error:
                finish(error)

        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
