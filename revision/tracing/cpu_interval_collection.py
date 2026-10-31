"""Owned CPU history-source binding. Not a live vLLM/Prometheus adapter."""
import asyncio
from dataclasses import dataclass,replace
import hashlib,json

from revision.tracing.arm_session import CpuTargetSession
from revision.tracing.feature_collection import http_body
from revision.tracing.interval_metrics import CounterStamp,WaitHistogram,wait_p95,metric,phase_unavailable
from revision.tracing.measured_evidence import Acquisition,fields_only,integer
from revision.tracing.arrival_schedule import unique_object


@dataclass(frozen=True)
class IntervalReceipt:
    window_id: str
    metrics: tuple
    requested_at_ns: int
    received_at_ns: int
    error: str | None


class CpuIntervalCollector:
    def __init__(self,session):
        if type(session) is not CpuTargetSession:raise ValueError('Owned CPU target required')
        self.session=session;self.clock=session.clock;self.binding=None;self.receipts=[]

    async def bind(self):
        if not self.session.interval_recording:raise ValueError('Interval source disabled for this arm')
        before=self.clock.now_ns();record=await self.session.command('/clock');after=self.clock.now_ns()
        if record.get('clock_name')!='time.monotonic_ns' or record.get('clock_domain')!=self.clock.domain:
            raise ValueError('CPU clock binding mismatch')
        integer(record.get('probe_ns'),'clock probe')
        if not before<=record['probe_ns']<=after:raise ValueError('Source clock probe outside parent bracket')
        self.binding=dict(requested_at_ns=before,received_at_ns=after,source=record,
            scope='owned_same_host_CPU_process_only_not_remote_or_GPU_clock_mapping')

    def parse(self,data,start,end,received,identity):
        self.session.validate(data)
        if data.get('interval_schema')!='cpu_admission_history_v1' or data.get('clock_name')!='time.monotonic_ns' or data.get('clock_domain')!=self.clock.domain:
            raise ValueError('Interval schema/clock mismatch')
        if data.get('semantics')!='queue_wait_seconds_observed_at_service_admission' or data.get('phase_attribution')!='not_instrumented':
            raise ValueError('Unsupported source semantics')
        if data.get('history_complete') is not True:raise ValueError('Incomplete source history')
        integer(data.get('collected_at_ns'),'collection timestamp');integer(data.get('epoch_ns'),'source epoch')
        if not data['epoch_ns']<=start<end<=data['collected_at_ns']<=received:raise ValueError('Invalid source collection bounds')
        bounds=data['upper_seconds']
        if type(bounds) is not list or not bounds or bounds[-1]!='+Inf':raise ValueError('Explicit +Inf histogram required')
        bounds=tuple(bounds[:-1])+ (float('inf'),)
        snapshots=[]
        for index,key,boundary in ((0,'previous',start),(1,'current',end)):
            raw=data[key];fields_only(raw,{'sampled_at_ns','generation','cumulative_counts','count'})
            if raw['sampled_at_ns']!=boundary:raise ValueError('As-of interval boundary mismatch')
            if raw['generation']!=str(self.session.generation):raise ValueError('Counter reset generation mismatch')
            if type(raw['cumulative_counts']) is not list:raise ValueError('Histogram counts must be a JSON list')
            stamp=CounterStamp(identity+':'+str(index),self.session.instance,raw['generation'],'cpu_wait_admission',boundary,received,self.clock.domain)
            snapshots.append(WaitHistogram(stamp,bounds,tuple(raw['cumulative_counts']),raw['count']))
        return wait_p95(*snapshots,now_ns=received,clock_domain=self.clock.domain)

    async def collect(self,clock,identity,start,end):
        if clock is not self.clock or self.binding is None:raise ValueError('Collector clock binding absent')
        requested=clock.now_ns();raw=None;data=None;error=None;wait=None
        try:
            if self.binding['source']['generation']!=self.session.generation:raise ValueError('Clock/source binding predates reset generation')
            status,raw=await http_body(self.session.endpoint+'/interval',method='POST',
                payload=dict(nonce=self.session.nonce,start_ns=start,end_ns=end),timeout_s=self.session.config.command_timeout_s)
            received=clock.now_ns()
            if status!=200:raise ValueError('Interval HTTP status '+str(status))
            data=json.loads(raw,object_pairs_hook=unique_object)
            wait=self.parse(data,start,end,received,identity)
        except asyncio.CancelledError:
            self.receipts.append(dict(window_id=identity,requested_at_ns=requested,received_at_ns=clock.now_ns(),error='cancelled',raw=None))
            raise
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        received=clock.now_ns();stamp=Acquisition(start,end,received,clock.domain)
        if wait is None:wait=metric('request_wait_p95_ms',stamp,reason='interval_source_error:'+error)
        else:wait=replace(wait,acquisition=stamp)
        result=IntervalReceipt(identity,(wait,phase_unavailable(stamp)),requested,received,error)
        self.receipts.append(dict(window_id=identity,requested_at_ns=requested,received_at_ns=received,error=error,
            raw=None if raw is None else raw.decode('utf-8',errors='replace'),
            raw_sha256=None if raw is None else hashlib.sha256(raw).hexdigest()))
        return result

    def snapshot(self):return dict(binding=self.binding,receipts=list(self.receipts),source='cpu_admission_history_v1')
