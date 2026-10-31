"""Engine-stall hook for the controlled case "engine stall" (case_server.py engine_stall_v1).

case_server.py puts this directory on PYTHONPATH and sets CASE_ENGINE_STALL_MS, so every Python process of the
server (including vLLM's engine-core process, which is spawned, not forked) runs this at startup. Nothing is
imported eagerly: an import hook patches vllm.v1.core.sched.scheduler.Scheduler.schedule when, and only when, the
process imports that module. The first patched call prints its pid as a check.
"""
import os
import sys

_MS = os.environ.get('CASE_ENGINE_STALL_MS')
_TARGET = 'vllm.v1.core.sched.scheduler'


def _patch(module):
    import time
    cls = module.Scheduler
    if getattr(cls.schedule, '_case_stall', False):
        return
    seconds, schedule = float(_MS) / 1000, cls.schedule

    def patched(self, *args, **kwargs):
        if not patched.announced:
            patched.announced = True
            print(f'case_site: engine stall {_MS} ms active in pid {os.getpid()}', file=sys.stderr, flush=True)
        end = time.perf_counter() + seconds
        while time.perf_counter() < end:  # CPU spin between GPU steps: the GPU waits on the host
            pass
        return schedule(self, *args, **kwargs)
    patched.announced, patched._case_stall = False, True
    cls.schedule = patched


class _Finder:
    def find_spec(self, name, path, target=None):
        if name != _TARGET:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, 'find_spec'):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None:
                break
        else:
            return None
        execute = spec.loader.exec_module

        def exec_module(module):
            execute(module)
            _patch(module)
        spec.loader.exec_module = exec_module
        return spec


if _MS:
    if _TARGET in sys.modules:
        _patch(sys.modules[_TARGET])
    else:
        sys.meta_path.insert(0, _Finder())
