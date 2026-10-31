#!/usr/bin/env python3
"""Exercise real subprocess lifecycle using a fake file-protocol profiler."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from revision.tracing.command_profiler import CommandPlan, CommandProfilerBackend
from revision.tracing.controller import ControllerConfig, StreamingController
from revision.tracing.timing import MonotonicClock, TimingRecorder
from revision.tracing.windows import CheapWindow, HealthyBaseline


def fixture_plan(mode='ok', **changes):
    commands = {stage: (sys.executable, str(ROOT / 'revision/scripts/fake_profiler_command.py'), stage,
                       '{directory}', '--mode', mode) for stage in ('collect', 'stop', 'export', 'parse')}
    return CommandPlan(**(dict(**commands, driver_id='file_protocol_fixture', driver_version='1',
        device_uuid='GPU-fixture', worker_pids=(4242,)) | changes))


async def run_demo(output, mode='ok'):
    clock = MonotonicClock()
    recorder = TimingRecorder(clock, provenance='synthetic_simulation')
    backend = CommandProfilerBackend(recorder, output / 'captures')
    plan = fixture_plan(mode, startup_s=.5 if mode == 'no-start-ack' else 2,
        stop_s=2, finalization_s=2, export_s=2, parse_s=2)
    controller = StreamingController(backend, HealthyBaseline(100, 'separate-fixture-calibration'),
        lambda summary: None, lambda identity, window: backend.start(identity, plan),
        ControllerConfig(burst_s=.03, startup_timeout_s=3, evidence_timeout_s=12))
    start = clock.now_ns()
    try:
        await asyncio.sleep(.001)
        now = clock.now_ns()
        controller.on_window(CheapWindow('fixture-window', start, now, now, clock.domain, 200, 95, 2))
        deadline = asyncio.get_running_loop().time() + 30
        while controller.state != 'monitoring':
            controller.tick()
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError('Fixture controller did not terminate')
            await asyncio.sleep(.005)
        controller.finish()
    finally:
        controller.finish()
        await backend.aclose()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(provenance='synthetic_simulation', gpu_used=False,
        note='Actual CPU subprocesses with fake acknowledgements/reports; no Nsight or CUDA capture validated.',
        cpu_role='development_execution_not_experimental_baseline',
        backend=backend.snapshot(), controller=controller.snapshot())
    (output / 'results.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    (output / 'timing_events.jsonl').write_text(recorder.jsonl())
    (output / 'controller_events.jsonl').write_text(controller.jsonl())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('ok', 'empty-summary', 'parse-exit', 'no-start-ack'), default='ok')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    output = (args.output_dir or ROOT / 'revision/examples/command_profiler' / args.mode).resolve()
    output.relative_to((ROOT / 'revision').resolve())
    result = asyncio.run(run_demo(output, args.mode))
    print(f'CPU command fixture {args.mode}: {len(result["backend"]["attempts"])} attempts, output: {output}')


if __name__ == '__main__':
    main()
