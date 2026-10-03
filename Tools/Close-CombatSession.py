"""End disposable QA and restore the editor preference changed for testing."""
import builtins
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    paths=['/Game/Enemies/BP_EnemyStraightRunner','/Game/Enemies/BP_EnemyRunnerFast',
           '/Game/Enemies/BP_EnemyRunnerSlow','/Game/Enemies/BP_EnemySniper',
           '/Game/Enemies/BP_EnemySpawnPoint','/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController',
           '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter','/Game/ThirdPerson/Blueprints/BP_AmmoHUD',
           '/Game/Weapons/Pistol/BP_Pistol','/Game/Weapons/Pistol/BP_PistolPickup',
           '/Game/Weapons/Pistol/BP_BulletProjectile']
    for path in paths:
        bp=unreal.load_asset(path)
        assert bp,path
        compile_blueprint(bp,True)
    controller=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    event=unreal.BlueprintGraphEditor.get_graph_editor_by_name(controller,'EventGraph')
    assert not any(any(p.name=='Command' and 'Tools/Editor-Queue.py' in p.value for p in i.input_pins) for i in BT.get_node_infos(list(event.list_all_nodes())))
    assert unreal.EditorAssetLibrary.save_loaded_asset(controller,False)
    material=unreal.load_asset('/Game/Enemies/Materials/M_AttackTelegraph')
    assert material and material.get_editor_property('blend_mode')==unreal.BlendMode.BLEND_TRANSLUCENT
    assert unreal.EditorAssetLibrary.save_loaded_asset(material,False)
    perf=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
    if hasattr(builtins,'_ols_old_background_throttle'):
        perf.set_editor_property('bThrottleCPUWhenNotForeground',builtins._ols_old_background_throttle)
        del builtins._ols_old_background_throttle
    queue=builtins.__dict__.pop('_ols_editor_queue',None)
    if queue:
        unreal.unregister_slate_post_tick_callback(queue['handle'])
    return {'compiled':paths,'shared_material_saved':material.get_path_name(),'bootstrap_absent':True,'pie_stopped':True,'background_preference_restored':True,'editor_queue_stopped':True}
run_editor(work,'CombatSessionClosed.json')
