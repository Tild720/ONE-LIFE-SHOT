"""Keep gameplay shots on a stable height despite hand animation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    gun=unreal.load_asset('/Game/Weapons/Pistol/BP_Pistol')
    var(gun,'ShotHeightOffset','float',0.0,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(gun,'Fire')
    infos=BT.get_node_infos(list(ed.list_all_nodes()))
    if not any(i.type_id.endswith('|GetShotHeightOffset') for i in infos):
        nodes={n.get_name():n for n in ed.list_all_nodes()}
        muzzle=call(ed,MATH+'BreakVector')
        link(out(nodes['K2Node_CallFunction_9']),inp(muzzle,'InVec'))
        owner=call(ed,ACT+'GetOwner')
        position=call(ed,ACT+'K2_GetActorLocation')
        link(out(owner),inp(position,'self'))
        axes=call(ed,MATH+'BreakVector')
        link(out(position),inp(axes,'InVec'))
        height=call(ed,MATH+'Add_DoubleDouble')
        link(out(axes,'Z'),inp(height,'A'))
        link(out(get(ed,'ShotHeightOffset'),'ShotHeightOffset'),inp(height,'B'))
        shot=call(ed,MATH+'MakeVector')
        for name in ['X','Y']:
            link(out(muzzle,name),inp(shot,name))
        link(out(height),inp(shot,'Z'))
        transform=nodes['K2Node_CallFunction_11']
        inp(transform,'Location').break_pin_links()
        link(out(shot),inp(transform,'Location'))
        origin=next(i.node for i in infos if i.type_id.endswith('|SetShotOrigin'))
        inp(origin,'ShotOrigin').break_pin_links()
        link(out(shot),inp(origin,'ShotOrigin'))
    compile_blueprint(gun,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(gun,'Fire')
    nodes={n.get_name():n for n in ed.list_all_nodes()}
    infos=BT.get_node_infos(list(ed.list_all_nodes()))
    if not any(i.type_id.endswith('|MakeRotator') for i in infos):
        owner=call(ed,ACT+'GetOwner')
        position=call(ed,ACT+'K2_GetActorLocation')
        link(out(owner),inp(position,'self'))
        look=call(ed,MATH+'FindLookAtRotation')
        link(out(position),inp(look,'Start'))
        for p in inp(nodes['K2Node_CallFunction_10'],'Target').list_connected_pins():
            link(p,inp(look,'Target'))
        angles=call(ed,MATH+'BreakRotator')
        link(out(look),inp(angles,'InRot'))
        flat=call(ed,MATH+'MakeRotator',Pitch=0,Roll=0)
        link(out(angles,'Yaw'),inp(flat,'Yaw'))
        for target in [inp(nodes['K2Node_CallFunction_11'],'Rotation'),
                       inp(next(i.node for i in infos if i.type_id.endswith('|SetShotRotation')),'ShotRotation')]:
            target.break_pin_links()
            link(out(flat),target)
    template=unreal.load_object(None,gun.generated_class().get_path_name()+':WeaponMesh_GEN_VARIABLE')
    assert template
    template.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    compile_blueprint(gun,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(gun,False)
    changed=[gun.get_path_name()]
    for path,graph_name in [('/Game/Enemies/BP_EnemyStraightRunner','ConfigureEnemyAppearance'),
                           ('/Game/Weapons/Pistol/BP_PistolPickup','ConfigurePickup'),
                           ('/Game/Weapons/Pistol/BP_Pistol','ConfigureRocketTube')]:
        bp=unreal.load_asset(path)
        component_name='PickupMesh' if path.endswith('BP_PistolPickup') else 'WeaponMesh'
        component=unreal.load_object(None,bp.generated_class().get_path_name()+':'+component_name+'_GEN_VARIABLE')
        assert component,component_name
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
        graph=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,graph_name)
        rotates=[i.node for i in BT.get_node_infos(list(graph.list_all_nodes())) if any(p.name=='NewRotation' for p in i.input_pins)]
        assert rotates,graph_name
        val(rotates[-1],'NewRotation','0, 0, 90')
        compile_blueprint(bp,True)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
        changed.append(bp.get_path_name())
    return {'saved':changed,'shot_height':'Owner Z + editable ShotHeightOffset','rpg_tube_rotation':'roll 90'}
run_editor(work,'CombatShotPlaneFix.json')
