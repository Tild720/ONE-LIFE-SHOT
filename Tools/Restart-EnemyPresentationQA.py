"""Explicitly reset the disposable presentation QA guard."""
import builtins,runpy
from pathlib import Path
previous=builtins.__dict__.pop('_ols_enemy_presentation_qa',None)
if previous:previous.get('cancel',lambda:None)()
runpy.run_path(str(Path(__file__).with_name('Test-EnemyPresentation.py')),run_name='__main__')
