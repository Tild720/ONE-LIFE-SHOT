"""Production play acceptance across the existing forward spawn windows."""
import builtins,runpy
from pathlib import Path
builtins._ols_play_policy='polished'
builtins._ols_play_advance_limit=3600
runpy.run_path(str(Path(__file__).with_name('Play-RealEncounter.py')))
del builtins._ols_play_advance_limit
