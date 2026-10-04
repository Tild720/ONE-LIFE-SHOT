"""Remove the temporary editor launcher, leaving the live editor queue intact."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    bp=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
    nodes=[i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if any(p.name=='Command' and 'Tools/Editor-Queue.py' in str(p.value) for p in i.input_pins)]
    for n in nodes:
        incoming=list(n.find_execute_pin().list_connected_pins())
        outgoing=list(n.find_then_pin().list_connected_pins())
        n.find_execute_pin().break_pin_links()
        n.find_then_pin().break_pin_links()
        for source in incoming:
            for target in outgoing:link(source,target)
    ed.remove_nodes(nodes)
    compile_blueprint(bp,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    return {'removed':len(nodes),'saved':True,'queue_remains_live':True}
run_editor(work,'BootstrapRemoved.json')
