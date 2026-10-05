"""Position the real PIE cursor over the first Canvas menu button for QA."""
import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
controller=unreal.GameplayStatics.get_player_controller(world,0);hud=controller.call_method('GetHUD')
controller.set_mouse_location(round(hud.get_editor_property('MenuWidth')*.5),round(hud.get_editor_property('MenuHeight')*.59))
