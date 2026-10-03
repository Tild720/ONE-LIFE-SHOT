import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    bp=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'ConfigureEnemyAppearance')
    rotations=[{'node':i.node.get_name(),'pins':[(p.name,p.value) for p in i.input_pins]} for i in BT.get_node_infos(list(ed.list_all_nodes())) if any(p.name=='NewRotation' for p in i.input_pins)]
    actor=unreal.get_editor_subsystem(unreal.EditorActorSubsystem).spawn_actor_from_class(bp.generated_class(),unreal.Vector(20000,20000,150))
    components=[{'name':c.get_name(),'class':c.get_class().get_name(),'pos':str(c.get_world_location()),'bounds':str(c.get_local_bounds()) if isinstance(c,unreal.StaticMeshComponent) else '', 'collision':str(c.get_collision_enabled()) if isinstance(c,unreal.PrimitiveComponent) else ''} for c in actor.get_components_by_class(unreal.SceneComponent)]
    bounds=str(actor.get_actor_bounds(True))
    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)
    return {'rotations':rotations,'enemy_components':components,'enemy_bounds':bounds}
run_editor(work,'FinalCombatInspection.json')
