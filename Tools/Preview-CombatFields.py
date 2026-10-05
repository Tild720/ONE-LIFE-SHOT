"""Disposable, frozen PIE visual previews, explicitly not gameplay acceptance.

Import and call preview('assault'|'sniper'|'heavy'|'rpg'), or queue this script
with builtins._ols_combat_fields_preview_mode set. Default mode is Assault.
Production warning/Detonate functions create the visuals. Only runtime actors
and timing are frozen for a native MCP CaptureEditorImage. Nothing is saved to
Content; ending PIE removes the fixture and restores background throttling.
"""
import builtins
import json
import time
import traceback
from pathlib import Path

import unreal

KEY = '_ols_combat_fields_preview'
MODES = {
    'assault': ('/Game/Enemies/BP_EnemyRunnerFast', 'BeginChargeWarning', (-150, 500, 0)),
    'sniper': ('/Game/Enemies/BP_EnemySniper', 'BeginSniperWarning', (220, 650, 0)),
    'heavy': ('/Game/Enemies/BP_EnemyRunnerSlow', 'BeginBlastWarning', (250, 530, 0)),
}


def preview(mode=None):
    mode = mode or getattr(builtins, '_ols_combat_fields_preview_mode', 'assault')
    assert mode in {*MODES, 'rpg'}, mode
    previous = getattr(builtins, KEY, None)
    if previous:
        previous.get('cleanup', lambda: None)()
    output = Path(unreal.Paths.project_saved_dir()) / ('CombatFieldsPreview_' + mode + '.json')
    session = {'mode': mode, 'status': 'startup', 'handle': None, 'tracked': [],
               'isolated': [], 'spawners': [], 'pawn': None, 'world': None,
               'performance': None, 'restored': False, 'report': {
                   'mode': mode, 'status': 'startup', 'acceptance_test': False,
                   'source': 'Frozen runtime visual fixture using production warnings/Detonate; no gameplay result inferred'}}
    setattr(builtins, KEY, session)
    wall_start = time.monotonic()
    statics = unreal.get_default_object(unreal.GameplayStatics.static_class())
    maths = unreal.get_default_object(unreal.MathLibrary.static_class())
    system = unreal.get_default_object(unreal.SystemLibrary.static_class())

    def valid(obj):
        return obj is not None and unreal.SystemLibrary.is_valid(obj)

    def clock():
        return float(statics.call_method('GetTimeSeconds', args=(session['world'],)))

    def vec(value):
        return [float(value.x), float(value.y), float(value.z)]

    def write():
        session['report']['wall_elapsed'] = round(time.monotonic() - wall_start, 3)
        output.write_text(json.dumps(session['report'], indent=2), encoding='utf-8')

    def clear(actor, name):
        system.call_method('K2_ClearTimer', args=(actor, name))

    def spawn(cls, position, properties=None):
        transform = maths.call_method('MakeTransform', args=(
            position, unreal.Rotator(), unreal.Vector(1, 1, 1)))
        scale_mode = unreal.SpawnActorScaleMethod.MULTIPLY_WITH_ROOT
        actor = statics.call_method('BeginDeferredActorSpawnFromClass', args=(
            session['world'], cls, transform,
            unreal.SpawnActorCollisionHandlingMethod.ALWAYS_SPAWN, None, scale_mode))
        assert valid(actor), 'Could not spawn disposable preview actor'
        session['tracked'].append(actor)
        for name, value in (properties or {}).items():
            actor.set_editor_property(name, value)
        statics.call_method('FinishSpawningActor', args=(actor, transform, scale_mode))
        return actor

    def cleanup():
        if session['restored']:
            return
        session['restored'] = True
        if session['handle'] is not None:
            unreal.unregister_slate_post_tick_callback(session['handle'])
            session['handle'] = None
        for actor in session['tracked']:
            if valid(actor):
                actor.destroy_actor()
        for actor, saved in session['isolated']:
            if not valid(actor):
                continue
            actor.set_editor_property('MoveSpeed', saved['speed'])
            actor.set_actor_enable_collision(saved['collision'])
            actor.set_actor_tick_enabled(saved['tick'])
            actor.set_actor_hidden_in_game(saved['hidden'])
            if saved['timer']:
                system.call_method('K2_SetTimer', args=(actor, 'EnemyRolePulse', .1, True, True, 0.0, 0.0))
        for actor, enabled, active in session['spawners']:
            if valid(actor):
                actor.set_editor_property('Enabled', enabled)
                if active:
                    system.call_method('K2_SetTimer', args=(actor, 'SpawnNext', .2, True, True, 0.0, 0.0))
        pawn = session['pawn']
        if valid(pawn) and 'pawn_saved' in session:
            saved = session['pawn_saved']
            movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
            movement.stop_movement_immediately()
            movement.set_movement_mode(saved['movement_mode'], saved['custom_movement_mode'])
            pawn.set_actor_location(saved['location'], False, True)
            pawn.set_actor_rotation(saved['rotation'], True)
            pawn.set_actor_tick_enabled(saved['tick'])
            controller = unreal.GameplayStatics.get_player_controller(session['world'], 0)
            if valid(controller):
                pawn.enable_input(controller)
        if valid(session['performance']):
            session['performance'].set_editor_property('bThrottleCPUWhenNotForeground', session['old_throttle'])
        session['report']['cleanup'] = 'Runtime preview removed; existing actors, input, movement, timers, and background throttling restored'
        write()

    session['cleanup'] = cleanup

    def setup(world, pawn):
        session['world'] = world
        session['pawn'] = pawn
        performance = unreal.load_object(None, '/Script/UnrealEd.Default__EditorPerformanceSettings')
        session['performance'] = performance
        session['old_throttle'] = performance.get_editor_property('bThrottleCPUWhenNotForeground')
        performance.set_editor_property('bThrottleCPUWhenNotForeground', False)
        base_class = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class()
        spawn_class = unreal.load_asset('/Game/Enemies/BP_EnemySpawnPoint').generated_class()
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, spawn_class):
            enabled = actor.get_editor_property('Enabled')
            active = bool(system.call_method('K2_IsTimerActive', args=(actor, 'SpawnNext')))
            session['spawners'].append((actor, enabled, active))
            actor.set_editor_property('Enabled', False)
            clear(actor, 'SpawnNext')
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, base_class):
            session['isolated'].append((actor, {
                'speed': actor.get_editor_property('MoveSpeed'),
                'collision': actor.get_actor_enable_collision(),
                'tick': actor.is_actor_tick_enabled(),
                'hidden': actor.get_editor_property('hidden'),
                'timer': bool(system.call_method('K2_IsTimerActive', args=(actor, 'EnemyRolePulse')))}))
            actor.set_editor_property('MoveSpeed', 0.0)
            actor.set_actor_enable_collision(False)
            actor.set_actor_tick_enabled(False)
            actor.set_actor_hidden_in_game(True)
            clear(actor, 'EnemyRolePulse')

        movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
        session['pawn_saved'] = {
            'location': pawn.get_actor_location(), 'rotation': pawn.get_actor_rotation(),
            'tick': pawn.is_actor_tick_enabled(),
            'movement_mode': movement.get_editor_property('movement_mode'),
            'custom_movement_mode': movement.get_editor_property('custom_movement_mode')}
        movement.stop_movement_immediately()
        movement.disable_movement()
        pawn.set_actor_tick_enabled(False)
        controller = unreal.GameplayStatics.get_player_controller(world, 0)
        pawn.disable_input(controller)
        # Use the actual corridor floor/camera, never an isolated white test cube.
        capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
        half_height = float(capsule.call_method('GetScaledCapsuleHalfHeight'))
        # Inspected corridor floor top is Z=50. Do not freeze the starter pawn
        # in mid-fall and falsely preview a floating warning above the floor.
        anchor = unreal.Vector(0, 1500, 50.0 + half_height + 2.25)
        session['anchor'] = anchor
        pawn.set_actor_location(anchor, False, True)
        pawn.set_actor_rotation(unreal.Rotator(pitch=0, yaw=90, roll=0), True)
        gun = pawn.get_editor_property('EquippedPistol')
        session['report']['equipped_weapon'] = gun.get_path_name() if valid(gun) else None
        session['report']['player'] = vec(anchor)
        if mode == 'rpg':
            cls = unreal.load_asset('/Game/Weapons/Pistol/BP_BulletProjectile').generated_class()
            actor = spawn(cls, anchor + unreal.Vector(120, 430, 0), {'WeaponKind': 3})
            actor.call_method('Detonate')
            clear(actor, 'Detonate')
            clear(actor, 'UpdateExplosionVisual')
            actor.set_life_span(0.0)
            actor.set_actor_tick_enabled(False)
            core = actor.get_editor_property('ExplosionSphere')
            ring = actor.get_editor_property('ExplosionRing')
            flare = actor.get_editor_property('ExplosionFlare')
            assert valid(core) and valid(ring) and valid(flare), 'Production RPG effect components are missing'
            core.set_visibility(False, False)
            ring.call_method('SetScalarParameterValueOnMaterials', args=('EffectProgress', .35))
            flare.call_method('SetScalarParameterValueOnMaterials', args=('EffectProgress', .35))
            session['target'] = actor
            session['report'].update({'status': 'frozen', 'effect_progress': .35,
                'core_visible': bool(core.is_visible()), 'ring_visible': bool(ring.is_visible()),
                'ring_position': vec(ring.get_world_location()),
                'ring_scale': vec(ring.get_editor_property('relative_scale3d')),
                'flare_visible': bool(flare.is_visible()),
                'flare_scale': vec(flare.get_editor_property('relative_scale3d')),
                'material': ring.get_material(0).get_path_name()})
            session['status'] = 'frozen'
            write()
            return

        path, function, offset = MODES[mode]
        actor = spawn(unreal.load_asset(path).generated_class(),
                      anchor + unreal.Vector(*offset), {'MoveSpeed': 0.0})
        actor.set_actor_enable_collision(False)
        actor.set_actor_tick_enabled(False)
        clear(actor, 'EnemyRolePulse')
        actor.call_method(function)
        # No decision pulse can discharge damage while this preview waits for
        # the real lock window. AttackTarget/Direction come from production.
        clear(actor, 'EnemyRolePulse')
        session['target'] = actor
        session['status'] = 'wait_lock'
        session['report']['status'] = 'wait_lock'
        write()

    def tick(_delta):
        try:
            les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
            if not les.is_in_play_in_editor():
                if session['status'] != 'startup':
                    cleanup()
                return
            if session['status'] == 'startup':
                assert time.monotonic() - wall_start < 12.0, 'Preview startup timed out'
                world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
                pawn = unreal.GameplayStatics.get_player_pawn(world, 0) if valid(world) else None
                if not valid(pawn):
                    return
                assert not pawn.get_editor_property('Dead'), 'Use a fresh, living PIE player'
                setup(world, pawn)
                return
            if session['status'] == 'wait_lock':
                actor = session['target']
                remaining = float(actor.get_editor_property('StateEndTime')) - clock()
                lead = float(actor.get_editor_property('WarningLockLeadTime'))
                if remaining > lead - .02:
                    return
                actor.call_method('UpdateAttackWarning')
                clear(actor, 'EnemyRolePulse')
                warning = actor.get_editor_property('TelegraphMesh')
                tint = warning.get_material(0).call_method('K2_GetVectorParameterValue', args=('TracerColor',))
                session['report'].update({'status': 'frozen', 'enemy': actor.get_path_name(),
                    'remaining_when_frozen': remaining, 'target': vec(actor.get_editor_property('AttackTarget')),
                    'direction': vec(actor.get_editor_property('AttackDirection')),
                    'tint': [tint.r, tint.g, tint.b], 'warning_visible': bool(warning.is_visible()),
                    'warning_position': vec(warning.get_world_location()),
                    'warning_rotation': str(warning.get_editor_property('relative_rotation')),
                    'warning_scale': vec(warning.get_editor_property('relative_scale3d')),
                    'material': warning.get_material(0).get_path_name()})
                session['status'] = 'frozen'
                write()
        except Exception:
            session['report']['error'] = traceback.format_exc()
            session['report']['status'] = 'error'
            write()
            cleanup()
            unreal.log_error(session['report']['error'])

    unreal.EditorPythonScripting.set_keep_python_script_alive(True)
    session['handle'] = unreal.register_slate_post_tick_callback(tick)
    write()
    return session


if __name__ == '__main__':
    preview()
