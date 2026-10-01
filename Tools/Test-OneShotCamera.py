"""Run in a fresh PIE session; results go to Saved/OneShotCameraTest.json.

Exercises the fixed camera, forward/back movement, and FailRun restart using
existing gameplay methods. It does not save assets, delete actors, or edit Ammo.
The builtins guard survives OpenLevel and prevents BeginPlay from rerunning QA.
To explicitly repeat the test, first run:
    import builtins; delattr(builtins, '_one_shot_camera_qa_session')
Do not clear that guard while its callback is still running.
"""
import builtins
import json
import math
from pathlib import Path
import time
import uuid

import unreal


SESSION_KEY = '_one_shot_camera_qa_session'


def run():
    if hasattr(builtins, SESSION_KEY):
        unreal.log('One-shot camera QA already started; reload replay ignored')
        return

    output = Path(unreal.Paths.project_saved_dir()) / 'OneShotCameraTest.json'
    report = {
        'nonce': uuid.uuid4().hex,
        'status': 'running',
        'source_modes': {
            'camera': 'PIE component transforms after forced pawn yaw and wall positions',
            'movement': 'Pawn.AddMovementInput world +Y/-Y; physical WASD mapping not exercised',
            'death': 'Existing Character.FailRun and Pickup.TryAcquire methods',
            'restart': 'Live PIE replacement pawn after existing OpenLevel delay',
        },
        'checks': [],
    }
    session = {'report': report, 'handle': None}
    setattr(builtins, SESSION_KEY, session)
    spawners = []
    pawn = None
    movement = None
    original_tick = None
    original_location = None
    original_rotation = None

    def write_report():
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')

    def check(name, passed, **evidence):
        report['checks'].append({'name': name, 'passed': bool(passed), **evidence})
        write_report()

    def valid(obj):
        # Python can retain an old UObject wrapper during OpenLevel teardown.
        try:
            return bool(obj) and unreal.SystemLibrary.is_valid(obj)
        except Exception:
            return False

    def vector(v):
        return [v.x, v.y, v.z]

    def angle_error(value, expected):
        return abs((value - expected + 180.0) % 360.0 - 180.0)

    def cleanup():
        for spawner, enabled in spawners:
            if valid(spawner):
                spawner.set_editor_property('Enabled', enabled)
        if valid(pawn) and original_tick is not None:
            pawn.set_actor_tick_enabled(original_tick)
            if not pawn.get_editor_property('Dead'):
                movement.stop_movement_immediately()
                pawn.set_actor_location(original_location, False, True)
                pawn.set_actor_rotation(original_rotation, True)

    try:
        editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
        world = editor.get_game_world()
        assert valid(world), 'Start PIE before running this check'
        pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        assert valid(pawn) and valid(controller), 'PIE player is not ready'
        assert not pawn.get_editor_property('Dead'), 'Run from a living player'
        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        assert movement, 'PIE pawn has no CharacterMovement component'
        original_location = pawn.get_actor_location()
        original_rotation = pawn.get_actor_rotation()
        original_tick = pawn.is_actor_tick_enabled()
        report['initial_pawn'] = pawn.get_path_name()
        report['initial_world'] = world.get_path_name()
        report['spawners_without_enabled'] = []
        for asset_path in ('/Game/Enemies/BP_EnemySpawnPoint',
                           '/Game/Enemies/BP_EnemyRunnerSpawner'):
            asset = unreal.load_asset(asset_path)
            assert asset, 'Existing spawner asset was not found: ' + asset_path
            for spawner in unreal.GameplayStatics.get_all_actors_of_class(world, asset.generated_class()):
                try:
                    enabled = spawner.get_editor_property('Enabled')
                except Exception:
                    report['spawners_without_enabled'].append(spawner.get_path_name())
                    continue  # The legacy single-spawn actor has no Enabled input.
                spawners.append((spawner, enabled))
                spawner.set_editor_property('Enabled', False)
        report['temporarily_disabled_spawners'] = [actor.get_path_name() for actor, _ in spawners]
        start_wall_clock = time.monotonic()
        state = {'phase': 'camera', 'index': 0, 'elapsed': 0.0, 'started': False}
        cases = [(0.0, 0.0), (0.0, 90.0), (0.0, 180.0),
                 (0.0, 270.0), (-430.0, 0.0), (430.0, 0.0)]
        # Hold the tested pawn yaw; its normal Tick continuously aims at the mouse.
        pawn.set_actor_tick_enabled(False)
        movement.stop_movement_immediately()

        def camera_sample(tested_pawn, label):
            arm = tested_pawn.get_editor_property('CameraBoom')
            camera = tested_pawn.get_editor_property('FollowCamera')
            rotation = camera.get_world_rotation()
            origin = arm.get_world_location() + arm.target_offset
            distance = (camera.get_world_location() - origin).length()
            socket = arm.socket_offset
            expected_distance = math.sqrt(
                (1400.0 - socket.x) ** 2 + socket.y ** 2 + socket.z ** 2)
            fixed = (angle_error(rotation.pitch, -55.0) < 0.2
                     and angle_error(rotation.yaw, 90.0) < 0.2
                     and angle_error(rotation.roll, 0.0) < 0.2
                     and abs(arm.target_arm_length - 1400.0) < 0.1
                     and not arm.do_collision_test
                     and abs(distance - expected_distance) < 2.0)
            check(label, fixed,
                  pawn_location=vector(tested_pawn.get_actor_location()),
                  pawn_yaw=tested_pawn.get_actor_rotation().yaw,
                  camera_rotation=[rotation.pitch, rotation.yaw, rotation.roll],
                  camera_location=vector(camera.get_world_location()),
                  arm_length=arm.target_arm_length,
                  camera_distance=distance, expected_distance=expected_distance,
                  collision_test=arm.do_collision_test)

        def finish(error=None):
            if session['handle'] is not None:
                unreal.unregister_slate_post_tick_callback(session['handle'])
                session['handle'] = None
            cleanup()
            report['status'] = 'complete'
            if error is not None:
                report['error'] = str(error)
            report['passed'] = error is None and bool(report['checks']) and all(
                item['passed'] for item in report['checks'])
            write_report()
            unreal.log('ONE_SHOT_CAMERA_QA ' + str(report['passed']))
            if error is not None:
                unreal.log_error(str(error))

        def current_player():
            candidate_world = editor.get_game_world()
            if valid(candidate_world):
                candidate = unreal.GameplayStatics.get_player_pawn(candidate_world, 0)
                if valid(candidate):
                    return candidate_world, candidate
            return None, None

        def tick(dt):
            try:
                if time.monotonic() - start_wall_clock > 20.0:
                    raise RuntimeError('QA timed out waiting for gameplay or level restart')
                state['elapsed'] += dt
                if state['phase'] == 'camera':
                    x, yaw = cases[state['index']]
                    if not state['started']:
                        movement.stop_movement_immediately()
                        location = pawn.get_actor_location()
                        pawn.set_actor_location(unreal.Vector(x, -100.0, location.z), False, True)
                        pawn.set_actor_rotation(unreal.Rotator(pitch=0.0, yaw=yaw, roll=0.0), True)
                        state['elapsed'] = 0.0
                        state['started'] = True
                        return
                    if state['elapsed'] < 0.15:
                        return
                    camera_sample(pawn, 'camera_yaw_' + str(yaw) + '_x_' + str(x))
                    check('forced_yaw_' + str(state['index']),
                          angle_error(pawn.get_actor_rotation().yaw, yaw) < 0.2)
                    state['index'] += 1
                    state['started'] = False
                    if state['index'] == len(cases):
                        pawn.set_actor_tick_enabled(original_tick)
                        state['phase'] = 'forward'
                    return

                if state['phase'] in ('forward', 'backward'):
                    direction = 1.0 if state['phase'] == 'forward' else -1.0
                    if not state['started']:
                        movement.stop_movement_immediately()
                        location = pawn.get_actor_location()
                        pawn.set_actor_location(unreal.Vector(0.0, -100.0, location.z), False, True)
                        state['move_start'] = pawn.get_actor_location()
                        state['elapsed'] = 0.0
                        state['started'] = True
                    if state['elapsed'] < 0.25:
                        pawn.add_movement_input(unreal.Vector(0.0, 1.0, 0.0), direction, False)
                        return
                    delta = pawn.get_actor_location() - state['move_start']
                    check(state['phase'] + '_movement', delta.y * direction > 2.0,
                          delta=vector(delta), input_direction=direction)
                    camera_sample(pawn, 'camera_after_' + state['phase'])
                    movement.stop_movement_immediately()
                    state['started'] = False
                    state['phase'] = 'backward' if direction > 0.0 else 'fail'
                    return

                if state['phase'] == 'fail':
                    location = pawn.get_actor_location()
                    pawn.set_actor_location(unreal.Vector(0.0, -100.0, location.z), False, True)
                    gun = pawn.get_editor_property('EquippedPistol')
                    previous_gun = gun.get_path_name() if gun else None
                    pickup_class = unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup').generated_class()
                    pickups = unreal.GameplayStatics.get_all_actors_of_class(world, pickup_class)
                    pawn.call_method('FailRun')
                    hud = controller.get_hud()
                    label = str(hud.get_editor_property('AmmoLabel')) if hud else ''
                    check('failrun_dead', pawn.get_editor_property('Dead'))
                    check('failrun_hud', label == 'DOWN', label=label)
                    check('failrun_movement_stopped', movement.movement_mode == unreal.MovementMode.MOVE_NONE,
                          mode=str(movement.movement_mode), velocity=vector(pawn.get_velocity()))
                    check('failrun_collision_disabled', not pawn.get_actor_enable_collision())
                    if pickups:
                        pickup = pickups[0]
                        pickup.call_method('TryAcquire')
                        after_gun = pawn.get_editor_property('EquippedPistol')
                        after_path = after_gun.get_path_name() if after_gun else None
                        check('dead_pickup_keeps_weapon_state',
                              after_path == previous_gun and valid(pickup),
                              before=previous_gun, after=after_path,
                              had_loaded_gun=bool(gun and gun.get_editor_property('Ammo') > 0))
                    else:
                        check('dead_pickup_available', False, reason='No existing Pistol pickup in this PIE world')
                    state['phase'] = 'restart'
                    state['elapsed'] = 0.0
                    write_report()
                    return

                if state['phase'] == 'restart':
                    new_world, new_pawn = current_player()
                    if not valid(new_pawn) or (valid(pawn) and new_pawn == pawn):
                        return
                    state['new_world'] = new_world
                    state['new_pawn'] = new_pawn
                    state['phase'] = 'restored'
                    state['elapsed'] = 0.0
                    return

                if state['phase'] == 'restored' and state['elapsed'] >= 0.2:
                    new_pawn = state['new_pawn']
                    new_world = state['new_world']
                    new_controller = unreal.GameplayStatics.get_player_controller(new_world, 0)
                    new_hud = new_controller.get_hud()
                    label = str(new_hud.get_editor_property('AmmoLabel')) if new_hud else ''
                    check('restart_replaced_pawn', not valid(pawn) or new_pawn != pawn,
                          world=new_world.get_path_name(), pawn=new_pawn.get_path_name())
                    check('restart_alive', not new_pawn.get_editor_property('Dead'))
                    check('restart_movement_restored',
                          new_pawn.get_component_by_class(unreal.CharacterMovementComponent).movement_mode != unreal.MovementMode.MOVE_NONE)
                    check('restart_collision_restored', new_pawn.get_actor_enable_collision())
                    check('restart_hud_restored', bool(label) and label != 'DOWN', label=label)
                    camera_sample(new_pawn, 'camera_after_restart')
                    finish()
            except Exception as error:
                finish(error)

        session['cancel'] = finish
        session['handle'] = unreal.register_slate_post_tick_callback(tick)
        write_report()
    except Exception as error:
        cleanup()
        report['status'] = 'complete'
        report['passed'] = False
        report['error'] = str(error)
        write_report()
        unreal.log_error(str(error))


run()
