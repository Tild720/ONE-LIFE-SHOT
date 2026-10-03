"""Do not acquire a spawned drop before Die assigns its weapon role."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    bp=unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup')
    unreal.get_default_object(bp.generated_class()).set_editor_property('ReturnDuration',.55)
    graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
    infos=BT.get_node_infos(list(graph.list_all_nodes()))
    for info in infos:
        if info.type_id.endswith('|TryAcquire'):
            info.node.find_execute_pin().break_pin_links()
        if any(p.name=='FunctionName' and p.value=='TryAcquire' for p in info.input_pins):
            val(info.node,'Time',.08)
    compile_blueprint(bp,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    return {'saved':bp.get_path_name(),'return_duration':.55,'acquisition':'existing repeating timer, 80 ms; returning drops keep their existing arrival event'}
run_editor(work,'CloseDropAcquisitionFix.json')
