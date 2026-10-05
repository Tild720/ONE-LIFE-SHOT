"""Extend inspected facility scenery through Editor APIs and reuse combat assets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import importlib, CombatAuthoring
importlib.reload(CombatAuthoring)
from CombatAuthoring import *
from editor_toolset.toolsets.actor import ActorTools as AT
HUD='/Game/ThirdPerson/Blueprints/BP_AmmoHUD'
SPAWN='/Game/Enemies/BP_EnemySpawnPoint'
PAD='/Game/Runner/BP_ClearPad'
END_Y=57750.0

def v(ed,name):return out(get(ed,name),name)
def binary(ed,fn,a,b):
    n=call(ed,MATH+fn)
    for key,pin in [('B',b),('A',a)]:
        if hasattr(pin,'is_valid'):link(pin,inp(n,key))
        else:link(out(call(ed,SYS+'MakeLiteralDouble',Value=pin)),inp(n,key))
    return out(n)

def neon_material():
    path='/Game/Runner/Materials/M_ClearNeon'
    material=unreal.load_asset(path)
    if not material:
        material=unreal.AssetToolsHelpers.get_asset_tools().create_asset('M_ClearNeon','/Game/Runner/Materials',unreal.Material,unreal.MaterialFactoryNew())
        material.set_editor_property('shading_model',unreal.MaterialShadingModel.MSM_UNLIT)
        expression=unreal.MaterialEditingLibrary.create_material_expression(material,unreal.MaterialExpressionConstant3Vector)
        expression.set_editor_property('constant',unreal.LinearColor(.02,5.0,3.0,1))
        assert unreal.MaterialEditingLibrary.connect_material_property(expression,'',unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        unreal.MaterialEditingLibrary.recompile_material(material)
        assert unreal.EditorAssetLibrary.save_loaded_asset(material,False)
    return material

def build_pad():
    bp=unreal.load_asset(PAD)
    if not bp:
        factory=unreal.BlueprintFactory();factory.set_editor_property('parent_class',unreal.Actor)
        bp=unreal.AssetToolsHelpers.get_asset_tools().create_asset('BP_ClearPad','/Game/Runner',unreal.Blueprint,factory)
    assert bp
    cube=unreal.load_asset('/Engine/BasicShapes/Cube');assert cube
    neon=neon_material()
    floor=unreal.load_asset('/Game/LevelPrototyping/KayKit/Materials/MI_FacilityTrim');assert floor
    components={c.get_name():c for c in AT.get_components(unreal.get_default_object(bp.generated_class()))}
    def mesh(name,location,scale,material,collision=False):
        component=components.get(name) or AT.add_component(bp,unreal.StaticMeshComponent.static_class(),name)
        component.set_editor_property('static_mesh',cube)
        component.set_editor_property('override_materials',[material])
        component.set_editor_property('relative_location',unreal.Vector(*location))
        component.set_editor_property('relative_scale3d',unreal.Vector(*scale))
        component.set_editor_property('cast_shadow',False)
        component.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
    mesh('PadBody',(0,0,6),(5.2,3.6,.12),floor,True)
    for name,loc,scale in [('NeonLeft',(-256,0,14),(.08,3.6,.04)),('NeonRight',(256,0,14),(.08,3.6,.04)),('NeonFront',(0,176,14),(5.2,.08,.04)),('NeonBack',(0,-176,14),(5.2,.08,.04)),('NeonCenter',(0,0,14),(1.1,.08,.04))]:mesh(name,loc,scale,neon)
    box=components.get('ClearTrigger') or AT.add_component(bp,unreal.BoxComponent.static_class(),'ClearTrigger')
    box.set_editor_property('relative_location',unreal.Vector(0,0,20))
    box.set_box_extent(unreal.Vector(250,170,8),False)
    box.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY)
    box.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
    box.set_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN,unreal.CollisionResponseType.ECR_OVERLAP)
    box.set_editor_property('generate_overlap_events',True)
    compile_blueprint(bp,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
    event=BT.add_event(bp,'ReceiveActorBeginOverlap');event.find_then_pin().break_pin_links()
    compare=call(ed,MATH+'EqualEqual_ObjectObject')
    link(out(event,'OtherActor'),inp(compare,'A'));link(out(call(ed,GAME+'GetPlayerPawn',PlayerIndex=0)),inp(compare,'B'))
    guard=branch(ed,out(compare));chain(event,guard)
    pc=call(ed,GAME+'GetPlayerController',PlayerIndex=0)
    hud=call(ed,'/Script/Engine.PlayerController.GetHUD');link(out(pc),inp(hud,'self'))
    cast=ed.create_node_from_name('Utilities|Casting|CastToBP_AmmoHUD',unreal.Vector2D(),[]);assert cast
    link(out(hud),inp(cast,'Object'));chain(guard,cast)
    output=next(p.name for p in BT.get_node_infos([cast])[0].output_pins if p.name.startswith('As'))
    clear=call(ed,unreal.load_asset(HUD).generated_class().get_path_name()+':ClearGame');link(out(cast,output),inp(clear,'self'));chain(cast,clear)
    compile_blueprint(bp,True);assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    return bp

def tune_combat():
    spawn=unreal.load_asset(SPAWN);assert spawn
    var(spawn,'SpawnAheadDistance','float',1600.0,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(spawn,'SpawnNext')
    node=next(i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if isinstance(i.node,unreal.K2Node_SpawnActorFromClass))
    # Preserve the point's lateral lane and floor height; spawn ahead of the
    # current player along the actual StartPoint -> EndPoint direction.
    pawn=out(call(ed,GAME+'GetPlayerPawn',PlayerIndex=0))
    playerloc=call(ed,ACT+'K2_GetActorLocation');link(pawn,inp(playerloc,'self'))
    ownloc=out(call(ed,ACT+'K2_GetActorLocation'))
    manager=unreal.load_asset('/Game/Runner/BP_RunnerProgress')
    points=[]
    for name in ['StartPoint','EndPoint']:
        point=get(ed,name,manager.generated_class().get_path_name());link(v(ed,'ProgressManager'),inp(point,'self'))
        location=call(ed,ACT+'K2_GetActorLocation');link(out(point,name),inp(location,'self'));points.append(out(location))
    direction=call(ed,MATH+'Vector_Normal2D');link(binary(ed,'Subtract_VectorVector',points[1],points[0]),inp(direction,'A'))
    own_delta=binary(ed,'Subtract_VectorVector',ownloc,out(playerloc))
    longitudinal=binary(ed,'Dot_VectorVector',own_delta,out(direction))
    along=binary(ed,'Multiply_VectorFloat',out(direction),binary(ed,'Subtract_DoubleDouble',longitudinal,v(ed,'SpawnAheadDistance')))
    rear=binary(ed,'Subtract_VectorVector',ownloc,along)
    transform=call(ed,MATH+'MakeTransform',Rotation='0, 0, 0',Scale='1, 1, 1');link(rear,inp(transform,'Location'))
    inp(node,'SpawnTransform').break_pin_links();link(out(transform),inp(node,'SpawnTransform'))
    compile_blueprint(spawn,True);assert unreal.EditorAssetLibrary.save_loaded_asset(spawn,False)
    char=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
    arm=next(c for c in AT.get_components(unreal.get_default_object(char.generated_class())) if isinstance(c,unreal.SpringArmComponent))
    arm.set_editor_property('target_arm_length',1400/1.5)
    arm.set_editor_property('target_offset',unreal.Vector(0,220/1.5,0))
    compile_blueprint(char,True);assert unreal.EditorAssetLibrary.save_loaded_asset(char,False)
    gun=unreal.load_asset('/Game/Weapons/Pistol/BP_Pistol');assert gun
    unreal.get_default_object(gun.generated_class()).set_editor_property('FireShakeScale',1.8)
    compile_blueprint(gun,True);assert unreal.EditorAssetLibrary.save_loaded_asset(gun,False)
    return {'camera_arm':1400/1.5,'shake_scale':1.8,'spawn_ahead_cm':1600}

def extend_map(pad):
    subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors=list(subsystem.get_all_level_actors());labels={a.get_actor_label():a for a in actors}
    assert all(k in labels for k in ['Runner_StartPoint','Runner_EndPoint','Runner_ProgressManager'])
    extension=labels.get('Facility_Extension')
    if not extension:
        extension=subsystem.spawn_actor_from_class(unreal.Actor,unreal.Vector())
        extension.set_actor_label('Facility_Extension');extension.set_folder_path('Facility/Extension')
        extension.set_editor_property('is_spatially_loaded',False)
    groups={};instances=0
    if not extension.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
        for source in actors:
            label=source.get_actor_label()
            if not isinstance(source,unreal.StaticMeshActor) or not label.startswith('Facility_') or label=='Facility_ExitRail' or label.startswith(('Facility_ExitBackdrop_','Facility_Wall_Back_')):continue
            component=source.static_mesh_component;mesh=component.static_mesh
            if not mesh:continue
            materials=[component.get_material(i) for i in range(component.get_num_materials())]
            key=(mesh.get_path_name(),tuple(m.get_path_name() if m else '' for m in materials),str(component.get_collision_enabled()),str(component.get_collision_profile_name()))
            if key not in groups:
                instance=AT.add_component(extension,unreal.HierarchicalInstancedStaticMeshComponent.static_class(),'Scenery_%02d'%len(groups))
                instance.set_editor_property('static_mesh',mesh);instance.set_editor_property('override_materials',materials)
                instance.set_collision_profile_name(component.get_collision_profile_name())
                instance.set_collision_enabled(component.get_collision_enabled())
                instance.set_editor_property('cast_shadow',False)
                instance.set_editor_property('mobility',unreal.ComponentMobility.STATIC)
                instance.set_cull_distances(2600,4200)
                groups[key]=instance
            origin,extent=source.get_actor_bounds(False)
            for section in range(1,13):
                offset=4800*section
                if origin.y+extent.y+offset>END_Y+450:continue
                transform=component.get_world_transform()
                pos=transform.translation;pos.y+=offset;transform.translation=pos
                assert groups[key].add_instance(transform,True)>=0
                instances+=1
    end=labels['Runner_EndPoint'];end.modify();end.root_component.modify();end.set_actor_location(unreal.Vector(0,END_Y,50),False,True)
    # Move the inspected decorative backdrop beyond the new exit, once.
    for actor in actors:
        if actor.get_actor_label().startswith('Facility_ExitBackdrop_') and actor.get_actor_location().y<10000:
            actor.modify();actor.root_component.modify()
            location=actor.get_actor_location();location.y+=END_Y-3850;actor.set_actor_location(location,False,True)
    spawner_cls=unreal.load_asset(SPAWN).generated_class()
    originals=[a for a in actors if a.get_class()==spawner_cls and not a.get_actor_label().startswith('Facility_LongSpawn_')]
    fields=['EarlyEnemyPool','MiddleEnemyPool','LateEnemyPool','FinalEnemyPool','EarlyInterval','MiddleInterval','LateInterval','FinalInterval','SpawnDelay','SpawnActivationDistance','MaxAliveEnemies','EnemyLifetime','Enabled','UseSpawnSpeedOverride']
    placed=0
    for template in originals:
        template.set_editor_property('SpawnAheadDistance',1600)
        template.set_editor_property('MaxAliveEnemies',2)
        template.set_editor_property('EnemyLifetime',35.0)
        for section in range(1,13):
            pos=template.get_actor_location();pos.y+=4800*section
            if pos.y>END_Y-650:continue
            label='Facility_LongSpawn_%02d_%s'%(section,template.get_actor_label())
            if label in labels:continue
            actor=subsystem.spawn_actor_from_class(spawner_cls,pos)
            actor.set_actor_label(label);actor.set_folder_path('Facility/Extension/Encounters')
            actor.set_editor_property('is_spatially_loaded',False)
            for field in fields:actor.set_editor_property(field,template.get_editor_property(field))
            actor.set_editor_property('ProgressManager',labels['Runner_ProgressManager'])
            actor.set_editor_property('SpawnAheadDistance',1600)
            placed+=1
    pads=[a for a in actors if a.get_class()==pad.generated_class()]
    assert len(pads)<=1
    finish=pads[0] if pads else subsystem.spawn_actor_from_class(pad.generated_class(),unreal.Vector(0,END_Y,50))
    finish.set_actor_label('Runner_ClearPad');finish.set_folder_path('Runner')
    finish.set_editor_property('is_spatially_loaded',False)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    return {'end_y':END_Y,'original_length':3850,'length_multiplier':15,'new_mesh_instances':instances,'mesh_groups':len(groups),'new_spawners':placed,'finish':finish.get_path_name()}

def extend_entry():
    descs=unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    if isinstance(descs,tuple):descs=next(value for value in descs if isinstance(value,(list,unreal.Array)))
    unreal.WorldPartitionBlueprintLibrary.load_actors([desc.guid for desc in descs if str(desc.label)=='Facility_ExitRail'])
    for desc in descs:
        if str(desc.label)=='Facility_ExitRail':unreal.load_object(None,str(desc.actor_path))
    subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    actors=list(subsystem.get_all_level_actors());labels={a.get_actor_label():a for a in actors}
    rail=labels.get('Facility_ExitRail')
    if rail:
        assert subsystem.destroy_actor(rail)
    end=labels['Runner_EndPoint'];end.modify();end.root_component.modify()
    end.set_actor_location(unreal.Vector(0,END_Y,50),False,True)
    for actor in actors:
        label=actor.get_actor_label()
        if (label.startswith('Facility_ExitBackdrop_') or label=='Facility_ExitText') and actor.get_actor_location().y<10000:
            actor.modify();actor.root_component.modify()
            position=actor.get_actor_location();position.y+=END_Y-3850
            actor.set_actor_location(position,False,True)
    # Remove old end barriers from already authored instancing groups. They
    # belong only beyond the final pad, never at repeated bay connections.
    extension=labels['Facility_Extension'];extension.modify();removed=0
    for component in extension.get_components_by_class(unreal.HierarchicalInstancedStaticMeshComponent):
        if component.static_mesh!=unreal.load_asset('/Engine/BasicShapes/Cube'):continue
        component.modify()
        for index in range(component.get_instance_count()-1,-1,-1):
            transform=component.get_instance_transform(index,True)
            scale=transform.scale3d;pos=transform.translation
            if abs(pos.x)<.1 and abs(scale.x-12.6)<.01 and abs(scale.y-.4)<.01 and abs((pos.y-4180)/4800-round((pos.y-4180)/4800))<.001:
                assert component.remove_instance(index);removed+=1
    removed_entry=[]
    for source in actors:
        label=source.get_actor_label()
        if not isinstance(source,unreal.StaticMeshActor):continue
        if label.startswith('Facility_Wall_Back_') and source.get_actor_location().y<-1000:
            source.modify();source.root_component.modify()
            pos=source.get_actor_location();pos.y+=800;source.set_actor_location(pos,False,True)
        if label.startswith('Facility_Entry_'):
            assert subsystem.destroy_actor(source);removed_entry.append(label)
    assert unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
    assert unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True)
    return {'temporary_rear_entry_removed':removed_entry,'internal_exit_rails_removed':removed,'original_exit_rail_removed':bool(rail),'end_y':END_Y}

def work():
    pad=build_pad();tuning=tune_combat();level=extend_map(pad)
    entry=extend_entry()
    return {'tuning':tuning,'level':level,'entry':entry,'saved_assets':[PAD,HUD,SPAWN,'/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter','/Game/Weapons/Pistol/BP_Pistol','/Game/Runner/Materials/M_ClearNeon']}

if __name__=='__main__':run_editor(work,'CourseExtended.json')
