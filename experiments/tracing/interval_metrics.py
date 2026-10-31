"""Typed instrumented counter adapters; no inference from gauges/request names.

Snapshots require an independently established host clock/instance binding.
This is not a parser for an unvalidated server's Prometheus endpoint.
"""
from dataclasses import dataclass
import math
from experiments.tracing.measured_evidence import Acquisition, MeasuredMetric, METRICS, identity, integer, finite


@dataclass(frozen=True)
class CounterStamp:
    sample_id: str
    instance_id: str
    generation: str
    series: str
    sampled_at_ns: int
    available_at_ns: int
    clock_domain: str

    def __post_init__(self):
        for name in ('sample_id','instance_id','generation','series','clock_domain'):identity(getattr(self,name),name)
        integer(self.sampled_at_ns,'sampled_at_ns');integer(self.available_at_ns,'available_at_ns')
        if self.available_at_ns<self.sampled_at_ns:raise ValueError('Snapshot precedes acquisition')


@dataclass(frozen=True)
class WaitHistogram:
    stamp: CounterStamp
    upper_seconds: tuple
    cumulative_counts: tuple
    count: int
    semantics: str = 'queue_wait_seconds_observed_at_service_admission'

    def __post_init__(self):
        if type(self.stamp) is not CounterStamp or self.semantics!='queue_wait_seconds_observed_at_service_admission':
            raise ValueError('Explicit wait admission semantics and typed stamp required')
        if type(self.upper_seconds) is not tuple or type(self.cumulative_counts) is not tuple or len(self.upper_seconds)<2 or len(self.upper_seconds)!=len(self.cumulative_counts):
            raise ValueError('Immutable histogram with finite and infinity buckets required')
        if self.upper_seconds[-1]!=math.inf:raise ValueError('Final +Inf bucket required')
        previous=-1
        for bound in self.upper_seconds[:-1]:
            finite(bound,'bucket bound')
            if bound<=previous:raise ValueError('Strictly increasing buckets required')
            previous=bound
        integer(self.count,'histogram count')
        previous=0
        for count in self.cumulative_counts:
            integer(count,'bucket count')
            if count<previous:raise ValueError('Cumulative buckets must be monotonic')
            previous=count
        if previous!=self.count:raise ValueError('+Inf bucket/count mismatch')


@dataclass(frozen=True)
class PhaseCounters:
    stamp: CounterStamp
    prefill_ns: int
    decode_ns: int
    other_ns: int
    total_ns: int
    semantics: str = 'exclusive_attributed_service_time_ns'

    def __post_init__(self):
        if type(self.stamp) is not CounterStamp or self.semantics!='exclusive_attributed_service_time_ns':
            raise ValueError('Explicit exclusive phase attribution required')
        for name in ('prefill_ns','decode_ns','other_ns','total_ns'):integer(getattr(self,name),name)
        if self.prefill_ns+self.decode_ns+self.other_ns!=self.total_ns:
            raise ValueError('Phase durations must partition attributed service time')


def interval(previous,current,*,now_ns,clock_domain):
    a,b=previous.stamp,current.stamp
    integer(now_ns,'now_ns')
    if a.clock_domain!=b.clock_domain or b.clock_domain!=clock_domain:raise ValueError('Unmapped counter clock')
    if a.sample_id==b.sample_id or a.sampled_at_ns>=b.sampled_at_ns:raise ValueError('Repeated/out-of-order snapshots')
    if a.available_at_ns>b.available_at_ns or b.available_at_ns>now_ns:raise ValueError('Future/out-of-order receipt')
    stamp=Acquisition(a.sampled_at_ns,b.sampled_at_ns,b.available_at_ns,clock_domain)
    changed=(a.instance_id,a.generation,a.series)!=(b.instance_id,b.generation,b.series)
    return stamp,'counter_identity_or_generation_changed' if changed else None


def metric(name,stamp,value=None,reason=None,valid=0,attempted=1):
    source,unit=METRICS[name]
    return MeasuredMetric(name,source,unit,value,valid,attempted,
        'unavailable' if value is None else ('complete' if valid==attempted else 'partial'),reason,stamp)


def wait_p95(previous,current,*,now_ns,clock_domain,min_events=1):
    if type(previous) is not WaitHistogram or type(current) is not WaitHistogram:raise ValueError('Typed wait snapshots required')
    integer(min_events,'min_events',1)
    stamp,reason=interval(previous,current,now_ns=now_ns,clock_domain=clock_domain)
    if previous.upper_seconds!=current.upper_seconds:reason='histogram_schema_changed'
    if reason:return metric('request_wait_p95_ms',stamp,reason=reason)
    delta=tuple(b-a for a,b in zip(previous.cumulative_counts,current.cumulative_counts))
    if any(x<0 for x in delta):return metric('request_wait_p95_ms',stamp,reason='counter_reset_or_decrease')
    if any(a>b for a,b in zip(delta,delta[1:])):return metric('request_wait_p95_ms',stamp,reason='inconsistent_bucket_deltas')
    count=delta[-1]
    if count<min_events:return metric('request_wait_p95_ms',stamp,reason='insufficient_interval_observations',attempted=count)
    rank=.95*count;lower=0.;lower_count=0
    for upper,upper_count in zip(current.upper_seconds,delta):
        if upper_count>=rank:
            if not math.isfinite(upper):return metric('request_wait_p95_ms',stamp,reason='quantile_in_infinite_bucket',attempted=count)
            value=upper if upper==lower else lower+(upper-lower)*(rank-lower_count)/(upper_count-lower_count)
            return metric('request_wait_p95_ms',stamp,value=value*1000,valid=count,attempted=count)
        lower,lower_count=upper,upper_count
    raise AssertionError('Validated cumulative histogram has no quantile')


def prefill_fraction(previous,current,*,now_ns,clock_domain):
    if type(previous) is not PhaseCounters or type(current) is not PhaseCounters:raise ValueError('Typed attributed phase counters required')
    stamp,reason=interval(previous,current,now_ns=now_ns,clock_domain=clock_domain)
    if reason:return metric('prefill_service_fraction',stamp,reason=reason)
    delta=[getattr(current,n)-getattr(previous,n) for n in ('prefill_ns','decode_ns','other_ns','total_ns')]
    if any(x<0 for x in delta):return metric('prefill_service_fraction',stamp,reason='counter_reset_or_decrease')
    if not delta[-1]:return metric('prefill_service_fraction',stamp,reason='no_attributed_service_time')
    return metric('prefill_service_fraction',stamp,value=delta[0]/delta[-1],valid=1)


def phase_unavailable(acquisition,reason='phase_attribution_not_instrumented'):
    return metric('prefill_service_fraction',acquisition,reason=reason)
