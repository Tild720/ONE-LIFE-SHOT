import builtins,runpy
from pathlib import Path
builtins._ols_facility_preview_y=120
builtins._ols_facility_preview_empty=False
builtins._ols_frame_name='FacilityResearch720'
runpy.run_path(str(Path(__file__).with_name('Preview-Facility.py')))
