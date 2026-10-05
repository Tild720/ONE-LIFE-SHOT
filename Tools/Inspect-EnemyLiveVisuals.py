"""Read actual warning transforms in the existing PIE encounter."""
import json
from pathlib import Path
import unreal
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
bp=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
result=[]
for a in unreal.GameplayStatics.get_all_actors_of_class(world,bp.generated_class()):
    warning=a.get_editor_property('TelegraphMesh')
    def xyz(p):return [p.x,p.y,p.z]
    result.append({'actor':a.get_name(),'kind':a.get_editor_property('WeaponKind'),'state':a.get_editor_property('AIState'),'location':xyz(a.get_actor_location()),
        'target':xyz(a.get_editor_property('AttackTarget')),'direction':xyz(a.get_editor_property('AttackDirection')),
        'visible':warning.is_visible(),'position':str(warning.get_editor_property('relative_location')),
        'rotation':str(warning.get_editor_property('relative_rotation')),'scale':str(warning.get_editor_property('relative_scale3d')),
        'absolute':[warning.get_editor_property(x) for x in ['absolute_location','absolute_rotation','absolute_scale']],
        'material':warning.get_material(0).get_path_name()})
(Path(unreal.Paths.project_saved_dir())/'EnemyLiveVisuals.json').write_text(json.dumps(result,indent=2))
