"""Blast cover uses geometry, so the struck robot cannot shield its neighbours."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    enemy=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    capsule=unreal.get_default_object(enemy.generated_class()).get_component_by_class(unreal.CapsuleComponent)
    capsule.set_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA,unreal.CollisionResponseType.ECR_IGNORE)
    compile_blueprint(enemy,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(enemy,False)
    bp=unreal.load_asset('/Game/Weapons/Pistol/BP_BulletProjectile')
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'Detonate')
    damage=next(i.node for i in BT.get_node_infos(list(ed.list_all_nodes())) if i.type_id.endswith('|ApplyRadialDamage'))
    val(damage,'DamagePreventionChannel','ECC_Camera')
    compile_blueprint(bp,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    return {'saved':[enemy.get_path_name(),bp.get_path_name()],'blast_cover':'Camera channel: world geometry blocks, enemy capsules ignore'}
run_editor(work,'RPGActorShieldingFix.json')
