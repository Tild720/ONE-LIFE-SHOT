import builtins
import runpy
from pathlib import Path
import unreal
perf=unreal.load_object(None,'/Script/UnrealEd.Default__EditorPerformanceSettings')
if not hasattr(builtins,'_ols_old_background_throttle'):
    builtins._ols_old_background_throttle=perf.get_editor_property('bThrottleCPUWhenNotForeground')
perf.set_editor_property('bThrottleCPUWhenNotForeground',False)
qa = builtins.__dict__.pop('_combat_roles_qa_session', None)
if qa:
    qa.get('cancel', lambda: None)()
runpy.run_path(str(Path(__file__).with_name('Test-CombatRoles.py')), run_name='__main__')
