import builtins,runpy
from pathlib import Path
builtins._ols_facility_play_policy='miss'
runpy.run_path(str(Path(__file__).with_name('Play-FacilityEncounter.py')))
