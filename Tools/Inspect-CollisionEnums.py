import unreal,json
from pathlib import Path
(Path(unreal.Paths.project_saved_dir())/'CollisionEnums.json').write_text(json.dumps({'response':dir(unreal.CollisionResponse),'channel':dir(unreal.CollisionChannel),'api':unreal.PrimitiveComponent.set_collision_response_to_channel.__doc__,'types':[n for n in dir(unreal) if 'CollisionResponse' in n]}))
