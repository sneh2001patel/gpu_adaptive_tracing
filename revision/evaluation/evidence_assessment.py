"""Evaluator-only retrospective evidence audit and gap-review contracts.

No classifier input, cause label, reference record/lock or prospective validity is
created. Sampled zero queues never certify healthy operation between scrapes.
"""
import hashlib,json,statistics
from pathlib import Path
from revision.tracing.arrival_schedule import ArrivalSchedule,unique_object
from revision.tracing.feature_collection import response_usage
from revision.tracing.live_features import load_receipt
from revision.tracing.measured_evidence import MeasuredObservation,fields_only,identity

VERSION='paired_evidence_gap_assessment_v1'
REVIEW_FIELDS=('work_mismatch_rationale','latency_mismatch_rationale','negative_evidence_limits',
               'clock_and_cohort_limits','additional_evidence_needed')


def canonical(data):return json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(data):return hashlib.sha256(canonical(data)).hexdigest()


class Bundle:
    def __init__(self,root,expected_manifest_sha256=None):
        self.root=Path(root).resolve()
        raw=self.read('artifact_manifest.json')
        self.manifest_sha256=hashlib.sha256(raw).hexdigest()
        if expected_manifest_sha256 is not None and expected_manifest_sha256!=self.manifest_sha256:raise ValueError('Unexpected artifact manifest identity')
        manifest=json.loads(raw,object_pairs_hook=unique_object);fields_only(manifest,{'files'})
        if type(manifest['files']) is not dict:raise ValueError('Manifest file map required')
        self.files=manifest['files']
        for relative,expected in self.files.items():
            if hashlib.sha256(self.read(relative)).hexdigest()!=expected:raise ValueError('Artifact hash mismatch: '+relative)
    def read(self,relative):
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts or not path.parts:raise ValueError('Bounded relative evidence path required')
        target=self.root/path
        if any(p.is_symlink() for p in [target,*target.parents] if p.is_relative_to(self.root)):raise ValueError('Evidence symlink not accepted')
        if not target.resolve().is_relative_to(self.root) or not target.is_file() or target.stat().st_size>128*1024*1024:raise ValueError('Missing/escaped/oversized evidence file')
        return target.read_bytes()
    def json(self,relative):
        if relative not in self.files:raise ValueError('Evidence not bound by source manifest')
        return json.loads(self.read(relative),object_pairs_hook=unique_object)


def audit_bundle(root,expected_manifest_sha256=None):
    bundle=Bundle(root,expected_manifest_sha256);packet=bundle.json('ADJUDICATION_PACKET.json');result=bundle.json('RESULT.json')
    if packet['record_role']!='artifact_packet_not_adjudicated_reference' or packet['references_created'] or packet['references_locked'] or packet['predictions_computed']:
        raise ValueError('Only unadjudicated prediction-free packets accepted')
    if not result['pilot_passed'] or result['classifier_run']:raise ValueError('Expected completed collection-only pilot')
    jobs=packet['jobs']
    if len(jobs)!=4 or len({j['job_id'] for j in jobs})!=4:raise ValueError('Four distinct paired jobs required')
    for artifact in packet['artifacts']:
        if artifact['path'] not in bundle.files or bundle.files[artifact['path']]!=artifact['sha256']:raise ValueError('Packet artifact is not manifest-bound')
    summaries=[];request_maps={}
    for job in jobs:
        base=job['directory'];play=bundle.json(base+'/collection/playback.json')
        if play['status']!='completed' or play['clock_domain'] is None:raise ValueError('Completed playback/domain required')
        schedule=ArrivalSchedule.from_bytes(bundle.read(base+'/offered.json'))
        if schedule.file_sha256!=play['schedule_file_sha256'] or schedule.file_sha256!=job['schedule_sha256']:raise ValueError('Schedule identity differs')
        requests=bundle.json(base+'/collection/requests/receipts.json');by_id={r['request_id']:r for r in requests}
        if len(by_id)!=len(requests) or set(by_id)!={r.request_id for r in schedule.requests}:raise ValueError('Duplicate/missing realized request IDs')
        latencies=[];usage={}
        for request in requests:
            path=base+'/collection/requests/'+request['response_path']
            raw=bundle.read(path)
            if path not in bundle.files or hashlib.sha256(raw).hexdigest()!=request['response_sha256']:raise ValueError('Response identity differs')
            prompt,output,error=response_usage(raw)
            if request['http_status']!=200 or request['error'] is not None or error:raise ValueError('Request diagnostics contain failure')
            if request['completed_at_ns']<=request['started_at_ns']:raise ValueError('Request clock order invalid')
            latency=(request['completed_at_ns']-request['started_at_ns'])/1e6
            latencies.append(latency);usage[request['request_id']]=(prompt,output)
        request_maps[job['job_id']]=(by_id,usage)
        samples=[]
        for path in sorted(p for p in bundle.files if p.startswith(base+'/collection/raw_metrics/') and p.endswith('.json')):
            meta=bundle.json(path)
            raw_path=str(Path(path).parent/meta['raw_path']) if meta['raw_path'] else None
            if raw_path not in bundle.files or bundle.files[raw_path]!=meta['raw_sha256']:raise ValueError('Metric bytes not manifest-bound')
            receipt=load_receipt(bundle.root/Path(path).parent,Path(path).name)
            if (receipt.binding.worker_pid,receipt.binding.generation,receipt.binding.session_nonce,receipt.binding.clock_domain)!=(job['worker_pid'],job['generation'],job['session_nonce'],play['clock_domain']):
                raise ValueError('Foreign raw metric receipt')
            # Values come from exact-series inspection, not packet job labels.
            from revision.tracing.live_features import map_receipt
            sample,_=map_receipt(receipt,receipt.binding,now_ns=receipt.received_at_ns)
            if sample.error is not None or sample.queue_depth is None:raise ValueError('Missing queue observation')
            samples.append(sample)
        samples.sort(key=lambda s:s.received_at_ns)
        times=[play['start_ns'],*[s.received_at_ns for s in samples],play['horizon_ns']]
        if not samples or any(a>b for a,b in zip(times,times[1:])):raise ValueError('Queue receipts outside horizon or absent')
        windows=[]
        for path in sorted(p for p in bundle.files if p.startswith(base+'/collection/window-') and p.endswith('/observation.json')):
            observation=MeasuredObservation.from_dict(bundle.json(path))
            metrics={m.name:m for m in observation.metrics}
            windows.append(dict(path=path,available_metrics=[n for n,m in metrics.items() if m.value is not None],
                missing={n:m.missing_reason for n,m in metrics.items() if m.value is None},
                sample_counts={n:dict(valid=m.valid_samples,attempted=m.attempted_samples) for n,m in metrics.items()}))
        trace_summary=None
        if job['has_trace']:
            from revision.tracing.nsys_backend import parse_kernel_database
            trace=bundle.json(base+'/trace_receipt.json')
            if not max(trace['start_ack_ns'],trace['start_callback_ns'])<=play['start_ns']<=play['finished_at_ns']<=trace['stop_ack_ns']<=trace['parsed_ready_ns']:
                raise ValueError('Trace control does not bracket playback')
            path=base+'/trace.sqlite'
            if path not in bundle.files:raise ValueError('Trace database not manifest-bound')
            parsed=parse_kernel_database(bundle.root/path,expected_uuid=trace['device_uuid'],expected_pids=[job['worker_pid']])
            trace_summary=dict(kernel_count=parsed['kernel_count'],worker_device_coverage=parsed['coverage'],
                playback_control_bracketed=True,per_request_GPU_clock_mapping=False,capture_active_s=None)
        summaries.append(dict(job_id=job['job_id'],pair_id=job['pair_id'],role=job['role'],request_count=len(requests),
            mean_client_latency_ms=statistics.fmean(latencies),queue_sample_count=len(samples),
            queue_positive_samples=sum(s.queue_depth>0 for s in samples),queue_max_observed=max(s.queue_depth for s in samples),
            max_queue_receipt_gap_including_edges_ms=max(b-a for a,b in zip(times,times[1:]))/1e6,
            queue_interval_claim='point_samples_only_no_continuous_zero_or_source_event_clock_mapping',
            windows=windows,trace=trace_summary))
    comparisons=[]
    for pair_id in ('short','long'):
        pair=[j for j in jobs if j['pair_id']==pair_id]
        if len(pair)!=2 or {j['role'] for j in pair}!={'feature_collection','matched_full_trace'}:raise ValueError('Incomplete pair roles')
        feature=next(j for j in pair if j['role']=='feature_collection');trace=next(j for j in pair if j['role']=='matched_full_trace')
        a,ua=request_maps[feature['job_id']];b,ub=request_maps[trace['job_id']]
        ids=sorted(a.keys()&b.keys());work_equal=set(a)==set(b) and ua==ub
        if not ids:raise ValueError('No matched requests')
        deltas=[]
        for request_id in ids:
            x=(a[request_id]['completed_at_ns']-a[request_id]['started_at_ns'])/1e6
            y=(b[request_id]['completed_at_ns']-b[request_id]['started_at_ns'])/1e6
            deltas.append(dict(request_id=request_id,feature_ms=x,trace_ms=y,trace_minus_feature_ms=y-x,trace_over_feature_ratio=y/x))
        comparisons.append(dict(pair_id=pair_id,artifact_paths=[a['path'] for a in packet['artifacts'] if a['job_id'] in {j['job_id'] for j in pair}],schedule_bytes_equal=feature['schedule_sha256']==trace['schedule_sha256'],
            actual_ID_and_token_work_equal=work_equal,matched_requests=len(ids),client_latency_deltas=deltas,
            latency_tolerance_ms=None,latency_tolerance_ratio=None,min_request_count_for_equivalence=None,
            tolerance_status='not_prospectively_specified_no_equivalence_verdict',reference_eligibility='not_established'))
    return dict(version=VERSION,record_role='retrospective_evidence_gap_audit_not_reference',
        source_manifest_sha256=bundle.manifest_sha256,verified_artifact_entries=len(bundle.files),
        source_packet_sha256=bundle.files['ADJUDICATION_PACKET.json'],jobs=summaries,pairs=comparisons,
        references_created=0,references_locked=0,calibration_enabled=False,study_ready=False,protocol_frozen=False,
        blocking_gaps=['no_prospectively_frozen_reference_rubric_or_mismatch_tolerances',
            'point_sampled_zero_queues_do_not_certify_absence_between_scrapes',
            'sparse_request_windows_have_no_valid_latency_p95',
            'admission_event_wait_clock_mapping_unavailable','exclusive_prefill_GPU_attribution_unavailable',
            'GPU_utilization_not_collected_in_this_pilot','separate_trace_run_has_no_same_execution_request_GPU_attribution',
            'low_rate_repeated_prompts_do_not_exercise_incident_or_recovery_conditions',
            'no_actual_assessor_adjudication_or_reference_lock'],
        note='Retrospective descriptions cannot establish prospective tolerance or scientific reference validity. Hashes are conditional on the supplied manifest, not administrator-proof provenance.')


def draft_rubric():
    return dict(version=VERSION,status='draft_not_frozen_not_fitted',record_role='assessment_rubric_not_reference',
        cause_scope_proposal='queue_pressure_only_candidate_prefill_claim_deferred',
        candidate_features=['request_p95_ms','completed_rps','queue_depth_mean'],
        context_only=['prompt_tokens_mean','output_tokens_mean'],
        unsupported_or_optional=['request_wait_p95_ms','prefill_service_fraction','gpu_util_mean'],
        prospective_limits_required=dict(max_queue_receipt_gap_ms=None,min_latency_completions_per_window=None,
            matched_work_token_tolerance=None,matched_latency_ratio_tolerance=None,min_independent_repetitions=None),
        criteria=[dict(id=key,required_evidence=text) for key,text in (
            ('queue_support','Same-run independently clock-bound server admission/wait evidence, sustained realized backlog and symptom/reversal evidence; intended rate is not a cause label.'),
            ('negative_or_healthy','Explicit supported-cause scope, adequate observation coverage and alternatives; zero queue samples or HTTP success alone are insufficient.'),
            ('matched_trace','Exact offered bytes plus actual work and prospective mismatch limits; separate executions remain distinct and trace loss/correlation limits must be recorded.'),
            ('phase_claim','Defer prefill diagnosis until exclusive GPU phase attribution and a validated clock/cohort mapping exist.'),
            ('adjudication','Assessor identity, actual blinding statement, criterion-linked artifacts, rationale and unresolved outcomes; lock through the existing reference store before scoring.'))],
        threshold_fitting_enabled=False,reference_export_enabled=False,
        next_collection_requirements=['clock-bound server admission/first-service/completion event collector',
            'enough actual completions for proposed latency windows','bounded offered-rate ramp and removal/recovery',
            'temporary lull then recurrence and an ambiguous/unresolved control','pinned disjoint calibration/development/confirmation corpora and seeds',
            'explicit prefix-cache policy and paired-run mismatch/repetition design'])


def review_template(audit,rubric):
    return dict(version=VERSION,record_role='evidence_gap_review_not_reference',audit_sha256=digest(audit),rubric_sha256=digest(rubric),
        assessor_id=None,blinded_to_predictions_and_policy=None,status='not_started',limitations=[],
        pairs=[dict(pair_id=p['pair_id'],outcome=None,reviewed_artifacts=[],**{name:None for name in REVIEW_FIELDS}) for p in audit['pairs']])


def validate_gap_review(review,audit,rubric,artifact_paths):
    fields_only(review,{'version','record_role','audit_sha256','rubric_sha256','assessor_id','blinded_to_predictions_and_policy','status','limitations','pairs'})
    if (review['version'],review['record_role'],review['status'])!=(VERSION,'evidence_gap_review_not_reference','completed'):raise ValueError('Completed gap-review record required')
    if review['audit_sha256']!=digest(audit) or review['rubric_sha256']!=digest(rubric):raise ValueError('Review is bound to another audit/rubric')
    identity(review['assessor_id'],'assessor identity')
    if type(review['blinded_to_predictions_and_policy']) is not bool:raise ValueError('Actual blinding statement required')
    if type(review['limitations']) is not list or not review['limitations']:raise ValueError('Single-assessor limitations required')
    for limitation in review['limitations']:identity(limitation,'limitation')
    pairs=review['pairs']
    if type(pairs) is not list or len(pairs)!=len(audit['pairs']) or {p['pair_id'] for p in pairs}!={p['pair_id'] for p in audit['pairs']}:raise ValueError('Exactly one review per observed pair required')
    for pair in pairs:
        fields_only(pair,{'pair_id','outcome','reviewed_artifacts',*REVIEW_FIELDS})
        if pair['outcome'] not in ('unresolved','needs_more_evidence'):raise ValueError('This incomplete pilot cannot assert healthy/supported reference outcomes')
        for name in REVIEW_FIELDS:identity(pair[name],name)
        paths=pair['reviewed_artifacts']
        allowed=next(p['artifact_paths'] for p in audit['pairs'] if p['pair_id']==pair['pair_id'])
        if type(paths) is not list or not paths or len(set(paths))!=len(paths) or not set(paths)<=set(artifact_paths)&set(allowed):raise ValueError('Reviewed artifacts must be known unique paths for this pair')
    return dict(version=VERSION,status='gap_review_structure_valid_not_authenticated_adjudication',
        assessor_id=review['assessor_id'],references_created=0,references_locked=0,reference_export_enabled=False,
        calibration_enabled=False,note='Validation does not authenticate assessor identity, verify actual blinding or create a ReferenceRecord.')
