"""Disposable exit-background preview; not a gameplay acceptance run."""
import builtins
import runpy
from pathlib import Path

builtins._ols_facility_preview_y = 3890
builtins._ols_facility_preview_empty = False
builtins._ols_frame_name = 'FacilityExit1080'
runpy.run_path(str(Path(__file__).with_name('Preview-Facility.py')))
