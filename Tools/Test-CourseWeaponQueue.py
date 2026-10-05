"""Run the existing weapon acceptance after entering the new start screen."""
import builtins,runpy
from pathlib import Path
import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
unreal.GameplayStatics.get_player_controller(world,0).call_method('GetHUD').call_method('StartGame')
builtins.__dict__.pop('_ols_weapon_queue_qa',None)
runpy.run_path(str(Path(__file__).with_name('Test-WeaponQueue.py')),run_name='__main__')
