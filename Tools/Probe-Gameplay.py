"""Read-only runtime probe for the existing PIE session."""
import json
from pathlib import Path
import unreal


def run():
    worlds = unreal.EditorLevelLibrary.get_pie_worlds(False)
    world = worlds[0]
    pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
    pc = unreal.GameplayStatics.get_player_controller(world, 0)
    arm = pawn.get_editor_property('CameraBoom')
    cam = pawn.get_editor_property('FollowCamera')
    enemies = unreal.GameplayStatics.get_all_actors_of_class(
        world, unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class())
    def vec(v):
        return [v.x, v.y, v.z]
    result = {
        'world': world.get_path_name(), 'pawn': pawn.get_path_name(),
        'position': vec(pawn.get_actor_location()),
        'camera': vec(cam.get_world_location()),
        'rotation': str(cam.get_world_rotation()),
        'arm_length': arm.target_arm_length,
        'collision_test': arm.do_collision_test,
        'enemy_count': len(enemies),
        'enemies': [{'path': a.get_path_name(), 'pos': vec(a.get_actor_location()),
                     'speed': a.get_editor_property('MoveSpeed')} for a in enemies],
        'mouse_cursor': pc.show_mouse_cursor,
    }
    (Path(unreal.Paths.project_saved_dir()) / 'GameplayProbe.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    unreal.log('ONE LIFE SHOT gameplay probe complete')


run()
