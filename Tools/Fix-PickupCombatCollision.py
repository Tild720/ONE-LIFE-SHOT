"""Pickup detection must not stop pellets, penetration, or blast visibility."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    bp=unreal.load_asset('/Game/Weapons/Pistol/BP_PistolPickup')
    component=unreal.load_object(None,bp.generated_class().get_path_name()+':PickupRange_GEN_VARIABLE')
    assert component
    component.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_IGNORE)
    component.set_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN,unreal.CollisionResponseType.ECR_OVERLAP)
    compile_blueprint(bp,True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp,False)
    return {'saved':bp.get_path_name(),'pickup_collision':'Pawn overlap only; bullets and visibility ignore'}
run_editor(work,'PickupCombatCollisionFix.json')
