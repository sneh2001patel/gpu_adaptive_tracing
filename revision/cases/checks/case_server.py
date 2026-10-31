"""Start a case environment's OpenAI server with a case patch applied in the server process.

Usage (run_episode.py --case-patch): <env>/bin/python case_server.py <patch> <api_server args...>

Patches:
  6240_cutlass_off     fp8.cutlass_fp8_supported() -> False before the model loads: the effect of fix PR #6384 on
                       SM89, as in check_6240_serving.py (the fixed side of vllm#6240; v0.5.1 serves in-process).
  3087_json_processor  every request gets the issue's outlines JSONLogitsProcessor, as in check_3087_logits_copy.py.
                       The processor is built once when the engine starts (one shared processor, as in the issue)
                       and attached in LLMEngine.add_request, ahead of v0.3.2's deepcopy of the sampling params.
                       Applied to both releases; the release is the toggle.
  engine_stall_v1:<ms> controlled case "engine stall" (host-bound; CALIBRATION_PLAN.md §3.2): every engine step spins the CPU for <ms> ms in
                       Scheduler.schedule, between GPU steps, so the GPU waits on the host. Delivered to every server
                       process through case_site/sitecustomize.py; the first call prints its pid as a check.
"""
import runpy
import sys
import time


def cutlass_off():
    from vllm.model_executor.layers.quantization import fp8
    fp8.cutlass_fp8_supported = lambda: False


def json_processor():
    from outlines.serve.vllm import JSONLogitsProcessor
    from pydantic import BaseModel, conlist
    from vllm.engine.llm_engine import LLMEngine

    class Output(BaseModel):  # the issue's schema
        names: conlist(str, max_length=5)
        organizations: conlist(str, max_length=5)
        locations: conlist(str, max_length=5)
        miscellanous: conlist(str, max_length=5)

    init, add = LLMEngine.__init__, LLMEngine.add_request

    def patched_init(self, *args, **kwargs):
        init(self, *args, **kwargs)
        processor = JSONLogitsProcessor(schema=Output, llm=self)
        processor.fsm.vocabulary = list(processor.fsm.vocabulary)  # the issue's workaround
        self._case_processor = processor

    def patched_add(self, *args, **kwargs):
        args = list(args)
        if 'sampling_params' in kwargs:
            kwargs['sampling_params'].logits_processors = [self._case_processor]
        else:  # add_request(request_id, prompt, sampling_params, ...)
            args[2].logits_processors = [self._case_processor]
        return add(self, *args, **kwargs)

    LLMEngine.__init__, LLMEngine.add_request = patched_init, patched_add


def engine_stall(ms):
    # vLLM 0.11 starts its engine core by spawn (seed-100 pre-run: a patch applied here never reached it), so the
    # patch travels as a sitecustomize hook on PYTHONPATH, which every child process runs at startup.
    import os
    from pathlib import Path
    site = str(Path(__file__).resolve().parent / 'case_site')
    os.environ['CASE_ENGINE_STALL_MS'] = ms
    os.environ['PYTHONPATH'] = os.pathsep.join(filter(None, [site, os.environ.get('PYTHONPATH')]))
    runpy.run_path(str(Path(site) / 'sitecustomize.py'), run_name='case_site')  # this process too


PATCHES = {'6240_cutlass_off': cutlass_off, '3087_json_processor': json_processor, 'engine_stall_v1': engine_stall}


def main():
    patch, rest = sys.argv[1], sys.argv[2:]
    name, *params = patch.split(':')  # e.g. engine_stall_v1:40
    PATCHES[name](*params)
    print(f'case_server: patch {patch} applied', flush=True)
    sys.argv = ['vllm.entrypoints.openai.api_server', *rest]
    runpy.run_module('vllm.entrypoints.openai.api_server', run_name='__main__', alter_sys=True)


if __name__ == '__main__':
    main()
