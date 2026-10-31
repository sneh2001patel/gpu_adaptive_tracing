"""vLLM 0.10.2 V1 worker: execute capture APIs in the actual CUDA owner.

Imported only by the GPU serving environment, never by CPU test discovery.
"""
import json
import os
from pathlib import Path
import time

import torch
from vllm.v1.worker.gpu_worker import Worker
from experiments.tracing.worker_barrier import worker_barrier


def atomic_json(path, record):
    temporary = path.with_suffix('.pending')
    temporary.write_text(json.dumps(record, allow_nan=False) + '\n')
    temporary.replace(path)


class CudaCaptureWorker(Worker):
    def revision_configuration(self):
        from experiments.tracing.worker_configuration import configuration_receipt
        directory=Path(os.environ['REVISION_SESSION_DIR'])
        command=json.loads((directory/'configuration_command.json').read_text())
        token=command['token']
        if not isinstance(token,str) or len(token)!=32 or any(c not in '0123456789abcdef' for c in token):
            raise ValueError('Invalid configuration token')
        if not hasattr(self,'_revision_configuration_tokens'):self._revision_configuration_tokens=set()
        if token in self._revision_configuration_tokens or len(self._revision_configuration_tokens)>=4:
            raise ValueError('Configuration replay/budget exceeded')
        config=self.vllm_config
        receipt=configuration_receipt(command,pid=os.getpid(),device_uuid=self._revision_uuid,
            session_nonce=os.environ['REVISION_SESSION_NONCE'],generation=int(os.environ['REVISION_GENERATION']),
            clock_domain=os.environ['REVISION_CLOCK_DOMAIN'],capture_active=self._revision_capture_active,
            config=dict(enable_prefix_caching=config.cache_config.enable_prefix_caching,
                async_scheduling=config.scheduler_config.async_scheduling,max_num_seqs=config.scheduler_config.max_num_seqs,
                tensor_parallel_size=config.parallel_config.tensor_parallel_size,
                pipeline_parallel_size=config.parallel_config.pipeline_parallel_size,data_parallel_size=config.parallel_config.data_parallel_size),
            now_ns=time.monotonic_ns)
        self._revision_configuration_tokens.add(token)
        atomic_json(directory/('configuration-'+token+'.json'),receipt)
        return receipt

    def revision_event_probe(self):
        if os.environ.get('REVISION_ENABLE_EVENTS')!='1':
            raise ValueError('Scheduler events were not enabled for this session')
        from experiments.tracing.event_probe import worker_probe
        return worker_probe(Path(os.environ['REVISION_SESSION_DIR'])/'scheduler-events',
            pid=os.getpid(),device_uuid=self._revision_uuid,
            session_nonce=os.environ['REVISION_SESSION_NONCE'],generation=int(os.environ['REVISION_GENERATION']),
            clock_domain=os.environ['REVISION_CLOCK_DOMAIN'],capture_active=self._revision_capture_active)

    def init_device(self):
        super().init_device()
        directory = Path(os.environ['REVISION_SESSION_DIR'])
        properties = torch.cuda.get_device_properties(self.device)
        device_uuid = str(properties.uuid)
        if not device_uuid.startswith('GPU-'):
            device_uuid = 'GPU-' + device_uuid
        self._revision_uuid = device_uuid
        self._revision_capture_active = False
        self._revision_barrier_tokens = set()
        atomic_json(directory / f'worker-{os.getpid()}.json', dict(pid=os.getpid(),
            device_uuid=device_uuid, device_index=torch.cuda.current_device(),
            clock_domain=os.environ['REVISION_CLOCK_DOMAIN'], ready_at_ns=time.monotonic_ns(),
            session_nonce=os.environ.get('REVISION_SESSION_NONCE'),generation=int(os.environ.get('REVISION_GENERATION','0')),
            reset_token=os.environ.get('REVISION_RESET_TOKEN')))

    def revision_barrier(self):
        directory=Path(os.environ['REVISION_SESSION_DIR'])
        command=json.loads((directory/'barrier_command.json').read_text())
        # Tokens are file-name components only after strict hexadecimal validation.
        if len(command['token'])!=32 or any(c not in '0123456789abcdef' for c in command['token']):
            raise ValueError('Invalid barrier token')
        if command['token'] in self._revision_barrier_tokens:raise ValueError('Worker barrier token already consumed')
        receipt=worker_barrier(command,pid=os.getpid(),device_uuid=self._revision_uuid,
            clock_domain=os.environ['REVISION_CLOCK_DOMAIN'],session_nonce=os.environ.get('REVISION_SESSION_NONCE'),
            generation=int(os.environ.get('REVISION_GENERATION','0')),capture_active=self._revision_capture_active,
            synchronize=torch.cuda.synchronize,now_ns=time.monotonic_ns)
        self._revision_barrier_tokens.add(command['token'])
        atomic_json(directory/f'barrier-{command["token"]}-{os.getpid()}.json',receipt)
        return receipt

    def profile(self, is_start=True):
        directory = Path(os.environ['REVISION_SESSION_DIR'])
        command = json.loads((directory / 'control.json').read_text())
        before = time.monotonic_ns()
        torch.cuda.synchronize()
        api = torch.cuda.cudart().cudaProfilerStart if is_start else torch.cuda.cudart().cudaProfilerStop
        result = api()
        if int(result) != 0:
            raise RuntimeError(f'CUDA profiler API returned {result}')
        after = time.monotonic_ns()
        self._revision_capture_active = bool(is_start)
        action = 'start' if is_start else 'stop'
        atomic_json(directory / f'{command["token"]}-{os.getpid()}-{action}.json', dict(
            capture_id=command['capture_id'], token=command['token'], ordinal=command['ordinal'],
            action=action, source='cuda_worker_api', pid=os.getpid(), device_uuid=self._revision_uuid,
            requested_at_ns=before, returned_at_ns=after, cuda_return_code=0,
            clock_domain=os.environ['REVISION_CLOCK_DOMAIN']))
