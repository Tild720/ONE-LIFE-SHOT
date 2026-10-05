"""Inspect actual editor assets and graphs, then restore the requested return time."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    result={'animations':{},'graphs':{}}
    registry=unreal.AssetRegistryHelpers.get_asset_registry()
    result['assets']=[str(a.package_name) for root in ['/Game/Enemies','/Game/Characters/KayKit/Anims'] for a in registry.get_assets_by_path(root,True)]
    bp=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    cdo=unreal.get_default_object(bp.generated_class())
    mesh=cdo.get_editor_property('Mesh')
    result['mesh']=str(mesh.get_editor_property('skeletal_mesh_asset'))
    for name in ['A_Dummy_Idle','A_Dummy_Walk','A_Dummy_Run']:
        a=unreal.load_asset('/Game/Characters/KayKit/Anims/'+name)
        assert a
        result['animations'][name]={'path':a.get_path_name(),'skeleton':str(a.get_editor_property('skeleton'))}
    for name in ['EventGraph','ConfigureEnemyAppearance','HideTelegraph','ShowAttackLine','ShowBlastZone','AssaultPulse','HeavyPulse','SniperPulse','EnemyRolePulse','Die']:
        graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,name)
        result['graphs'][name]=[{'name':i.node.get_name(),'type':i.type_id,
            'in':[{'name':p.name,'value':p.value,'links':[str(x.node.get_name())+':'+str(x.index_id) for x in p.connected_pins]} for p in i.input_pins],
            'out':[{'name':p.name,'links':[str(x.node.get_name())+':'+str(x.index_id) for x in p.connected_pins]} for p in i.output_pins]} for i in BT.get_node_infos(list(graph.list_all_nodes()))]
    pickup=unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup')
    unreal.get_default_object(pickup.generated_class()).set_editor_property('ReturnDuration',.55)
    compile_blueprint(pickup,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(pickup,False)
    result['return_duration']=.55
    return result
run_editor(work,'EnemyPresentationInspection.json')
