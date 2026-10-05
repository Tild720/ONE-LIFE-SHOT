"""Disposable PIE acceptance for current + one FIFO reserve weapon.

Uses production TryAcquire and Fire, real Shotgun and Sniper defeats/returns,
three returning drops overflowing two slots, and swept contact for restart.
Never writes Ammo, QueuedWeaponKind,
Dead or damage. Only runtime formations, movement isolation and a floor are
created. Physical mouse-button hold/release bindings are not exercised.
Output: Saved/WeaponQueueTest.json. Restart PIE afterwards to reset inventory.
"""
import builtins
import json
import time
from pathlib import Path

import unreal

SESSION_KEY = '_ols_weapon_queue_qa'
WEAPONS = ('Pistol', 'Shotgun', 'Sniper', 'RPG')
PATHS = {'enemy': '/Game/Enemies/BP_EnemyStraightRunner',
         'heavy': '/Game/Enemies/BP_EnemyRunnerSlow',
         'sniper': '/Game/Enemies/BP_EnemySniper',
         'spawner': '/Game/Enemies/BP_EnemySpawnPoint',
         'gun': '/Game/Weapons/Pistol/BP_Pistol',
         'pickup': '/Game/Weapons/Pistol/BP_PistolPickup',
         'bullet': '/Game/Weapons/Pistol/BP_BulletProjectile'}


def run():
    if hasattr(builtins, SESSION_KEY):
        unreal.log('WEAPON_QUEUE_QA: retained session; restart replay ignored')
        return
    output = Path(unreal.Paths.project_saved_dir()) / 'WeaponQueueTest.json'
    report = {'status': 'running', 'passed': False, 'checks': [], 'shots': [], 'samples': [],
              'source': 'Production pickup acceptance, actual Fire, Shotgun multi-kill, three Sniper returns overflowing two slots, and swept contact/restart',
              'contract': {'current': 'EquippedPistol', 'reserve': 'QueuedWeaponKind', 'empty_reserve': -1,
                           'capacity': 'Current + one reserve = 2', 'return_seconds': .55},
              'limitations': 'Function calls verify one invocation, not physical held-button input transitions'}
    session = {'handle': None, 'finished': False}
    setattr(builtins, SESSION_KEY, session)
    wall_start = time.monotonic()
    state = {'phase': 'flush', 'index': 0, 'step_started': None, 'last_sample': -1,
             'flush_time': None, 'flush_count': 0, 'multi_fired': False,
             'multi_drops': {}, 'early_return': [], 'capacity_violations': [],
             'overflow_fired': False, 'overflow_drops': {}, 'overflow_early_return': []}
    tracked, isolated, disabled = {}, [], []
    world = pawn = controller = movement = performance = statics = maths = system = None
    initial_pawn = original_location = original_rotation = original_throttle = None

    def valid(obj):
        try:
            return obj is not None and unreal.SystemLibrary.is_valid(obj)
        except Exception:
            return False

    def clock():
        return float(statics.call_method('GetTimeSeconds', args=(world,)))

    def write():
        report['wall_elapsed'] = round(time.monotonic() - wall_start, 3)
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def check(name, condition, **evidence):
        report['checks'].append({'name': name, 'passed': bool(condition), **evidence})
        write()

    def current_player():
        candidate_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        candidate = unreal.GameplayStatics.get_player_pawn(candidate_world, 0) if valid(candidate_world) else None
        return candidate_world, candidate

    def current(player=None):
        return (player or pawn).get_editor_property('EquippedPistol')

    def slots(player=None):
        player = player or pawn
        weapon = current(player)
        reserve = int(player.get_editor_property('QueuedWeaponKind'))
        return {'current': weapon.get_path_name() if valid(weapon) else None,
                'kind': int(weapon.get_editor_property('WeaponKind')) if valid(weapon) else None,
                'ammo': int(weapon.get_editor_property('Ammo')) if valid(weapon) else 0,
                'reserve': reserve, 'count': int(valid(weapon)) + int(reserve >= 0)}

    def actors(kind):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, classes[kind]))

    def remember(actor):
        if valid(actor):
            tracked[actor.get_path_name()] = actor
        return actor

    def collect():
        for kind in ('gun', 'pickup', 'bullet'):
            for actor in actors(kind):
                path = actor.get_path_name()
                if path not in baseline[kind]:
                    remember(actor)
                if kind == 'pickup' and state['multi_fired'] and path not in state['multi_pickups_before']:
                    state['multi_drops'].setdefault(path, {
                        'kind': int(actor.get_editor_property('WeaponKind')),
                        'returning': bool(actor.get_editor_property('Returning')),
                        'start': float(actor.get_editor_property('ReturnStartTime')),
                        'duration': float(actor.get_editor_property('ReturnDuration'))})
                if kind == 'pickup' and state['overflow_fired'] and path not in state['overflow_pickups_before']:
                    state['overflow_drops'].setdefault(path, {
                        'kind': int(actor.get_editor_property('WeaponKind')),
                        'returning': bool(actor.get_editor_property('Returning')),
                        'start': float(actor.get_editor_property('ReturnStartTime')),
                        'duration': float(actor.get_editor_property('ReturnDuration'))})
        if state['multi_fired'] and state['multi_drops'] and slots()['count']:
            first_start = min(row['start'] for row in state['multi_drops'].values())
            if clock() - first_start < .50:
                state['early_return'].append({'at': clock(), 'slots': slots(), 'first_return_start': first_start})
        if state['overflow_fired'] and state['overflow_drops'] and slots()['count']:
            first_start = min(row['start'] for row in state['overflow_drops'].values())
            if clock() - first_start < .50:
                state['overflow_early_return'].append({'at': clock(), 'slots': slots(), 'first_return_start': first_start})

    def spawn(cls, position, properties=None, scale=None):
        transform = maths.call_method('MakeTransform', args=(position, unreal.Rotator(), scale or unreal.Vector(1, 1, 1)))
        method = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        actor = statics.call_method('BeginDeferredActorSpawnFromClass', args=(world, cls, transform,
            unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, method))
        assert valid(actor), 'Could not create runtime queue fixture'
        remember(actor)
        for name, value in (properties or {}).items():
            actor.set_editor_property(name, value)
        statics.call_method('FinishSpawningActor', args=(actor, transform, method))
        return actor

    def pickup(kind):
        actor = spawn(classes['pickup'], pawn.get_actor_location(), {'WeaponKind': kind})
        actor.call_method('TryAcquire')
        collect()
        return actor

    def pair():
        assert slots()['count'] == 0, 'Start fixture from a queue emptied through Fire'
        pickup(0)
        pickup(2)

    def reserve_hud():
        hud = controller.get_hud()
        expected = WEAPONS[slots()['reserve']] if slots()['reserve'] >= 0 else 'EMPTY'
        actual = str(hud.get_editor_property('ReserveWeaponLabel'))
        return actual.casefold() == expected.casefold(), actual, expected

    def aim(offset=None):
        point = pawn.get_actor_location() + (offset or unreal.Vector(-350, 50, -92.25))
        pixel = unreal.GameplayStatics.project_world_to_screen(controller, point)
        assert pixel is not None, 'Queue fixture aim does not project into the PIE viewport'
        controller.set_mouse_location(round(pixel.x), round(pixel.y))

    def fire(label):
        weapon = current()
        before = slots()
        assert valid(weapon) and before['ammo'] == 1, 'Production Fire requires a real loaded weapon'
        projectiles_before = {actor.get_path_name() for actor in actors('bullet')}
        weapon.call_method('Fire')
        collect()
        after = slots()
        new_projectiles = [actor for actor in actors('bullet') if actor.get_path_name() not in projectiles_before]
        kinds = [int(actor.get_editor_property('WeaponKind')) for actor in new_projectiles]
        report['shots'].append({'name': label, 'at': clock(), 'before': before, 'after': after,
                                'projectile_kinds': kinds})
        check(label + '_consumed_actor_is_removed', not valid(weapon), before=before, after=after)
        check(label + '_one_fire_consumes_only_current_slot', after['count'] == before['count'] - 1,
              before=before, after=after)
        check(label + '_promoted_weapon_does_not_fire_on_same_call',
              (before['reserve'] < 0 and after['count'] == 0)
              or (after['kind'] == before['reserve'] and after['ammo'] == 1 and after['reserve'] == -1),
              before=before, after=after)
        check(label + '_projectiles_belong_only_to_fired_weapon', bool(kinds) and all(k == before['kind'] for k in kinds),
              kinds=kinds, fired_kind=before['kind'])
        state['last_consumed'] = weapon

    def remove_effects():
        collect()
        held = current()
        for key, actor in list(tracked.items()):
            if actor != state.get('floor') and actor != held:
                if valid(actor):
                    actor.destroy_actor()
                tracked.pop(key, None)

    def assert_slots(name, kind, reserve):
        observed = slots()
        check(name, observed['kind'] == kind and observed['reserve'] == reserve
              and observed['ammo'] == (1 if kind is not None else 0)
              and observed['count'] == int(kind is not None) + int(reserve >= 0), slots=observed)

    def cleanup():
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        for actor in tracked.values():
            if valid(actor):
                actor.destroy_actor()
        for actor, before in isolated:
            if valid(actor):
                actor.set_actor_enable_collision(before['collision'])
                actor.set_actor_tick_enabled(before['tick'])
                if before['timer']:
                    system.call_method('K2_SetTimer', args=(actor, 'EnemyRolePulse', .1, True, True, 0.0, 0.0))
        for actor, enabled in disabled:
            if valid(actor):
                actor.set_editor_property('Enabled', enabled)
        if valid(initial_pawn) and not initial_pawn.get_editor_property('Dead'):
            movement.stop_movement_immediately()
            initial_pawn.set_actor_location(original_location, False, True)
            initial_pawn.set_actor_rotation(original_rotation, True)
        if valid(performance) and original_throttle is not None:
            performance.set_editor_property('bThrottleCPUWhenNotForeground', original_throttle)
        report['cleanup'] = 'Runtime fixtures removed and isolation restored; no saved asset changed; restart resets inventory'

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
        report['passed'] = error is None and bool(report['checks']) and all(row['passed'] for row in report['checks'])
        if error is not None:
            report['error'] = str(error)
            unreal.log_error('WEAPON_QUEUE_QA: ' + str(error))
        write()

    session['cancel'] = lambda: finish('Explicitly cancelled')
    try:
        world, pawn = current_player()
        assert valid(world) and valid(pawn) and not pawn.get_editor_property('Dead'), 'Fresh living PIE player required'
        initial_pawn = pawn
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        maths = unreal.get_default_object(unreal.MathLibrary.static_class())
        system = unreal.get_default_object(unreal.SystemLibrary.static_class())
        classes = {name: unreal.load_asset(path).generated_class() for name, path in PATHS.items()}
        baseline = {name: {actor.get_path_name() for actor in actors(name)} for name in ('gun', 'pickup', 'bullet')}
        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        original_location, original_rotation = pawn.get_actor_location(), pawn.get_actor_rotation()
        performance = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
        original_throttle = performance.get_editor_property('bThrottleCPUWhenNotForeground')
        performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
        for actor in actors('spawner'):
            disabled.append((actor, actor.get_editor_property('Enabled')))
            actor.set_editor_property('Enabled', False)
        for actor in actors('enemy'):
            isolated.append((actor, {'collision': actor.get_actor_enable_collision(), 'tick': actor.is_actor_tick_enabled(),
                                     'timer': bool(system.call_method('K2_IsTimerActive', args=(actor, 'EnemyRolePulse')))}))
            actor.set_actor_enable_collision(False)
            actor.set_actor_tick_enabled(False)
            system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))
        anchor = unreal.Vector(20000, 20000, 142.25)
        floor = spawn(unreal.StaticMeshActor.static_class(), unreal.Vector(20000, 22500, 0), scale=unreal.Vector(120, 120, 1))
        component = floor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        assert component.set_static_mesh(unreal.load_asset('/Engine/BasicShapes/Cube'))
        component.set_collision_profile_name('BlockAll')
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        state['floor'] = floor
        movement.stop_movement_immediately()
        pawn.set_actor_location(anchor, False, True)
        aim()
        state['flush_time'] = clock()
        check('pickup_return_duration_remains_point_55', abs(float(unreal.get_default_object(classes['pickup']).get_editor_property('ReturnDuration')) - .55) < .001)

        def fifo_ready():
            assert_slots('sequential_pickups_fill_current_then_fifo_reserve', 0, 2)
            passed, actual, expected = reserve_hud()
            check('reserve_hud_matches_actual_second_weapon', passed, actual=actual, expected=expected)

        def full_setup():
            pair()
            state['excess_pickup'] = pickup(3)

        def full_check():
            assert_slots('third_pickup_cannot_overfill_two_slots', 0, 2)
            check('full_queue_leaves_excess_world_pickup_intact', valid(state['excess_pickup']),
                  excess_kind=3)

        def reclaimed():
            assert_slots('opening_capacity_keeps_fifo_current_and_reclaims_world_weapon', 2, 3)
            check('reclaimed_pickup_is_removed_only_after_acceptance', not valid(state['excess_pickup']))

        def multi_setup():
            remove_effects()
            assert slots()['count'] == 0
            pickup(1)
            targets = []
            for name, x in [('enemy', -75), ('sniper', 75)]:
                actor = spawn(classes[name], anchor + unreal.Vector(x, 450, 0), {'MoveSpeed': 0.0})
                actor.set_editor_property('MoveSpeed', 0.0)
                system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))
                targets.append(actor)
            state['multi_targets'] = targets
            state['multi_pickups_before'] = {actor.get_path_name() for actor in actors('pickup')}
            aim(unreal.Vector(0, 600, -92.25))

        def multi_fire():
            fire('shotgun_multikill')
            state['multi_fired'] = True

        def multi_check():
            drops = list(state['multi_drops'].values())
            observed = slots()
            check('real_shotgun_defeats_both_distinct_enemy_variants', all(
                not valid(actor) or actor.get_editor_property('Dead') for actor in state['multi_targets']))
            check('real_multikill_returns_two_matching_enemy_weapons', sorted(row['kind'] for row in drops) == [0, 2]
                  and all(row['returning'] and abs(row['duration'] - .55) < .001 for row in drops), drops=drops)
            check('two_real_returns_fill_current_and_one_reserve', observed['count'] == 2
                  and observed['ammo'] == 1 and sorted([observed['kind'], observed['reserve']]) == [0, 2], slots=observed)
            check('multikill_preserves_empty_point_55_return_interval', not state['early_return'], early_acquisitions=state['early_return'])
            state['multi_second_kind'] = observed['reserve']
            state['multi_fired'] = False
            aim()

        def after_multi_first():
            assert_slots('multikill_second_weapon_promotes_without_firing', state['multi_second_kind'], -1)

        def overflow_setup():
            remove_effects()
            assert slots()['count'] == 0
            pickup(2)
            targets = []
            # Same actual child classes and aligned distances as the combat
            # penetration regression, with production collision left enabled.
            for name, y in [('enemy', 700), ('heavy', 1400), ('sniper', 2100)]:
                actor = spawn(classes[name], anchor + unreal.Vector(0, y, 0), {'MoveSpeed': 0.0})
                actor.set_editor_property('MoveSpeed', 0.0)
                system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))
                targets.append(actor)
            state['overflow_targets'] = targets
            state['overflow_pickups_before'] = {actor.get_path_name() for actor in actors('pickup')}
            aim(unreal.Vector(0, 600, -92.25))

        def overflow_fire():
            # Sniper resolves damage synchronously. Observe drops during the
            # Fire helper's collection, before the first .55 return can finish.
            state['overflow_fired'] = True
            fire('sniper_three_returning_drops')

        def overflow_check():
            records = state['overflow_drops']
            drops = list(records.values())
            observed = slots()
            waiting = [actor for actor in actors('pickup') if actor.get_path_name() in records]
            check('real_sniper_defeats_all_three_aligned_enemy_variants', all(
                not valid(actor) or actor.get_editor_property('Dead') for actor in state['overflow_targets']))
            check('three_real_defeats_start_three_matching_point_55_returns',
                  sorted(row['kind'] for row in drops) == [0, 2, 3]
                  and all(row['returning'] and abs(row['duration'] - .55) < .001 for row in drops),
                  drops=drops)
            check('three_actual_returns_fill_only_two_slots_and_keep_one_world_pickup',
                  observed['count'] == 2 and observed['ammo'] == 1 and len(waiting) == 1
                  and sorted([observed['kind'], observed['reserve']] +
                             [int(actor.get_editor_property('WeaponKind')) for actor in waiting]) == [0, 2, 3],
                  slots=observed, waiting_paths=[actor.get_path_name() for actor in waiting])
            check('three_return_overflow_preserves_empty_point_55_interval',
                  not state['overflow_early_return'], early_acquisitions=state['overflow_early_return'])
            assert len(waiting) == 1 and observed['count'] == 2, 'Expected one real overflow pickup waiting behind two slots'
            leftover = waiting[0]
            state['overflow_world_pickup'] = leftover
            state['overflow_original_reserve'] = observed['reserve']
            state['overflow_rejected_kind'] = int(leftover.get_editor_property('WeaponKind'))
            returned_for = clock() - records[leftover.get_path_name()]['start']
            travel_active = bool(system.call_method('K2_IsTimerActive', args=(leftover, 'UpdateReturn')))
            acquire_active = bool(system.call_method('K2_IsTimerActive', args=(leftover, 'TryAcquire')))
            check('full_actual_return_stops_travel_and_waits_unconsumed_with_acquisition_timer',
                  valid(leftover) and not leftover.get_editor_property('Returning')
                  and not leftover.get_editor_property('Consumed') and returned_for >= .55
                  and not travel_active and acquire_active,
                  returned_for=returned_for, travel_timer=travel_active, acquisition_timer=acquire_active,
                  waiting_kind=state['overflow_rejected_kind'])
            state['overflow_fired'] = False
            aim()

        def overflow_reclaimed():
            assert_slots('firing_after_three_returns_preserves_original_reserve_before_overflow_weapon',
                         state['overflow_original_reserve'], state['overflow_rejected_kind'])
            check('actual_return_overflow_pickup_is_removed_only_after_capacity_opens',
                  not valid(state['overflow_world_pickup']))

        def after_overflow_second():
            assert_slots('third_returned_weapon_promotes_after_original_reserve_is_spent',
                         state['overflow_rejected_kind'], -1)

        def death_setup():
            remove_effects()
            pair()
            assert_slots('death_starts_with_a_real_current_and_reserve', 0, 2)
            enemy = spawn(classes['enemy'], pawn.get_actor_location() + unreal.Vector(0, 300, 0), {'MoveSpeed': 0.0})
            enemy.set_editor_property('MoveSpeed', 0.0)
            system.call_method('K2_ClearTimer', args=(enemy, 'EnemyRolePulse'))
            state['contact_sweep'] = str(enemy.set_actor_location(pawn.get_actor_location(), True, False))

        def death_check():
            check('real_swept_contact_kills_player_with_full_inventory', pawn.get_editor_property('Dead'), sweep=state['contact_sweep'])
            check('death_clears_reserved_weapon', slots()['reserve'] == -1, slots=slots())

        def restart_check():
            new_world, new_pawn = current_player()
            check('death_restarts_with_a_new_living_player', valid(new_pawn) and new_pawn != initial_pawn
                  and not new_pawn.get_editor_property('Dead'))
            observed = slots(new_pawn)
            check('restart_never_carries_the_old_reserve', observed['reserve'] == -1 and observed['count'] <= 1,
                  slots=observed)
            check('no_phase_exceeds_two_total_slots', not state['capacity_violations'], violations=state['capacity_violations'])

        steps = []
        def step(name, action=None, delay=.12, verify=None):
            steps.append((name, action, delay, verify))
        step('fifo_setup', pair, verify=fifo_ready)
        step('fifo_first_aim', aim, .16)
        step('fifo_first_fire', lambda: fire('fifo_first'), verify=lambda: assert_slots('fifo_first_promotes_sniper', 2, -1))
        step('fifo_second_aim', aim, .16)
        step('fifo_second_fire', lambda: fire('fifo_second'), verify=lambda: assert_slots('two_acquired_weapons_allow_no_third_shot', None, -1))
        step('full_setup', full_setup, verify=full_check)
        step('full_first_aim', aim, .16)
        step('full_first_fire', lambda: fire('capacity_first'), .20, reclaimed)
        step('full_second_aim', aim, .16)
        step('full_second_fire', lambda: fire('capacity_second'), verify=lambda: assert_slots('reclaimed_rpg_waits_behind_original_reserve', 3, -1))
        step('full_third_aim', aim, .16)
        step('full_third_fire', lambda: fire('reclaimed_rpg'), verify=lambda: assert_slots('reclaimed_weapon_also_has_only_one_shot', None, -1))
        step('multi_setup', multi_setup, .16)
        step('multi_fire', multi_fire, 1.0, multi_check)
        step('multi_first_aim', aim, .16)
        step('multi_first_fire', lambda: fire('multi_first'), verify=after_multi_first)
        step('multi_second_aim', aim, .16)
        step('multi_second_fire', lambda: fire('multi_second'), verify=lambda: assert_slots('real_multikill_supplies_exactly_two_shots', None, -1))
        step('overflow_setup', overflow_setup, .16)
        step('overflow_fire', overflow_fire, .95, overflow_check)
        step('overflow_first_aim', aim, .16)
        step('overflow_first_fire', lambda: fire('actual_overflow_first'), .24, overflow_reclaimed)
        step('overflow_second_aim', aim, .16)
        step('overflow_second_fire', lambda: fire('actual_overflow_second'), verify=after_overflow_second)
        step('overflow_third_aim', aim, .16)
        step('overflow_third_fire', lambda: fire('actual_overflow_third'),
             verify=lambda: assert_slots('three_real_defeats_supply_exactly_three_following_shots', None, -1))
        step('death_contact', death_setup, .20, death_check)
        step('restart', None, 0.0, restart_check)

        def tick(_dt):
            try:
                assert time.monotonic() - wall_start < 45, 'Weapon queue acceptance timed out'
                if state['phase'] == 'restart':
                    _, replacement = current_player()
                    if not valid(replacement) or replacement == initial_pawn:
                        return
                    restart_check()
                    finish()
                    return
                assert valid(world) and valid(pawn), 'Unexpected world/player change'
                assert not pawn.get_editor_property('Dead') or state['phase'] == 'death_contact', 'Unexpected contact death'
                collect()
                now = clock()
                snapshot = slots()
                if snapshot['count'] > 2 or (snapshot['reserve'] >= 0 and snapshot['current'] is None):
                    state['capacity_violations'].append({'at': now, 'phase': state['phase'], 'slots': snapshot})
                if now - state['last_sample'] >= .05:
                    state['last_sample'] = now
                    report['samples'].append({'at': now, 'phase': state['phase'], 'slots': snapshot})
                    write()
                if state['phase'] == 'flush':
                    if now - state['flush_time'] < .16:
                        return
                    if valid(current()):
                        state['flush_count'] += 1
                        assert state['flush_count'] <= 2, 'Startup inventory exceeded two slots'
                        fire('startup_spend_' + str(state['flush_count']))
                        remove_effects()
                        aim()
                        state['flush_time'] = now
                        return
                    assert slots()['count'] == 0, 'Startup left an orphan reserve'
                    state['phase'] = 'plan'
                name, action, delay, verify = steps[state['index']]
                if state['step_started'] is None:
                    state['phase'] = name
                    state['step_started'] = now
                    if action:
                        action()
                    return
                if now - state['step_started'] < delay:
                    return
                if verify:
                    verify()
                state['index'] += 1
                state['step_started'] = None
            except Exception as error:
                finish(error)

        unreal.EditorPythonScripting.set_keep_python_script_alive(True)
        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
