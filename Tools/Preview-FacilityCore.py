import builtins,runpy
from pathlib import Path
builtins._ols_facility_preview_y=2850
builtins._ols_facility_preview_empty=True
builtins._ols_frame_name='FacilityCore1080'
runpy.run_path(str(Path(__file__).with_name('Preview-Facility.py')))
