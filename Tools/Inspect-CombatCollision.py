import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    result={}
    subsystem=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for path in ['/Game/Weapons/Pistol/BP_PistolPickup','/Game/Weapons/Pistol/BP_BulletProjectile','/Game/Enemies/BP_EnemyStraightRunner']:
        bp=unreal.load_asset(path)
        actor=subsystem.spawn_actor_from_class(bp.generated_class(),unreal.Vector(20000,20000,150))
        result[path]=[{'name':c.get_name(),'enabled':str(c.get_collision_enabled()),'type':str(c.get_collision_object_type()),'bullet':str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_BULLET)),'visibility':str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY))} for c in actor.get_components_by_class(unreal.PrimitiveComponent)]
        subsystem.destroy_actor(actor)
    return result
run_editor(work,'CombatCollisionInspection.json')
