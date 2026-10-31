"""Strict measured-only contracts. No workload truth or GPU imports.

Interval timestamps describe acquisition/aggregation in the supplied host domain;
they do not establish GPU capture-active boundaries or NVML averaging intervals.
"""
from dataclasses import dataclass
import math

VERSION = 'measured_evidence_v1'
METRICS = {
    'request_p95_ms': ('request', 'ms'),
    'completed_rps': ('request', 'requests/s'),
    'prompt_tokens_mean': ('request', 'tokens'),
    'output_tokens_mean': ('request', 'tokens'),
    'queue_depth_mean': ('server', 'requests'),
    'request_wait_p95_ms': ('server', 'ms'),
    'prefill_service_fraction': ('server', 'fraction'),
    'gpu_util_mean': ('gpu', 'percent'),
}
PROVENANCES = {'synthetic_simulation', 'live_online'}


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}')


def identity(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be nonempty text')


def fields_only(data, required):
    if type(data) is not dict or set(data) != set(required):
        raise ValueError(f'Expected exactly these fields: {sorted(required)}')


def finite(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and nonnegative')


@dataclass(frozen=True)
class Acquisition:
    start_ns: int
    end_ns: int
    available_at_ns: int
    clock_domain: str

    def __post_init__(self):
        for key in ('start_ns', 'end_ns', 'available_at_ns'):
            integer(getattr(self, key), key)
        identity(self.clock_domain, 'clock_domain')
        if not self.start_ns < self.end_ns <= self.available_at_ns:
            raise ValueError('Acquisition must precede availability')

    @classmethod
    def from_dict(cls, data):
        fields_only(data, cls.__dataclass_fields__)
        return cls(**data)

    def require_visible(self, now_ns, clock_domain):
        integer(now_ns, 'now_ns')
        if clock_domain != self.clock_domain:
            raise ValueError('Unmapped clock domain')
        if now_ns < self.available_at_ns:
            raise ValueError('Evidence is not available at decision time')


@dataclass(frozen=True)
class MeasuredMetric:
    name: str
    source: str
    unit: str
    value: float | None
    valid_samples: int
    attempted_samples: int
    coverage: str
    missing_reason: str | None
    acquisition: Acquisition

    def __post_init__(self):
        if self.name not in METRICS or (self.source, self.unit) != METRICS[self.name]:
            raise ValueError('Unsupported metric/source/unit')
        if type(self.acquisition) is not Acquisition:
            raise ValueError('Typed acquisition required')
        integer(self.valid_samples, 'valid_samples')
        integer(self.attempted_samples, 'attempted_samples')
        if self.valid_samples > self.attempted_samples:
            raise ValueError('Valid samples exceed attempts')
        if self.value is None:
            if self.coverage != 'unavailable' or self.valid_samples != 0:
                raise ValueError('Missing measurements cannot claim valid coverage')
            identity(self.missing_reason, 'missing_reason')
        else:
            finite(self.value, 'metric value')
            if not self.valid_samples or self.missing_reason is not None:
                raise ValueError('Measured values require samples and no missing reason')
            expected = 'complete' if self.valid_samples == self.attempted_samples else 'partial'
            if self.coverage != expected:
                raise ValueError('Coverage does not match sample accounting')
            if self.unit == 'percent' and self.value > 100 or self.unit == 'fraction' and self.value > 1:
                raise ValueError('Metric outside its unit range')
            if self.name == 'request_p95_ms' and self.value == 0:
                raise ValueError('Completed request latency must be positive')

    @classmethod
    def from_dict(cls, data):
        fields_only(data, cls.__dataclass_fields__)
        return cls(**(data | {'acquisition': Acquisition.from_dict(data['acquisition'])}))


@dataclass(frozen=True)
class KernelObservation:
    capture_id: str
    evidence_id: str
    device_uuid: str
    worker_pids: tuple[int, ...]
    kernel_count: int
    kernel_time_sum_s: float
    coverage: str
    acquisition: Acquisition

    def __post_init__(self):
        for key in ('capture_id', 'evidence_id', 'device_uuid'):
            identity(getattr(self, key), key)
        if not self.device_uuid.startswith('GPU-'):
            raise ValueError('Explicit physical GPU UUID required')
        if type(self.worker_pids) is not tuple or len(self.worker_pids) != 1:
            raise ValueError('Only single-worker coverage is supported')
        integer(self.worker_pids[0], 'worker PID', 1)
        integer(self.kernel_count, 'kernel_count', 1)
        finite(self.kernel_time_sum_s, 'kernel_time_sum_s')
        if self.kernel_time_sum_s == 0 or self.coverage != 'single_configured_worker_and_device_verified':
            raise ValueError('Positive kernels and verified single-worker coverage required')
        if type(self.acquisition) is not Acquisition:
            raise ValueError('Typed acquisition required')

    @classmethod
    def from_dict(cls, data):
        fields_only(data, cls.__dataclass_fields__)
        if type(data['worker_pids']) is not list:
            raise ValueError('worker_pids must be a JSON list')
        return cls(**(data | {'worker_pids': tuple(data['worker_pids']),
                             'acquisition': Acquisition.from_dict(data['acquisition'])}))


@dataclass(frozen=True)
class MeasuredObservation:
    observation_id: str
    provenance: str
    acquisition: Acquisition
    metrics: tuple[MeasuredMetric, ...]
    kernel: KernelObservation | None

    def __post_init__(self):
        identity(self.observation_id, 'observation_id')
        if self.provenance not in PROVENANCES or type(self.acquisition) is not Acquisition:
            raise ValueError('Explicit provenance and typed acquisition required')
        if type(self.metrics) is not tuple or any(type(m) is not MeasuredMetric for m in self.metrics):
            raise ValueError('Typed immutable metrics required')
        if len({m.name for m in self.metrics}) != len(self.metrics):
            raise ValueError('Duplicate measured metric')
        for metric in self.metrics:
            stamp=metric.acquisition
            if (stamp.clock_domain, stamp.start_ns, stamp.end_ns) != (
                    self.acquisition.clock_domain, self.acquisition.start_ns, self.acquisition.end_ns):
                raise ValueError('Metric belongs to a different acquisition interval/domain')
            if stamp.available_at_ns > self.acquisition.available_at_ns:
                raise ValueError('Bundle cannot precede its metrics')
        if self.kernel is not None:
            if type(self.kernel) is not KernelObservation:
                raise ValueError('Typed kernel observation required')
            stamp=self.kernel.acquisition
            if stamp.clock_domain != self.acquisition.clock_domain or not (
                    self.acquisition.start_ns <= stamp.start_ns < stamp.end_ns <= self.acquisition.end_ns):
                raise ValueError('Kernel acquisition must be inside the observation in its clock domain')
            if stamp.available_at_ns > self.acquisition.available_at_ns:
                raise ValueError('Bundle cannot precede parsed kernel evidence')

    @classmethod
    def from_dict(cls, data):
        fields_only(data, cls.__dataclass_fields__)
        if type(data['metrics']) is not list:
            raise ValueError('metrics must be a JSON list')
        return cls(**(data | {'acquisition': Acquisition.from_dict(data['acquisition']),
            'metrics': tuple(MeasuredMetric.from_dict(m) for m in data['metrics']),
            'kernel': None if data['kernel'] is None else KernelObservation.from_dict(data['kernel'])}))

    def require_visible(self, now_ns, clock_domain):
        self.acquisition.require_visible(now_ns, clock_domain)
