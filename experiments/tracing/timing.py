"""Monotonic, explicitly scoped timing events; unknown measurements stay null."""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Protocol


class Clock(Protocol):
    domain: str

    def now_ns(self) -> int: ...


class MonotonicClock:
    def __init__(self):
        self.domain = f"process-monotonic-{uuid.uuid4()}"

    def now_ns(self) -> int:
        return time.monotonic_ns()


class ManualClock:
    """Deterministic simulation clock. Never sleeps or reports real GPU time."""

    def __init__(self, start_ns: int = 0):
        if not isinstance(start_ns, int) or start_ns < 0:
            raise ValueError("start_ns must be a nonnegative integer")
        self.domain = f"simulation-monotonic-{uuid.uuid4()}"
        self._now = start_ns

    def now_ns(self) -> int:
        return self._now

    def advance(self, seconds: float) -> None:
        self.advance_to(self._now + seconds_to_ns(seconds))

    def advance_to(self, timestamp_ns: int) -> None:
        if not isinstance(timestamp_ns, int) or timestamp_ns < self._now:
            raise ValueError("A monotonic clock cannot move backward")
        self._now = timestamp_ns


def seconds_to_ns(seconds: float) -> int:
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Duration must be finite and nonnegative")
    return round(seconds * 1_000_000_000)


@dataclass(frozen=True)
class TimingEvent:
    sequence: int
    name: str
    scope: str
    timestamp_ns: int
    clock_domain: str
    provenance: str
    status: str | None = None


class TimingRecorder:
    def __init__(self, clock: Clock, *, provenance: str):
        self.clock = clock
        self.provenance = provenance
        self._events: list[TimingEvent] = []
        self._spans: dict[tuple[str, str], tuple[int, int | None, str | None]] = {}
        self._capture_intervals: dict[str, list[tuple[int, int]]] = {}

    @property
    def events(self) -> tuple[TimingEvent, ...]:
        return tuple(self._events)

    def mark(self, name: str, scope: str, *, status: str | None = None) -> TimingEvent:
        now = self.clock.now_ns()
        if self._events and now < self._events[-1].timestamp_ns:
            raise ValueError("Event clock moved backward")
        event = TimingEvent(len(self._events), name, scope, now, self.clock.domain, self.provenance, status)
        self._events.append(event)
        return event

    def begin(self, phase: str, scope: str) -> None:
        if (scope, phase) in self._spans:
            raise ValueError(f"Phase already started: {scope}/{phase}")
        event = self.mark(f"{phase}_started", scope)
        self._spans[scope, phase] = event.timestamp_ns, None, None

    def end(self, phase: str, scope: str, *, status: str = "ok") -> None:
        if status not in {"ok", "failed", "cancelled"}:
            raise ValueError("Unsupported phase status")
        span = self._spans.get((scope, phase))
        if span is None or span[1] is not None:
            raise ValueError(f"Phase is not open: {scope}/{phase}")
        event = self.mark(f"{phase}_finished", scope, status=status)
        self._spans[scope, phase] = span[0], event.timestamp_ns, status

    def duration(self, phase: str, scope: str) -> float | None:
        span = self._spans.get((scope, phase))
        return (span[1] - span[0]) / 1e9 if span and span[1] is not None else None

    def confirm_capture_interval(self, scope: str, start_ns: int, end_ns: int,
                                 *, clock_domain: str) -> None:
        if clock_domain != self.clock.domain:
            raise ValueError("Cannot subtract timestamps across clock domains")
        if not (isinstance(start_ns, int) and isinstance(end_ns, int)
                and 0 <= start_ns <= end_ns <= self.clock.now_ns()):
            raise ValueError("Capture interval is invalid or extends into the future")
        self._capture_intervals.setdefault(scope, []).append((start_ns, end_ns))
        self.mark("capture_interval_confirmed", scope)

    def metrics(self, scope: str) -> dict:
        intervals = sorted(self._capture_intervals.get(scope, []))
        merged: list[list[int]] = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        phases = ("server_startup", "target_initialization", "workload_span", "shutdown",
                  "capture_control_window", "profile_process_wall", "report_finalization",
                  "stats_command", "summary_parse", "diagnosis_compute", "lifecycle_total")
        phases += ("evidence_collection",)
        result = {f"{phase}_s": self.duration(phase, scope) for phase in phases}
        result.update(
            capture_active_s=sum(end - start for start, end in merged) / 1e9 if intervals else None,
            capture_active_status="confirmed_intervals" if intervals else "unavailable",
            clock_domain=self.clock.domain, timing_provenance=self.provenance,
            timing_schema_version="timing_v1",
            phase_status={phase: self._spans.get((scope, phase), (None, None, None))[2] for phase in phases},
        )
        for name in ("evidence_ready", "decision_ready"):
            matches = [event.timestamp_ns for event in self._events if event.scope == scope and event.name == name]
            result[f"{name}_at_ns"] = matches[-1] if matches else None
        return result

    def jsonl(self) -> str:
        return "".join(json.dumps(asdict(event), allow_nan=False) + "\n" for event in self._events)
