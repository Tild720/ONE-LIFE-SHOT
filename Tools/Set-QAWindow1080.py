import builtins,runpy
from pathlib import Path
builtins._ols_qa_window_size=(1920,1080)
runpy.run_path(str(Path(__file__).with_name('Set-QAWindow.py')))
