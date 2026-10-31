"""CPU-only prospective schedules and engineering gates; no GPU launcher/labels."""
import hashlib,json
from pathlib import Path
from experiments.tracing.arrival_schedule import ArrivalSchedule,canonical
from experiments.tracing.live_features import MetricReceipt,map_receipt
from experiments.tracing.measured_evidence import integer,fields_only
from experiments.tracing.server_events import scheduler_wait_bounds

NS=1_000_000_000
RATES=(.5,1,2,4,8)
VERSION='event_challenge_preparation_v1'


def job_design():
    jobs=[]
    for case in ('rate_ladder','pressure_then_removal','lull_then_recurrence','unresolved_source_gap_control'):
        for block,order in enumerate((('off','on'),('on','off')) if case!='unresolved_source_gap_control' else (('complete','withheld'),('withheld','complete'))):
            for role in order:
                jobs.append(dict(job_id=f'{case}-b{block}-{role}',case_id=case,block=block,role=role,
                    event_instrumentation=role!='off',prefix_caching=False,fresh_owned_restart_required=True,
                    schedule_id='rate_ladder' if case=='rate_ladder' else 'select_exact_bank_entry_using_primary_off_ladder_rate',
                    evidence_withheld_offsets_ns=[10*NS,40*NS] if role=='withheld' else None,executed=False))
    return jobs


def phases(case,rate=None):
    if case=='rate_ladder':return [(f'level-{i}',i*8,(i+1)*8,r) for i,r in enumerate(RATES)]+[('removal',40,60,0)]
    if rate not in RATES:raise ValueError('Predeclared rate required')
    if case in ('pressure_then_removal','unresolved_source_gap_control'):
        return [('baseline',0,10,.5),('pressure',10,40,rate),('removal',40,60,0)]
    if case=='lull_then_recurrence':
        return [('baseline',0,10,.5),('pressure',10,25,rate),('lull',25,30,0),('recurrence',30,50,rate),('removal',50,60,0)]
    raise ValueError('Unknown challenge case')


def make_schedule(case,prompt,model,rate=None):
    rows=[]
    for name,start,end,rps in phases(case,rate):
        if not rps:continue
        period=round(NS/rps)
        for offset in range(start*NS,end*NS,period):
            rows.append(dict(request_id=f'{case}-r{rate if rate is not None else "ladder"}-{len(rows):04d}',
                offset_ns=offset,payload=dict(model=model,prompt=prompt,max_tokens=32,stream=False,temperature=0,ignore_eos=True)))
    if len(rows)+1>512:raise ValueError('Warmup-inclusive request budget exceeded')
    return ArrivalSchedule.from_bytes(canonical(dict(version='offered_arrivals_v1',duration_ns=60*NS,requests=rows)))


def wire_payload(offered):
    """Declared adapter overlay for the commissioned n=1 ID mapping."""
    return offered.payload|dict(request_id=offered.request_id,n=1)


def materialize(output,*,corpus_raw,spec_raw,commission_raw,validation_raw):
    spec=json.loads(spec_raw);corpus=json.loads(corpus_raw)
    commission=json.loads(commission_raw);validation=json.loads(validation_raw)
    if spec['version']!='server_event_instrumentation_pilot_spec_v1' or spec['corpus_sha256']!=hashlib.sha256(corpus_raw).hexdigest():
        raise ValueError('Prospective specification/corpus mismatch')
    if not commission.get('commission_passed') or commission.get('total_request_attempts')!=8 or commission.get('errors') or not validation.get('passed') or validation.get('requests_joined')!=8:
        raise ValueError('Passing eight-request commissioning and backup audit required')
    long=[p for p in corpus['prompts'] if p['band']=='long']
    if len(long)!=1:raise ValueError('Single pinned long prompt required')
    prompt=long[0]
    if hashlib.sha256(prompt['prompt'].encode()).hexdigest()!=prompt['prompt_utf8_sha256'] or prompt['tokenizer_prompt_tokens']!=1072:
        raise ValueError('Pinned 1,072-token prompt required')
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    entries=[]
    for case in ('rate_ladder','pressure_then_removal','lull_then_recurrence','unresolved_source_gap_control'):
        for rate in ((None,) if case=='rate_ladder' else RATES):
            key=case if rate is None else case+'-'+str(rate)
            schedule=make_schedule(case,prompt['prompt'],'Qwen/Qwen2.5-7B-Instruct',rate)
            raw=canonical(schedule.as_dict())
            if len(raw)>2*1024*1024:raise ValueError('Schedule byte budget exceeded')
            (root/(key+'.json')).write_bytes(raw)
            boundaries=sorted({10,20,30,40,50,60}|{p[2] for p in phases(case,rate)})
            entries.append(dict(schedule_id=key,path=key+'.json',file_sha256=hashlib.sha256(raw).hexdigest(),
                wire_content_sha256=hashlib.sha256(canonical([dict(offset_ns=r.offset_ns,payload=wire_payload(r)) for r in schedule.requests])).hexdigest(),
                case_id=case,rate_rps=rate,offered_requests=len(schedule.requests),total_requests_with_warmup=len(schedule.requests)+1,
                phase_table=[dict(name=n,start_ns=s*NS,end_ns=e*NS,rate_rps=r) for n,s,e,r in phases(case,rate)],
                event_probe_offsets_ns=[t*NS for t in boundaries],
                total_event_probes_including_before_and_after_drain=len(boundaries)+2))
    jobs=job_design()
    worst=sum(4*max(e['total_requests_with_warmup'] for e in entries if e['case_id']==case)
        for case in ('rate_ladder','pressure_then_removal','lull_then_recurrence','unresolved_source_gap_control'))
    plan=dict(version=VERSION,status='CPU_prepared_not_executed',launch_supported=False,study_ready=False,
        calibration_enabled=False,reference_export_enabled=False,protocol_frozen=False,
        input_sha256={name:hashlib.sha256(raw).hexdigest() for name,raw in dict(corpus=corpus_raw,prospective_spec=spec_raw,
            commission=commission_raw,commission_audit=validation_raw).items()},
        budgets=dict(max_jobs=16,max_total_requests_including_warmups=worst,max_requests_per_session=512,
            max_journal_events=4096,max_probes_per_session=32,max_client_inflight=32,server_max_num_seqs=16,
            horizon_ns=60*NS,drain_ns=30*NS,request_timeout_s=30,max_admission_lateness_ns=50_000_000,
            per_job_work_deadline_s=240,cleanup_deadline_s=45,max_schedule_bytes=2*1024*1024),
        common=dict(prefix_caching=False,warmup_requests=1,warmup_output_tokens=32,prompt_tokens=1072,
            output_tokens=32,metric_interval_ns=NS//2,max_metric_receipt_gap_ns=750_000_000,
            min_successful_completions_for_p95_review=20,latency_ratio_review_flag=1.25,
            metric_collection_both_roles=True,profiler_enabled=False,extra_inference_probes=0,
            warmup_request_id='challenge-warmup',warmup_outside_case=True,
            wire_overlay='request_id=offered_request_id,n=1; exact same transformation in both roles',
            cache_verification='actual_effective_cache_config_required_in_both_roles_before_workload',
            quiet_barriers='two_before_and_two_after_case_outside_measured_horizon_in_every_role',
            event_probe_schedule='before_case_after_warmup; declared offsets; final_after_drain; off_role_records_noop_markers',
            guard_failure='retain_failure_no_retry_no_unplanned_rate_or_threshold_adjustment'),
        selection=dict(primary_job_id='rate_ladder-b0-off',rule='lowest_complete_level_with_three_consecutive_positive_queue_receipts_spanning_at_least_one_second',
            min_receipts_per_level=12,min_positive_streak=3,min_positive_span_ns=NS,
            require_all_five_levels_covered=True,require_exact_successful_work_and_timely_admission=True,
            no_candidate='no_sampled_pressure_candidate_stop_dependent_cases_no_cause_label',
            incomplete='incomplete_evidence_stop_dependent_cases',use_classifier=False,use_instrumented_ladder=False),
        observation_limits=['sampled_queue_evidence_not_continuous_queue_duration_or_causal_diagnosis',
            'two_order_blocks_are_engineering_controls_not_statistical_power',
            'receipt_withholding_is_consumer_unavailability_not_profiler_failure_or_true_journal_loss',
            'latency_ratio_is_review_flag_not_equivalence; missing_or_mismatched_work_is_ineligible'],
        schedules=entries,jobs=jobs,scientific_limits=spec['scientific_limits'],
        next_blockers=['owned_concurrent_challenge_runner_and_raw_receipt_adapters',
            'effective_cache_receipt_for_uninstrumented_worker','CPU_lifecycle_control_and_budget_integration',
            'prospective_packet_hash_and_source_freeze_before_GPU_execution'])
    (root/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
    for name,raw in dict(corpus_input=corpus_raw,prospective_input=spec_raw,commission_input=commission_raw,commission_audit_input=validation_raw).items():
        (root/(name+'.json')).write_bytes(raw)
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.iterdir()) if p.is_file()}
    (root/'artifact_manifest.json').write_text(json.dumps(dict(files=manifest),indent=2)+'\n')
    return plan


def select_pressure(receipts,binding,*,case_start_ns,request_rows,schedule,job):
    if not schedule.requests:raise ValueError('Nonempty version-specific ladder required')
    expected=make_schedule('rate_ladder',schedule.requests[0].payload['prompt'],schedule.requests[0].payload['model'])
    return select_pressure_profile(receipts,binding,case_start_ns=case_start_ns,request_rows=request_rows,
        schedule=schedule,job=job,expected=expected,rates=RATES)


def select_pressure_profile(receipts,binding,*,case_start_ns,request_rows,schedule,job,expected,rates):
    """Primary OFF ladder only, with raw scoped receipts and exact work receipts.

    The caller must bind this input to primary_job_id in the owned run manifest.
    This result is an engineering candidate, never a diagnosis or reference.
    """
    integer(case_start_ns,'case start')
    if job.get('job_id')!='rate_ladder-b0-off' or job.get('event_instrumentation') is not False or job.get('prefix_caching') is not False:
        raise ValueError('Only the predeclared primary uninstrumented/cache-off ladder can select pressure')
    if schedule.duration_ns!=60*NS or len(schedule.requests)!=len(expected.requests):
        raise ValueError('Exact version-specific request ladder required')
    if schedule.content_sha256!=expected.content_sha256:raise ValueError('Noncanonical rate ladder')
    if len({r['request_id'] for r in request_rows})!=len(request_rows):raise ValueError('Duplicate work ID')
    by_id={r['request_id']:r for r in request_rows}
    good_work=set(by_id)=={r.request_id for r in schedule.requests}
    for offered in schedule.requests:
        row=by_id.get(offered.request_id)
        if row is None:continue
        fields_only(row,{'request_id','admitted_at_ns','completed_at_ns','http_status','error','prompt_tokens','output_tokens'})
        a=row['admitted_at_ns'];b=row['completed_at_ns']
        good_work=good_work and (type(a) is int and type(b) is int and
            case_start_ns+offered.offset_ns<=a<=case_start_ns+offered.offset_ns+50_000_000 and
            a<=b<=case_start_ns+90*NS and row['http_status']==200 and row['error'] is None and row['prompt_tokens']==1072 and row['output_tokens']==32)
    if not good_work:return dict(status='incomplete_work',selected_rate_rps=None,levels=[])
    points=[];seen=set()
    for receipt in receipts:
        if type(receipt) is not MetricReceipt or receipt.binding!=binding:raise ValueError('Foreign/untyped queue receipt')
        if receipt.sample_id in seen:raise ValueError('Duplicate queue receipt')
        seen.add(receipt.sample_id)
        if receipt.received_at_ns>case_start_ns+90*NS:raise ValueError('Receipt beyond case/drain deadline')
        sample,_=map_receipt(receipt,binding,now_ns=case_start_ns+90*NS)
        points.append((receipt,sample))
    if any(b[0].requested_at_ns<a[0].received_at_ns for a,b in zip(points,points[1:])):
        raise ValueError('Queue receipt order overlaps/reverses serialized collection')
    levels=[]
    for i,rate in enumerate(rates):
        start=case_start_ns+i*8*NS;end=start+8*NS
        rows=[(r,s) for r,s in points if start<=r.requested_at_ns<=r.received_at_ns<end]
        covered=len(rows)>=12 and all(s.error is None and s.queue_depth is not None and s.queue_depth>=0 and r.received_at_ns-r.requested_at_ns<=750_000_000 for r,s in rows)
        if rows:
            covered=covered and rows[0][0].requested_at_ns-start<=750_000_000 and end-rows[-1][0].received_at_ns<=750_000_000
            covered=covered and all(b[0].received_at_ns-a[0].received_at_ns<=750_000_000 for a,b in zip(rows,rows[1:]))
        streak=[];positive=False
        for receipt,sample in rows:
            if sample.error is None and sample.queue_depth is not None and sample.queue_depth>0:
                streak.append(receipt.received_at_ns)
                if len(streak)>=3 and streak[-1]-streak[0]>=NS:positive=True
            else:streak=[]
        levels.append(dict(rate_rps=rate,receipt_count=len(rows),covered=bool(covered),sampled_pressure_streak=positive))
    if not all(level['covered'] for level in levels):status='incomplete_evidence';rate=None
    else:
        rate=next((l['rate_rps'] for l in levels if l['sampled_pressure_streak']),None)
        status='engineering_candidate' if rate is not None else 'no_sampled_pressure_candidate'
    return dict(status=status,selected_rate_rps=rate,levels=levels)


def load_prepared(directory):
    root=Path(directory);manifest=json.loads((root/'artifact_manifest.json').read_text())
    for name,expected in manifest['files'].items():
        if Path(name).name!=name or (root/name).is_symlink():raise ValueError('Unsafe prepared artifact path')
        raw=(root/name).read_bytes()
        if len(raw)>2*1024*1024 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Prepared artifact hash/size mismatch')
    plan=json.loads((root/'PLAN.json').read_text())
    if plan['version']!=VERSION or plan['launch_supported'] or plan['study_ready'] or plan['protocol_frozen']:
        raise ValueError('Only an unfrozen CPU-prepared packet is supported')
    if len(plan['jobs'])!=16 or len(plan['schedules'])!=16:raise ValueError('Incomplete bounded job/schedule bank')
    if plan['jobs']!=job_design() or any(j['prefix_caching'] is not False or type(j['event_instrumentation']) is not bool for j in plan['jobs']):
        raise ValueError('Job IDs/order/roles/cache/injection differ from the prepared design')
    schedules={}
    for entry in plan['schedules']:
        if entry['path'] not in manifest['files']:raise ValueError('Schedule not covered by manifest')
        schedule=ArrivalSchedule.load(root/entry['path'])
        if schedule.file_sha256!=entry['file_sha256'] or len(schedule.requests)!=entry['offered_requests']:
            raise ValueError('Schedule count/hash mismatch')
        expected=make_schedule(entry['case_id'],schedule.requests[0].payload['prompt'],schedule.requests[0].payload['model'],entry['rate_rps'])
        if expected.content_sha256!=schedule.content_sha256:raise ValueError('Schedule differs from phase generator')
        wire=canonical([dict(offset_ns=r.offset_ns,payload=wire_payload(r)) for r in schedule.requests])
        if hashlib.sha256(wire).hexdigest()!=entry['wire_content_sha256']:raise ValueError('Wire transformation mismatch')
        if len(schedule.requests)+1>512 or entry['total_event_probes_including_before_and_after_drain']>32:raise ValueError('Prepared budget exceeded')
        schedules[entry['schedule_id']]=schedule
    return plan,schedules


def event_window(receipt,binding,*,start_ns,end_ns,decision_ns,withheld_interval=None):
    """Consumer gate only; preserve the backing raw receipt without modification."""
    for value in (start_ns,end_ns,decision_ns):integer(value,'window/decision time')
    if not start_ns<end_ns<=decision_ns:raise ValueError('Window outside decision time')
    if withheld_interval is not None:
        a,b=withheld_interval
        integer(a,'withheld start');integer(b,'withheld end')
        if a>=b:raise ValueError('Empty/reversed withholding interval')
        if start_ns<b and a<end_ns:
            return dict(status='unresolved',reason='deliberately_withheld_consumer_event_evidence',bounds=None,diagnosis=None)
    if receipt is None:return dict(status='unresolved',reason='missing_event_receipt',bounds=None,diagnosis=None)
    if receipt['received_at_ns']>decision_ns:
        return dict(status='unresolved',reason='event_receipt_not_ready_at_decision',bounds=None,diagnosis=None)
    try:
        bounds=scheduler_wait_bounds(receipt['data'],receipt['command'],binding,received_at_ns=receipt['received_at_ns'],start_ns=start_ns,end_ns=end_ns)
    except (ValueError,KeyError,TypeError) as exc:
        return dict(status='unresolved',reason='invalid_event_evidence:'+type(exc).__name__,bounds=None,diagnosis=None)
    return dict(status='bounds_available',reason=None,bounds=bounds,diagnosis=None)
