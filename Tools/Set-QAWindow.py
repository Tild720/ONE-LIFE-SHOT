"""Temporary, unsaved PIE window dimensions for UI visual checks."""
import builtins,json
from pathlib import Path
import unreal
from CombatAuthoring import run_editor

def work():
    settings=unreal.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
    assert settings
    if not hasattr(builtins, '_ols_qa_window_original'):
        builtins._ols_qa_window_original={name:settings.get_editor_property(name) for name in ['NewWindowWidth','NewWindowHeight','NewWindowPosition','CenterNewWindow']}
    size=getattr(builtins, '_ols_qa_window_size', (1280,720))
    settings.set_editor_property('NewWindowWidth',size[0])
    settings.set_editor_property('NewWindowHeight',size[1])
    settings.set_editor_property('NewWindowPosition',unreal.IntPoint(0,0))
    settings.set_editor_property('CenterNewWindow',False)
    return {'size':list(size),'saved':False}
run_editor(work,'QAWindow.json')
