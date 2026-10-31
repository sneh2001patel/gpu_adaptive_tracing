"""Async HTTP admissions and sample callbacks serialized onto one controller loop.

No GPU dependency. HTTP transport supports nonstreaming Content-Length or
connection-close responses; chunked/SSE is explicitly unsupported in this pilot.
"""
from __future__ import annotations

import asyncio
import json
import math
import ssl
from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

from revision.tracing.aggregation import GpuSample, RequestCompletion, RequestStarted
from revision.tracing.timing import seconds_to_ns


@dataclass(frozen=True)
class ProducerConfig:
    endpoint: str
    rate_rps: float = 10
    max_inflight: int = 4
    request_timeout_s: float = 2
    drain_s: float = 2
    sample_interval_s: float = .1
    max_response_bytes: int = 1024 * 1024

    def __post_init__(self):
        url = urlsplit(self.endpoint)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError('Supply an HTTP(S) endpoint without credentials or fragment')
        _ = url.port
        if not math.isfinite(self.rate_rps) or not 0 < self.rate_rps <= 1e6:
            raise ValueError('Rate must be positive and at most 1e6')
        for value in (self.request_timeout_s, self.sample_interval_s):
            if seconds_to_ns(value) <= 0:
                raise ValueError('Timeout and sampling period must be positive')
        seconds_to_ns(self.drain_s)
        for value in (self.max_inflight, self.max_response_bytes):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError('Concurrency and response limit must be positive integers')


async def http_post(config: ProducerConfig, payload: bytes) -> int:
    """Measure through full response-body receipt. No retry or token streaming."""
    url = urlsplit(config.endpoint)
    port = url.port or (443 if url.scheme == 'https' else 80)
    writer = None
    try:
        reader, writer = await asyncio.open_connection(url.hostname, port,
            ssl=ssl.create_default_context() if url.scheme == 'https' else None)
        path = url.path or '/'
        if url.query:
            path += '?' + url.query
        host = f'[{url.hostname}]' if ':' in url.hostname else url.hostname
        request = (f'POST {path} HTTP/1.1\r\nHost: {host}:{port}\r\n'
                   f'Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n'
                   'Connection: close\r\n\r\n').encode('ascii')
        writer.write(request + payload)
        await writer.drain()
        header = (await reader.readuntil(b'\r\n\r\n')).decode('iso-8859-1')
        lines = header.split('\r\n')
        status = int(lines[0].split()[1])
        headers = {}
        for line in lines[1:]:
            if line:
                name, value = line.split(':', 1)
                name = name.lower()
                if name in headers:
                    raise ValueError('Duplicate response header')
                headers[name] = value.strip()
        if 'transfer-encoding' in headers or headers.get('content-type', '').startswith('text/event-stream'):
            raise ValueError('Streaming/chunked responses are unsupported')
        if 'content-length' in headers:
            size = int(headers['content-length'])
            if not 0 <= size <= config.max_response_bytes:
                raise ValueError('Response size limit')
            await reader.readexactly(size)
        else:
            size = 0
            while True:
                chunk = await reader.read(min(65536, config.max_response_bytes - size + 1))
                if not chunk:
                    break
                size += len(chunk)
                if size > config.max_response_bytes:
                    raise ValueError('Response size limit')
        return status
    finally:
        if writer is not None:
            writer.close()
            # close() aborts further writes; do not let TLS shutdown extend drain.


class ProducerBridge:
    """One asyncio loop owns producers, queue, adapter, backend and controller.

    The unbounded queue is research instrumentation, not a throughput claim.
    Slow synchronous callbacks delay service; adapter receipt time exposes lateness.
    sampler is an async no-argument callback returning utilization or None.
    """
    def __init__(self, adapter, controller, config: ProducerConfig, payload: dict, sampler):
        if adapter.clock is not controller.recorder.clock:
            raise ValueError('Producer and controller must share the same clock object')
        self.adapter, self.controller, self.clock = adapter, controller, adapter.clock
        self.config, self.payload, self.sampler = config, json.dumps(payload, allow_nan=False).encode(), sampler
        self.queue = asyncio.Queue()
        self.events = []
        self.stats = dict(admitted=0, skipped_capacity=0, skipped_scheduler=0,
                          completed=0, errors=0, drain_cancelled=0, sampler_errors=0, peak_inflight=0)
        self._used = False

    def _publish(self, record):
        self.queue.put_nowait(record)

    async def _request(self, identity, start):
        success, error = False, None
        try:
            status = await asyncio.wait_for(http_post(self.config, self.payload), self.config.request_timeout_s)
            success = 200 <= status < 300
            error = None if success else f'http_{status}'
        except asyncio.CancelledError:
            error = 'drain_cancelled'
            self.stats['drain_cancelled'] += 1
        except Exception as exc:
            error = type(exc).__name__
        end = self.clock.now_ns()
        self._publish(RequestCompletion(identity, start, end, end, self.clock.domain, success, error))
        self.stats['completed'] += 1
        self.stats['errors'] += not success

    async def _samples(self):
        index = 0
        while self.clock.now_ns() < self.adapter.config.horizon_ns:
            try:
                value = await self.sampler()
                now = self.clock.now_ns()
                record = GpuSample(f'sample-{index}', now, now, self.clock.domain, value)
            except asyncio.CancelledError:
                raise
            except Exception:
                self.stats['sampler_errors'] += 1
                now = self.clock.now_ns()
                record = GpuSample(f'sample-{index}', now, now, self.clock.domain, None)
            if now < self.adapter.config.horizon_ns:
                self._publish(record)
            index += 1
            await asyncio.sleep(self.config.sample_interval_s)

    async def _produce(self):
        tasks = set()
        sampling = asyncio.create_task(self._samples())
        step = seconds_to_ns(1 / self.config.rate_rps)
        due = max(self.adapter.config.start_ns, self.clock.now_ns())
        try:
            while due < self.adapter.config.horizon_ns:
                await asyncio.sleep(max(0, (due - self.clock.now_ns()) / 1e9))
                now = self.clock.now_ns()
                if now >= self.adapter.config.horizon_ns:
                    break
                # Skip missed admission slots instead of issuing catch-up bursts.
                missed = (now - due) // step
                self.stats['skipped_scheduler'] += missed
                due += (missed + 1) * step
                tasks = {task for task in tasks if not task.done()}
                if len(tasks) >= self.config.max_inflight:
                    self.stats['skipped_capacity'] += 1
                    continue
                identity = f'request-{self.stats["admitted"]}'
                self._publish(RequestStarted(identity, now, now, self.clock.domain))
                tasks.add(asyncio.create_task(self._request(identity, now)))
                self.stats['admitted'] += 1
                self.stats['peak_inflight'] = max(self.stats['peak_inflight'], len(tasks))
            await asyncio.sleep(max(0, (self.adapter.config.horizon_ns - self.clock.now_ns()) / 1e9))
            sampling.cancel()
            await asyncio.gather(sampling, return_exceptions=True)
            if tasks:
                _, pending = await asyncio.wait(tasks, timeout=self.config.drain_s)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*tasks)
        finally:
            sampling.cancel()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(sampling, *tasks, return_exceptions=True)

    async def run(self):
        if self._used:
            raise RuntimeError('Bridge is single-use')
        if self.clock.now_ns() < self.adapter.config.start_ns or self.clock.now_ns() >= self.adapter.config.horizon_ns:
            raise ValueError('Run inside the predeclared observation interval')
        self._used = True
        producer = asyncio.create_task(self._produce())
        handlers = {RequestStarted: self.adapter.on_request_started,
                    RequestCompletion: self.adapter.on_request_completed, GpuSample: self.adapter.on_gpu_sample}
        try:
            while not producer.done() or not self.queue.empty() or self.adapter.next_wakeup_ns() is not None:
                # Snapshot queue size to keep telemetry from starving deadlines.
                for _ in range(self.queue.qsize()):
                    record = self.queue.get_nowait()
                    received = self.clock.now_ns()
                    accepted = handlers[type(record)](record)
                    self.events.append(dict(sequence=len(self.events), received_at_ns=received,
                        queue_delay_ns=received - record.available_at_ns, type=type(record).__name__,
                        accepted=accepted, record=asdict(record)))
                self.adapter.advance()
                if self.adapter.next_wakeup_ns() is None:
                    if not self.controller.finished:
                        self.controller.finish()
                else:
                    self.controller.tick()
                deadlines = [d for d in (self.adapter.next_wakeup_ns(),
                    None if self.controller.finished else self.controller.next_wakeup_ns()) if d is not None]
                delay = min(.005, max(0, (min(deadlines) - self.clock.now_ns()) / 1e9)) if deadlines else .005
                await asyncio.sleep(delay)
            await producer  # Surface producer failure rather than silently finish.
            self.adapter.finish()
            if not self.controller.finished:
                self.controller.finish()
            return dict(producer_version='producer_v1', config=asdict(self.config), **self.stats,
                        observation_start_ns=self.adapter.config.start_ns,
                        observation_horizon_ns=self.adapter.config.horizon_ns,
                        finished_at_ns=self.clock.now_ns(), queue_records=len(self.events),
                        clock_domain=self.clock.domain, baseline=asdict(self.controller.baseline))
        finally:
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
            if not self.controller.finished:
                self.controller.finish()
