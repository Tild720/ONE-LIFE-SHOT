import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    bp=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    cdo=unreal.get_default_object(bp.generated_class())
    capsule=cdo.get_component_by_class(unreal.CapsuleComponent)
    assert capsule
    previous=str(capsule.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY))
    capsule.set_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY,unreal.CollisionResponseType.ECR_BLOCK)
    compile_blueprint(bp,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'Die')
    gun=unreal.load_asset('/Game/Weapons/Pistol/BP_Pistol')
    graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(gun,'ResolveSniper')
    channels=[[(p.name,p.value) for p in i.input_pins if p.name=='TraceChannel'] for i in BT.get_node_infos(list(graph.list_all_nodes())) if any(p.name=='TraceChannel' for p in i.input_pins)]
    return {'saved':bp.get_path_name(),'previous_visibility':previous,'sniper_trace_channel':channels}
run_editor(work,'SniperHitboxFix.json')
