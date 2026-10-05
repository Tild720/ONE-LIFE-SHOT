"""Inspect raw key node IDs and Blueprint input settings, read-only."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from CombatAuthoring import *
def work():
    unreal.SystemLibrary.execute_console_command(None,'GetIni EditorSettings:ProjectDefinedChords ProjectDefinedChords')
    bp=unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController')
    ed=unreal.BlueprintGraphEditor.get_graph_editor_by_name(bp,'EventGraph')
    return {'nodes':[str(n) for n in ed.list_available_nodes([]) if any(k in str(n) for k in ['Escape','Enter','LeftMouseButton'])]}
run_editor(work,'MenuKeyNodes.json')
