"""Opt-in vLLM 0.10.2 synchronous single-worker scheduler instrumentation.

Import only in the pinned serving environment through --scheduler-cls. No model,
installed package or existing serving default is changed by importing CPU tools.
"""
import hashlib,inspect,json,os,time
from dataclasses import asdict
from pathlib import Path
from importlib.metadata import version
from vllm.v1.core.sched.scheduler import Scheduler
from experiments.tracing.server_events import EventJournal,atomic_json
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.event_probe import register_source

SCHEDULER_SHA256='2bd28fc32cea71370298bb8da0d9a0bbd163ab315b2c6428540131e3999a255f'


class EventScheduler(Scheduler):
    def __init__(self,*args,**kwargs):
        if version('vllm')!='0.10.2' or hashlib.sha256(Path(inspect.getfile(Scheduler)).read_bytes()).hexdigest()!=SCHEDULER_SHA256:
            raise RuntimeError('Installed scheduler differs from reviewed source')
        config=kwargs.get('vllm_config',args[0] if args else None)
        if config is None or config.scheduler_config.async_scheduling or config.parallel_config.tensor_parallel_size!=1 or config.parallel_config.pipeline_parallel_size!=1 or config.parallel_config.data_parallel_size!=1:
            raise ValueError('Pinned synchronous single-worker configuration required')
        super().__init__(*args,**kwargs)
        self._event_directory=Path(os.environ['REVISION_SESSION_DIR'])/'scheduler-events';self._event_directory.mkdir(exist_ok=False)
        workers=list(self._event_directory.parent.glob('worker-*.json'))
        if len(workers)!=1:raise ValueError('Exactly one verified worker record required')
        worker=json.loads(workers[0].read_text())
        # Reject different scheduler/CUDA-owner processes rather than invent a mapping.
        if worker['pid']!=os.getpid():raise ValueError('Scheduler and verified CUDA-owner PID differ')
        binding=ServingBinding(os.environ['REVISION_SESSION_NONCE'],int(os.environ['REVISION_GENERATION']),os.getpid(),
            worker['device_uuid'],config.model_config.served_model_name[0] if isinstance(config.model_config.served_model_name,list) else config.model_config.served_model_name,
            '0',os.environ['REVISION_CLOCK_DOMAIN'])
        if any(worker[k]!=v for k,v in dict(session_nonce=binding.session_nonce,generation=binding.generation,clock_domain=binding.clock_domain).items()):raise ValueError('Worker/scheduler session mismatch')
        self._events=EventJournal(binding,time.monotonic_ns)
        self._event_source=register_source(self._event_directory,self._events)
        atomic_json(self._event_directory/'startup.json',dict(version='scheduler_hook_events_v1',binding=asdict(binding),worker_record=worker,
            scheduler_source_sha256=SCHEDULER_SHA256,clock_name='time.monotonic_ns',epoch_ns=self._events.epoch,
            effective_config=dict(enable_prefix_caching=config.cache_config.enable_prefix_caching,
                max_num_seqs=config.scheduler_config.max_num_seqs,async_scheduling=config.scheduler_config.async_scheduling),
            evidence_scope='host_scheduler_hooks_not_GPU_execution_or_client_response_delivery'))
    def _checkpoint(self):
        path=self._event_directory/'probe_command.json'
        if not path.is_file():return
        try:
            self._event_source.publish()
        except Exception as exc:
            self._events.fault('probe_or_persistence_error:'+type(exc).__name__)
    def add_request(self,request):
        start=time.monotonic_ns();result=super().add_request(request);end=time.monotonic_ns()
        self._events.record('engine_admitted',request.request_id,start,end);self._checkpoint();return result
    def schedule(self):
        start=time.monotonic_ns();result=super().schedule();end=time.monotonic_ns()
        self._events.scheduled([rid for rid,count in result.num_scheduled_tokens.items() if count>0],start,end)
        self._checkpoint();return result
    def _free_request(self,request):
        start=time.monotonic_ns();result=super()._free_request(request);end=time.monotonic_ns()
        self._events.record('scheduler_finished',request.request_id,start,end,terminal_status=request.status.name)
        self._checkpoint();return result
