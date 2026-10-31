"""Nonblocking fake capture backend and evidence interface. No GPU imports."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Protocol

from revision.tracing.timing import TimingRecorder, seconds_to_ns


class EvidenceNotReady(RuntimeError):
    pass


class CaptureFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class ReadyEvidence:
    capture_id: str
    evidence_id: str
    ready_at_ns: int
    clock_domain: str
    payload: dict
    provenance: str


class ProfilerBackend(Protocol):
    recorder: TimingRecorder

    def state(self, capture_id: str) -> str: ...
    def evidence(self, capture_id: str) -> ReadyEvidence: ...


class StreamingProfilerBackend(ProfilerBackend, Protocol):
    def poll(self, capture_id: str) -> str: ...
    def stop(self, capture_id: str) -> None: ...
    def cancel(self, capture_id: str, reason: str) -> None: ...
    def next_deadline_ns(self, capture_id: str) -> int | None: ...


@dataclass(frozen=True)
class FakeCapturePlan:
    startup_s: float = 1.0
    finalization_s: float = 2.0
    stats_s: float = 3.0
    parse_s: float = 0.5
    confirm_capture: bool = False
    fail_at: str | None = None
    kernel_summary: dict = field(default_factory=dict)

    def __post_init__(self):
        for value in (self.startup_s, self.finalization_s, self.stats_s, self.parse_s):
            seconds_to_ns(value)
        if self.fail_at not in {None, "startup", "stop", "finalization", "stats", "parse"}:
            raise ValueError("Unsupported fake failure stage")


@dataclass
class _Capture:
    plan: FakeCapturePlan
    state: str
    deadline_ns: int | None
    start_ns: int | None = None
    ready: ReadyEvidence | None = None
    failure_reason: str | None = None


class FakeProfilerBackend:
    """Each poll advances at most one due stage; the caller controls the clock.

    Stage completion is timestamped when actually polled, not backdated to a
    scheduled deadline. Capture boundaries are unavailable by default. Optional
    confirmed boundaries are synthetic, never a GPU coverage measurement.
    """

    def __init__(self, recorder: TimingRecorder):
        if recorder.provenance != "synthetic_simulation":
            raise ValueError("The fake backend must be labeled synthetic_simulation")
        self.recorder = recorder
        self._captures: dict[str, _Capture] = {}

    def start(self, capture_id: str, plan: FakeCapturePlan) -> None:
        if capture_id in self._captures:
            raise ValueError("Capture attempt IDs must be unique")
        self._captures[capture_id] = _Capture(copy.deepcopy(plan), "starting", None)
        self.recorder.mark("capture_attempted", capture_id)
        self.recorder.begin("evidence_collection", capture_id)
        self.recorder.begin("profile_process_wall", capture_id)
        self.recorder.begin("server_startup", capture_id)
        self._schedule(capture_id, plan.startup_s)

    def _schedule(self, capture_id: str, seconds: float) -> None:
        self._captures[capture_id].deadline_ns = self.recorder.clock.now_ns() + seconds_to_ns(seconds)

    def state(self, capture_id: str) -> str:
        return self._captures[capture_id].state

    def next_deadline_ns(self, capture_id: str) -> int | None:
        return self._captures[capture_id].deadline_ns

    def _fail(self, capture_id: str, phase: str, *, status: str = "failed", reason: str | None = None) -> None:
        capture = self._captures[capture_id]
        self.recorder.end(phase, capture_id, status=status)
        if phase in {"server_startup", "capture_control_window", "report_finalization"}:
            self.recorder.end("profile_process_wall", capture_id, status=status)
        self.recorder.end("evidence_collection", capture_id, status=status)
        capture.failure_reason = reason or phase
        self.recorder.mark("capture_failed", capture_id, status=capture.failure_reason)
        capture.state, capture.deadline_ns = "failed", None

    def poll(self, capture_id: str) -> str:
        capture = self._captures[capture_id]
        now = self.recorder.clock.now_ns()
        if capture.deadline_ns is None or now < capture.deadline_ns:
            return capture.state
        capture.deadline_ns = None
        stages = {
            "starting": ("server_startup", "startup"),
            "finalizing": ("report_finalization", "finalization"),
            "exporting": ("stats_command", "stats"),
            "parsing": ("summary_parse", "parse"),
        }
        phase, failure = stages[capture.state]
        if capture.plan.fail_at == failure:
            self._fail(capture_id, phase)
            return capture.state
        self.recorder.end(phase, capture_id)
        if capture.state == "starting":
            capture.state, capture.start_ns = "capturing", now
            self.recorder.begin("capture_control_window", capture_id)
        elif capture.state == "finalizing":
            self.recorder.end("profile_process_wall", capture_id)
            self.recorder.mark("report_ready", capture_id)
            capture.state = "exporting"
            self.recorder.begin("stats_command", capture_id)
            self._schedule(capture_id, capture.plan.stats_s)
        elif capture.state == "exporting":
            capture.state = "parsing"
            self.recorder.begin("summary_parse", capture_id)
            self._schedule(capture_id, capture.plan.parse_s)
        else:
            event = self.recorder.mark("evidence_ready", capture_id)
            capture.ready = ReadyEvidence(capture_id, f"{capture_id}:parsed-summary", now,
                                          event.clock_domain, copy.deepcopy(capture.plan.kernel_summary),
                                          "synthetic_simulation")
            capture.state = "ready"
            self.recorder.end("evidence_collection", capture_id)
        return capture.state

    def stop(self, capture_id: str) -> None:
        capture = self._captures[capture_id]
        if capture.state != "capturing":
            raise ValueError("Stop requires a successful capture start")
        if capture.plan.fail_at == "stop":
            self._fail(capture_id, "capture_control_window")
            return
        self.recorder.end("capture_control_window", capture_id)
        if capture.plan.confirm_capture:
            self.recorder.confirm_capture_interval(capture_id, capture.start_ns, self.recorder.clock.now_ns(),
                                                   clock_domain=self.recorder.clock.domain)
        capture.state = "finalizing"
        self.recorder.begin("report_finalization", capture_id)
        self._schedule(capture_id, capture.plan.finalization_s)

    def evidence(self, capture_id: str) -> ReadyEvidence:
        capture = self._captures[capture_id]
        if capture.state == "failed":
            raise CaptureFailed(f"Capture attempt failed: {capture_id} ({capture.failure_reason})")
        if capture.state != "ready" or capture.ready is None:
            raise EvidenceNotReady(f"Evidence is not ready: {capture_id} ({capture.state})")
        return copy.deepcopy(capture.ready)

    def cancel(self, capture_id: str, reason: str) -> None:
        capture = self._captures[capture_id]
        if capture.state in {"ready", "failed"}:
            return
        phase = {"starting": "server_startup", "capturing": "capture_control_window",
                 "finalizing": "report_finalization", "exporting": "stats_command",
                 "parsing": "summary_parse"}[capture.state]
        self._fail(capture_id, phase, status="cancelled", reason=reason)
