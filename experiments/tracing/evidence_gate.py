"""Gate policy updates on parsed evidence readiness, using a single pending attempt."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable

from experiments.tracing.policies import PolicyDecision, PolicyEvidence, StoppingPolicy
from experiments.tracing.profiler import CaptureFailed, EvidenceNotReady, ProfilerBackend


@dataclass(frozen=True)
class TimedDecision:
    decision: PolicyDecision
    capture_id: str
    evidence_id: str | None
    evidence_ready_at_ns: int | None
    decision_ready_at_ns: int
    clock_domain: str
    status: str
    error: str | None
    provenance: str


class EvidenceDecisionGate:
    """Small CPU harness; scheduling and production cleanup belong to the controller.

    start_attempt is injected so the gate does not require a particular backend
    configuration type. Only one attempt may be pending; failed attempts also
    consume policy budget when evaluated. An early evaluate call changes neither
    the policy nor the classifier state.
    """

    def __init__(self, backend: ProfilerBackend, policy: StoppingPolicy,
                 classifier: Callable[[dict], str | None]):
        self.backend, self.policy, self.classifier = backend, policy, classifier
        self.pending: str | None = None
        self.attempts: set[str] = set()
        self.consumed_evidence: set[str] = set()
        self._start_error: str | None = None

    @property
    def pending_start_failed(self) -> bool:
        return self.pending is not None and self._start_error is not None

    def start_capture(self, capture_id: str, start_attempt: Callable[[], None]) -> None:
        if self.pending is not None:
            raise RuntimeError("Resolve the pending attempt before starting another")
        if not self.policy.can_capture:
            raise RuntimeError("Policy has stopped or exhausted its capture budget")
        if not capture_id or capture_id in self.attempts:
            raise ValueError("Capture attempt IDs must be nonempty and unique")
        self.pending = capture_id
        self.attempts.add(capture_id)
        self._start_error = None
        try:
            start_attempt()
        except Exception as error:
            # Launch failures may occur before the backend has a capture record.
            # Keep the attempt pending until an explicit failure decision charges it.
            self._start_error = str(error)
            self.backend.recorder.mark("attempt_start_failed", capture_id, status="failed")

    def evaluate(self, window_id: str, *, latency_ratio: float | None = None,
                 gpu_util: float | None = None, suspicious: bool | None = None,
                 recovery_evidence_id: str | None = None) -> TimedDecision:
        if self.pending is None:
            raise RuntimeError("No pending capture attempt")
        if window_id in self.policy.window_ids:
            raise ValueError("A decision window may only be observed once")
        capture_id = self.pending
        recorder = self.backend.recorder
        status, error, ready, label = "ok", self._start_error, None, None
        if error is not None:
            status = "capture_failed"
        else:
            try:
                ready = self.backend.evidence(capture_id)
            except CaptureFailed as failure:
                status, error = "capture_failed", str(failure)
            # EvidenceNotReady propagates before any classifier/policy mutation.
        if ready is not None:
            if not isinstance(ready.ready_at_ns, int) or ready.ready_at_ns < 0 or not ready.evidence_id:
                raise ValueError("Evidence requires a valid timestamp and nonempty identity")
            if ready.clock_domain != recorder.clock.domain:
                raise ValueError("Evidence uses a different clock domain")
            if ready.provenance != recorder.provenance:
                raise ValueError("Evidence provenance does not match the recorder")
            if ready.ready_at_ns > recorder.clock.now_ns():
                raise EvidenceNotReady("Evidence-ready timestamp is in the future")
            if ready.capture_id != capture_id or ready.evidence_id in self.consumed_evidence:
                raise ValueError("Evidence is from a different attempt or was already consumed")
            recorder.begin("diagnosis_compute", capture_id)
            try:
                label = self.classifier(copy.deepcopy(ready.payload))
                if label is not None and not isinstance(label, str):
                    raise ValueError("Classifier must return a label string or None")
            except Exception as failure:
                recorder.end("diagnosis_compute", capture_id, status="failed")
                label, status, error = None, "diagnosis_failed", str(failure)
            else:
                recorder.end("diagnosis_compute", capture_id)
            self.consumed_evidence.add(ready.evidence_id)
        evidence_id = ready.evidence_id if ready is not None and status == "ok" else None
        decision = self.policy.observe(PolicyEvidence(
            window_id=window_id, diagnosis_label=label, capture_id=capture_id,
            diagnosis_evidence_id=evidence_id, latency_ratio=latency_ratio,
            gpu_util=gpu_util, suspicious=suspicious,
            recovery_evidence_id=recovery_evidence_id,
        ))
        event = recorder.mark("decision_ready", capture_id, status=status)
        self.pending, self._start_error = None, None
        return TimedDecision(decision, capture_id, evidence_id,
                             ready.ready_at_ns if ready else None, event.timestamp_ns,
                             event.clock_domain, status, error, event.provenance)
