"""Observed streaming inputs. Workload truth has no place in this interface."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HealthyBaseline:
    p95_latency_ms: float
    source_id: str
    throughput_rps: float | None = None

    def __post_init__(self):
        if not math.isfinite(self.p95_latency_ms) or self.p95_latency_ms <= 0 or not self.source_id:
            raise ValueError("Supply a positive healthy p95 and its calibration source")
        if self.throughput_rps is not None and (not math.isfinite(self.throughput_rps) or self.throughput_rps <= 0):
            raise ValueError("Baseline throughput must be positive or unavailable")


@dataclass(frozen=True)
class CheapWindow:
    window_id: str
    start_ns: int
    end_ns: int
    available_at_ns: int
    clock_domain: str
    p95_latency_ms: float | None
    gpu_util: float | None
    sample_count: int
    throughput_rps: float | None = None
    request_count: int | None = None
    request_error_count: int | None = None
    gpu_sample_count: int | None = None
    outstanding_request_count: int | None = None
    oldest_pending_ms: float | None = None

    def __post_init__(self):
        if not self.window_id or not self.clock_domain:
            raise ValueError("Window and clock identities are required")
        if any(not isinstance(value, int) for value in (self.start_ns, self.end_ns, self.available_at_ns)):
            raise ValueError("Window timestamps must be integer nanoseconds")
        if not 0 <= self.start_ns < self.end_ns <= self.available_at_ns:
            raise ValueError("Window bounds and availability must be chronological")
        if not isinstance(self.sample_count, int) or self.sample_count < 0:
            raise ValueError("sample_count must be a nonnegative integer")
        for value in (self.p95_latency_ms, self.gpu_util, self.throughput_rps):
            if value is not None and (not math.isfinite(value) or value < 0):
                raise ValueError("Metrics must be finite/nonnegative or None")
        if self.p95_latency_ms is not None and (self.p95_latency_ms == 0 or not self.sample_count):
            raise ValueError("Latency requires a positive value and completed samples")
        if self.gpu_util is not None and self.gpu_util > 100:
            raise ValueError("GPU utilization must not exceed 100 percent")
        for value in (self.request_count, self.request_error_count, self.gpu_sample_count, self.outstanding_request_count):
            if value is not None and (not isinstance(value, int) or value < 0):
                raise ValueError("Observation counts must be nonnegative integers or unavailable")
        if self.request_count is not None and self.request_count != self.sample_count:
            raise ValueError("Latency sample count must equal observed completion count")
        if self.request_error_count is not None and (
                self.request_count is None or self.request_error_count > self.request_count):
            raise ValueError("Request errors require a compatible completion count")
        if self.gpu_sample_count == 0 and self.gpu_util is not None:
            raise ValueError("Zero valid GPU samples cannot establish GPU utilization")
        if self.oldest_pending_ms is not None and (
                not math.isfinite(self.oldest_pending_ms) or self.oldest_pending_ms < 0
                or not self.outstanding_request_count):
            raise ValueError("Pending age requires a finite age and observed outstanding requests")
