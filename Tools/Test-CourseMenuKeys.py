"""Host-side native Slate key events, not direct calls to menu functions."""
import json,runpy,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];saved=root/'One_life_Shot/Saved'
api=runpy.run_path(str(Path(__file__).with_name('Editor-Mcp.py')));call=api['call']
report={'passed':False,'checks':[],'source':'Native Unreal Slate PressKey -> PlayerController raw key event -> HUD menu'}
counter=0
def check(name,passed,**data):
    report['checks'].append({'name':name,'passed':bool(passed),**data})
    (saved/'CourseMenuKeyTest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def script(path):
    global counter
    counter+=1;identifier='native-key-qa-'+str(time.time_ns())
    (saved/'EditorCommand.json').write_text(json.dumps({'id':identifier,'script':path}),encoding='utf-8')
    start=time.monotonic()
    while time.monotonic()-start<12:
        time.sleep(.1)
        try:data=json.loads((saved/'EditorCommandResult.json').read_text(encoding='utf-8'))
        except (FileNotFoundError,json.JSONDecodeError):continue
        if data.get('id')==identifier:
            if data.get('error'):raise RuntimeError(data['error'])
            return
    raise TimeoutError(path)
def inspect():
    script('Tools/Inspect-CoursePlay.py')
    return json.loads((saved/'CoursePlayInspection.json').read_text(encoding='utf-8'))
try:
    call('EditorToolset.EditorAppToolset','StartPIE',{'options':{'bSimulate':False,'playMode':'PlayMode_InEditorFloating','warmupSeconds':.15}})
    initial=inspect();check('Saved start menu pauses the game',initial['state']==0 and initial['paused'])
    call('SlateInspectorToolset.SlateInspectorToolset','PressKey',{'key':'Enter'});state=inspect()
    check('Native Enter starts play',state['state']==1 and not state['paused'],state=state)
    call('SlateInspectorToolset.SlateInspectorToolset','PressKey',{'key':'Escape'});state=inspect()
    check('Native ESC opens pause without closing PIE',state['state']==2 and state['paused'],state=state)
    call('SlateInspectorToolset.SlateInspectorToolset','PressKey',{'key':'Escape'});state=inspect()
    check('Native ESC resumes paused play',state['state']==1 and not state['paused'],state=state)
    call('SlateInspectorToolset.SlateInspectorToolset','PressKey',{'key':'Escape'});inspect()
    script('Tools/Position-CourseMenuClick.py')
    call('SlateInspectorToolset.SlateInspectorToolset','PressKey',{'key':'LeftMouseButton'});state=inspect()
    check('Native mouse input activates the Resume button',state['state']==1 and not state['paused'],state=state)
    report['passed']=all(c['passed'] for c in report['checks'])
except Exception as error:report['error']=repr(error)
(saved/'CourseMenuKeyTest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
