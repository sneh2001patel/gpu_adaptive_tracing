#!/usr/bin/env python3
"""Write an explicitly synthetic, CPU-only two-capture timing/readiness demo."""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.tracing.evidence_gate import EvidenceDecisionGate
from experiments.tracing.policies import PolicyConfig, StoppingPolicy
from experiments.tracing.profiler import FakeCapturePlan, FakeProfilerBackend
from experiments.tracing.timing import ManualClock, TimingRecorder


def finish_due_stage(backend, clock, capture_id):
    deadline = backend.next_deadline_ns(capture_id)
    if deadline is None:
        raise RuntimeError("No scheduled stage to finish")
    clock.advance_to(deadline)
    backend.poll(capture_id)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments/examples/fake_profiler")
    parser.add_argument("--confirm-synthetic-capture", action="store_true")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.relative_to((ROOT / "experiments").resolve())
    clock = ManualClock()
    recorder = TimingRecorder(clock, provenance="synthetic_simulation")
    backend = FakeProfilerBackend(recorder)
    policy = StoppingPolicy("stability_stop", PolicyConfig())

    def classify(summary):
        # An illustrative fake-summary classifier, not the study's classifier.
        return "compute_bound" if "gemm" in summary.get("top_kernel_name", "").lower() else None

    gate = EvidenceDecisionGate(backend, policy, classify)
    plan = FakeCapturePlan(confirm_capture=args.confirm_synthetic_capture,
                           kernel_summary={"top_kernel_name": "synthetic_gemm", "kernel_instances": 12})
    decisions, timings = [], {}
    for index in range(2):
        capture_id = f"synthetic-capture-{index}"
        gate.start_capture(capture_id, lambda: backend.start(capture_id, plan))
        finish_due_stage(backend, clock, capture_id)
        clock.advance(10)
        backend.stop(capture_id)
        while backend.state(capture_id) not in {"ready", "failed"}:
            finish_due_stage(backend, clock, capture_id)
        decisions.append(asdict(gate.evaluate(f"window-{index}", suspicious=True)))
        timings[capture_id] = recorder.metrics(capture_id)
        if policy.terminal:
            break
    output.mkdir(parents=True, exist_ok=True)
    (output / "events.jsonl").write_text(recorder.jsonl())
    (output / "results.json").write_text(json.dumps(dict(
        evidence_mode="synthetic_simulation", gpu_used=False,
        note="Virtual-clock mechanics demo. No real GPU timing or diagnostic validation. lifecycle_total_s is unknown; evidence_collection_s ends at parsed-evidence readiness.",
        decisions=decisions, timings=timings,
    ), indent=2, allow_nan=False) + "\n")
    print(f"Synthetic demo: {decisions[-1]['decision']['reason']}; output: {output}")


if __name__ == "__main__":
    main()
