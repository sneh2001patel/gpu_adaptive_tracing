"""Owned challenge lifecycles; injectable transport for CPU failure tests."""
import asyncio,hashlib,json,math,uuid
from dataclasses import asdict,dataclass
from pathlib import Path
from revision.feasibility.challenge_protocol import NS,load_prepared,select_pressure,event_window
from revision.feasibility.activity import OwnedLiveActivity
from revision.feasibility.harness import check
from revision.scripts.run_l4_discovery import save
from revision.scripts.play_arrivals import write_sources
from revision.tracing.arrival_schedule import canonical
from revision.tracing.aggregation import RequestCompletion
from revision.tracing.feature_collection import http_body,ObservedCompletion
from revision.tracing.live_features import ServingBinding,LiveMetricCollector,persist_receipt,map_receipt
from revision.tracing.schedule_playback import SchedulePlayback,PlaybackConfig
from revision.tracing.server_events import collect_snapshot,atomic_json,validate_snapshot
from revision.tracing.worker_configuration import validate_configuration


@dataclass(frozen=True)
class EpisodeOptions:
    window_s:float=10
    grace_s:float=.75
    drain_s:float=30
    timeout_s:float=30
    metric_interval_s:float=.5
    max_inflight:int=32
    max_lateness_s:float=.05
    tick_s:float=.002


class CampaignBudget:
    def __init__(self,output,max_total=3612,max_session=512):
        self.output=Path(output);self.max_total=max_total;self.max_session=max_session;self.counts={};self.reserved={}
    def reserve(self,job_id,count):
        if job_id in self.reserved or type(count) is not int or not 1<=count<=self.max_session or sum(self.reserved.values())+count>self.max_total:
            raise ValueError('Campaign/session reservation exceeded or reused')
        self.reserved[job_id]=count;self.counts[job_id]=0;self.persist()
    def charge(self,job_id):
        if self.counts[job_id]>=self.reserved[job_id]:raise ValueError('Request attempt budget exceeded')
        self.counts[job_id]+=1;self.persist()  # no await: charged before dispatch, never refunded
    def persist(self):atomic_json(self.output/'request_budget.json',dict(reserved=self.reserved,attempts=self.counts,max_total=self.max_total))


class OwnedChallengeTarget:
    live=True
    def __init__(self,config,clock,endpoint,model_path):
        self.clock=clock;self.config=config;self.endpoint=endpoint
        self.activity=OwnedLiveActivity(config,clock,endpoint,model_path)
    async def open(self,job,output,generation):
        self.output=output
        session=await self.activity.start(output,generation,reset_token=uuid.uuid4().hex,
            event_instrumentation=job['event_instrumentation'],prefix_caching=False)
        worker=session['worker'];self.session=session
        self.binding=ServingBinding(session['nonce'],generation,worker['pid'],worker['device_uuid'],self.config['model'],self.config['engine'],self.clock.domain)
        inventory=await self.activity.discovery().inventory(output,{})
        check('inventory',inventory,self.config,{},output,'live_online',self.clock.domain);save(output/'inventory.json',inventory)
        command=dict(token=uuid.uuid4().hex,session_nonce=session['nonce'],generation=generation,clock_domain=self.clock.domain,requested_at_ns=self.clock.now_ns())
        atomic_json(session['directory']/'configuration_command.json',command)
        status,_=await http_body(self.endpoint+'/revision/configuration',method='POST',payload={},timeout_s=12)
        received=self.clock.now_ns()
        if status!=200:raise RuntimeError('Effective worker configuration RPC failed')
        receipt=json.loads((session['directory']/('configuration-'+command['token']+'.json')).read_text())
        validate_configuration(receipt,command,self.binding,received)
        save(output/'effective_configuration.json',dict(command=command,received_at_ns=received,receipt=receipt))
        self.collector=LiveMetricCollector(self.endpoint+'/metrics',self.binding,timeout_s=2)
        return self.binding
    async def complete(self,payload,timeout_s):
        return await http_body(self.endpoint+'/v1/completions',method='POST',payload=payload,timeout_s=timeout_s)
    async def metric(self,sample_id):return await self.collector.sample(self.clock,sample_id)
    async def probe(self):
        async def trigger():
            status,_=await http_body(self.endpoint+'/revision/events/probe',method='POST',payload={},timeout_s=2)
            if status!=200:raise RuntimeError('Event RPC failed')
        return await collect_snapshot(self.clock,self.binding,self.session['directory']/'scheduler-events',trigger,timeout_s=2)
    async def quiet(self,label):return await self.activity.quiet(self.output,label)
    async def close(self):return await self.activity.cleanup(self.output,{})


class RawChallengeRequests:
    def __init__(self,target,clock,output,budget,job_id):
        self.target,self.clock,self.output,self.budget,self.job_id=target,clock,Path(output),budget,job_id
        self.output.mkdir();self.rows=[]
    async def collect(self,clock,request_id,endpoint,payload,**options):
        self.budget.charge(self.job_id);start=clock.now_ns();raw=None;status=None;error=None;prompt=output=None
        payload=payload|dict(request_id=request_id,n=1)
        try:
            status,raw=await asyncio.wait_for(self.target.complete(payload,options['timeout_s']),options['timeout_s'])
            if status!=200:raise ValueError('http_'+str(status))
            response=json.loads(raw);usage=response['usage'];prompt=usage['prompt_tokens'];output=usage['completion_tokens']
            if (response['id']!='cmpl-'+request_id or response['model']!=payload['model'] or type(prompt) is not int or prompt!=1072 or
                type(output) is not int or output!=32 or usage['total_tokens']!=1104 or len(response['choices'])!=1 or
                response['choices'][0]['finish_reason']!='length'):raise ValueError('Actual response ID/model/token/terminal mismatch')
        except asyncio.CancelledError:error='client_cancelled';raise
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        finally:
            end=clock.now_ns();name=hashlib.sha256(request_id.encode()).hexdigest()+'.json' if raw is not None else None
            if raw is not None:(self.output/name).write_bytes(raw)
            row=dict(request_id=request_id,admitted_at_ns=start,completed_at_ns=end,http_status=status,error=error,
                prompt_tokens=prompt,output_tokens=output,response_path=name,
                response_sha256=None if raw is None else hashlib.sha256(raw).hexdigest())
            self.rows.append(row)
            with (self.output/'receipts.jsonl').open('a') as stream:stream.write(json.dumps(row,allow_nan=False)+'\n')
        return ObservedCompletion(RequestCompletion(request_id,start,end,end,clock.domain,error is None,error),
            prompt if error is None else None,output if error is None else None,error)


class EpisodeMetrics:
    def __init__(self,target,clock,binding,output):self.target,self.clock,self.binding,self.output=target,clock,binding,output;self.receipts=[]
    async def sample(self,clock,sample_id):
        receipt=await self.target.metric(sample_id)
        if receipt.binding!=self.binding:raise ValueError('Foreign metric session')
        persist_receipt(self.output,receipt);self.receipts.append(receipt)
        return map_receipt(receipt,self.binding,now_ns=clock.now_ns())[0]


class EpisodeEvidence:
    def __init__(self,target,clock,binding,job,entry,output,options):
        self.target,self.clock,self.binding,self.job,self.entry,self.output,self.options=target,clock,binding,job,entry,output,options
        self.task=None;self.next_probe=0;self.next_window=0;self.receipts=[];self.probes=[];self.windows=[];self.error=None
    async def probe(self,label):
        if len(self.probes)>=32:raise ValueError('Event probe budget exceeded')
        requested=self.clock.now_ns();receipt=None
        if self.job['event_instrumentation']:
            receipt=await self.target.probe()
            validate_snapshot(receipt['data'],receipt['command'],self.binding,receipt['received_at_ns'])
            if receipt['received_at_ns']>self.clock.now_ns():raise ValueError('Future event receipt')
            self.receipts.append(receipt);save(self.output/f'probe-{len(self.probes):02d}.json',receipt)
        self.probes.append(dict(label=label,requested_at_ns=requested,received_at_ns=self.clock.now_ns(),noop=receipt is None))
        save(self.output/'probe_log.json',self.probes)
        return receipt
    def _consume(self):
        if self.task is not None and self.task.done():
            self.task.result();self.task=None
    def service(self,driver):
        self._consume();now=self.clock.now_ns();offsets=self.entry['event_probe_offsets_ns']
        if self.next_probe<len(offsets) and now>=driver.start_ns+offsets[self.next_probe]:
            if self.task is not None:raise RuntimeError('Prior event probe still active at next fixed offset')
            if now-driver.start_ns-offsets[self.next_probe]>round(self.options.max_lateness_s*NS):
                raise RuntimeError('Event probe offset missed; no catch-up probe')
            self.task=asyncio.create_task(self.probe('offset-'+str(offsets[self.next_probe])));self.next_probe+=1
        width=round(self.options.window_s*NS);grace=round(self.options.grace_s*NS)
        while driver.start_ns+(self.next_window+1)*width<=driver.horizon_ns:
            start=driver.start_ns+self.next_window*width;end=start+width;deadline=end+grace
            if now<deadline:break
            available=[r for r in self.receipts if r['received_at_ns']<=deadline]
            withheld=None if self.job['evidence_withheld_offsets_ns'] is None else tuple(driver.start_ns+x for x in self.job['evidence_withheld_offsets_ns'])
            gate=event_window(available[-1] if available else None,self.binding,start_ns=start,end_ns=end,decision_ns=deadline,withheld_interval=withheld)
            if now-deadline>round(self.options.max_lateness_s*NS):
                gate=dict(status='unresolved',reason='owner_decision_deadline_missed',bounds=None,diagnosis=None)
            self.windows.append(dict(start_ns=start,end_ns=end,decision_ns=deadline,owner_observed_at_ns=now,
                owner_late=now-deadline>round(self.options.max_lateness_s*NS),**gate))
            self.next_window+=1;save(self.output/'consumer_windows.json',self.windows)
    async def finish(self):
        if self.task is not None:await self.task;self.task=None
    async def cancel(self):
        if self.task is not None:
            self.task.cancel();await asyncio.gather(self.task,return_exceptions=True);self.task=None


def normalized_work(rows):
    return [{k:r[k] for k in ('request_id','admitted_at_ns','completed_at_ns','http_status','error','prompt_tokens','output_tokens')} for r in rows]


def final_lifecycle(receipt,binding,rows):
    states=validate_snapshot(receipt['data'],receipt['command'],binding,receipt['received_at_ns'])
    if set(states)!={'cmpl-'+r['request_id']+'-0' for r in rows}:raise ValueError('Unexpected/missing engine IDs in final history')
    for row in rows:
        state=states['cmpl-'+row['request_id']+'-0']
        if row['error'] is not None or any(state[k] is None for k in ('admission','scheduled','finished')):raise ValueError('Incomplete successful lifecycle')
        if state['finished']['terminal_status']!='FINISHED_LENGTH_CAPPED':raise ValueError('Unexpected source terminal status')
        for event in state.values():
            if not row['admitted_at_ns']<=event['hook_enter_ns']<=event['hook_return_ns']<=row['completed_at_ns']:
                raise ValueError('Source lifecycle outside exact client bracket')


async def run_episode(target,clock,job,entry,schedule,output,budget,generation,*,options=None,selection_fn=select_pressure):
    options=options or EpisodeOptions()
    if target.live and (options!=EpisodeOptions() or schedule.duration_ns!=60*NS):raise ValueError('Live execution requires exact prepared durations/options')
    output=Path(output);output.mkdir();write_sources(output);save(output/'job.json',job|dict(schedule_id=entry['schedule_id']))
    budget.reserve(job['job_id'],len(schedule.requests)+1)
    requests=RawChallengeRequests(target,clock,output/'requests',budget,job['job_id'])
    driver=evidence=None;result=None;errors=[];cleanup=None
    async def work():
        nonlocal driver,evidence,result
        binding=await target.open(job,output,generation);save(output/'binding.json',asdict(binding))
        await requests.collect(clock,'challenge-warmup','',schedule.requests[0].payload,timeout_s=options.timeout_s)
        if requests.rows[-1]['error']:raise RuntimeError('Warmup failed; no retry')
        await target.quiet('before')
        evidence=EpisodeEvidence(target,clock,binding,job,entry,output,options)
        initial=await evidence.probe('before-case')
        if initial is not None:final_lifecycle(initial,binding,requests.rows)
        collector=EpisodeMetrics(target,clock,binding,output/'raw_metrics')
        config=PlaybackConfig(max_inflight=options.max_inflight,request_timeout_s=options.timeout_s,drain_s=options.drain_s,
            max_admission_lateness_s=options.max_lateness_s,window_s=options.window_s,grace_s=options.grace_s,
            min_latency_samples=20,sample_interval_s=options.metric_interval_s,sample_timeout_s=2,tick_s=options.tick_s)
        driver=SchedulePlayback(schedule,clock,'http://127.0.0.1:8012/v1/completions',provenance='live_online' if target.live else 'synthetic_simulation',
            config=config,completion_collector=requests.collect,server_collector=collector,service_evidence=lambda:evidence.service(driver))
        playback=await driver.run();await evidence.finish();save(output/'playback.json',playback)
        if playback['counts']['completed']!=len(schedule.requests) or playback['admitted']!=len(schedule.requests):
            raise RuntimeError('Incomplete offered work; retain skips/errors/censors, no retry')
        if any(playback['sampling_errors'].values()) or any(playback['sampling_skips'].values()) or playback['telemetry_overflows']:
            raise RuntimeError('Incomplete metric sampling')
        await target.quiet('after')
        final=await evidence.probe('after-drain')
        if final is not None:final_lifecycle(final,binding,requests.rows)
        scheduled=normalized_work([r for r in requests.rows if r['request_id']!='challenge-warmup'])
        save(output/'normalized_work.json',scheduled)
        result=dict(job_id=job['job_id'],binding=asdict(binding),case_start_ns=driver.start_ns,
            requests=scheduled,metric_receipts=collector.receipts,consumer_windows=evidence.windows,
            schedule_sha256=schedule.file_sha256,engineering_complete=True)
        if job['job_id']=='rate_ladder-b0-off':
            result['selection']=selection_fn(collector.receipts,binding,case_start_ns=driver.start_ns,request_rows=scheduled,schedule=schedule,job=job)
            save(output/'selection.json',result['selection'])
    try:await asyncio.wait_for(work(),240)
    except BaseException as exc:
        errors.append(type(exc).__name__+': '+str(exc));raise
    finally:
        if evidence is not None:await evidence.cancel()
        if driver is not None:save(output/'playback.json',driver.snapshot())
        try:cleanup=await asyncio.wait_for(target.close(),45)
        except Exception as exc:errors.append('cleanup: '+str(exc))
        save(output/'RESULT.json',dict(job_id=job['job_id'],passed=not errors and result is not None and cleanup is not None and cleanup.get('confirmed_absent') is True,
            errors=errors,cleanup=cleanup,request_attempts=len(requests.rows),study_ready=False,protocol_frozen=False))
        save(output/'artifact_manifest.json',dict(files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}))
        if cleanup is None or cleanup.get('confirmed_absent') is not True:raise RuntimeError('Owned cleanup not confirmed: '+'; '.join(errors))
    return result


def compare_observers(schedule,off,on):
    if off['schedule_sha256']!=on['schedule_sha256'] or off['schedule_sha256']!=schedule.file_sha256:
        return dict(status='ineligible',reason='offered_hash_mismatch',windows=[])
    indexes=[]
    for result in (off,on):
        rows=result['requests'];by_id={r['request_id']:r for r in rows}
        if len(by_id)!=len(rows) or set(by_id)!={r.request_id for r in schedule.requests}:return dict(status='ineligible',reason='work_ID_mismatch',windows=[])
        for offered in schedule.requests:
            r=by_id[offered.request_id];due=result['case_start_ns']+offered.offset_ns
            if (r['error'] is not None or r['http_status']!=200 or r['prompt_tokens']!=1072 or r['output_tokens']!=32 or
                not due<=r['admitted_at_ns']<=due+50_000_000 or not r['admitted_at_ns']<=r['completed_at_ns']<=result['case_start_ns']+90*NS):
                return dict(status='ineligible',reason='work_or_admission_mismatch',windows=[])
        indexes.append(by_id)
    windows=[]
    for start in range(0,schedule.duration_ns,10*NS):
        ids=[r.request_id for r in schedule.requests if start<=r.offset_ns<start+10*NS]
        row=dict(start_offset_ns=start,count=len(ids),p95_off_ms=None,p95_on_ms=None,symmetric_ratio=None,review_flag=None)
        if len(ids)<20:row['reason']='below_twenty_matched_requests'
        else:
            p95=[]
            for index in indexes:
                values=sorted((index[i]['completed_at_ns']-index[i]['admitted_at_ns'])/1e6 for i in ids)
                p95.append(values[math.ceil(.95*len(values))-1])
            if min(p95)<=0:row['reason']='nonpositive_denominator'
            else:
                ratio=max(p95)/min(p95);row.update(p95_off_ms=p95[0],p95_on_ms=p95[1],symmetric_ratio=ratio,review_flag=ratio>1.25,reason=None)
        windows.append(row)
    return dict(status='engineering_review_only',reason=None,windows=windows,equivalence_established=False)


async def run_campaign(target,clock,packet,output,*,loader=load_prepared,selection_fn=select_pressure):
    plan,bank=loader(packet);output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    budget=CampaignBudget(output,max_total=plan['budgets']['max_total_requests_including_warmups']);results=[];jobs=[];selection=None;errors=[]
    save(output/'input_manifest.json',dict(protocol_version=plan['version'],packet_manifest_sha256=hashlib.sha256((Path(packet)/'artifact_manifest.json').read_bytes()).hexdigest()))
    try:
        for generation,job in enumerate(plan['jobs']):
            if job['case_id']!='rate_ladder' and (selection is None or selection['status']!='engineering_candidate'):
                jobs.append(dict(job_id=job['job_id'],status='skipped_no_eligible_rate'));continue
            key='rate_ladder' if job['case_id']=='rate_ladder' else job['case_id']+'-'+str(selection['selected_rate_rps'])
            entry=next(e for e in plan['schedules'] if e['schedule_id']==key)
            result=await run_episode(target,clock,job,entry,bank[key],output/job['job_id'],budget,generation,selection_fn=selection_fn)
            results.append(result);jobs.append(dict(job_id=job['job_id'],status='completed',schedule_id=key))
            if 'selection' in result:selection=result['selection']
            save(output/'jobs.json',jobs)
        comparisons=[]
        for i in range(0,len(results),2):
            pair=results[i:i+2]
            if len(pair)!=2:break
            first=plan['jobs'][i];key=jobs[i]['schedule_id']
            off,on=(pair if first['role'] in ('off','complete') else pair[::-1])
            comparisons.append(dict(first_job=pair[0]['job_id'],second_job=pair[1]['job_id'],**compare_observers(bank[key],off,on)))
        save(output/'paired_reviews.json',comparisons)
    except asyncio.CancelledError:errors.append('campaign_cancelled');raise
    except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
    finally:
        finished={j['job_id'] for j in jobs}
        for job in plan['jobs']:
            if job['job_id'] not in finished:jobs.append(dict(job_id=job['job_id'],status='not_completed_campaign_failure'))
        save(output/'jobs.json',jobs)
        save(output/'RESULT.json',dict(protocol_version=plan['version'],status='failed' if errors else 'engineering_collection_complete',errors=errors,
            completed_jobs=len(results),selection=selection,total_request_attempts=sum(budget.counts.values()),
            GPU_used=target.live,classifier_run=False,calibration_enabled=False,references_created=0,study_ready=False,protocol_frozen=False))
        save(output/'artifact_manifest.json',dict(files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}))
    return not errors
