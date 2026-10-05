"""Read-only editor inventory before extending the existing course."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *
from editor_toolset.toolsets.actor import ActorTools as AT

def work():
    descs=unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    if isinstance(descs,tuple):descs=next(value for value in descs if isinstance(value,(list,unreal.Array)))
    unreal.WorldPartitionBlueprintLibrary.load_actors([desc.guid for desc in descs if str(desc.label)=='Facility_ExitRail'])
    rail_objects=[unreal.load_object(None,str(d.actor_path)) for d in descs if str(d.label)=='Facility_ExitRail']
    result = {'descs':[{'label':str(d.label),'path':str(d.actor_path),'bounds':str(d.bounds)} for d in descs if 'rail' in str(d.label).lower()], 'assets': list(unreal.EditorAssetLibrary.list_assets('/Game/Runner', True, False)), 'actors': [], 'blueprints': {}}
    result['rail_objects']=[{'object':str(a),'label':a.get_actor_label() if a else None,'location':str(a.get_actor_location()) if a else None,'valid':unreal.SystemLibrary.is_valid(a)} for a in rail_objects]
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        mesh = actor.get_component_by_class(unreal.StaticMeshComponent)
        result['actors'].append({'label': actor.get_actor_label(), 'class': actor.get_class().get_path_name(), 'location': str(actor.get_actor_location()), 'bounds': str(actor.get_actor_bounds(False)), 'mesh': str(mesh.static_mesh) if mesh else None, 'collision': str(mesh.get_collision_enabled()) if mesh else None})
    result['barriers'] = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        for component in actor.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
            for index in range(component.get_instance_count()):
                transform = component.get_instance_transform(index, True)
                if abs(transform.translation.y-4200)<100 or abs(transform.translation.y-8980)<100:
                    result['barriers'].append({'actor':actor.get_actor_label(),'component':component.get_name(),'index':index,'mesh':str(component.static_mesh),'transform':str(transform)})
    for path in ['/Game/Weapons/Pistol/BP_Pistol', '/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController', '/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter']:
        bp = unreal.load_asset(path)
        item = {'defaults': {str(n): str(unreal.get_default_object(bp.generated_class()).get_editor_property(str(n))) for n in unreal.BlueprintEditorLibrary.list_member_variable_names(bp,False)}, 'components': [], 'graphs': {}}
        for component in AT.get_components(unreal.get_default_object(bp.generated_class())):
            c = {'name':component.get_name(),'path':component.get_path_name(),'class':component.get_class().get_path_name()}
            for prop in ['ortho_width','projection_mode','target_arm_length','relative_location','relative_rotation','shake_duration','rot_oscillation','loc_oscillation']:
                try:c[prop]=str(component.get_editor_property(prop))
                except Exception:pass
            item['components'].append(c)
        for graph in unreal.BlueprintEditorLibrary.list_graphs(bp):
            ed=unreal.BlueprintGraphEditor.get_graph_editor(graph)
            item['graphs'][graph.get_name()]=[{'name':i.node.get_name(),'type':i.type_id,'inputs':{p.name:str(p.value) for p in i.input_pins}} for i in BT.get_node_infos(list(ed.list_all_nodes()))]
        result['blueprints'][path]=item
    return result

run_editor(work,'CourseExpansionInspection.json')
