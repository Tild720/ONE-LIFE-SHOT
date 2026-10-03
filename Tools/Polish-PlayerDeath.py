"""Reuse the existing compatible robot death animation for visible player failure."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    bp = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter')
    anim = unreal.load_asset('/Game/Enemies/Animations/Rig_Medium_General_Death_A')
    assert anim
    ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp, 'EventGraph')
    infos = BT.get_node_infos(list(ed.list_all_nodes()))
    if not any(i.type_id.endswith('|PlayAnimation') for i in infos):
        stop = next(i.node for i in infos if i.type_id.endswith('|DisableMovement'))
        tick = call(ed, ACT+'SetActorTickEnabled', bEnabled='false')
        dodge = setv(ed, 'Dodging', 'false'); chain(tick, dodge)
        mesh = get(ed, 'Mesh')
        death = call(ed, '/Script/Engine.SkeletalMeshComponent.PlayAnimation',
                     NewAnimToPlay=anim.get_path_name(), bLooping='false')
        link(out(mesh, 'Mesh'), inp(death, 'self')); chain(dodge, death)
        insert_after(ed, stop, tick, death)
    compile_blueprint(bp, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp, False)
    return {'saved': bp.get_path_name(), 'death_animation': anim.get_path_name()}

run_editor(work, 'PlayerDeathPolish.json')
