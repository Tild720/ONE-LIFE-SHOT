"""Ask Unreal to render a screenshot of the live PIE viewport with its HUD."""
import builtins
from pathlib import Path
import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
assert world
controller=unreal.GameplayStatics.get_player_controller(world,0)
name=getattr(builtins,'_ols_frame_name','FacilityFrame')
assert name.replace('_','').isalnum()
path=Path(unreal.Paths.project_saved_dir())/(name+'.png')
unreal.SystemLibrary.execute_console_command(world,'Shot SHOWUI filename="'+str(path)+'" -nosuffix',controller)
