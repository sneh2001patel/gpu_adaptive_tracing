"""Bounded closed-loop throughput probes and deterministic candidate schedules.

Observed probe rates are not saturation capacity, calibrated thresholds or labels.
"""
import asyncio
from dataclasses import asdict, dataclass
import hashlib,json,math,random
from pathlib import Path
from revision.tracing.arrival_schedule import ArrivalSchedule,canonical
from revision.tracing.feature_collection import http_body,response_usage,ObservedCompletion
from revision.tracing.aggregation import RequestCompletion
from revision.tracing.live_features import LiveFeatureWindow,LiveMetricCollector
from revision.tracing.measured_evidence import integer

VERSION='bounded_capacity_corpus_probe_v1'


def corpus():
    short='Summarize why a server request queue can grow when incoming work exceeds service rate.'
    paragraph=('A serving system accepts requests, waits for available execution slots, processes prompt tokens, '
        'and generates output tokens. Engineers compare arrival rates, queue depth, completed work and latency. '
        'Measurements can overlap and missing observations must remain explicit. ')
    return dict(short=short,long='Read this technical note and summarize its operational implications.\n'+paragraph*24+'\nWrite a concise summary.')


def pin_corpus(tokenizer):
    rows=[]
    for band,prompt in corpus().items():
        ids=tokenizer.encode(prompt,add_special_tokens=False)
        if not ids or len(ids)+32>2048:raise ValueError('Corpus exceeds pinned context budget')
        rows.append(dict(band=band,prompt=prompt,prompt_utf8_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
            tokenizer_prompt_tokens=len(ids),token_ids_sha256=hashlib.sha256(canonical(ids)).hexdigest(),
            tokenizer_options=dict(add_special_tokens=False)))
    if rows[1]['tokenizer_prompt_tokens']<=rows[0]['tokenizer_prompt_tokens']:raise ValueError('Long prompt must contain more tokens')
    return dict(version=VERSION,scope='pilot_corpus_not_disjoint_frozen_study_corpora',prompts=rows)


@dataclass(frozen=True)
class ProbeConfig:
    duration_s: float=8
    concurrency: tuple=(1,2,4)
    max_requests: int=24
    request_timeout_s: float=12
    drain_s: float=15
    sample_interval_s: float=.5

    def __post_init__(self):
        for name,maximum in (('duration_s',10),('request_timeout_s',15),('drain_s',20),('sample_interval_s',2)):
            value=getattr(self,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<value<=maximum:raise ValueError('Bounded positive '+name+' required')
        integer(self.max_requests,'max_requests',1)
        if self.max_requests>32:raise ValueError('Request budget exceeded')
        if type(self.concurrency) is not tuple or not self.concurrency or len(set(self.concurrency))!=len(self.concurrency):raise ValueError('Distinct concurrency levels required')
        for value in self.concurrency:
            integer(value,'concurrency',1)
            if value>4:raise ValueError('Pilot concurrency budget exceeded')


async def probe_cell(clock,endpoint,binding,prompt,output,config,concurrency,*,provenance,expected_prompt_tokens):
    if concurrency not in config.concurrency:raise ValueError('Undeclared concurrency')
    integer(expected_prompt_tokens,'expected_prompt_tokens',1)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    start=clock.now_ns();end=start+round(config.duration_s*1e9)
    window=LiveFeatureWindow(clock,start,end,binding=binding,provenance=provenance,
        min_latency_samples=2,grace_ns=round(config.drain_s*1e9))
    collector=LiveMetricCollector(endpoint+'/metrics',binding,timeout_s=2)
    rows=[];issued=0;inflight=0;peak=0;sampling=True
    async def worker():
        nonlocal issued,inflight,peak
        while clock.now_ns()<end and issued<config.max_requests:
            index=issued;issued+=1;request_id=f'r{index:03d}';began=clock.now_ns();inflight+=1;peak=max(peak,inflight)
            status=raw=None;error=None;tokens=(None,None,'request_failed')
            try:
                status,raw=await http_body(endpoint+'/v1/completions',method='POST',payload=dict(model=binding.model,
                    prompt=prompt,max_tokens=32,stream=False,temperature=0,ignore_eos=True),timeout_s=config.request_timeout_s)
                if status!=200:error='http_'+str(status)
                else:
                    tokens=response_usage(raw)
                    if tokens[2]:error=tokens[2]
                    elif tokens[:2]!=(expected_prompt_tokens,32):error='actual_token_usage_mismatch'
            except asyncio.CancelledError:error='drain_cancelled';raise
            except Exception as exc:error=type(exc).__name__+': '+str(exc)
            finally:
                done=clock.now_ns();inflight-=1
                response_path=request_id+'.json' if raw is not None else None
                if raw is not None:(output/response_path).write_bytes(raw)
                record=ObservedCompletion(RequestCompletion(request_id,began,done,done,clock.domain,error is None,error),
                    tokens[0] if error is None else None,tokens[1] if error is None else None,None if error is None else error)
                window.on_completion(record)
                rows.append(dict(request_id=request_id,started_at_ns=began,completed_at_ns=done,http_status=status,error=error,
                    prompt_tokens=tokens[0],output_tokens=tokens[1],response_path=response_path,
                    response_sha256=None if raw is None else hashlib.sha256(raw).hexdigest(),completed_in_horizon=done<end))
    async def sample():
        index=0
        while sampling and clock.now_ns()<end:
            receipt=await collector.sample(clock,f's{index:03d}');index+=1;window.on_scrape(receipt)
            await asyncio.sleep(config.sample_interval_s)
    tasks=[asyncio.create_task(worker()) for _ in range(concurrency)]
    sampler=asyncio.create_task(sample());cancelled=False
    try:
        await asyncio.sleep(max(0,(end-clock.now_ns())/1e9))
        done,pending=await asyncio.wait(tasks,timeout=config.drain_s)
        if pending:
            cancelled=True
            for task in pending:task.cancel()
        results=await asyncio.gather(*tasks,return_exceptions=True)
        if pending:raise RuntimeError('Probe drain deadline exceeded')
        for result in results:
            if isinstance(result,BaseException):raise result
    finally:
        sampling=False
        for task in tasks:
            if not task.done():task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        if not sampler.done():sampler.cancel()
        sample_result=await asyncio.gather(sampler,return_exceptions=True)
        if isinstance(sample_result[0],Exception):raise sample_result[0]
        # Preserve every terminal response even on interruption/failure.
        (output/'requests.json').write_text(json.dumps(sorted(rows,key=lambda r:r['request_id']),indent=2)+'\n')
    # Window closure is intentionally after the complete configured grace period.
    await asyncio.sleep(max(0,(window.deadline_ns-clock.now_ns())/1e9))
    window.persist(output/'features','probe-window')
    errors=sum(r['error'] is not None for r in rows);in_horizon=sum(r['error'] is None and r['completed_in_horizon'] for r in rows)
    result=dict(version=VERSION,clock_domain=clock.domain,requested_duration_s=config.duration_s,start_ns=start,horizon_ns=end,
        completed_at_ns=clock.now_ns(),concurrency=concurrency,issued=issued,terminal_count=len(rows),peak_inflight=peak,
        request_errors=errors,drain_cancelled=cancelled,request_budget_reached=issued==config.max_requests,
        successful_in_horizon=in_horizon,successful_in_horizon_rps=in_horizon/config.duration_s,
        completion_cohort='successful_client_completions_before_horizon_not_admission_cohort',
        interpretation='finite_closed_loop_probe_not_saturation_capacity',capture_count=0)
    (output/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    if errors or cancelled or issued!=len(rows):raise RuntimeError('Incomplete or failed capacity probe; retain raw results')
    return result


def materialize_pairs(corpus_record,cells,model,output,seed=2101):
    """Same immutable offered bytes per pair; order seeded, never execute here."""
    integer(seed,'seed');output=Path(output);output.mkdir(parents=True,exist_ok=False)
    rates=[c['successful_in_horizon_rps'] for c in cells if math.isfinite(c['successful_in_horizon_rps']) and c['successful_in_horizon_rps']>0 and not c['request_errors']]
    if len(rates)!=len(cells) or not rates:raise ValueError('All probe cells need positive error-free observations')
    candidate_rate=min(min(rates)*.5,1.5);duration_ns=8_000_000_000
    count=max(1,min(12,math.floor(candidate_rate*8)));rng=random.Random(seed);jobs=[];schedules=[]
    for row in corpus_record['prompts']:
        requests=[dict(request_id=f'r{i:03d}',offset_ns=i*duration_ns//count,
            payload=dict(model=model,prompt=row['prompt'],max_tokens=32,stream=False,temperature=0,ignore_eos=True,seed=seed)) for i in range(count)]
        raw=canonical(dict(version='offered_arrivals_v1',duration_ns=duration_ns,requests=requests))
        schedule=ArrivalSchedule.from_bytes(raw);name=row['band']+'_offered.json';(output/name).write_bytes(raw)
        roles=['feature_collection','matched_full_trace'];rng.shuffle(roles)
        for position,role in enumerate(roles):jobs.append(dict(pair_id=row['band'],role=role,order_in_pair=position,
            schedule_path=name,file_sha256=schedule.file_sha256,fresh_owned_restart_required=True,executed=False))
        schedules.append(dict(band=row['band'],offered_count=count,realized_offered_rps=count/8,
            file_sha256=schedule.file_sha256,content_sha256=schedule.content_sha256))
    result=dict(version=VERSION,status='candidate_schedules_materialized_not_executed',seed=seed,jobs=jobs,schedules=schedules,
        rate_rule='half_minimum_positive_observed_probe_completion_rate_capped_at_1_5_rps_then_integer_request_count',
        candidate_rate_rps=candidate_rate,saturation_capacity_established=False,calibration_enabled=False,study_ready=False,protocol_frozen=False)
    (output/'PAIRS.json').write_text(json.dumps(result,indent=2)+'\n');return result
