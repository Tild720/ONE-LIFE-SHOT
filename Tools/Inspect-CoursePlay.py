"""Read-only runtime menu, input and camera state."""
import json
from pathlib import Path
import unreal
w=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_game_world()
pc=unreal.GameplayStatics.get_player_controller(w,0);hud=pc.call_method('GetHUD');p=unreal.GameplayStatics.get_player_pawn(w,0)
data={'state':hud.get_editor_property('MenuState'),'paused':unreal.GameplayStatics.is_game_paused(w),'fade':hud.get_editor_property('MenuFade'),'player':str(p.get_actor_location()),'width':hud.get_editor_property('MenuWidth'),'height':hud.get_editor_property('MenuHeight'),'held':{n:hud.get_editor_property(n) for n in ['MenuEnterHeld','MenuEscHeld','MenuClickHeld']}}
(Path(unreal.Paths.project_saved_dir())/'CoursePlayInspection.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
