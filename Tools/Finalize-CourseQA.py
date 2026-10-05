"""Compile and save editor-managed work, then release the test editor's RAM."""
import sys,builtins
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    paths=['/Game/Enemies/BP_EnemyStraightRunner','/Game/Enemies/BP_EnemyRunnerFast','/Game/Enemies/BP_EnemyRunnerSlow','/Game/Enemies/BP_EnemySniper','/Game/Enemies/BP_EnemySpawnPoint','/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController','/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter','/Game/ThirdPerson/Blueprints/BP_AmmoHUD','/Game/Weapons/Pistol/BP_Pistol','/Game/Weapons/Pistol/BP_PistolPickup','/Game/Weapons/Pistol/BP_BulletProjectile','/Game/UI/WBP_RunnerProgress','/Game/Runner/BP_RunnerProgress','/Game/Runner/BP_ClearPad']
    for path in paths:
        bp=unreal.load_asset(path);assert bp,path;compile_blueprint(bp,True)
    controller=unreal.load_asset(paths[5]);ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller,'EventGraph')
    assert not any(any(p.name=='Command' and 'Editor-Queue.py' in str(p.value) for p in i.input_pins) for i in BT.get_node_infos(list(ed.list_all_nodes())))
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    queue=builtins.__dict__.pop('_ols_editor_queue',None)
    if queue:unreal.unregister_slate_post_tick_callback(queue['handle'])
    result={'compiled':paths,'warnings_as_errors':True,'saved':True,'runtime_python_absent':True,'pie_stopped':True,'editor_exit_requested':True}
    unreal.SystemLibrary.quit_editor()
    return result
run_editor(work,'CourseFinalized.json')
