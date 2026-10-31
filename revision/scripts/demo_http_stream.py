#!/usr/bin/env python3
"""Real local HTTP I/O with fake samples and a fake profiler; no GPU required."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from revision.tracing.aggregation import StreamingWindowAdapter, WindowConfig
from revision.tracing.controller import ControllerConfig, StreamingController
from revision.tracing.producers import ProducerBridge, ProducerConfig
from revision.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from revision.tracing.timing import MonotonicClock, TimingRecorder, seconds_to_ns
from revision.tracing.windows import HealthyBaseline


class LocalService:
    """Loopback-only nonstreaming HTTP fixture, with explicit task cleanup."""
    def __init__(self, scenario='slow'):
        self.scenario, self.tasks, self.count = scenario, set(), 0
        self.server = None

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0)
        self.endpoint = f'http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}/generate'
        return self

    async def __aexit__(self, *args):
        self.server.close()
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*list(self.tasks), return_exceptions=True)
        await self.server.wait_closed()

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            header = await reader.readuntil(b'\r\n\r\n')
            size = next(int(line.split(b':', 1)[1]) for line in header.split(b'\r\n')
                        if line.lower().startswith(b'content-length:'))
            await reader.readexactly(size)
            self.count += 1
            number = self.count
            delay = 10 if self.scenario == 'drain' else .06 if self.scenario == 'slow' else .005
            await asyncio.sleep(delay)
            status = '503 Service Unavailable' if self.scenario == 'errors' and number % 2 else '200 OK'
            writer.write(f'HTTP/1.1 {status}\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{{}}'.encode())
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            self.tasks.discard(task)


async def run_demo(scenario='slow', duration=.8):
    async with LocalService(scenario) as service:
        clock = MonotonicClock()
        recorder = TimingRecorder(clock, provenance='synthetic_simulation')
        backend = FakeProfilerBackend(recorder)
        # The value is a supplied fixture reference; it is not estimated from this run.
        controller = StreamingController(backend, HealthyBaseline(20, 'fixture-reference-20ms'),
            lambda summary: None,
            lambda identity, window: backend.start(identity, FakeCapturePlan(
                startup_s=.005, finalization_s=.005, stats_s=.005, parse_s=.005)),
            ControllerConfig(burst_s=.03, cooldown_s=.1))
        start = clock.now_ns()
        adapter = StreamingWindowAdapter(clock, WindowConfig(start, start + seconds_to_ns(duration),
            window_s=.1, allowed_lateness_s=.02, require_request_starts=True), controller.on_window,
            provenance='cpu_http_dry_run')
        async def sample():
            return None if scenario == 'missing' else 95.0
        bridge = ProducerBridge(adapter, controller, ProducerConfig(service.endpoint,
            rate_rps=40, max_inflight=3, request_timeout_s=2, drain_s=.05, sample_interval_s=.025),
            {'prompt': 'local fixture', 'stream': False}, sample)
        producer = await bridge.run()
        result = dict(provenance='cpu_http_dry_run', request_source='local_fake_http_service',
            gpu_sample_source='fake_sampler', profiler_source='fake_profiler', gpu_used=False,
            cpu_role='development_execution_not_experimental_baseline',
            note='Real local HTTP receipt timings; synthetic workload, GPU samples and profiler evidence. No GPU performance or diagnostic accuracy measured.',
            producer=producer, aggregation=adapter.summary(), controller=controller.snapshot())
        return result, bridge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=('slow', 'errors', 'missing', 'drain'), default='slow')
    parser.add_argument('--duration', type=float, default=.8)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    output = (args.output_dir or ROOT / 'revision/examples/http_stream' / args.scenario).resolve()
    output.relative_to((ROOT / 'revision').resolve())
    result, bridge = asyncio.run(run_demo(args.scenario, args.duration))
    output.mkdir(parents=True, exist_ok=True)
    (output / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    for name, rows in (('producer_events', bridge.events), ('windows', bridge.adapter.reports)):
        (output / f'{name}.jsonl').write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    (output / 'aggregation_events.jsonl').write_text(bridge.adapter.jsonl())
    (output / 'controller_events.jsonl').write_text(bridge.controller.jsonl())
    (output / 'timing_events.jsonl').write_text(bridge.controller.recorder.jsonl())
    print(f'CPU HTTP dry run {args.scenario}: {result["producer"]["admitted"]} admissions, '
          f'{result["aggregation"]["emitted_windows"]} windows; output: {output}')


if __name__ == '__main__':
    main()
