"""Offline precision/cohort audit; no classifier mapping, labels or GPU activity."""
from collections import Counter
import hashlib,json,math,statistics
from pathlib import Path
from revision.feasibility.challenge_protocol import event_window
from revision.feasibility.challenge_runner import final_lifecycle
from revision.tracing.live_features import ServingBinding
from revision.tracing.server_events import validate_snapshot


def sha(raw):return hashlib.sha256(raw).hexdigest()


def distribution(values):
    values=sorted(values)
    if not values:return dict(n=0,min=None,median=None,p95=None,max=None)
    return dict(n=len(values),min=values[0],median=statistics.median(values),p95=values[math.ceil(.95*len(values))-1],max=values[-1])


def assessment_draft():
    """Unfilled scientific criteria; observed development results set no limits."""
    return dict(version='scheduler_bound_acceptance_draft_v1',status='blocked_scientific_criteria_unset',
        proposed_measurand='host_engine_admission_to_first_positive_CPU_schedule_decision_interval',
        cohort='schedule_bracket_wholly_inside_half_open_window',existing_wait_metric_mapping='unsupported',
        scientific_limits={key:None for key in ('max_hook_bracket_width_ms','max_wait_interval_width_ms',
            'relative_uncertainty_normalizer','max_relative_wait_uncertainty','max_boundary_ambiguous_fraction',
            'min_scheduler_requests_per_window','target_percentile_precision','target_confidence_level',
            'max_evidence_readiness_latency_ms','max_source_probe_gap_ms','max_pair_work_mismatch',
            'max_pair_latency_mismatch','min_independent_repetitions','reference_agreement_requirement')},
        assessor_identity=None,actual_blinding_statement=None,adjudication_rationale=None,
        requirements=['justify_and_lock_criteria_before_new_confirmation_collection',
            'keep_development_data_separate_from_held_out_confirmation',
            'retain_boundary_and_censor_denominators_not_only_successful_waits',
            'do_not_use_same_proxy_as_both_classifier_input_and_independent_causal_reference',
            'require_separate_evidence_for_healthy_recovery_and_alternative_causes',
            'record_actual_work_clock_scope_and_observer_mismatch_for_separate_trace_evidence',
            'no_exclusive_GPU_phase_or_GPU_execution_start_claim_from_host_hooks'],
        calibration_enabled=False,classifier_feature_profile_created=False,references_created=0,
        numerical_acceptance_established=False,study_ready=False,protocol_frozen=False)


def cohort(states,start,end):
    """Independent bracket reconstruction, with uncertain boundaries kept out."""
    observations=[];ambiguous=[]
    for rid,state in states.items():
        scheduled=state['scheduled']
        if scheduled is None:continue
        lo,hi=scheduled['hook_enter_ns'],scheduled['hook_return_ns']
        if hi<start or lo>=end:continue
        if not start<=lo<=hi<end:ambiguous.append(rid);continue
        admitted=state['admission']
        lower=max(0,lo-admitted['hook_return_ns'])/1e6
        upper=(hi-admitted['hook_enter_ns'])/1e6
        if upper<lower:raise ValueError('Reversed scheduler wait bounds')
        observations.append(dict(request_id=rid,wait_lower_ms=lower,wait_upper_ms=upper))
    return observations,ambiguous


def boundary_state(states,end):
    """Retrospective final-history reconstruction; never online probe counts."""
    counts=Counter();ids={'unscheduled':[],'unfinished':[]}
    for rid,state in states.items():
        admission=state['admission']
        if admission['hook_enter_ns']>=end:continue
        if admission['hook_return_ns']>=end:
            counts['admission_boundary_ambiguous']+=1;continue
        counts['definitely_admitted_before_end']+=1
        for key,label in [('scheduled','unscheduled'),('finished','unfinished')]:
            event=state[key]
            if event is None or event['hook_enter_ns']>=end:
                counts[label+'_definite']+=1;ids[label].append(rid)
            elif event['hook_return_ns']>=end:counts[label+'_boundary_ambiguous']+=1
    return {key:counts[key] for key in ('definitely_admitted_before_end','admission_boundary_ambiguous',
        'unscheduled_definite','unscheduled_boundary_ambiguous','unfinished_definite','unfinished_boundary_ambiguous')}|{
        label+'_definite_request_ids':sorted(values) for label,values in ids.items()}


def audit_window(probes,binding,window,final_states,requests,withheld_interval=None):
    start,end,deadline=(window[k] for k in ('start_ns','end_ns','decision_ns'))
    if deadline!=end+750_000_000:raise ValueError('Changed consumer deadline')
    late=window['owner_observed_at_ns']-deadline>50_000_000
    if late!=window['owner_late']:raise ValueError('Incorrect owner lateness flag')
    ready=[(name,r) for name,r in probes if r['received_at_ns']<=deadline]
    name,receipt=max(ready,key=lambda p:p[1]['received_at_ns']) if ready else (None,None)
    expected=event_window(receipt,binding,start_ns=start,end_ns=end,decision_ns=deadline,withheld_interval=withheld_interval)
    if late:expected=dict(status='unresolved',reason='owner_decision_deadline_missed',bounds=None,diagnosis=None)
    if any(window[k]!=v for k,v in expected.items()):raise ValueError('Recorded consumer gate differs')
    raw=None;states=None
    if receipt is not None:
        states=validate_snapshot(receipt['data'],receipt['command'],binding,receipt['received_at_ns'])
        if receipt['data']['epoch_ns']<=start<end<=receipt['data']['source_probe_ns']:
            observations,ambiguous=cohort(states,start,end)
            raw=dict(observations=observations,boundary_ambiguous_request_ids=ambiguous,
                still_unscheduled_at_probe=sum(s['scheduled'] is None and s['finished'] is None for s in states.values()),
                still_unscheduled_at_probe_request_ids=sorted(rid for rid,s in states.items() if s['scheduled'] is None and s['finished'] is None),
                finished_without_schedule_at_probe=sum(s['scheduled'] is None and s['finished'] is not None for s in states.values()))
    if expected['status']=='bounds_available':
        if raw is None or raw['observations']!=expected['bounds']['observations'] or raw['boundary_ambiguous_request_ids']!=expected['bounds']['boundary_ambiguous_request_ids']:
            raise ValueError('Independent bound/cohort reconstruction differs')
    scheduled_ids={r['request_id'] for r in raw['observations']} if raw else set()
    client_admitted={'cmpl-'+r['request_id']+'-0' for r in requests if start<=r['admitted_at_ns']<end}
    client_completed={'cmpl-'+r['request_id']+'-0' for r in requests if start<=r['completed_at_ns']<end}
    final_observations,final_ambiguous=cohort(final_states,start,end) if final_states is not None else (None,None)
    reconstructed=boundary_state(final_states,end) if final_states is not None else None
    probe_pending=set(raw['still_unscheduled_at_probe_request_ids']) if raw is not None else None
    historical_pending=set(reconstructed['unscheduled_definite_request_ids']) if reconstructed is not None else None
    proxy=None
    if raw is not None:
        observations=raw['observations'];low=sorted(r['wait_lower_ms'] for r in observations);high=sorted(r['wait_upper_ms'] for r in observations)
        rank=math.ceil(.95*len(low))-1
        proxy=dict(n=len(low),lower_ms=low[rank] if low else None,upper_ms=high[rank] if high else None,
            interpretation='descriptive_sample_order_statistic_bounds_no_precision_or_existing_metric_acceptance')
    return dict(start_ns=start,end_ns=end,decision_ns=deadline,consumer_status=expected['status'],consumer_reason=expected['reason'],
        selected_probe=name,ready_probe_count=len(ready),later_probes_not_used=len(probes)-len(ready),
        selected_receipt_after_window_end_ms=None if receipt is None else (receipt['received_at_ns']-end)/1e6,
        receipt_margin_before_deadline_ms=None if receipt is None else (deadline-receipt['received_at_ns'])/1e6,
        owner_lateness_ms=(window['owner_observed_at_ns']-deadline)/1e6,owner_late=late,
        raw_source_at_deadline=raw,raw_source_interpretation='offline_only_including_withheld_rows_never_retrofill_consumer',
        consumer_usable_bound_observations=len(raw['observations']) if raw is not None and expected['status']=='bounds_available' else 0,
        descriptive_proxy_p95_bounds=proxy,
        client_admission_count=len(client_admitted),client_completion_count=len(client_completed),
        client_pending_at_window_end=sum(r['admitted_at_ns']<end<=r['completed_at_ns'] for r in requests),
        schedule_cohort_not_client_admission_ids=sorted(scheduled_ids-client_admitted) if raw is not None else None,
        client_admission_not_schedule_cohort_ids=sorted(client_admitted-scheduled_ids) if raw is not None else None,
        schedule_cohort_not_client_completion_ids=sorted(scheduled_ids-client_completed) if raw is not None else None,
        client_completion_not_schedule_cohort_ids=sorted(client_completed-scheduled_ids) if raw is not None else None,
        retrospective_final_cohort_count=None if final_observations is None else len(final_observations),
        retrospective_final_boundary_ambiguous_ids=final_ambiguous,
        retrospective_source_state_at_window_end=reconstructed,
        probe_only_unscheduled_ids=sorted(probe_pending-historical_pending) if probe_pending is not None and historical_pending is not None else None,
        window_end_only_unscheduled_ids=sorted(historical_pending-probe_pending) if probe_pending is not None and historical_pending is not None else None,
        retrospective_state_is_online_feature=False,existing_request_wait_p95_mapping_supported=False,
        classifier_feature_accepted=False,diagnosis=None)


def audit_campaign(campaign,expected_manifest_sha256):
    campaign=Path(campaign).resolve();manifest_raw=(campaign/'artifact_manifest.json').read_bytes()
    if sha(manifest_raw)!=expected_manifest_sha256:raise ValueError('Campaign manifest differs from retained digest')
    manifest=json.loads(manifest_raw)['files']
    def load(name):
        path=Path(name);full=campaign/path
        if path.is_absolute() or '..' in path.parts or full.is_symlink() or not full.resolve().is_relative_to(campaign):raise ValueError('Unsafe campaign path')
        if name not in manifest:raise ValueError('Unmanifested input: '+name)
        raw=full.read_bytes()
        if sha(raw)!=manifest[name]:raise ValueError('Campaign artifact hash mismatch: '+name)
        return raw
    for name in manifest:load(name)
    def read(name):return json.loads(load(name))
    result=read('RESULT.json')
    if result['status']!='engineering_collection_complete' or result['protocol_version']!='event_challenge_preparation_v2':
        raise ValueError('Complete v2 development campaign required for this audit')
    jobs=[];all_observations=[];hook_admission=[];hook_schedule=[];probe_rtt=[];windows=[]
    for entry in read('jobs.json'):
        job_id=entry['job_id'];prefix=job_id+'/';job=read(prefix+'job.json')
        binding=ServingBinding(**read(prefix+'binding.json'));playback=read(prefix+'playback.json')
        requests=[json.loads(line) for line in load(prefix+'requests/receipts.jsonl').splitlines()]
        if len({r['request_id'] for r in requests})!=len(requests):raise ValueError('Duplicate client IDs')
        probes=[];tokens=set()
        for name in sorted(n for n in manifest if n.startswith(prefix+'probe-') and n.endswith('.json')):
            receipt=read(name);validate_snapshot(receipt['data'],receipt['command'],binding,receipt['received_at_ns'])
            if receipt['command']['token'] in tokens:raise ValueError('Repeated probe token')
            tokens.add(receipt['command']['token'])
            if probes and receipt['data']['events'][:len(probes[-1][1]['data']['events'])]!=probes[-1][1]['data']['events']:
                raise ValueError('Source history is not an immutable prefix')
            raw_name=prefix+f'session-{binding.generation}/scheduler-events/snapshot-'+receipt['command']['token']+'.json'
            if sha(load(raw_name))!=receipt['raw_sha256']:raise ValueError('Raw source snapshot hash differs')
            if json.loads(load(raw_name))!=receipt['data']:raise ValueError('Source snapshot differs from receipt')
            probes.append((name,receipt));probe_rtt.append((receipt['received_at_ns']-receipt['command']['requested_at_ns'])/1e6)
        if bool(probes)!=job['event_instrumentation']:raise ValueError('Unexpected collector role/source history')
        final_states=None;job_observations=[]
        if probes:
            final_lifecycle(probes[-1][1],binding,requests)
            final_states=validate_snapshot(probes[-1][1]['data'],probes[-1][1]['command'],binding,probes[-1][1]['received_at_ns'])
            for r in requests:
                if r['request_id']=='challenge-warmup':continue
                rid='cmpl-'+r['request_id']+'-0';s=final_states[rid];a=s['admission'];p=s['scheduled']
                lower=max(0,p['hook_enter_ns']-a['hook_return_ns'])/1e6;upper=(p['hook_return_ns']-a['hook_enter_ns'])/1e6
                row=dict(job_id=job_id,request_id=rid,wait_lower_ms=lower,wait_upper_ms=upper,width_ms=upper-lower,
                    admission_hook_width_ms=(a['hook_return_ns']-a['hook_enter_ns'])/1e6,
                    schedule_hook_width_ms=(p['hook_return_ns']-p['hook_enter_ns'])/1e6)
                job_observations.append(row);hook_admission.append(row['admission_hook_width_ms']);hook_schedule.append(row['schedule_hook_width_ms'])
            all_observations.extend(job_observations)
        recorded_windows=read(prefix+'consumer_windows.json')
        if len(recorded_windows)!=6:raise ValueError('Expected six recorded windows')
        withheld=None if job['evidence_withheld_offsets_ns'] is None else tuple(playback['start_ns']+x for x in job['evidence_withheld_offsets_ns'])
        audited=[]
        for i,w in enumerate(recorded_windows):
            if (w['start_ns'],w['end_ns'])!=(playback['start_ns']+i*10_000_000_000,playback['start_ns']+(i+1)*10_000_000_000):raise ValueError('Changed window grid')
            audited.append(audit_window(probes,binding,w,final_states,requests,withheld))
        windows.extend(audited)
        jobs.append(dict(job_id=job_id,role=job['role'],source_collection_enabled=job['event_instrumentation'],
            binding=read(prefix+'binding.json'),source_probes=len(probes),
            scheduled_client_requests=len(requests)-1,final_source_case_requests=len(job_observations) if probes else None,
            final_incomplete_lifecycles=0 if probes else None,windows=audited,request_bounds=job_observations))
    raw_windows=[w for w in windows if w['raw_source_at_deadline'] is not None]
    accepted=[w for w in windows if w['consumer_status']=='bounds_available']
    withheld=[w for w in windows if w['consumer_reason']=='deliberately_withheld_consumer_event_evidence']
    summary=dict(jobs=len(jobs),windows=len(windows),source_enabled_jobs=sum(j['source_collection_enabled'] for j in jobs),
        source_probes=len(probe_rtt),final_source_case_requests=len(all_observations),
        raw_ready_windows=len(raw_windows),consumer_bound_windows=len(accepted),withheld_windows=len(withheld),
        consumer_statuses=dict(Counter(w['consumer_status'] for w in windows)),
        consumer_reasons=dict(Counter(w['consumer_reason'] for w in windows if w['consumer_reason'])),
        consumer_usable_bound_observations=sum(w['consumer_usable_bound_observations'] for w in windows),
        raw_withheld_observations=sum(len(w['raw_source_at_deadline']['observations']) for w in withheld if w['raw_source_at_deadline'] is not None),
        raw_boundary_ambiguous_occurrences=sum(len(w['raw_source_at_deadline']['boundary_ambiguous_request_ids']) for w in raw_windows),
        source_at_probe_unscheduled_occurrences=sum(w['raw_source_at_deadline']['still_unscheduled_at_probe'] for w in raw_windows),
        source_at_probe_finished_without_schedule_occurrences=sum(w['raw_source_at_deadline']['finished_without_schedule_at_probe'] for w in raw_windows),
        final_incomplete_source_case_lifecycles=0,
        retrospective_window_end_unscheduled_occurrences=sum(w['retrospective_source_state_at_window_end']['unscheduled_definite'] for w in raw_windows),
        retrospective_window_end_unfinished_occurrences=sum(w['retrospective_source_state_at_window_end']['unfinished_definite'] for w in raw_windows),
        probe_vs_window_end_unscheduled_mismatch_windows=sum(bool(w['probe_only_unscheduled_ids'] or w['window_end_only_unscheduled_ids']) for w in raw_windows),
        schedule_vs_client_admission_mismatch_windows=sum(bool(w['schedule_cohort_not_client_admission_ids'] or w['client_admission_not_schedule_cohort_ids']) for w in raw_windows),
        schedule_vs_client_completion_mismatch_windows=sum(bool(w['schedule_cohort_not_client_completion_ids'] or w['client_completion_not_schedule_cohort_ids']) for w in raw_windows),
        raw_schedule_cohort_below_twenty_windows=sum(len(w['raw_source_at_deadline']['observations'])<20 for w in raw_windows),
        raw_schedule_cohort_empty_windows=sum(not w['raw_source_at_deadline']['observations'] for w in raw_windows),
        wait_width_ms=distribution([r['width_ms'] for r in all_observations]),
        admission_hook_width_ms=distribution(hook_admission),schedule_hook_width_ms=distribution(hook_schedule),
        source_probe_round_trip_ms=distribution(probe_rtt),
        receipt_after_window_end_ms=distribution([w['selected_receipt_after_window_end_ms'] for w in raw_windows]),
        receipt_margin_before_deadline_ms=distribution([w['receipt_margin_before_deadline_ms'] for w in raw_windows]),
        owner_late_windows=sum(w['owner_late'] for w in windows))
    return dict(version='scheduler_bound_precision_audit_v1',processing_mode='offline_development_audit_no_replayed_online_decisions',
        campaign_manifest_sha256=sha(manifest_raw),artifact_hashes_verified=len(manifest),summary=summary,jobs=jobs,
        cohort='first_positive_CPU_schedule_bracket_wholly_inside_half_open_window',
        sample_p95_interpretation='descriptive_order_statistic_bounds_not_population_precision',
        twenty_request_count_is_engineering_context_not_scientific_acceptance=True,
        existing_request_wait_p95_mapping_supported=False,prefill_service_fraction=None,phase_attribution='not_instrumented',
        classifier_activated=False,calibration_enabled=False,references_created=0,GPU_used=False,study_ready=False,protocol_frozen=False)
