import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    gun=unreal.load_asset('/Game/Weapons/Pistol/BP_Pistol')
    var(gun,'ShotStartDistance','float',60.0,True)
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(gun,'Fire')
    infos=BT.get_node_infos(list(ed.list_all_nodes()))
    if not any(i.type_id.endswith('|GetShotStartDistance') for i in infos):
        origin=next(i.node for i in infos if i.type_id.endswith('|SetShotOrigin'))
        originpin=list(inp(origin,'ShotOrigin').list_connected_pins())[0]
        maker=originpin.get_owning_node()
        owner=call(ed,ACT+'GetOwner')
        location=call(ed,ACT+'K2_GetActorLocation')
        link(out(owner),inp(location,'self'))
        trans=next(n for n in ed.list_all_nodes() if n.get_name()=='K2Node_CallFunction_11')
        forward=call(ed,MATH+'GetForwardVector')
        link(list(inp(trans,'Rotation').list_connected_pins())[0],inp(forward,'InRot'))
        distance=call(ed,MATH+'Multiply_VectorFloat')
        link(out(forward),inp(distance,'A'))
        link(out(get(ed,'ShotStartDistance'),'ShotStartDistance'),inp(distance,'B'))
        start=call(ed,MATH+'Add_VectorVector')
        link(out(location),inp(start,'A'))
        link(out(distance),inp(start,'B'))
        axes=call(ed,MATH+'BreakVector')
        link(out(start),inp(axes,'InVec'))
        for name in ['X','Y']:
            inp(maker,name).break_pin_links()
            link(out(axes,name),inp(maker,name))
    compile_blueprint(gun,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(gun,False)
    bullet=unreal.load_asset('/Game/Weapons/Pistol/BP_BulletProjectile')
    collision=unreal.load_object(None,bullet.generated_class().get_path_name()+':Collision_GEN_VARIABLE')
    assert collision
    object_type=collision.get_collision_object_type()
    collision.set_collision_response_to_channel(unreal.CollisionChannel.ECC_BULLET,unreal.CollisionResponseType.ECR_IGNORE)
    compile_blueprint(bullet,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bullet,False)
    return {'saved':[gun.get_path_name(),bullet.get_path_name()],'bullet_object_type':str(object_type),'pellets_ignore_bullet_channel':True}
run_editor(work,'CombatAimPelletFix.json')
