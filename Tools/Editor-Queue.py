"""Temporary editor-only runner; does not become a gameplay asset."""
import builtins
import json
import runpy
from pathlib import Path
import unreal

root = Path(__file__).resolve().parents[1]
inbox = root / 'One_life_Shot/Saved/EditorCommand.json'
reply = root / 'One_life_Shot/Saved/EditorCommandResult.json'
session = {'last': None, 'handle': None}
previous = getattr(builtins, '_ols_editor_queue', None)
if previous:
    unreal.unregister_slate_post_tick_callback(previous['handle'])
builtins._ols_editor_queue = session

def pulse(dt):
    if not inbox.exists():
        return
    command = json.loads(inbox.read_text(encoding='utf-8'))
    if command['id'] == session['last']:
        return
    session['last'] = command['id']
    script = (root / command['script']).resolve()
    assert script.is_relative_to(root / 'Tools'), script
    try:
        runpy.run_path(str(script), run_name='__main__')
        reply.write_text(json.dumps({'id':command['id'],'executed':str(script)}), encoding='utf-8')
    except Exception as error:
        reply.write_text(json.dumps({'id':command['id'],'error':repr(error)}), encoding='utf-8')
        unreal.log_error(str(error))

unreal.EditorPythonScripting.set_keep_python_script_alive(True)
session['handle'] = unreal.register_slate_post_tick_callback(pulse)
unreal.log('OLS editor-only queue ready')
