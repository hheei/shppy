import inspect
from pathlib import Path
from multiprocessing import cpu_count

def get_workers(k: int = 1) -> int:
    if k < 0:
        return cpu_count()
    return k

def this_dir() -> Path:
    frame = inspect.currentframe()
    if frame is not None and frame.f_back is not None:
        caller_globals = frame.f_back.f_globals
        if "__file__" in caller_globals:
            return Path(caller_globals["__file__"]).parent
        elif "__vsc_ipynb_file__" in caller_globals:
            return Path(caller_globals["__vsc_ipynb_file__"]).parent
    return Path.cwd()