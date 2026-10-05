"""Read current editor-managed assets before encounter/VFX changes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    registry=unreal.AssetRegistryHelpers.get_asset_registry()
    result={'assets':[{'path':str(a.package_name),'class':str(a.asset_class_path)} for a in registry.get_assets_by_path('/Game',True)],'blueprints':{},'actors':[]}
    for path in ['/Game/Enemies/BP_EnemySpawnPoint','/Game/Runner/BP_RunnerProgress','/Game/Enemies/BP_EnemyStraightRunner','/Game/Weapons/Pistol/BP_BulletProjectile','/Game/Weapons/Pistol/BP_PistolImpactBits']:
        bp=unreal.load_asset(path);assert bp,path
        data={'graphs':{},'defaults':{str(n):str(unreal.get_default_object(bp.generated_class()).get_editor_property(str(n))) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp,False)}}
        for graph in unreal.BlueprintEditorLibrary.list_graphs(bp):
            ed=unreal.BlueprintGraphEditor.get_graph_editor(graph)
            data['graphs'][graph.get_name()]=[{'name':i.node.get_name(),'type':i.type_id,
                'in':[{'name':p.name,'value':p.value,'links':[str(x.node.get_name())+':'+str(x.index_id) for x in p.connected_pins]} for p in i.input_pins],
                'out':[{'name':p.name,'links':[str(x.node.get_name())+':'+str(x.index_id) for x in p.connected_pins]} for p in i.output_pins]} for i in BT.get_node_infos(list(ed.list_all_nodes()))]
        data['components']=[{'name':c.get_name(),'class':c.get_class().get_path_name()} for c in unreal.get_default_object(bp.generated_class()).get_components_by_class(unreal.ActorComponent)]
        result['blueprints'][path]=data
    for a in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        row={'label':a.get_actor_label(),'class':a.get_class().get_path_name(),'location':str(a.get_actor_location())}
        if 'BP_EnemySpawnPoint' in row['class'] or 'BP_RunnerProgress' in row['class']:
            props=unreal.BlueprintEditorLibrary.list_member_variable_names(unreal.load_asset(row['class'].split('.')[0]),False)
            row['properties']={str(p):str(a.get_editor_property(str(p))) for p in props}
        result['actors'].append(row)
    assert unreal.load_asset('/Engine/BasicShapes/Plane')
    return result
run_editor(work,'PolishTargetsInspection.json')
