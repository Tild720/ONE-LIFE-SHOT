"""Runtime-only map/UI preview; frozen threats are not gameplay acceptance."""
import builtins, json
from pathlib import Path
import unreal

world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world
pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
assert pawn
system = unreal.get_default_object(unreal.SystemLibrary.static_class())
enemy = unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner').generated_class()
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, enemy):
    actor.set_actor_tick_enabled(False)
    actor.set_actor_enable_collision(False)
    system.call_method('K2_ClearTimer', args=(actor, 'EnemyRolePulse'))
for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.Actor):
    if 'SpawnPoint' in actor.get_class().get_name():
        system.call_method('K2_ClearTimer', args=(actor, 'SpawnNext'))
movement = pawn.get_component_by_class(unreal.CharacterMovementComponent)
movement.stop_movement_immediately()
y = getattr(builtins, '_ols_facility_preview_y', 120)
capsule = pawn.get_component_by_class(unreal.CapsuleComponent)
pawn.set_actor_location(unreal.Vector(0, y, 50 + capsule.get_scaled_capsule_half_height() + 2.25), False, False)
pawn.set_actor_rotation(unreal.Rotator(yaw=90), False)
controller = unreal.GameplayStatics.get_player_controller(world, 0)
point = unreal.GameplayStatics.project_world_to_screen(controller, unreal.Vector(0, y + 500, 50))
if point:
    controller.set_mouse_location(round(point.x), round(point.y))
if getattr(builtins, '_ols_facility_preview_empty', False):
    gun = pawn.get_editor_property('EquippedPistol')
    if gun and gun.get_editor_property('Ammo'):
        controller.set_mouse_location(30, 100)
        gun.call_method('Fire')
report = {'status':'ready', 'acceptance_test':False, 'preview_y':y,
          'player_location':str(pawn.get_actor_location()),
          'source':'Production map and HUD with runtime threats frozen; end PIE removes preview'}
(Path(unreal.Paths.project_saved_dir())/'FacilityPreview.json').write_text(json.dumps(report, indent=2))
