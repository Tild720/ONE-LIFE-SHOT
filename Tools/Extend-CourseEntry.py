"""Open repeated bay connections and remove temporary entry scenery."""
import runpy
from pathlib import Path
api=runpy.run_path(str(Path(__file__).with_name('Extend-Course.py')),run_name='course_library')
api['run_editor'](api['extend_entry'],'CourseEntryExtended.json')
