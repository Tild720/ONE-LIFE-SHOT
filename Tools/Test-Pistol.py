"""Run through Unreal Python during PIE after picking up the Pistol.

Exercises IA_Fire three times while aiming outside the floor island.
Writes Saved/PistolTest.json and reports the assertion in Output Log.
"""
import json
from pathlib import Path
import unreal


def run():
    world = unreal.EditorLevelLibrary.get_pie_worlds(False)[0]
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    controller = unreal.GameplayStatics.get_player_controller(world, 0)
    gun = pawn.get_editor_property('EquippedPistol')
    assert gun, 'Pick up the Pistol before running this check'
    context = unreal.load_asset('/Game/Input/IMC_Default')
    subsystem = next(s for s in unreal.ObjectIterator(unreal.EnhancedInputLocalPlayerSubsystem)
                     if s.get_path_name().startswith('/Engine/Transient.')
                     and s.has_mapping_context(context) is not None)
    fire = unreal.load_asset('/Game/Input/Actions/IA_Fire')
    bullet_class = unreal.load_asset('/Game/Weapons/Pistol/BP_BulletProjectile').generated_class()
    state = {'frames': 0, 'projectiles': {}}
    output = Path(unreal.Paths.project_saved_dir()) / 'PistolTest.json'

    def tick(_dt):
        try:
            state['frames'] += 1
            frame = state['frames']
            controller.set_mouse_location(40, 40)
            subsystem.inject_input_vector_for_action(
                fire, unreal.Vector(1 if frame in (12, 24, 36) else 0, 0, 0), [], [])
            for bullet in unreal.GameplayStatics.get_all_actors_of_class(world, bullet_class):
                position = bullet.get_actor_location()
                state['projectiles'].setdefault(bullet.get_name(), []).append(
                    [position.x, position.y, position.z, bullet.get_velocity().length()])
            if frame < 65:
                return
            unreal.unregister_slate_post_tick_callback(handle)
            trajectories = list(state['projectiles'].values())
            state['passed'] = len(trajectories) >= 3 and all(
                len(points) > 1 and points[0][:3] != points[-1][:3]
                and points[0][3] > 0 for points in trajectories)
            output.write_text(json.dumps(state), encoding='utf-8')
            assert state['passed'], 'Three clicks must produce three moving projectiles'
            unreal.log('Pistol repeat-fire check passed')
        except Exception as error:
            unreal.unregister_slate_post_tick_callback(handle)
            state['error'] = str(error)
            output.write_text(json.dumps(state), encoding='utf-8')
            unreal.log_error(str(error))

    handle = unreal.register_slate_post_tick_callback(tick)


run()
