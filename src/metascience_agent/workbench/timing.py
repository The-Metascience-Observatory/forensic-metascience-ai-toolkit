"""Per-request timings emitted by the service and exposed as Server-Timing."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter

current = ContextVar('workbench_timings',default=None)
active = ContextVar('workbench_timing_scopes',default=frozenset())

@contextmanager
def measure(name):
    scopes=active.get()
    if name in scopes:
        yield
        return
    token=active.set(scopes | {name})
    start=perf_counter()
    try: yield
    finally:
        active.reset(token)
        values=current.get()
        if values is not None: values[name]=values.get(name,0)+(perf_counter()-start)*1000


def timed(name):
    def decorate(fn):
        @wraps(fn)
        def run(*args,**kwargs):
            with measure(name): return fn(*args,**kwargs)
        return run
    return decorate
