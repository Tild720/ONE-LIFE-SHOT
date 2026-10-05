"""One in-process 800x450 test window; no second editor or standalone process."""
import unreal
settings=unreal.load_object(None,'/Script/UnrealEd.Default__LevelEditorPlaySettings')
settings.set_editor_property('NewWindowWidth',800)
settings.set_editor_property('NewWindowHeight',450)
settings.set_editor_property('CenterNewWindow',True)
