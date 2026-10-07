"""Keep independent mouse presses from being swallowed by viewport capture."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from CombatAuthoring import *

def work():
    hud = unreal.load_asset('/Game/ThirdPerson/Blueprints/BP_AmmoHUD')
    changed = []
    for name in ('ShowStart', 'StartGame', 'ShowPause'):
        ed = unreal.BlueprintGraphEditor.get_graph_editor_by_name(hud, name)
        infos = BT.get_node_infos(list(ed.list_all_nodes()))
        existing = [i.node for i in infos if 'SetViewportMouseCaptureMode' in i.type_id]
        if existing:
            assert len(existing) == 1
            val(existing[0], 'MouseCaptureMode', 'CapturePermanently_IncludingInitialMouseDown')
        else:
            mode = [i.node for i in infos if i.type_id.endswith('SetInputMode_GameOnly')]
            assert len(mode) == 1, name
            capture = call(ed, GAME + 'SetViewportMouseCaptureMode',
                           MouseCaptureMode='CapturePermanently_IncludingInitialMouseDown')
            insert_after(ed, mode[0], capture)
        changed.append(name)
    compile_blueprint(hud, True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(hud, False)
    return {'saved': hud.get_path_name(), 'graphs': changed,
            'activation_click_still_flushed': True}

run_editor(work, 'ClickCaptureFix.json')
