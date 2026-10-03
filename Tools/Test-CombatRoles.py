"""Behavioral combat acceptance in a fresh, disposable PIE session.

Run through Unreal Python once the local player exists and focus the PIE viewport.
Calls the production Fire, EquipPistol, Die, TryAcquire, and TryDodge functions;
it does not write Ammo or invoke FailRun to fake contact damage. This checks
combat outcomes, not physical LMB/Space bindings. All formations and cover are
runtime actors. Results are written incrementally to Saved/CombatRolesTest.json.

The builtins guard survives OpenLevel so a BeginPlay test hook cannot overwrite
the completed result. Stop PIE, then explicitly reset it for another run:
    import builtins
    qa = builtins.__dict__.get('_combat_roles_qa_session')
    qa and qa.get('cancel', lambda: None)()
    builtins.__dict__.pop('_combat_roles_qa_session', None)
"""

import builtins
import json
import time
from pathlib import Path

import unreal


SESSION_KEY = '_combat_roles_qa_session'
WEAPONS = ('Pistol', 'Shotgun', 'Sniper', 'RPG')
ENEMY_PATHS = (
    '/Game/Enemies/BP_EnemyStraightRunner',
    '/Game/Enemies/BP_EnemyRunnerFast',
    '/Game/Enemies/BP_EnemySniper',
    '/Game/Enemies/BP_EnemyRunnerSlow',
)


def run():
    if hasattr(builtins, SESSION_KEY):
        unreal.log('COMBAT_ROLES_QA: preserved existing session; skipped reload replay')
        return

    output = Path(unreal.Paths.project_saved_dir()) / 'CombatRolesTest.json'
    report = {
        'passed': False, 'status': 'running', 'phase': 'startup',
        'source_modes': {
            'firing': 'Production Fire after viewport mouse projection; physical LMB not exercised',
            'acquisition': 'Production EquipPistol and enemy Die/returning pickup',
            'dodge': 'Production TryDodge; physical Space binding not exercised',
            'empty_recovery': 'Production Assault warning/pulse and actual charge into WorldStatic cover; no Die call',
            'contact': 'Runtime enemy root collision swept into the player, never direct FailRun',
            'restart': 'Replacement local PIE pawn after production death/restart',
        },
        'checks': [], 'events': [], 'enemy_appearance': [],
    }
    session = {'report': report, 'handle': None, 'finished': False}
    setattr(builtins, SESSION_KEY, session)
    tracked = {}
    isolated = []
    disabled_spawners = []
    state = {'phase': 'startup', 'phase_time': 0.0, 'case_index': 0, 'drop_kind': 0}
    pawn = None
    controller = None
    world = None
    original_location = None
    original_rotation = None
    wall_start = time.monotonic()

    def valid(obj):
        try:
            return obj is not None and unreal.SystemLibrary.is_valid(obj)
        except Exception:
            return False

    def vector(value):
        return [value.x, value.y, value.z]

    def write():
        report['wall_elapsed'] = time.monotonic() - wall_start
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def event(name, **evidence):
        report['events'].append({'name': name, 'game_time': game_time(), **evidence})

    def check(name, condition, **evidence):
        report['checks'].append({'name': name, 'passed': bool(condition), **evidence})
        write()
        assert condition, name

    def current_player():
        current_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
        if valid(current_world):
            current_pawn = unreal.GameplayStatics.get_player_pawn(current_world, 0)
            if valid(current_pawn):
                return current_world, current_pawn
        return None, None

    def game_time():
        return float(statics.call_method('GetTimeSeconds', args=(world,))) if valid(world) else 0.0

    def phase(name):
        state['phase'] = name
        state['phase_time'] = game_time()
        report['phase'] = name
        write()

    def remember(actor):
        if valid(actor):
            tracked[actor.get_path_name()] = actor
        return actor

    def actors(kind):
        return list(unreal.GameplayStatics.get_all_actors_of_class(world, classes[kind]))

    def paths(kind):
        return {actor.get_path_name() for actor in actors(kind)}

    def collect_runtime_effects():
        if not valid(world):
            return
        for kind in ('gun', 'pickup', 'bullet'):
            for actor in actors(kind):
                if actor.get_path_name() not in baseline[kind]:
                    remember(actor)
        for target in state.get('targets', []):
            actor = target['actor']
            if valid(actor) and actor.get_editor_property('Dead'):
                target['observed_dead'] = True

    def gun():
        return pawn.get_editor_property('EquippedPistol') if valid(pawn) else None

    def ammo():
        current = gun()
        return current.get_editor_property('Ammo') if valid(current) else 0

    def clear_decision(actor):
        # Clearing the shared decision timer freezes test formations without
        # changing a Blueprint CDO or invoking a damage function.
        system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))

    def spawn(cls, location, properties=None, scale=None):
        transform = maths.call_method('MakeTransform', args=(
            location, unreal.Rotator(), scale or unreal.Vector(1.0, 1.0, 1.0)))
        method = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        actor = statics.call_method('BeginDeferredActorSpawnFromClass', args=(
            world, cls, transform, unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN,
            None, method))
        assert valid(actor), 'Could not create runtime QA actor'
        remember(actor)
        for name, value in (properties or {}).items():
            actor.set_editor_property(name, value)
        statics.call_method('FinishSpawningActor', args=(actor, transform, method))
        return actor

    def enemy(offset, kind=0):
        actor = spawn(enemy_classes[kind], anchor + offset, {'MoveSpeed': 0.0})
        actor.set_editor_property('MoveSpeed', 0.0)
        clear_decision(actor)
        return actor

    def cover(offset, scale):
        actor = spawn(unreal.StaticMeshActor.static_class(), anchor + offset, scale=scale)
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        assert component and component.set_static_mesh(cube), 'Could not configure runtime cover'
        component.set_collision_profile_name('BlockAll')
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
        return actor

    def aim(offset):
        point = pawn.get_actor_location() + offset
        pixel = unreal.GameplayStatics.project_world_to_screen(controller, point)
        assert pixel is not None, 'QA aim point does not project into the PIE viewport'
        controller.set_mouse_location(round(pixel.x), round(pixel.y))
        state['aim_offset'] = offset
        report['aim'] = {'point': vector(point), 'pixel': [pixel.x, pixel.y]}

    def fire_once(label):
        current = gun()
        assert valid(current) and ammo() == 1, 'Fire must begin with a real one-shot weapon'
        mouse = controller.get_mouse_position()
        ray = controller.deproject_mouse_position_to_world()
        assert mouse is not None and ray is not None, 'Focus the PIE viewport; mouse deprojection is unavailable'
        before = paths('bullet')
        current.call_method('Fire')
        collect_runtime_effects()
        check(label + '_consumes_one_shot', current.get_editor_property('Ammo') == 0,
              weapon_kind=current.get_editor_property('WeaponKind'))
        after_first = paths('bullet')
        current.call_method('Fire')
        current.call_method('Fire')
        collect_runtime_effects()
        extra = paths('bullet') - after_first
        check(label + '_rejects_extra_presses', not extra and current.get_editor_property('Ammo') == 0,
              projectiles_first=len(after_first - before), extra_projectiles=len(extra))
        return current

    def cleanup_case():
        collect_runtime_effects()
        # Keep the current QA weapon long enough to spend it through Fire when
        # setting up the next case. Remove only tracked targets/drops/projectiles.
        current = gun()
        current_path = current.get_path_name() if valid(current) else None
        for path, actor in list(tracked.items()):
            if path != current_path and valid(actor):
                actor.destroy_actor()
            if path != current_path:
                tracked.pop(path, None)
        state['targets'] = []
        movement.stop_movement_immediately()
        pawn.set_actor_location(anchor, False, True)

    def equip_kind(kind):
        assert ammo() == 0, 'Do not bypass the loaded-weapon pickup gate'
        before = paths('gun')
        pawn.set_editor_property('NextWeaponKind', kind)
        pawn.call_method('EquipPistol')
        collect_runtime_effects()
        current = gun()
        check(WEAPONS[kind].lower() + '_equips_requested_kind',
              valid(current) and current.get_editor_property('WeaponKind') == kind and ammo() == 1,
              kind=current.get_editor_property('WeaponKind') if valid(current) else None,
              new_weapons=len(paths('gun') - before))
        check(WEAPONS[kind].lower() + '_has_no_unlimited_ammo',
              not current.get_editor_property('UnlimitedAmmo'))
        hud = controller.get_hud()
        check(WEAPONS[kind].lower() + '_hud_matches_weapon',
              valid(hud) and str(hud.get_editor_property('WeaponLabel')).casefold() == WEAPONS[kind].casefold(),
              label=str(hud.get_editor_property('WeaponLabel')) if valid(hud) else None,
              configured_name=str(current.get_editor_property('WeaponName')))

    def cleanup():
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        current = gun()
        if valid(current) and current.get_path_name() in tracked:
            pawn.set_editor_property('EquippedPistol', None)
        for actor in list(tracked.values()):
            if valid(actor):
                actor.destroy_actor()
        for actor, saved in isolated:
            if valid(actor):
                actor.set_editor_property('MoveSpeed', saved['speed'])
                actor.set_actor_enable_collision(saved['collision'])
                actor.set_actor_tick_enabled(saved['tick'])
                if saved['decision_timer']:
                    system.call_method('K2_SetTimer', args=(actor, 'EnemyRolePulse', 0.1, True, True, 0.0, 0.0))
        for actor, enabled in disabled_spawners:
            if valid(actor):
                actor.set_editor_property('Enabled', enabled)
        if valid(pawn) and not pawn.get_editor_property('Dead') and original_location is not None:
            movement.stop_movement_immediately()
            pawn.set_actor_location(original_location, False, True)
            pawn.set_actor_rotation(original_rotation, True)
        report['cleanup'] = 'Removed only tracked runtime QA actors; restored runtime isolation; restart PIE to reset inventory'

    def finish(error=None):
        if session['finished']:
            return
        session['finished'] = True
        try:
            cleanup()
        except Exception as cleanup_error:
            report['cleanup_error'] = str(cleanup_error)
            if error is None:
                error = cleanup_error
        report['status'] = 'complete'
        report['passed'] = error is None and bool(report['checks']) and all(item['passed'] for item in report['checks'])
        if error is not None:
            report['error'] = str(error)
            unreal.log_error('COMBAT_ROLES_QA: ' + str(error))
        write()
        unreal.log('COMBAT_ROLES_QA: passed=' + str(report['passed']))

    session['cancel'] = lambda: finish('Explicitly cancelled')

    try:
        write()
        world, pawn = current_player()
        assert valid(world) and valid(pawn), 'Start a fresh PIE session before this check'
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        assert valid(controller) and not pawn.get_editor_property('Dead'), 'Run from a living local player'
        unreal.WidgetBlueprintLibrary.set_focus_to_game_viewport()
        statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
        maths = unreal.get_default_object(unreal.MathLibrary.static_class())
        system = unreal.get_default_object(unreal.SystemLibrary.static_class())
        classes = {}
        for kind, path in {
            'spawner': '/Game/Enemies/BP_EnemySpawnPoint',
            'enemy': ENEMY_PATHS[0],
            'pickup': '/Game/Weapons/Pistol/BP_PistolPickup',
            'gun': '/Game/Weapons/Pistol/BP_Pistol',
            'bullet': '/Game/Weapons/Pistol/BP_BulletProjectile',
        }.items():
            asset = unreal.load_asset(path)
            assert asset, 'Required existing asset is missing: ' + path
            classes[kind] = asset.generated_class()
        enemy_classes = []
        for path in ENEMY_PATHS:
            asset = unreal.load_asset(path)
            assert asset, 'Implemented enemy role is missing: ' + path
            enemy_classes.append(asset.generated_class())
        cube = unreal.load_asset('/Engine/BasicShapes/Cube.Cube')
        assert cube, 'Engine Cube asset is unavailable for runtime cover acceptance'
        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        assert movement, 'Player has no CharacterMovement component'
        original_location = pawn.get_actor_location()
        original_rotation = pawn.get_actor_rotation()
        anchor = unreal.Vector(0.0, 3000.0, original_location.z)
        baseline = {kind: paths(kind) for kind in ('gun', 'pickup', 'bullet')}
        for spawner in actors('spawner'):
            disabled_spawners.append((spawner, spawner.get_editor_property('Enabled')))
            spawner.set_editor_property('Enabled', False)
        for original in actors('enemy'):
            timer_active = bool(system.call_method('K2_IsTimerActive', args=(original, 'EnemyRolePulse')))
            isolated.append((original, {
                'speed': original.get_editor_property('MoveSpeed'),
                'collision': original.get_actor_enable_collision(),
                'tick': original.is_actor_tick_enabled(), 'decision_timer': timer_active,
            }))
            original.set_editor_property('MoveSpeed', 0.0)
            original.set_actor_enable_collision(False)
            original.set_actor_tick_enabled(False)
            clear_decision(original)
        movement.stop_movement_immediately()
        pawn.set_actor_location(anchor, False, True)
        report['initial_player'] = pawn.get_path_name()
        report['anchor'] = vector(anchor)
        report['isolated_original_enemies'] = len(isolated)
        report['disabled_spawners'] = len(disabled_spawners)

        # Distinct formations check player-visible role outcomes. The cover
        # cases ensure penetration/blast cannot damage through solid geometry.
        cases = [
            {'name': 'pistol_single_target', 'kind': 0,
             'targets': [(0.0, 650.0, True), (0.0, 1050.0, False)]},
            {'name': 'pistol_stops_before_sniper_distance', 'kind': 0, 'wait': 1.4,
             'targets': [(0.0, 2500.0, False)]},
            {'name': 'shotgun_close_spread', 'kind': 1,
             'targets': [(-75.0, 450.0, True), (75.0, 450.0, True), (0.0, 1500.0, False)]},
            {'name': 'sniper_aligned_targets', 'kind': 2,
             'targets': [(0.0, 2500.0, True), (0.0, 3500.0, True)]},
            {'name': 'sniper_stops_at_cover', 'kind': 2,
             'targets': [(0.0, 700.0, True), (0.0, 1500.0, False)],
             'cover': [(unreal.Vector(0.0, 1050.0, 0.0), unreal.Vector(4.0, 0.25, 4.0))]},
            {'name': 'rpg_cluster_radius', 'kind': 3,
             'targets': [(0.0, 1000.0, True), (-140.0, 1050.0, True),
                         (140.0, 1050.0, True), (420.0, 1400.0, False)]},
            {'name': 'rpg_respects_cover', 'kind': 3,
             'targets': [(0.0, 1000.0, True), (-130.0, 1000.0, True), (220.0, 1000.0, False)],
             'cover': [(unreal.Vector(110.0, 1000.0, 0.0), unreal.Vector(0.25, 4.0, 4.0))]},
        ]
        phase('startup')

        def tick(_dt):
            try:
                assert time.monotonic() - wall_start < 60.0, 'Combat QA exceeded its wall-clock limit'
                if state['phase'] == 'restart':
                    new_world, new_pawn = current_player()
                    if not valid(new_pawn) or (valid(pawn) and new_pawn == pawn):
                        return
                    check('contact_death_restarts_with_new_living_player',
                          not new_pawn.get_editor_property('Dead') and new_pawn.get_actor_enable_collision(),
                          pawn=new_pawn.get_path_name(), world=new_world.get_path_name())
                    new_controller = unreal.GameplayStatics.get_player_controller(new_world, 0)
                    label = str(new_controller.get_hud().get_editor_property('AmmoLabel'))
                    check('restart_clears_down_state', label != 'DOWN', label=label)
                    finish()
                    return
                assert valid(pawn) and valid(world), 'Player disappeared before the expected contact restart'
                assert not pawn.get_editor_property('Dead') or state['phase'] == 'contact_wait', 'Unexpected player death'
                collect_runtime_effects()
                age = game_time() - state['phase_time']
                current_phase = state['phase']

                if current_phase == 'startup':
                    if age < 0.4:
                        return
                    if ammo() == 0:
                        equip_kind(0)
                    aim(unreal.Vector(-350.0, 50.0, -92.0))
                    phase('spend_for_case')
                    return

                if current_phase == 'spend_for_case':
                    aim(state['aim_offset'])
                    if age < 0.15:
                        return
                    if ammo() == 1:
                        fire_once('setup_' + str(state['case_index']))
                    cleanup_case()
                    if state['case_index'] >= len(cases):
                        phase('drop_setup')
                        return
                    case = cases[state['case_index']]
                    equip_kind(case['kind'])
                    state['case'] = case
                    state['targets'] = []
                    for x, y, expected in case['targets']:
                        target = enemy(unreal.Vector(x, y, 0.0))
                        state['targets'].append({'actor': target, 'expected_dead': expected,
                                                 'observed_dead': False, 'position': [x, y]})
                    for offset, scale in case.get('cover', []):
                        cover(offset, scale)
                    aim(unreal.Vector(0.0, 600.0, -92.0))
                    phase('case_aim')
                    return

                if current_phase == 'case_aim':
                    aim(state['aim_offset'])
                    if age < 0.15:
                        return
                    fire_once(state['case']['name'])
                    phase('case_outcome')
                    return

                if current_phase == 'case_outcome':
                    if age < state['case'].get('wait', 1.15 if state['case']['kind'] == 3 else 0.85):
                        return
                    outcomes = []
                    for target in state['targets']:
                        actor = target['actor']
                        dead = target['observed_dead'] or not valid(actor)
                        outcomes.append({'position': target['position'], 'expected_dead': target['expected_dead'],
                                         'dead': dead, 'observed_dead': target['observed_dead']})
                    check(state['case']['name'] + '_outcome',
                          all(item['dead'] == item['expected_dead'] for item in outcomes),
                          targets=outcomes)
                    state['case_index'] += 1
                    aim(unreal.Vector(-350.0, 50.0, -92.0))
                    phase('spend_for_case')
                    return

                if current_phase == 'drop_setup':
                    kind = state['drop_kind']
                    assert ammo() == 0, 'Drop acquisition must start from an actually spent weapon'
                    target = enemy(unreal.Vector(300.0, 650.0, 0.0), kind)
                    weapon_component = target.get_editor_property('WeaponMesh')
                    weapon_mesh = weapon_component.get_editor_property('static_mesh')
                    appearance = {
                        'kind': kind, 'class': target.get_class().get_path_name(),
                        'actual_scale': vector(target.get_actor_scale3d()),
                        'configured_tint': vector(target.get_editor_property('BodyTint')),
                        'actual_weapon_mesh': weapon_mesh.get_path_name() if valid(weapon_mesh) else None,
                    }
                    report['enemy_appearance'].append(appearance)
                    check(WEAPONS[kind].lower() + '_enemy_has_visible_weapon_mesh',
                          valid(weapon_mesh) and weapon_component.is_visible(),
                          appearance=appearance)
                    before = paths('pickup')
                    target.call_method('Die')
                    target.call_method('Die')
                    collect_runtime_effects()
                    drops = [remember(actor) for actor in actors('pickup') if actor.get_path_name() not in before]
                    check(WEAPONS[kind].lower() + '_enemy_drops_once', len(drops) == 1, count=len(drops))
                    drop = drops[0]
                    check(WEAPONS[kind].lower() + '_drop_matches_enemy',
                          drop.get_editor_property('WeaponKind') == kind,
                          pickup_kind=drop.get_editor_property('WeaponKind'),
                          enemy_class=target.get_class().get_path_name())
                    check(WEAPONS[kind].lower() + '_drop_starts_returning', drop.get_editor_property('Returning'))
                    state['drop'] = drop
                    phase('drop_acquire')
                    return

                if current_phase == 'drop_acquire':
                    kind = state['drop_kind']
                    if ammo() == 0 and age < 1.0:
                        return
                    current = gun()
                    hud = controller.get_hud()
                    check(WEAPONS[kind].lower() + '_return_equips_matching_next_shot',
                          valid(current) and ammo() == 1 and current.get_editor_property('WeaponKind') == kind
                          and not valid(state['drop']),
                          kind=current.get_editor_property('WeaponKind') if valid(current) else None,
                          return_elapsed=age)
                    check(WEAPONS[kind].lower() + '_return_updates_hud',
                          str(hud.get_editor_property('WeaponLabel')).casefold() == WEAPONS[kind].casefold()
                          and str(hud.get_editor_property('AmmoLabel')) == '1/1',
                          weapon=str(hud.get_editor_property('WeaponLabel')),
                          ammo=str(hud.get_editor_property('AmmoLabel')))
                    aim(unreal.Vector(-350.0, 50.0, -92.0))
                    phase('spend_drop')
                    return

                if current_phase == 'spend_drop':
                    aim(state['aim_offset'])
                    if age < 0.15:
                        return
                    fire_once('drop_' + WEAPONS[state['drop_kind']].lower())
                    cleanup_case()
                    state['drop_kind'] += 1
                    if state['drop_kind'] < len(WEAPONS):
                        phase('drop_setup')
                    else:
                        looks = report['enemy_appearance']
                        check('all_four_enemy_roles_have_distinct_scale_tint_and_weapon_mesh',
                              len({tuple(item['actual_scale']) for item in looks}) == 4
                              and len({tuple(item['configured_tint']) for item in looks}) == 4
                              and len({item['actual_weapon_mesh'] for item in looks}) == 4,
                              roles=looks)
                        phase('charge_setup')
                    return

                if current_phase == 'charge_setup':
                    check('miss_recovery_starts_with_empty_weapon', ammo() == 0)
                    target = enemy(unreal.Vector(0.0, 650.0, 0.0), 1)
                    state['targets'] = [{'actor': target, 'expected_dead': True,
                                         'observed_dead': False, 'position': [0.0, 650.0]}]
                    state['charge_enemy'] = target
                    state['charge_pickups_before'] = paths('pickup')
                    target.call_method('BeginChargeWarning')
                    check('assault_warns_before_empty_state_recovery',
                          target.get_editor_property('AIState') == 1
                          and not target.get_editor_property('ChargeActive') and ammo() == 0)
                    # Add cover after the enemy has committed its warning aim.
                    # Re-enable its real pulse and let its normal movement hit
                    # the wall. The test never sets ChargeActive or calls Die.
                    cover(unreal.Vector(0.0, 350.0, 0.0), unreal.Vector(4.0, 0.25, 4.0))
                    system.call_method('K2_SetTimer', args=(target, 'EnemyRolePulse', 0.1, True, True, 0.0, 0.0))
                    phase('charge_recovery')
                    return

                if current_phase == 'charge_recovery':
                    target = state['charge_enemy']
                    if valid(target) and target.get_editor_property('ChargeActive'):
                        state['observed_real_charge'] = True
                    drops = [remember(actor) for actor in actors('pickup')
                             if actor.get_path_name() not in state['charge_pickups_before']]
                    if drops and 'charge_recovery_drop' not in state:
                        check('assault_wall_collision_drops_one_shotgun',
                              len(drops) == 1 and drops[0].get_editor_property('WeaponKind') == 1,
                              count=len(drops), kind=drops[0].get_editor_property('WeaponKind'))
                        state['charge_recovery_drop'] = drops[0]
                    if ammo() == 0 and age < 3.0:
                        return
                    current = gun()
                    check('empty_weapon_recovers_from_real_charge_wall_death',
                          valid(current) and ammo() == 1 and current.get_editor_property('WeaponKind') == 1
                          and state['targets'][0]['observed_dead']
                          and not pawn.get_editor_property('Dead'),
                          elapsed=age, observed_charge=state.get('observed_real_charge', False),
                          observed_dead=state['targets'][0]['observed_dead'])
                    cleanup_case()
                    aim(unreal.Vector(-350.0, 50.0, -92.0))
                    phase('spend_recovery')
                    return

                if current_phase == 'spend_recovery':
                    aim(state['aim_offset'])
                    if age < 0.15:
                        return
                    fire_once('wall_recovery_shotgun')
                    cleanup_case()
                    phase('dodge_setup')
                    return

                if current_phase == 'dodge_setup':
                    check('empty_weapon_before_survival_check', ammo() == 0)
                    movement.stop_movement_immediately()
                    pawn.set_actor_location(anchor, False, True)
                    pawn.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=90.0, roll=0.0), True)
                    state['contact_enemy'] = enemy(unreal.Vector(0.0, 300.0, 0.0))
                    pawn.call_method('TryDodge')
                    check('empty_weapon_can_start_dodge', pawn.get_editor_property('Dodging')
                          and pawn.get_editor_property('DodgeCooling'))
                    pawn.call_method('TryDodge')
                    phase('dodge_window')
                    return

                if current_phase == 'dodge_window':
                    if age < 0.05:
                        return
                    check('qa_samples_contact_inside_active_dodge_window', pawn.get_editor_property('Dodging'),
                          elapsed=age, required_window=pawn.get_editor_property('DodgeDuration'))
                    check('dodge_moves_empty_player', pawn.get_velocity().length() > 20.0,
                          velocity=vector(pawn.get_velocity()))
                    # Sweep actual collision geometry during the production
                    # invulnerability window; no damage event is invoked.
                    hit = state['contact_enemy'].set_actor_location(pawn.get_actor_location(), True, False)
                    state['dodge_contact_hit'] = str(hit)
                    distance = state['contact_enemy'].get_distance_to(pawn)
                    check('dodge_contact_has_blocking_geometry', 10.0 < distance < 180.0,
                          hit=str(hit), remaining_distance=distance)
                    check('contact_during_dodge_does_not_kill', not pawn.get_editor_property('Dead'),
                          hit=state['dodge_contact_hit'])
                    if valid(state['contact_enemy']):
                        state['contact_enemy'].destroy_actor()
                    phase('dodge_ends')
                    return

                if current_phase == 'dodge_ends':
                    if age < 0.22:
                        return
                    check('dodge_window_ends_before_cooldown', not pawn.get_editor_property('Dodging')
                          and pawn.get_editor_property('DodgeCooling'))
                    pawn.call_method('TryDodge')
                    check('dodge_cooldown_blocks_repeat', not pawn.get_editor_property('Dodging'))
                    phase('dodge_cooldown')
                    return

                if current_phase == 'dodge_cooldown':
                    if pawn.get_editor_property('DodgeCooling') and age < 1.3:
                        return
                    check('dodge_cooldown_recovers', not pawn.get_editor_property('DodgeCooling'))
                    pawn.call_method('TryDodge')
                    check('dodge_available_again_without_ammo', pawn.get_editor_property('Dodging') and ammo() == 0)
                    phase('before_contact')
                    return

                if current_phase == 'before_contact':
                    if age < 0.3:
                        return
                    check('contact_check_is_outside_dodge', not pawn.get_editor_property('Dodging'))
                    movement.stop_movement_immediately()
                    pawn.set_actor_location(anchor, False, True)
                    contact_enemy = enemy(unreal.Vector(0.0, 300.0, 0.0))
                    hit = contact_enemy.set_actor_location(pawn.get_actor_location(), True, False)
                    event('physical_contact_sweep', hit=str(hit))
                    phase('contact_wait')
                    return

                if current_phase == 'contact_wait':
                    if not pawn.get_editor_property('Dead') and age < 0.25:
                        return
                    hud = controller.get_hud()
                    check('enemy_physical_contact_kills_player', pawn.get_editor_property('Dead'))
                    check('contact_death_sets_down_hud', str(hud.get_editor_property('AmmoLabel')) == 'DOWN',
                          label=str(hud.get_editor_property('AmmoLabel')))
                    check('contact_death_stops_movement', movement.movement_mode == unreal.MovementMode.MOVE_NONE)
                    check('contact_death_disables_collision', not pawn.get_actor_enable_collision())
                    phase('restart')

            except Exception as error:
                finish(error)

        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write()
    except Exception as error:
        finish(error)


run()
