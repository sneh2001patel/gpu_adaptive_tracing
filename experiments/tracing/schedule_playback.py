"""Bounded exact-arrival playback with one serialized feature-window owner.

CPU fixtures exercise this driver. It neither launches serving/profiler sessions
nor implements experimental arm/reset logic. Request/sample workers only publish
receipts; the owner makes admissions, closes windows and services evidence hooks.
"""
import asyncio
from dataclasses import asdict, dataclass
import math

from experiments.tracing.aggregation import GpuSample, RequestCompletion
from experiments.tracing.arrival_schedule import ArrivalSchedule
from experiments.tracing.feature_collection import (ObservedCompletion, ServerSample, FeatureWindow, collect_completion)
from experiments.tracing.measured_evidence import integer, finite, PROVENANCES
from experiments.tracing.timing import seconds_to_ns
from experiments.tracing.cpu_interval_collection import IntervalReceipt
from experiments.tracing.interval_metrics import metric,phase_unavailable
from experiments.tracing.measured_evidence import Acquisition


@dataclass(frozen=True)
class PlaybackConfig:
    max_inflight: int = 8
    request_timeout_s: float = 2
    drain_s: float = .5
    max_admission_lateness_s: float = .02
    window_s: float = .1
    grace_s: float = .01
    min_latency_samples: int = 2
    sample_interval_s: float = .02
    sample_timeout_s: float = .2
    telemetry_queue_size: int = 64
    tick_s: float = .001

    def __post_init__(self):
        for key in ('max_inflight','min_latency_samples','telemetry_queue_size'):
            integer(getattr(self,key),key,1)
        for key in ('request_timeout_s','window_s','sample_interval_s','sample_timeout_s','tick_s'):
            value=getattr(self,key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or seconds_to_ns(value)<=0:
                raise ValueError('Positive finite playback durations required')
        for key in ('drain_s','max_admission_lateness_s','grace_s'):
            value=getattr(self,key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
                raise ValueError('Nonnegative finite playback durations required')


class SchedulePlayback:
    def __init__(self,schedule,clock,endpoint,*,provenance,config=None,server_collector=None,gpu_sampler=None,
                 on_window=None,service_evidence=None,interval_collector=None,window_factory=None,completion_collector=None):
        if type(schedule) is not ArrivalSchedule or provenance not in PROVENANCES:
            raise ValueError('Validated schedule and explicit provenance required')
        self.schedule,self.clock,self.endpoint=schedule,clock,endpoint
        self.provenance,self.config=provenance,config or PlaybackConfig()
        self.server_collector,self.gpu_sampler=server_collector,gpu_sampler
        self.on_window,self.service_evidence=on_window,service_evidence
        self.window_factory,self.completion_collector=window_factory,completion_collector
        self.interval_collector=interval_collector;self.interval_task=None
        self.interval_receipts=asyncio.Queue(maxsize=self.config.telemetry_queue_size)
        self.interval_audit=[];self.interval_errors=0
        self.terminals=asyncio.Queue(maxsize=self.config.max_inflight)
        self.telemetry=asyncio.Queue(maxsize=self.config.telemetry_queue_size)
        self.inflight={};self.started=set();self.cancel_reasons={};self.sampling=[]
        self.ledger={};self.windows=[];self.closed=set();self.events=[];self.raw=[];self.drops=[]
        self.sampling_skips={'server':0,'gpu':0};self.sampling_cancelled={'server':0,'gpu':0}
        self.sampling_errors={'server':0,'gpu':0}
        self.next_offer=0;self.peak=0;self.used=False;self.status='not_started';self.failure=None
        self.start_ns=self.horizon_ns=self.finished_at_ns=None;self.observed_horizon=None

    def _log(self,event,**details):
        self.events.append(dict(sequence=len(self.events),event=event,received_at_ns=self.clock.now_ns(),**details))

    def _censored(self,request_id,reason):
        row=self.ledger[request_id];now=self.clock.now_ns()
        return ObservedCompletion(RequestCompletion(request_id,row['admitted_at_ns'],now,now,self.clock.domain,
            False,reason),None,None,reason)

    async def _request(self,arrival):
        self.started.add(arrival.request_id)
        try:
            record=await (self.completion_collector or collect_completion)(self.clock,arrival.request_id,self.endpoint,arrival.payload,
                                            timeout_s=self.config.request_timeout_s)
        except asyncio.CancelledError:
            record=self._censored(arrival.request_id,self.cancel_reasons.get(arrival.request_id,'run_cancelled'))
        except Exception as exc:
            record=self._censored(arrival.request_id,'worker_error:'+type(exc).__name__)
        # Reserved terminal capacity: each admitted ID owns one slot until the
        # owner consumes it, and admissions cannot exceed max_inflight. No await
        # here can turn a completed response into a cancellation or lose a receipt.
        self.terminals.put_nowait(record)

    async def _sample(self,kind):
        index=0;interval=seconds_to_ns(self.config.sample_interval_s);due=self.start_ns
        while due<self.horizon_ns:
            await asyncio.sleep(max(0,(due-self.clock.now_ns())/1e9))
            now=self.clock.now_ns()
            if now>=self.horizon_ns:break
            missed=(now-due)//interval;self.sampling_skips[kind]+=missed;due+=(missed+1)*interval
            identity=f'{kind}-{index}';index+=1;requested=self.clock.now_ns()
            try:
                if kind=='server':
                    record=await asyncio.wait_for(self.server_collector.sample(self.clock,identity),self.config.sample_timeout_s)
                    if type(record) is not ServerSample:raise ValueError('Server collector returned untyped sample')
                else:
                    value=await asyncio.wait_for(self.gpu_sampler(),self.config.sample_timeout_s)
                    if value is not None:finite(value,'GPU callback value')
                    now=self.clock.now_ns();record=GpuSample(identity,now,now,self.clock.domain,value)
            except asyncio.CancelledError:
                self.sampling_cancelled[kind]+=1
                raise
            except Exception as exc:
                now=self.clock.now_ns()
                record=ServerSample(identity,requested,now,self.clock.domain,None,type(exc).__name__) if kind=='server' else GpuSample(identity,now,now,self.clock.domain,None)
            missing=record.queue_depth is None if kind=='server' else record.gpu_util is None
            if missing:self.sampling_errors[kind]+=1
            try:self.telemetry.put_nowait(record)
            except asyncio.QueueFull:
                self.drops.append(dict(kind=kind,reason='telemetry_queue_full',record=asdict(record),received_at_ns=self.clock.now_ns()))

    async def _sample_intervals(self):
        # Sequential, bounded work. Source supports exact as-of snapshots; no
        # receipt timestamps are relabeled as acquisition boundaries.
        for index,window in enumerate(self.windows):
            await asyncio.sleep(max(0,(window.end_ns-self.clock.now_ns())/1e9))
            identity=f'window-{index}';requested=self.clock.now_ns()
            try:
                receipt=await asyncio.wait_for(self.interval_collector.collect(self.clock,identity,
                    window.start_ns,window.end_ns),self.config.sample_timeout_s)
                if type(receipt) is not IntervalReceipt or receipt.window_id!=identity:
                    raise ValueError('Invalid interval receipt identity/type')
            except asyncio.CancelledError:raise
            except Exception as exc:
                self.interval_errors+=1;now=self.clock.now_ns()
                stamp=Acquisition(window.start_ns,window.end_ns,now,self.clock.domain)
                receipt=IntervalReceipt(identity,(metric('request_wait_p95_ms',stamp,reason='interval_collection_error:'+type(exc).__name__),
                    phase_unavailable(stamp)),requested,now,type(exc).__name__)
            await self.interval_receipts.put(receipt)

    def _consume_intervals(self):
        for _ in range(self.interval_receipts.qsize()):
            receipt=self.interval_receipts.get_nowait();index=int(receipt.window_id.split('-')[1]);window=self.windows[index]
            for measured in receipt.metrics:
                accepted=False;reason=None
                try:window.on_interval_metric(measured);accepted=True
                except ValueError as exc:reason=str(exc)
                self.interval_audit.append(dict(window_id=receipt.window_id,owner_received_at_ns=self.clock.now_ns(),
                    requested_at_ns=receipt.requested_at_ns,received_at_ns=receipt.received_at_ns,
                    collection_error=receipt.error,accepted=accepted,rejection_reason=reason,metric=asdict(measured)))

    def _route(self,record):
        if type(record) is ObservedCompletion:
            timestamp=record.completion.end_ns;method='on_completion'
        elif type(record) is ServerSample:
            timestamp=record.received_at_ns;method='on_server'
        else:timestamp=record.timestamp_ns;method='on_gpu'
        window_id=None;accepted=False
        if self.start_ns<=timestamp<=self.horizon_ns:
            index=min((timestamp-self.start_ns)//seconds_to_ns(self.config.window_s),len(self.windows)-1)
            window=self.windows[index];window_id=f'window-{index}'
            accepted=getattr(window,method)(record)
        self.raw.append(dict(type=type(record).__name__,received_at_ns=self.clock.now_ns(),
            window_id=window_id,accepted=accepted,record=asdict(record)))

    def _consume(self):
        for _ in range(self.terminals.qsize()):
            record=self.terminals.get_nowait();r=record.completion;row=self.ledger[r.request_id]
            if row['state']!='admitted':raise ValueError('Unexpected/duplicate request terminal')
            if r.error_kind in ('drain_cancelled','run_cancelled'):state='censored'
            else:state='completed' if r.success else 'failed'
            row.update(state=state,terminal=asdict(record),terminal_received_at_ns=self.clock.now_ns())
            self.inflight.pop(r.request_id)
            self._route(record)
        # Snapshot-sized batches prevent telemetry from starving admission/deadlines.
        for _ in range(self.telemetry.qsize()):self._route(self.telemetry.get_nowait())

    def _close_due(self,*,notify=True):
        for index,window in enumerate(self.windows):
            if index not in self.closed and self.clock.now_ns()>=window.deadline_ns:
                window.close();self.closed.add(index)
                self._log('window_closed',window_id=f'window-{index}',
                    outstanding_admitted_ids=[i for i,r in self.ledger.items() if r['state']=='admitted'])
                if notify and self.on_window is not None:self.on_window(f'window-{index}',window)

    def _dispatch(self):
        while self.next_offer<len(self.schedule.requests):
            arrival=self.schedule.requests[self.next_offer];row=self.ledger[arrival.request_id]
            now=self.clock.now_ns();due=row['due_at_ns']
            if now<due:break
            self.next_offer+=1;row['dispatch_at_ns']=now;row['lateness_ns']=now-due
            if now>=self.horizon_ns:row['state']='skipped_horizon'
            elif now-due>seconds_to_ns(self.config.max_admission_lateness_s):row['state']='skipped_scheduler'
            elif len(self.inflight)>=self.config.max_inflight:row['state']='skipped_capacity'
            else:
                row.update(state='admitted',admitted_at_ns=now)
                self.inflight[arrival.request_id]=asyncio.create_task(self._request(arrival))
                self.peak=max(self.peak,len(self.inflight))
            self._log('offered_request_decided',request_id=arrival.request_id,state=row['state'],due_at_ns=due)

    def _cancel_requests(self,reason):
        for request_id,task in self.inflight.items():
            if task.done():continue
            self.cancel_reasons[request_id]=reason;task.cancel()
            # A coroutine cancelled before its first instruction cannot publish.
            if request_id not in self.started:self.terminals.put_nowait(self._censored(request_id,reason))

    async def run(self):
        if self.used:raise RuntimeError('Playback is single-use')
        self.used=True;self.status='running';self.start_ns=self.clock.now_ns()
        self.horizon_ns=self.start_ns+self.schedule.duration_ns
        width=seconds_to_ns(self.config.window_s)
        self.windows=[(self.window_factory or FeatureWindow)(self.clock,start,min(start+width,self.horizon_ns),
            min_latency_samples=self.config.min_latency_samples,grace_ns=seconds_to_ns(self.config.grace_s),
            include_end=start+width>=self.horizon_ns) for start in range(self.start_ns,self.horizon_ns,width)]
        self.ledger={r.request_id:dict(request_id=r.request_id,offset_ns=r.offset_ns,due_at_ns=self.start_ns+r.offset_ns,
            state='offered',admitted_at_ns=None,terminal=None) for r in self.schedule.requests}
        if self.server_collector is not None:self.sampling.append(asyncio.create_task(self._sample('server')))
        if self.gpu_sampler is not None:self.sampling.append(asyncio.create_task(self._sample('gpu')))
        if self.interval_collector is not None:self.interval_task=asyncio.create_task(self._sample_intervals())
        drain_deadline=self.horizon_ns+seconds_to_ns(self.config.drain_s)
        try:
            while True:
                self._consume();self._consume_intervals();self._close_due()
                if self.service_evidence is not None:self.service_evidence()
                self._dispatch();now=self.clock.now_ns()
                if now>=self.horizon_ns and self.observed_horizon is None:
                    self.observed_horizon=dict(observed_at_ns=now,pending_ids=[i for i,r in self.ledger.items() if r['state']=='admitted'])
                    for task in self.sampling:task.cancel()
                if now>=drain_deadline:self._cancel_requests('drain_cancelled')
                if now>=self.horizon_ns and not self.inflight and len(self.closed)==len(self.windows) and all(t.done() for t in self.sampling) and (self.interval_task is None or self.interval_task.done()):break
                await asyncio.sleep(self.config.tick_s)
            self.status='completed'
        except BaseException as exc:
            self.status='aborted';self.failure=type(exc).__name__
            raise
        finally:
            for task in self.sampling:task.cancel()
            if self.interval_task is not None:self.interval_task.cancel()
            self._cancel_requests('run_cancelled')
            await asyncio.gather(*self.sampling,*list(self.inflight.values()),*([self.interval_task] if self.interval_task is not None else []),return_exceptions=True)
            self._consume();self._consume_intervals()
            for row in self.ledger.values():
                if row['state']=='offered':row['state']='not_dispatched_run_abort'
            self.finished_at_ns=self.clock.now_ns()
        return self.snapshot()

    def snapshot(self):
        rows=list(self.ledger.values());admitted=[r for r in rows if r['admitted_at_ns'] is not None]
        def ended(row):return row['terminal']['completion']['end_ns'] if row['terminal'] is not None else None
        counts={name:sum(r['state']==name for r in rows) for name in ('completed','failed','censored','admitted',
            'skipped_capacity','skipped_scheduler','skipped_horizon','not_dispatched_run_abort','offered')}
        horizon_reached=self.observed_horizon is not None
        accounting=dict(all_offers_accounted=sum(counts.values())==len(self.schedule.requests),
            admitted_conserved=len(admitted)==sum(counts[s] for s in ('completed','failed','censored','admitted')),
            concurrency_respected=self.peak<=self.config.max_inflight)
        return dict(playback_version='schedule_playback_v1',provenance=self.provenance,status=self.status,failure=self.failure,
            schedule_file_sha256=self.schedule.file_sha256,schedule_content_sha256=self.schedule.content_sha256,
            config=asdict(self.config),start_ns=self.start_ns,horizon_ns=self.horizon_ns,finished_at_ns=self.finished_at_ns,
            clock_domain=self.clock.domain,offered=len(self.schedule.requests),admitted=len(admitted),counts=counts,
            peak_inflight=self.peak,observed_horizon=self.observed_horizon,horizon_reached=horizon_reached,accounting_checks=accounting,
            pending_at_horizon_reconstructed=None if not horizon_reached else [r['request_id'] for r in admitted if ended(r) is None or ended(r)>self.horizon_ns],
            post_horizon_terminals=sum(ended(r)>self.horizon_ns for r in admitted if ended(r) is not None),
            post_horizon_completed=sum(r['state']=='completed' and ended(r)>self.horizon_ns for r in admitted if ended(r) is not None),
            post_horizon_failed=sum(r['state']=='failed' and ended(r)>self.horizon_ns for r in admitted if ended(r) is not None),
            telemetry_overflows=len(self.drops),sampling_skips=dict(self.sampling_skips),sampling_errors=dict(self.sampling_errors),sampling_cancelled=dict(self.sampling_cancelled),
            receipt_coverage_clean=not self.drops and not any(self.sampling_skips.values()),
            interval_records=list(self.interval_audit),interval_collection_errors=self.interval_errors,
            live_interval_tasks=int(self.interval_task is not None and not self.interval_task.done()),
            live_request_tasks=sum(not t.done() for t in self.inflight.values()),live_sampling_tasks=sum(not t.done() for t in self.sampling),
            ledger=rows,raw_records=list(self.raw),telemetry_drops=list(self.drops),events=list(self.events),
            feature_windows=[dict(window_id=f'window-{i}',metrics=None if w.metrics is None else [asdict(m) for m in w.metrics],
                audit=w.audit()) for i,w in enumerate(self.windows)],
            note='Offered schedule is fixed; admitted/completed work may differ. Reconstructed horizon state uses later receipts and is evaluator-only. No server/profiler lifecycle or calibrated diagnosis implemented.')
