"""Run target-order playback with production FIFO promotion, even after miss mode."""
import builtins
import runpy
from pathlib import Path

builtins._ols_facility_play_policy = 'order'
runpy.run_path(str(Path(__file__).with_name('Play-FacilityEncounter.py')))
