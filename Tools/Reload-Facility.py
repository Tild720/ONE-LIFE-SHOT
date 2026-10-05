"""Unload the current level and reload its saved map and external actors."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import run_editor,unreal
def work():
    dirty=list(unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages())+list(unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    assert not dirty,[p.get_path_name() for p in dirty]
    world=unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
    assert world
    blank_name=world.get_path_name()
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('/Game/ThirdPerson/Lvl_ThirdPerson')
    loaded=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    return {'blank_world':blank_name,'loaded_world':loaded.get_path_name(),'saved_packages_reloaded':True}
run_editor(work,'FacilityReload.json')
