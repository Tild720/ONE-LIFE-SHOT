import unreal,json
from pathlib import Path
mat=unreal.load_asset('/Game/Enemies/Materials/M_EnemyRed')
report={'parameters':[str(n) for n in unreal.MaterialEditingLibrary.get_vector_parameter_names(mat)]}
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
if world:
    bp=unreal.load_asset('/Game/Enemies/BP_EnemyStraightRunner')
    report['enemies']=[{'kind':a.get_editor_property('WeaponKind'),'materials':[m.get_path_name() if m else None for m in a.get_editor_property('Mesh').get_materials()]} for a in unreal.GameplayStatics.get_all_actors_of_class(world,bp.generated_class())]
(Path(unreal.Paths.project_saved_dir())/'EnemyTintInspection.json').write_text(json.dumps(report,indent=2))
