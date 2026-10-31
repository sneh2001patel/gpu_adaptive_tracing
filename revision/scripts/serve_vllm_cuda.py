#!/usr/bin/env python3
"""Expose vLLM 0.10.2 control routes without enabling Torch/Kineto capture.

The API module gates route registration on VLLM_TORCH_PROFILER_DIR. Set that
only during import, then remove it before constructing frontend/worker engines.
The selected CudaCaptureWorker implements those routes using CUDA profiler APIs.
"""
import os
from importlib.metadata import version


def main():
    if version('vllm')!='0.10.2':
        raise RuntimeError('This serving adapter is pinned to vLLM 0.10.2')
    os.environ['VLLM_TORCH_PROFILER_DIR']=os.environ['REVISION_SESSION_DIR']+'/route_registration_only'
    try:
        from vllm.entrypoints.openai import api_server
    finally:
        os.environ.pop('VLLM_TORCH_PROFILER_DIR',None)
    if os.environ.get('REVISION_ENABLE_BARRIER')=='1':
        from revision.tracing.worker_barrier import install_barrier_route
        install_barrier_route(api_server)
        from revision.tracing.worker_configuration import install_configuration_route
        install_configuration_route(api_server)
    if os.environ.get('REVISION_ENABLE_EVENTS')=='1':
        from revision.tracing.event_probe import install_event_route
        install_event_route(api_server)
    from vllm import envs
    # The pinned release can cache environment lookups. Clear any imported
    # route-registration value before constructing AsyncLLM or CUDA workers.
    if hasattr(envs,'disable_envs_cache'):
        envs.disable_envs_cache()
    api_server.cli_env_setup()
    parser=api_server.make_arg_parser(api_server.FlexibleArgumentParser(description=__doc__))
    args=parser.parse_args()
    api_server.validate_parsed_serve_args(args)
    api_server.uvloop.run(api_server.run_server(args))


if __name__=='__main__':main()
