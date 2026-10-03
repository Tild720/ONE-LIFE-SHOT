"""Explicitly select aimed production encounter play after other QA policies."""
import builtins,runpy
from pathlib import Path
builtins._ols_play_policy='aimed'
runpy.run_path(str(Path(__file__).with_name('Play-RealEncounter.py')),run_name='__main__')
