"""Read-only native editor inventory for the requested map rebuilding pass."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def vector(v):return [v.x,v.y,v.z]
def work():
    registry=unreal.AssetRegistryHelpers.get_asset_registry()
    assets=registry.get_assets_by_path('/Game',True)
    result={'assets':[],'actors':[],'materials':{}}
    for data in assets:
        path=str(data.package_name); cls=str(data.asset_class_path.asset_name)
        if '__External' in path:continue
        row={'path':path,'class':cls}
        if cls=='StaticMesh':
            mesh=data.get_asset()
            bounds=mesh.get_bounds()
            row.update({'bounds_origin':vector(bounds.origin),'bounds_extent':vector(bounds.box_extent),'materials':[str(s.material_interface.get_path_name()) if s.material_interface else None for s in mesh.get_editor_property('static_materials')]})
        result['assets'].append(row)
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        row={'label':actor.get_actor_label(),'class':actor.get_class().get_path_name(),'location':vector(actor.get_actor_location()),'rotation':str(actor.get_actor_rotation()),'scale':vector(actor.get_actor_scale3d()),'hidden':str(actor.get_editor_property('hidden')),'collision':actor.get_actor_enable_collision()}
        mesh=actor.get_component_by_class(unreal.StaticMeshComponent)
        if mesh:
            asset=mesh.get_editor_property('static_mesh')
            row['mesh']=asset.get_path_name() if asset else None
            row['materials']=[m.get_path_name() if m else None for m in mesh.get_materials()]
        if isinstance(actor,(unreal.DirectionalLight,unreal.SkyLight)):
            for property_name in ['intensity','light_color']:
                try:row[property_name]=str(actor.get_editor_property('light_component').get_editor_property(property_name))
                except Exception:pass
        result['actors'].append(row)
    for path in ['/Game/Characters/KayKit/Materials/M_Dummy','/Game/LevelPrototyping/Materials/M_FlatCol']:
        material=unreal.load_asset(path); assert material,path
        library=unreal.MaterialEditingLibrary
        result['materials'][path]={'scalar_params':[str(x) for x in library.get_scalar_parameter_names(material)],'vector_params':[str(x) for x in library.get_vector_parameter_names(material)],'texture_params':[str(x) for x in library.get_texture_parameter_names(material)]}
    return result

run_editor(work,'FacilityInventory.json')
