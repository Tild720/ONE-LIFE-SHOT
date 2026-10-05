"""Read-only native Blueprint inventory for the two-slot request."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    paths = ['/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter',
             '/Game/Weapons/Pistol/BP_Pistol', '/Game/Weapons/Pistol/BP_PistolPickup',
             '/Game/ThirdPerson/Blueprints/BP_AmmoHUD']
    report = {}
    for path in paths:
        bp = unreal.load_asset(path)
        assert bp, path
        names = [str(n) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp, False)]
        graphs = {}
        for graph in unreal.BlueprintEditorLibrary.list_graphs(bp):
            name = graph.get_name()
            if name not in ['EquipPistol', 'UpdateAmmoHUD', 'Fire', 'TryAcquire', 'FailRun',
                            'EventGraph', 'ConfigureWeapon', 'AttachToPlayer']:
                continue
            ed = unreal.BlueprintGraphEditor.get_graph_editor(graph)
            graphs[name] = [{'node': i.node.get_name(), 'type': i.type_id,
                            'inputs': [{'name': p.name, 'value': str(p.value),
                                        'links': [c.node.get_name() for c in p.connected_pins]}
                                       for p in i.input_pins],
                            'outputs': [{'name': p.name, 'links': [c.node.get_name() for c in p.connected_pins]}
                                        for p in i.output_pins]}
                           for i in BT.get_node_infos(list(ed.list_all_nodes()))]
        report[path] = {'variables': names, 'graphs': graphs}
    return report

run_editor(work, 'WeaponInventoryInspection.json')
