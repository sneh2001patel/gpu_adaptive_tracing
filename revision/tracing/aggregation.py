"""Online, truth-free aggregation of completions and device samples.

Fixed observation horizon, fixed windows, explicit arrival grace. Windows are
half-open except the final horizon boundary, which belongs to the final window.
Closed windows never change; late records remain visible in the audit ledger.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import asdict, dataclass
from typing import Callable

from revision.tracing.timing import Clock, seconds_to_ns
from revision.tracing.windows import CheapWindow


def _timestamps(domain: str, *values: int) -> None:
    if not domain or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
        raise ValueError("A clock domain and nonnegative integer timestamps are required")


@dataclass(frozen=True)
class RequestStarted:
    request_id: str
    start_ns: int
    available_at_ns: int
    clock_domain: str

    def __post_init__(self):
        _timestamps(self.clock_domain, self.start_ns, self.available_at_ns)
        if not self.request_id or self.start_ns > self.available_at_ns:
            raise ValueError("Invalid request start")


@dataclass(frozen=True)
class RequestCompletion:
    request_id: str
    start_ns: int
    end_ns: int
    available_at_ns: int
    clock_domain: str
    success: bool
    error_kind: str | None = None

    def __post_init__(self):
        _timestamps(self.clock_domain, self.start_ns, self.end_ns, self.available_at_ns)
        if not self.request_id or not self.start_ns < self.end_ns <= self.available_at_ns:
            raise ValueError("Request completion needs a positive lifetime and valid availability")
        if not isinstance(self.success, bool) or (self.success and self.error_kind is not None):
            raise ValueError("Success must be boolean and cannot carry an error")


@dataclass(frozen=True)
class GpuSample:
    sample_id: str
    timestamp_ns: int
    available_at_ns: int
    clock_domain: str
    gpu_util: float | None

    def __post_init__(self):
        _timestamps(self.clock_domain, self.timestamp_ns, self.available_at_ns)
        if not self.sample_id or self.timestamp_ns > self.available_at_ns:
            raise ValueError("Invalid GPU sample time")
        if self.gpu_util is not None and (not math.isfinite(self.gpu_util) or not 0 <= self.gpu_util <= 100):
            raise ValueError("GPU utilization must be in [0, 100] or unavailable")


@dataclass(frozen=True)
class WindowConfig:
    start_ns: int
    horizon_ns: int
    window_s: float = 10.0
    allowed_lateness_s: float = 0.0
    window_prefix: str = "raw-window"
    require_request_starts: bool = False

    def __post_init__(self):
        _timestamps("configuration", self.start_ns, self.horizon_ns)
        if self.horizon_ns <= self.start_ns or seconds_to_ns(self.window_s) <= 0 or not self.window_prefix:
            raise ValueError("Configure a positive window and observation horizon")
        seconds_to_ns(self.allowed_lateness_s)
        if not isinstance(self.require_request_starts, bool):
            raise ValueError("require_request_starts must be boolean")


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.95
    lower, upper = math.floor(position), math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


class StreamingWindowAdapter:
    """Single-threaded ingestion adapter; serialize producer callbacks externally.

    Supply all arrivals at a timestamp before advance() closes equal-time
    deadlines. Data arriving after a deadline is dropped from control metrics,
    even if the producer supplied an earlier availability timestamp.
    """

    def __init__(self, clock: Clock, config: WindowConfig, on_window: Callable[[CheapWindow], None],
                 *, provenance: str):
        self.clock, self.config, self.on_window, self.provenance = clock, config, on_window, provenance
        self.width_ns = seconds_to_ns(config.window_s)
        self.grace_ns = seconds_to_ns(config.allowed_lateness_s)
        self.total_windows = (config.horizon_ns - config.start_ns + self.width_ns - 1) // self.width_ns
        self.next_index = 0
        self.finished = False
        self.delivery_failed = False
        self._requests: dict[int, list[RequestCompletion]] = {}
        self._samples: dict[int, list[GpuSample]] = {}
        self._seen_completions: set[str] = set()
        self._seen_samples: set[str] = set()
        self._seen_starts: set[str] = set()
        self._pending: dict[str, int] = {}
        self.tracked_admissions = 0
        self.untracked_completions = 0
        self.late_completions = 0
        self.late_samples = 0
        self.drain_completions = 0
        self.outside_completions = 0
        self.reports: list[dict] = []
        self.events: list[dict] = []

    def _check(self, record) -> int:
        if self.finished or self.delivery_failed:
            raise RuntimeError("Adapter is finished or its consumer failed")
        if record.clock_domain != self.clock.domain:
            raise ValueError("Raw event uses a different clock domain")
        now = self.clock.now_ns()
        if record.available_at_ns > now:
            raise ValueError("Raw event is not available yet")
        return now

    def _log(self, event: str, **details) -> None:
        self.events.append(dict(sequence=len(self.events), event=event,
                                timestamp_ns=self.clock.now_ns(), clock_domain=self.clock.domain,
                                provenance=self.provenance, **details))

    def _index(self, timestamp_ns: int) -> int | None:
        if not self.config.start_ns <= timestamp_ns <= self.config.horizon_ns:
            return None
        return min((timestamp_ns - self.config.start_ns) // self.width_ns, self.total_windows - 1)

    def _bounds(self, index: int) -> tuple[int, int]:
        start = self.config.start_ns + index * self.width_ns
        return start, min(start + self.width_ns, self.config.horizon_ns)

    def on_request_started(self, record: RequestStarted) -> bool:
        received = self._check(record)
        if record.request_id in self._seen_starts or record.request_id in self._seen_completions:
            raise ValueError("Request start is duplicate or arrives after completion")
        self._close_due(received, inclusive=False)
        self._seen_starts.add(record.request_id)
        accepted = record.start_ns < self.config.horizon_ns
        if accepted:
            self._pending[record.request_id] = record.start_ns
            self.tracked_admissions += 1
        self._log("request_started", accepted=accepted, received_at_ns=received, record=asdict(record))
        return accepted

    def on_request_completed(self, record: RequestCompletion) -> bool:
        received = self._check(record)
        if record.request_id in self._seen_completions:
            raise ValueError("Duplicate request completion")
        tracked = record.request_id in self._pending
        if tracked and self._pending[record.request_id] != record.start_ns:
            raise ValueError("Request completion disagrees with its observed start")
        if not tracked and self.config.require_request_starts:
            raise ValueError("An observed start is required before completion")
        self._close_due(received, inclusive=False)
        self._seen_completions.add(record.request_id)
        if tracked:
            del self._pending[record.request_id]
        else:
            self.untracked_completions += 1
        index = self._index(record.end_ns)
        if index is None:
            if record.end_ns > self.config.horizon_ns and record.start_ns < self.config.horizon_ns:
                self.drain_completions += 1
                status = "drain_completion"
            else:
                self.outside_completions += 1
                status = "outside_observation"
        elif index < self.next_index:
            self.late_completions += 1
            status = "late_completion"
        else:
            self._requests.setdefault(index, []).append(record)
            status = "accepted_completion"
        self._log(status, received_at_ns=received, record=asdict(record))
        return status == "accepted_completion"

    def on_gpu_sample(self, record: GpuSample) -> bool:
        received = self._check(record)
        if record.sample_id in self._seen_samples:
            raise ValueError("Duplicate GPU sample")
        self._close_due(received, inclusive=False)
        self._seen_samples.add(record.sample_id)
        index = self._index(record.timestamp_ns)
        if index is None:
            status = "outside_observation_sample"
        elif index < self.next_index:
            self.late_samples += 1
            status = "late_gpu_sample"
        else:
            self._samples.setdefault(index, []).append(record)
            status = "accepted_gpu_sample"
        self._log(status, received_at_ns=received, record=asdict(record))
        return status == "accepted_gpu_sample"

    def _emit(self, index: int) -> None:
        start, end = self._bounds(index)
        requests = self._requests.pop(index, [])
        samples = self._samples.pop(index, [])
        latencies = [(record.end_ns - record.start_ns) / 1e6 for record in requests]
        utils = [record.gpu_util for record in samples if record.gpu_util is not None]
        errors = sum(not record.success for record in requests)
        successful = len(requests) - errors
        duration_s = (end - start) / 1e9
        pending = [timestamp for timestamp in self._pending.values() if timestamp < end]
        window = CheapWindow(
            window_id=f"{self.config.window_prefix}-{index}", start_ns=start, end_ns=end,
            available_at_ns=self.clock.now_ns(), clock_domain=self.clock.domain,
            p95_latency_ms=p95(latencies), gpu_util=statistics.fmean(utils) if utils else None,
            sample_count=len(requests), throughput_rps=successful / duration_s,
            request_count=len(requests), request_error_count=errors, gpu_sample_count=len(utils),
            outstanding_request_count=len(pending),
            oldest_pending_ms=(end - min(pending)) / 1e6 if pending else None,
        )
        self.next_index += 1
        report = dict(window=asdict(window), partial_window=end - start < self.width_ns,
                      gpu_sample_records=len(samples), successful_requests=successful,
                      completed_throughput_rps=len(requests) / duration_s,
                      request_ids=[record.request_id for record in requests],
                      gpu_sample_ids=[record.sample_id for record in samples],
                      latency_population="all_observed_completions_including_errors",
                      throughput_population="successful_completions_per_second",
                      final_boundary_inclusive=index == self.total_windows - 1)
        self.reports.append(report)
        self._log("window_emitted", window_id=window.window_id)
        try:
            self.on_window(window)
        except Exception:
            self.delivery_failed = True
            self._log("window_delivery_failed", window_id=window.window_id)
            raise

    def _close_due(self, cutoff_ns: int, *, inclusive: bool) -> None:
        while self.next_index < self.total_windows:
            deadline = self._bounds(self.next_index)[1] + self.grace_ns
            if deadline > cutoff_ns or (deadline == cutoff_ns and not inclusive):
                break
            self._emit(self.next_index)

    def next_wakeup_ns(self) -> int | None:
        if self.finished or self.delivery_failed or self.next_index == self.total_windows:
            return None
        return max(self.clock.now_ns(), self._bounds(self.next_index)[1] + self.grace_ns)

    def advance(self) -> None:
        if self.finished or self.delivery_failed:
            raise RuntimeError("Adapter is finished or its consumer failed")
        self._close_due(self.clock.now_ns(), inclusive=True)

    def finish(self) -> dict:
        if self.finished:
            return self.summary()
        if self.clock.now_ns() < self.config.horizon_ns + self.grace_ns:
            raise ValueError("Observation horizon and arrival grace have not elapsed")
        self.advance()
        self.finished = True
        self._log("adapter_finished", outstanding_tracked_requests=len(self._pending))
        return self.summary()

    def summary(self) -> dict:
        return dict(adapter_version="aggregation_v1", config=asdict(self.config),
                    clock_domain=self.clock.domain, provenance=self.provenance,
                    finished=self.finished, delivery_failed=self.delivery_failed,
                    emitted_windows=len(self.reports), completed_records_seen=len(self._seen_completions),
                    gpu_records_seen=len(self._seen_samples), tracked_admissions=self.tracked_admissions,
                    untracked_completions=self.untracked_completions, late_completions=self.late_completions,
                    late_gpu_samples=self.late_samples, drain_completions=self.drain_completions,
                    outside_completions=self.outside_completions,
                    outstanding_tracked_requests=[dict(request_id=key, start_ns=value)
                                                  for key, value in sorted(self._pending.items())],
                    censoring_scope="observed_starts_only; unregistered requests cannot be counted",
                    control_latency_scope="observed_completion_windows; not a censoring-corrected SLO estimate")

    def jsonl(self) -> str:
        return "".join(json.dumps(event, allow_nan=False) + "\n" for event in self.events)
