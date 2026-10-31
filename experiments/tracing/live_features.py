"""Pinned vLLM receipt mapping. Logger histograms are diagnostic sidecars only."""
import asyncio
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from experiments.feasibility.metrics import inspect, GAUGES
from experiments.tracing.feature_collection import FeatureWindow, ServerSample, http_body
from experiments.tracing.measured_evidence import (Acquisition, MeasuredObservation, PROVENANCES,
    fields_only, identity, integer)

VERSION = 'vllm_finished_cohort_mapping_v1'
UNSUPPORTED = {
    'request_wait_p95_ms': 'finished_request_logger_cohort_has_no_admission_window_clock_mapping',
    'prefill_service_fraction': 'request_phase_durations_do_not_partition_exclusive_GPU_service',
}


@dataclass(frozen=True)
class ServingBinding:
    session_nonce: str
    generation: int
    worker_pid: int
    device_uuid: str
    model: str
    engine: str
    clock_domain: str

    def __post_init__(self):
        for name in ('session_nonce', 'device_uuid', 'model', 'engine', 'clock_domain'):
            identity(getattr(self, name), name)
        integer(self.generation, 'generation'); integer(self.worker_pid, 'worker_pid', 1)
        if not self.device_uuid.startswith('GPU-'): raise ValueError('Explicit GPU UUID required')


@dataclass(frozen=True)
class MetricReceipt:
    sample_id: str
    binding: ServingBinding
    requested_at_ns: int
    received_at_ns: int
    http_status: int | None
    raw: bytes | None
    error: str | None

    def __post_init__(self):
        identity(self.sample_id, 'sample_id')
        if type(self.binding) is not ServingBinding: raise ValueError('Typed serving binding required')
        integer(self.requested_at_ns, 'requested_at_ns'); integer(self.received_at_ns, 'received_at_ns')
        if self.received_at_ns < self.requested_at_ns: raise ValueError('Reversed receipt clock')
        if self.http_status is not None:
            integer(self.http_status, 'http_status', 100)
            if self.http_status > 599: raise ValueError('Invalid HTTP status')
        if self.raw is not None and (type(self.raw) is not bytes or len(self.raw) > 1048576):
            raise ValueError('Bounded raw bytes required')
        if self.error is not None: identity(self.error, 'error')
        if self.error is None and (self.http_status != 200 or self.raw is None):
            raise ValueError('Unsuccessful collection needs an explicit error')


def map_receipt(receipt, binding, *, now_ns):
    if type(binding) is not ServingBinding or type(receipt) is not MetricReceipt or receipt.binding != binding:
        raise ValueError('Foreign worker/session/generation/series/clock receipt')
    integer(now_ns, 'now_ns')
    if receipt.received_at_ns > now_ns: raise ValueError('Future metric receipt')
    report = None; error = receipt.error; value = None
    if error is None:
        try:
            report = inspect(receipt.raw, model=binding.model, engine=binding.engine)
            gauge = report['gauges'][GAUGES[0]]
            if gauge['available']: value = gauge['value']
            else: error = gauge['reason']
        except (ValueError, TypeError, UnicodeError) as exc:
            error = 'invalid_metric_exposition:' + str(exc)
    sample = ServerSample(receipt.sample_id, receipt.requested_at_ns, receipt.received_at_ns,
                          binding.clock_domain, value, error)
    audit = dict(mapping_version=VERSION, sample_id=receipt.sample_id, binding=asdict(binding),
        requested_at_ns=receipt.requested_at_ns, received_at_ns=receipt.received_at_ns,
        raw_sha256=None if receipt.raw is None else hashlib.sha256(receipt.raw).hexdigest(),
        http_status=receipt.http_status, error=error, inspection=report,
        controller_mapping={'queue_depth_mean': 'receipt_assigned_unweighted_gauge_sample', **UNSUPPORTED},
        histogram_role='diagnostic_only_not_controller_features',
        source_event_clock_mapping=False)
    return sample, audit


class LiveMetricCollector:
    """Binding must come from independently verified owned-worker startup.

    HTTP does not authenticate worker identity. The caller must close/rebind this
    collector after any restart; it cannot discover a restart from metric bytes.
    """
    def __init__(self, endpoint, binding, **http_options):
        url = urlsplit(endpoint)
        if (url.scheme != 'http' or url.hostname not in ('127.0.0.1', 'localhost', '::1')
                or url.port is None or url.username or url.password or url.query or url.fragment):
            raise ValueError('Explicit loopback HTTP endpoint required')
        if type(binding) is not ServingBinding: raise ValueError('Typed binding required')
        self.endpoint, self.binding, self.options = endpoint, binding, http_options

    async def sample(self, clock, sample_id):
        if clock.domain != self.binding.clock_domain: raise ValueError('Collector clock differs from owned session')
        start = clock.now_ns(); status = raw = error = None
        try:
            status, raw = await http_body(self.endpoint, **self.options)
            if status != 200: error = 'metrics_http_' + str(status)
        except asyncio.CancelledError: raise
        except Exception as exc: error = type(exc).__name__ + ': ' + str(exc)
        return MetricReceipt(sample_id, self.binding, start, clock.now_ns(), status, raw, error)


def persist_receipt(root, receipt):
    """Exclusive immutable-name persistence; never replace a previous sample."""
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    name = hashlib.sha256(receipt.sample_id.encode()).hexdigest()
    data = {k: v for k, v in asdict(receipt).items() if k != 'raw'}
    data.update(version=VERSION, raw_path=None, raw_sha256=None)
    if receipt.raw is not None:
        data.update(raw_path=name + '.txt', raw_sha256=hashlib.sha256(receipt.raw).hexdigest())
        with (root/data['raw_path']).open('xb') as stream: stream.write(receipt.raw)
    with (root/(name + '.json')).open('x') as stream: json.dump(data, stream, indent=2)
    return name + '.json'


def load_receipt(root, path):
    root = Path(root).resolve()
    def bounded(relative):
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts: raise ValueError('Relative receipt artifact path required')
        target = root/p
        if target.is_symlink() or not target.resolve().is_relative_to(root): raise ValueError('Receipt path escape')
        if target.stat().st_size > 1048576: raise ValueError('Oversized receipt artifact')
        return target
    data = json.loads(bounded(path).read_text())
    fields_only(data, {'version', 'sample_id', 'binding', 'requested_at_ns', 'received_at_ns',
                      'http_status', 'error', 'raw_path', 'raw_sha256'})
    if data.pop('version') != VERSION: raise ValueError('Unsupported mapping version')
    raw_path = data.pop('raw_path'); expected = data.pop('raw_sha256')
    raw = None if raw_path is None else bounded(raw_path).read_bytes()
    if (None if raw is None else hashlib.sha256(raw).hexdigest()) != expected: raise ValueError('Raw metric hash mismatch')
    fields_only(data['binding'], ServingBinding.__dataclass_fields__)
    return MetricReceipt(**(data | {'binding': ServingBinding(**data['binding']), 'raw': raw}))


class LiveFeatureWindow(FeatureWindow):
    """Receipt-window gauges plus existing measured client/NVML inputs.

    Both unsupported statistics remain unavailable even when histograms exist.
    Complete sample coverage does not imply temporal or admission-cohort coverage.
    """
    def __init__(self, clock, start_ns, end_ns, *, binding, provenance, **options):
        if type(binding) is not ServingBinding or binding.clock_domain != clock.domain:
            raise ValueError('Window clock differs from serving binding')
        if provenance not in PROVENANCES: raise ValueError('Explicit provenance required')
        super().__init__(clock, start_ns, end_ns, **options)
        self.binding, self.provenance = binding, provenance
        self.receipt_audits = []; self.receipts = []

    def on_server(self, record): raise ValueError('Use bound raw metric receipts')
    def on_interval_metric(self, record): raise ValueError('Pinned live interval mapping is unsupported')

    def on_scrape(self, receipt):
        sample, audit = map_receipt(receipt, self.binding, now_ns=self.clock.now_ns())
        accepted = super().on_server(sample)
        self.receipt_audits.append(audit | {'accepted_into_window': accepted})
        self.receipts.append(receipt)
        return accepted

    def close(self):
        metrics = super().close()
        self.metrics = tuple(replace(m, missing_reason=UNSUPPORTED[m.name]) if m.name in UNSUPPORTED else m for m in metrics)
        return self.metrics

    def observation(self, observation_id):
        metrics = self.close()
        return MeasuredObservation(observation_id, self.provenance,
            Acquisition(self.start_ns, self.end_ns, self.closed_at_ns, self.clock.domain), metrics, None)

    def audit(self):
        return super().audit() | dict(mapping_version=VERSION, binding=asdict(self.binding),
            receipt_audits=self.receipt_audits, unsupported=dict(UNSUPPORTED),
            coverage_scope='accepted_records_only_not_planned_sample_completeness')

    def persist(self, root, observation_id):
        observation = self.observation(observation_id)
        root = Path(root); root.mkdir(parents=True, exist_ok=False)
        paths = [persist_receipt(root/'receipts', r) for r in self.receipts]
        (root/'observation.json').write_text(json.dumps(asdict(observation), indent=2)+'\n')
        (root/'window_audit.json').write_text(json.dumps(self.audit() | {'receipt_paths': paths}, indent=2)+'\n')
        files = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(root.rglob('*')) if p.is_file()}
        (root/'artifact_manifest.json').write_text(json.dumps(dict(files=files), indent=2)+'\n')
        return observation
