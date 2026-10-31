"""CPU-compatible HTTP/response collectors and immutable measured windows.

No workload names or configured token lengths enter returned features. Server
collection currently supports one exact queue-depth gauge series only; interval
wait quantiles and prefill attribution are explicitly unsupported, never inferred.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import math
import re
import ssl
import statistics
from urllib.parse import urlsplit

from revision.tracing.aggregation import RequestCompletion, GpuSample, p95
from revision.tracing.measured_evidence import Acquisition, MeasuredMetric, METRICS, integer, identity, finite


async def http_body(endpoint, *, method='GET', payload=None, timeout_s=2, max_bytes=1048576):
    """Bounded nonstreaming HTTP/1.1 transport; all stages share one deadline."""
    url=urlsplit(endpoint)
    if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError('HTTP(S) endpoint without credentials/fragment required')
    integer(max_bytes,'max_bytes',1)
    if isinstance(timeout_s,bool) or not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError('Positive finite HTTP timeout required')
    if method not in ('GET','POST'):
        raise ValueError('Unsupported method')
    data=b'' if payload is None else json.dumps(payload,allow_nan=False).encode()
    async def exchange():
        writer=None
        try:
            port=url.port or (443 if url.scheme=='https' else 80)
            reader,writer=await asyncio.open_connection(url.hostname,port,
                ssl=ssl.create_default_context() if url.scheme=='https' else None)
            host=f'[{url.hostname}]' if ':' in url.hostname else url.hostname
            path=url.path or '/'
            if url.query:path+='?'+url.query
            writer.write((f'{method} {path} HTTP/1.1\r\nHost: {host}:{port}\r\n'
                f'Content-Type: application/json\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n').encode('ascii')+data)
            await writer.drain()
            header=(await reader.readuntil(b'\r\n\r\n')).decode('iso-8859-1')
            lines=header.split('\r\n');status=int(lines[0].split()[1]);headers={}
            for line in lines[1:]:
                if not line:continue
                key,value=line.split(':',1);key=key.lower()
                if key in headers:raise ValueError('Duplicate HTTP header')
                headers[key]=value.strip()
            if 'transfer-encoding' in headers or headers.get('content-type','').startswith('text/event-stream'):
                raise ValueError('Chunked/streaming responses unsupported')
            if 'content-length' in headers:
                size=int(headers['content-length'])
                if not 0 <= size <= max_bytes:raise ValueError('HTTP body exceeds limit')
                body=await reader.readexactly(size)
            else:
                body=bytearray()
                while True:
                    chunk=await reader.read(min(65536,max_bytes-len(body)+1))
                    if not chunk:break
                    body.extend(chunk)
                    if len(body)>max_bytes:raise ValueError('HTTP body exceeds limit')
                body=bytes(body)
            return status,body
        finally:
            if writer is not None:writer.close()
    return await asyncio.wait_for(exchange(),timeout_s)


@dataclass(frozen=True)
class ObservedCompletion:
    completion: RequestCompletion
    prompt_tokens: int | None
    output_tokens: int | None
    usage_error: str | None

    def __post_init__(self):
        if type(self.completion) is not RequestCompletion:
            raise ValueError('Typed completion required')
        for value in (self.prompt_tokens,self.output_tokens):
            if value is not None:integer(value,'observed token count')
        missing=self.prompt_tokens is None or self.output_tokens is None
        if missing != (self.usage_error is not None):
            raise ValueError('Missing token usage requires an explicit reason')
        if not self.completion.success and not missing:
            raise ValueError('Failed request cannot establish successful token usage')


def response_usage(body):
    """Extract reported actual usage, never prompt/config/max_tokens estimates."""
    try:
        data=json.loads(body)
        usage=data['usage'];prompt=usage['prompt_tokens'];output=usage['completion_tokens']
        integer(prompt,'prompt_tokens');integer(output,'completion_tokens')
        return prompt,output,None
    except (ValueError,TypeError,KeyError,UnicodeDecodeError):
        return None,None,'missing_or_invalid_response_usage'


async def collect_completion(clock, request_id, endpoint, payload, **http_options):
    start=clock.now_ns();success=False;error=None;prompt=output=None;usage_error='request_failed'
    try:
        status,body=await http_body(endpoint,method='POST',payload=payload,**http_options)
        success=200 <= status < 300
        if success:prompt,output,usage_error=response_usage(body)
        else:error=f'http_{status}'
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        error=type(exc).__name__
    end=clock.now_ns()
    return ObservedCompletion(RequestCompletion(request_id,start,end,end,clock.domain,success,error),
                              prompt,output,usage_error)


@dataclass(frozen=True)
class ServerSample:
    sample_id: str
    requested_at_ns: int
    received_at_ns: int
    clock_domain: str
    queue_depth: float | None
    error: str | None

    def __post_init__(self):
        identity(self.sample_id,'sample_id');identity(self.clock_domain,'clock_domain')
        integer(self.requested_at_ns,'requested_at_ns');integer(self.received_at_ns,'received_at_ns')
        if self.received_at_ns < self.requested_at_ns:raise ValueError('Invalid HTTP receipt order')
        if self.queue_depth is None:identity(self.error,'missing queue reason')
        else:
            finite(self.queue_depth,'queue_depth')
            if self.error is not None:raise ValueError('Measured queue value cannot carry an error')


class QueueGaugeCollector:
    """One configured exact text series; labels/order must match the endpoint.

    Not a full Prometheus/OpenMetrics parser. Reject duplicate matches, nonfinite
    values and explicit remote timestamps. Receipt time is not server event time.
    Endpoint/name/labels still require validation on the next GPU deployment.
    """
    def __init__(self,endpoint,series,**http_options):
        identity(series,'queue series')
        if re.fullmatch(r'[a-zA-Z_:][a-zA-Z0-9_:]*(?:\{[^{}\s]*\})?',series) is None:
            raise ValueError('Queue selector must be an exact metric/label series without whitespace')
        self.endpoint,self.series,self.options=endpoint,series,http_options
        self.pattern=re.compile(re.escape(series)+r'[ \t]+([^ \t]+)[ \t]*')

    async def sample(self,clock,sample_id):
        start=clock.now_ns();value=None;error=None
        try:
            status,body=await http_body(self.endpoint,**self.options)
            if not 200 <= status < 300:raise ValueError('metrics_http_status')
            candidates=[]
            lines=body.decode('utf-8').splitlines()
            metric_name=self.series.split('{',1)[0]
            types=[line.strip().split()[-1] for line in lines
                   if line.strip().startswith('# TYPE '+metric_name+' ')]
            if types != ['gauge']:raise ValueError('unsupported_or_missing_queue_gauge_type')
            for line in lines:
                line=line.strip()
                if not line or line.startswith('#'):continue
                if line.startswith(self.series) and len(line)>len(self.series) and line[len(self.series)].isspace():
                    match=self.pattern.fullmatch(line)
                    if match is None:raise ValueError('unsupported_series_or_remote_timestamp')
                    candidates.append(float(match.group(1)))
            if not candidates:raise ValueError('configured_series_missing')
            if len(candidates)!=1:raise ValueError('configured_series_ambiguous')
            finite(candidates[0],'queue_depth');value=candidates[0]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
        return ServerSample(sample_id,start,clock.now_ns(),clock.domain,value,error)


class FeatureWindow:
    """Single-loop, half-open receipt-audited window; close once after grace.

    A completion is assigned by completion time, samples by parent receipt. Set
    include_end only for the final horizon boundary, matching the existing raw
    adapter. Late/outside records are audited, never used to rewrite features.
    """
    def __init__(self,clock,start_ns,end_ns,*,min_latency_samples,grace_ns=0,include_end=False):
        Acquisition(start_ns,end_ns,end_ns,clock.domain)
        integer(grace_ns,'grace_ns');integer(min_latency_samples,'min_latency_samples',1)
        if type(include_end) is not bool:raise ValueError('include_end must be boolean')
        self.clock,self.start_ns,self.end_ns=clock,start_ns,end_ns
        self.deadline_ns=end_ns+grace_ns;self.minimum=min_latency_samples;self.include_end=include_end
        self.requests=[];self.server=[];self.gpu=[];self.events=[];self.seen=set();self.metrics=None
        self.closed_at_ns=None
        self.interval_metrics={}

    def _accept(self,kind,identity_,timestamp,available,domain):
        now=self.clock.now_ns()
        if domain != self.clock.domain or not timestamp <= available <= now:
            raise ValueError('Future evidence or unmapped acquisition clock')
        key=(kind,identity_)
        if key in self.seen:raise ValueError('Duplicate input identity')
        self.seen.add(key)
        inside=self.start_ns <= timestamp < self.end_ns or (self.include_end and timestamp==self.end_ns)
        reason='accepted'
        if not inside:reason='outside_interval'
        elif self.metrics is not None or now>self.deadline_ns:reason='late_receipt'
        self.events.append(dict(kind=kind,identity=identity_,received_at_ns=now,accepted=reason=='accepted',reason=reason))
        return reason=='accepted'

    def on_completion(self,record):
        if type(record) is not ObservedCompletion:raise ValueError('Typed observed completion required')
        r=record.completion
        if self._accept('request',r.request_id,r.end_ns,r.available_at_ns,r.clock_domain):
            self.requests.append(record);return True
        return False

    def on_server(self,record):
        if type(record) is not ServerSample:raise ValueError('Typed server sample required')
        if self._accept('server',record.sample_id,record.received_at_ns,record.received_at_ns,record.clock_domain):
            self.server.append(record);return True
        return False

    def on_gpu(self,record):
        if type(record) is not GpuSample:raise ValueError('Typed GPU sample required')
        if record.gpu_util is not None:finite(record.gpu_util,'gpu utilization')
        if self._accept('gpu',record.sample_id,record.timestamp_ns,record.available_at_ns,record.clock_domain):
            self.gpu.append(record);return True
        return False

    def on_interval_metric(self,record):
        """Accept only exact-window, already available instrumented statistics."""
        if type(record) is not MeasuredMetric or record.name not in ('request_wait_p95_ms','prefill_service_fraction'):
            raise ValueError('Typed supported interval metric required')
        a=record.acquisition;now=self.clock.now_ns()
        if (a.start_ns,a.end_ns,a.clock_domain)!=(self.start_ns,self.end_ns,self.clock.domain):
            raise ValueError('Interval metric does not match this window')
        a.require_visible(now,self.clock.domain)
        if self.metrics is not None or now>self.deadline_ns:raise ValueError('Closed/late interval metric')
        if record.name in self.interval_metrics:raise ValueError('Duplicate interval metric')
        self.interval_metrics[record.name]=record

    def close(self):
        if self.metrics is not None:return self.metrics
        now=self.clock.now_ns()
        if now < self.deadline_ns:raise ValueError('Window has not reached its closure deadline')
        stamp=Acquisition(self.start_ns,self.end_ns,now,self.clock.domain)
        result=[]
        def measured(name,values,attempts,reason):
            source,unit=METRICS[name]
            if values:
                value=p95(values) if name=='request_p95_ms' else statistics.fmean(values)
                result.append(MeasuredMetric(name,source,unit,value,len(values),attempts,
                    'complete' if len(values)==attempts else 'partial',None,stamp))
            else:result.append(MeasuredMetric(name,source,unit,None,0,attempts,'unavailable',reason,stamp))
        successes=[r for r in self.requests if r.completion.success]
        latency=[(r.completion.end_ns-r.completion.start_ns)/1e6 for r in successes]
        measured('request_p95_ms',latency if len(latency)>=self.minimum else [],len(self.requests),
                 'insufficient_successful_completions')
        # One closed-window successful-completion counter observation, even if zero.
        measured('completed_rps',[len(successes)/((self.end_ns-self.start_ns)/1e9)],1,'counter_unavailable')
        for name,attribute in [('prompt_tokens_mean','prompt_tokens'),('output_tokens_mean','output_tokens')]:
            values=[getattr(r,attribute) for r in successes if getattr(r,attribute) is not None]
            measured(name,values,len(successes),'no_valid_response_usage')
        measured('queue_depth_mean',[r.queue_depth for r in self.server if r.queue_depth is not None],
                 len(self.server),'no_valid_server_queue_samples')
        measured('gpu_util_mean',[r.gpu_util for r in self.gpu if r.gpu_util is not None],
                 len(self.gpu),'no_valid_gpu_samples')
        for name in ('request_wait_p95_ms','prefill_service_fraction'):
            if name in self.interval_metrics:result.append(self.interval_metrics[name])
            else:measured(name,[],0,'unsupported_interval_statistic_by_queue_gauge_collector')
        self.closed_at_ns=now;self.metrics=tuple(result)
        return self.metrics

    def audit(self):
        return dict(start_ns=self.start_ns,end_ns=self.end_ns,deadline_ns=self.deadline_ns,
            closed_at_ns=self.closed_at_ns,min_latency_samples=self.minimum,
            threshold_role='development_guard_not_calibrated',
            completion_count=len(self.requests),successful_completions=sum(r.completion.success for r in self.requests),
            request_errors=sum(not r.completion.success for r in self.requests),
            usage_missing=sum(r.usage_error is not None for r in self.requests),events=list(self.events),
            note='Completion-cohort features; pending admissions/censoring are recorded by the workload driver. Gauge means are sample means, not time-weighted means.')
