"""Read the production click, menu and firing paths without changing assets."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    graphs = {}
    owners = ('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter',
              '/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController',
              '/Game/ThirdPerson/Blueprints/BP_AmmoHUD', '/Game/Weapons/Pistol/BP_Pistol')
    for path in owners:
        bp = unreal.load_asset(path)
        for graph in unreal.BlueprintEditorLibrary.list_graphs(bp):
            ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
            graphs[path + ':' + graph.get_name()] = [
                {'node': i.node.get_name(), 'type': i.type_id,
                 'inputs': [(p.name, p.value, [x.get_owning_node().get_name() for x in i.node.find_input_pin(p.name).list_connected_pins()]) for p in i.input_pins],
                 'outputs': [(p.name, [x.get_owning_node().get_name() for x in i.node.find_output_pin(p.name).list_connected_pins()]) for p in i.output_pins]}
                for i in BT.get_node_infos(list(ed.list_all_nodes()))]
    action = unreal.load_asset('/Game/Input/Actions/IA_Fire')
    return {'graphs': graphs, 'fire_action': {
        'value_type': str(action.get_editor_property('value_type')),
        'triggers': [str(x) for x in action.get_editor_property('triggers')],
        'modifiers': [str(x) for x in action.get_editor_property('modifiers')]}}

run_editor(work, 'FireInputInspection.json')
