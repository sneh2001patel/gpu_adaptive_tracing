#!/usr/bin/env python3
"""Synthetic raw arrivals -> online windows -> controller -> fake captures."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from revision.tracing.aggregation import GpuSample, RequestCompletion, RequestStarted, StreamingWindowAdapter, WindowConfig
from revision.tracing.controller import ControllerConfig, StreamingController
from revision.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from revision.tracing.timing import ManualClock, TimingRecorder
from revision.tracing.windows import HealthyBaseline


def ns(seconds):
    return round(seconds * 1e9)


def run_demo(scenario: str, lateness: float = 0):
    clock = ManualClock()
    recorder = TimingRecorder(clock, provenance="synthetic_simulation")
    backend = FakeProfilerBackend(recorder)
    controller = StreamingController(backend, HealthyBaseline(100, "separate-synthetic-calibration", 2),
        lambda summary: "compute_bound" if summary.get("top_kernel_name") == "synthetic_gemm" else None,
        lambda identity, window: backend.start(identity, FakeCapturePlan(startup_s=0.1, finalization_s=0.1,
              stats_s=0.1, parse_s=0.1, kernel_summary={"top_kernel_name": "synthetic_gemm"})),
        ControllerConfig(burst_s=1, cooldown_s=1))
    adapter = StreamingWindowAdapter(clock, WindowConfig(0, ns(20), window_s=1,
        allowed_lateness_s=lateness, require_request_starts=True), controller.on_window,
        provenance="synthetic_simulation")
    raw = []

    def request(identity, start, end, *, received=None, success=True):
        raw.append((ns(start), "start", RequestStarted(identity, ns(start), ns(start), clock.domain)))
        received = end if received is None else received
        raw.append((ns(received), "completion", RequestCompletion(identity, ns(start), ns(end), ns(received),
                                                                  clock.domain, success)))

    for second in range(20):
        anomalous = 5 <= second < 12
        for offset in (0.1, 0.4):
            start = second + offset
            success = not (scenario == "errors" and second == 7 and offset == 0.1)
            latency = 0.001 if not success else 0.2 if anomalous else 0.1
            request(f"request-{second}-{offset}", start, start + latency, success=success)
        if scenario != "missing" or second not in (8, 9):
            for offset in (0.2, 0.7):
                timestamp = ns(second + offset)
                raw.append((timestamp, "gpu", GpuSample(f"gpu-{second}-{offset}", timestamp,
                                                        timestamp, clock.domain, 95 if anomalous else 20)))
    request("at-final-boundary", 19.9, 20)
    if scenario == "drain":
        request("drain-request", 19.9, 20.3)
    if scenario == "late":
        request("delayed-request", 5.9, 6.1, received=7.4)
    raw.sort(key=lambda row: row[0])
    index = 0
    handlers = {"start": adapter.on_request_started, "completion": adapter.on_request_completed,
                "gpu": adapter.on_gpu_sample}
    # Service deadlines even when no new request has completed. Ingestion wins
    # timestamp ties; closure then backend service follow in a documented order.
    for _ in range(10000):
        window_wake = adapter.next_wakeup_ns()
        if index == len(raw) and window_wake is None:
            break
        candidates = [value for value in (raw[index][0] if index < len(raw) else None,
                       window_wake, controller.next_wakeup_ns()) if value is not None]
        now = min(candidates)
        clock.advance_to(now)
        while index < len(raw) and raw[index][0] == now:
            _, kind, record = raw[index]
            handlers[kind](record)
            index += 1
        adapter.advance()
        controller.tick()
    else:
        raise RuntimeError("Synthetic scheduler failed to make progress")
    adapter.finish()
    controller.finish()
    return controller, adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("stable", "missing", "errors", "late", "drain"), default="stable")
    parser.add_argument("--allowed-lateness", type=float, default=0)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output = (args.output_dir or ROOT / "revision/examples/raw_stream" / args.scenario).resolve()
    output.relative_to((ROOT / "revision").resolve())
    controller, adapter = run_demo(args.scenario, args.allowed_lateness)
    payload = controller.snapshot()
    payload.update(aggregation=adapter.summary(), gpu_used=False,
        cpu_role="simulation_execution_not_experimental_baseline",
        note="Synthetic raw-event integration; no real serving overhead, GPU savings, or diagnosis accuracy measured.")
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    (output / "windows.jsonl").write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in adapter.reports))
    (output / "aggregation_events.jsonl").write_text(adapter.jsonl())
    (output / "controller_events.jsonl").write_text(controller.jsonl())
    (output / "timing_events.jsonl").write_text(controller.recorder.jsonl())
    print(f"Synthetic {args.scenario}: {len(adapter.reports)} online windows, "
          f"{adapter.late_completions} late completions, {adapter.drain_completions} drain completions; output: {output}")


if __name__ == "__main__":
    main()
