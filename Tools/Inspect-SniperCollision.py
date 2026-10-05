"""Read-only diagnosis of live and default enemy query collision."""
import json
from pathlib import Path
import unreal
report={'defaults':{},'runtime':[]}
paths=['/Game/Enemies/BP_EnemyStraightRunner','/Game/Enemies/BP_EnemyRunnerFast','/Game/Enemies/BP_EnemyRunnerSlow','/Game/Enemies/BP_EnemySniper']
def components(actor):
    result=[]
    for c in actor.get_components_by_class(unreal.PrimitiveComponent):
        result.append({'name':c.get_name(),'class':c.get_class().get_name(),'enabled':str(c.get_collision_enabled()),'profile':str(c.get_collision_profile_name()),'visibility':str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_VISIBILITY)),'camera':str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_CAMERA)),'bullet':str(c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_BULLET)),'location':str(c.get_world_location()),'scale':str(c.get_world_scale())})
    return result
for p in paths:
    bp=unreal.load_asset(p)
    report['defaults'][p]=components(unreal.get_default_object(bp.generated_class()))
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world:
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.load_asset(paths[0]).generated_class()):
        report['runtime'].append({'actor':actor.get_path_name(),'dead':actor.get_editor_property('Dead'),'kind':actor.get_editor_property('WeaponKind'),'components':components(actor)})
(Path(unreal.Paths.project_saved_dir())/'SniperCollisionInspection.json').write_text(json.dumps(report,indent=2))
