"""Optional device telemetry isolated from the asyncio/controller process.

Only the spawned worker imports pynvml. Parent receipt timestamps describe when
an NVML reading became available, not its unknown device sampling interval.
"""
from __future__ import annotations

import asyncio
import importlib
import math
import multiprocessing
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version

from experiments.tracing.timing import seconds_to_ns


class SamplingError(RuntimeError):
    pass


@dataclass(frozen=True)
class NvmlConfig:
    device_uuid: str
    startup_timeout_s: float = 5
    read_timeout_s: float = 1
    shutdown_timeout_s: float = .5

    def __post_init__(self):
        if not isinstance(self.device_uuid, str) or not self.device_uuid.startswith('GPU-') or len(self.device_uuid) <= 4:
            raise ValueError('Explicit physical GPU UUID required; indices and MIG UUIDs are unsupported')
        for value in (self.startup_timeout_s, self.read_timeout_s, self.shutdown_timeout_s):
            if seconds_to_ns(value) <= 0:
                raise ValueError('NVML deadlines must be positive')


def _text(value):
    return value.decode('ascii') if isinstance(value, bytes) else str(value)


class NvmlSession:
    """Synchronous NVML lifecycle; run inside the worker, never on asyncio."""
    def __init__(self, module, device_uuid):
        self.module, self.initialized = module, False
        try:
            module.nvmlInit()
            self.initialized = True
            self.handle = module.nvmlDeviceGetHandleByUUID(device_uuid)
            actual = _text(module.nvmlDeviceGetUUID(self.handle))
            if actual != device_uuid:
                raise SamplingError('Resolved GPU UUID differs from configured UUID')
            try:
                current, _ = module.nvmlDeviceGetMigMode(self.handle)
            except module.NVMLError_NotSupported:
                current = 0
            if current != 0:
                raise SamplingError('MIG-enabled device utilization is unsupported in this adapter')
            self.metadata = dict(device_uuid=actual, name=_text(module.nvmlDeviceGetName(self.handle)),
                                 driver_version=_text(module.nvmlSystemGetDriverVersion()),
                                 scope='device_wide_not_process_attributed', mig_enabled=False)
        except BaseException:
            self.close()
            raise

    def read(self):
        value = self.module.nvmlDeviceGetUtilizationRates(self.handle).gpu
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
            raise SamplingError('Invalid NVML utilization')
        return float(value)

    def close(self):
        if self.initialized:
            self.initialized = False
            self.module.nvmlShutdown()


def _worker(connection, device_uuid):
    session = None
    try:
        module = importlib.import_module('pynvml')
        session = NvmlSession(module, device_uuid)
        try:
            package_version = version('nvidia-ml-py')
        except PackageNotFoundError:
            package_version = None
        connection.send(dict(kind='ready', metadata=dict(session.metadata, binding_version=package_version)))
        while True:
            command = connection.recv()
            if command['kind'] == 'close':
                session.close()
                connection.send(dict(kind='closed'))
                break
            identity = command['request_id']
            try:
                value = session.read()
                connection.send(dict(kind='reading', request_id=identity, gpu_util=value))
            except Exception as exc:
                connection.send(dict(kind='error', request_id=identity, error_type=type(exc).__name__))
    except (EOFError, BrokenPipeError):
        pass
    except Exception as exc:
        try:
            connection.send(dict(kind='startup_error', error_type=type(exc).__name__))
        except (EOFError, BrokenPipeError):
            pass
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
        connection.close()


class NvmlSampler:
    """Async callback for ProducerBridge, with native calls in a spawn worker.

    Timeouts/protocol failures/cancellation close this session; do not reuse a
    stale outstanding reply. Native read errors are raised, never mapped to zero.
    Own via `async with` OUTSIDE the bridge so cancellation cleanup is explicit.
    """
    def __init__(self, config: NvmlConfig, clock, *, _worker_target=_worker):
        self.config, self.clock, self._target = config, clock, _worker_target
        self.process = self.connection = None
        self.metadata = None
        self.events = []
        self._lock = asyncio.Lock()
        self._used, self.closed, self._sequence = False, False, 0
        self.forced_termination = False
        self._close_task = None

    def _event(self, name, **details):
        self.events.append(dict(event=name, timestamp_ns=self.clock.now_ns(),
                                clock_domain=self.clock.domain, **details))

    async def _receive(self, timeout_s):
        deadline = asyncio.get_running_loop().time() + timeout_s
        while True:
            if self.connection.poll():
                try:
                    return self.connection.recv()
                except EOFError as exc:
                    raise SamplingError('NVML worker exited without a reply') from exc
            if not self.process.is_alive():
                raise SamplingError('NVML worker exited')
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise SamplingError('NVML worker deadline exceeded')
            await asyncio.sleep(min(.005, remaining))

    async def open(self):
        if self._used or self.closed:
            raise SamplingError('NVML session is single-use')
        self._used = True
        context = multiprocessing.get_context('spawn')
        self.connection, child = context.Pipe()
        self.process = context.Process(target=self._target, args=(child, self.config.device_uuid), daemon=True)
        self._event('nvml_start_requested')
        try:
            self.process.start()
            child.close()
            response = await self._receive(self.config.startup_timeout_s)
            if response.get('kind') != 'ready':
                raise SamplingError(f'NVML initialization failed: {response.get("error_type", "protocol_error")}')
            metadata = response['metadata']
            if metadata.get('device_uuid') != self.config.device_uuid or metadata.get('mig_enabled') is not False:
                raise SamplingError('Worker device identity/MIG contract failed')
            self.metadata = metadata
            self._event('nvml_ready', metadata=metadata)
            return self
        except BaseException:
            child.close()
            await self.aclose()
            raise

    async def __call__(self):
        async with self._lock:
            if self.closed or self.metadata is None:
                raise SamplingError('NVML sampler is not open')
            identity = self._sequence
            self._sequence += 1
            self._event('nvml_read_requested', request_id=identity)
            try:
                self.connection.send(dict(kind='read', request_id=identity))
                response = await self._receive(self.config.read_timeout_s)
                if response.get('request_id') != identity or response.get('kind') not in ('reading', 'error'):
                    raise SamplingError('NVML reply identity/protocol mismatch')
                if response['kind'] == 'error':
                    self._event('nvml_read_failed', request_id=identity, error_type=response.get('error_type'))
                    # A completed read failure has no dangling response; retry next poll.
                    raise _CompletedReadError(f'NVML read failed: {response.get("error_type")}')
                value = response.get('gpu_util')
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 100:
                    raise SamplingError('Invalid worker utilization')
                self._event('nvml_read_received', request_id=identity, gpu_util=float(value),
                            sampling_interval='unknown', timestamp_semantics='parent_receipt')
                return float(value)
            except _CompletedReadError:
                raise
            except BaseException:
                await self.aclose()
                raise

    async def aclose(self):
        # Keep cleanup alive through cancellation at ANY await, including the
        # post-TERM/KILL polling interval. Concurrent close callers share it.
        if self._close_task is None:
            self.closed = True
            self._close_task = asyncio.create_task(self._close_impl())
        cancelled = False
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError:
                cancelled = True
        self._close_task.result()
        if cancelled:
            raise asyncio.CancelledError

    async def _close_impl(self):
        process = self.process
        acknowledged = False
        if process is not None and process.pid is not None:
            try:
                if process.is_alive():
                    self.connection.send(dict(kind='close'))
                    reply = await self._receive(self.config.shutdown_timeout_s)
                    acknowledged = reply.get('kind') == 'closed'
            except Exception:
                pass
            if process.is_alive():
                if not acknowledged:
                    self.forced_termination = True
                    process.terminate()
                deadline = asyncio.get_running_loop().time() + self.config.shutdown_timeout_s
                while process.is_alive() and asyncio.get_running_loop().time() < deadline:
                    await asyncio.sleep(.005)
                if process.is_alive():
                    self.forced_termination = True
                    process.kill()
                    deadline = asyncio.get_running_loop().time() + self.config.shutdown_timeout_s
                    while process.is_alive() and asyncio.get_running_loop().time() < deadline:
                        await asyncio.sleep(.005)
            process.join(timeout=0)
        if self.connection is not None:
            self.connection.close()
        alive = process is not None and process.pid is not None and process.is_alive()
        self._event('nvml_closed', shutdown_acknowledged=acknowledged,
                    forced_termination=self.forced_termination, worker_alive=alive)
        if alive:
            raise SamplingError('NVML worker did not exit after terminate/kill')

    async def __aenter__(self):
        return await self.open()

    async def __aexit__(self, *args):
        await self.aclose()


class _CompletedReadError(SamplingError):
    pass
