"""Exact offered paired collection helpers; no truth labels or reference locks."""
import asyncio,hashlib,json
from dataclasses import asdict
from pathlib import Path
from experiments.tracing.arrival_schedule import ArrivalSchedule
from experiments.tracing.live_features import LiveMetricCollector,LiveFeatureWindow,map_receipt,persist_receipt
from experiments.tracing.feature_collection import http_body,response_usage,ObservedCompletion
from experiments.tracing.aggregation import RequestCompletion
from experiments.tracing.schedule_playback import SchedulePlayback,PlaybackConfig
from experiments.tracing.measured_evidence import fields_only

ROLES={'feature_collection','matched_full_trace'}


def load_pairs(directory):
    directory=Path(directory);manifest=json.loads((directory/'PAIRS.json').read_text())
    if manifest['status']!='candidate_schedules_materialized_not_executed' or manifest['study_ready'] or manifest['calibration_enabled'] or manifest['protocol_frozen']:
        raise ValueError('Only unfrozen candidate pairs accepted')
    jobs=manifest['jobs']
    if len(jobs)!=4:raise ValueError('Exactly two pairs/four jobs permitted')
    result=[]
    for pair in ('short','long'):
        rows=[j for j in jobs if j['pair_id']==pair]
        if len(rows)!=2 or any(type(j['order_in_pair']) is not int for j in rows) or {j['role'] for j in rows}!=ROLES or {j['order_in_pair'] for j in rows}!={0,1}:raise ValueError('Invalid paired roles/order')
        hashes=set()
        for row in sorted(rows,key=lambda j:j['order_in_pair']):
            fields_only(row,{'pair_id','role','order_in_pair','schedule_path','file_sha256','fresh_owned_restart_required','executed'})
            if row['fresh_owned_restart_required'] is not True or row['executed'] is not False:raise ValueError('Fresh unexecuted jobs required')
            path=Path(row['schedule_path'])
            if path.is_absolute() or '..' in path.parts or (directory/path).is_symlink():raise ValueError('Bounded schedule path required')
            path=(directory/path).resolve()
            if not path.is_relative_to(directory.resolve()) or path.stat().st_size>1048576:raise ValueError('Schedule escape/size limit')
            schedule=ArrivalSchedule.load(path)
            if schedule.file_sha256!=row['file_sha256']:raise ValueError('Offered file hash mismatch')
            if schedule.duration_ns!=8_000_000_000 or not 1<=len(schedule.requests)<=12:raise ValueError('Bounded eight-second offered schedule required')
            if any(r.payload['max_tokens']!=32 or r.payload.get('ignore_eos') is not True for r in schedule.requests):raise ValueError('Pilot requires exactly 32 requested output tokens')
            hashes.add(schedule.file_sha256);result.append((row,schedule))
        if len(hashes)!=1:raise ValueError('Paired roles must share exact offered bytes')
    return manifest,result


class BoundCollector:
    def __init__(self,endpoint,binding):
        self.binding=binding;self.collector=LiveMetricCollector(endpoint,binding,timeout_s=2);self.receipts={}
    async def sample(self,clock,sample_id):
        if sample_id in self.receipts:raise ValueError('Duplicate scrape identity')
        receipt=await self.collector.sample(clock,sample_id);self.receipts[sample_id]=receipt
        return map_receipt(receipt,self.binding,now_ns=clock.now_ns())[0]
    def window(self,clock,start,end,**options):
        collector=self
        class BoundWindow(LiveFeatureWindow):
            def on_server(self,record):
                receipt=collector.receipts[record.sample_id]
                expected,_=map_receipt(receipt,self.binding,now_ns=clock.now_ns())
                if expected!=record:raise ValueError('Server sample differs from backing raw receipt')
                return self.on_scrape(receipt)
        return BoundWindow(clock,start,end,binding=self.binding,provenance=self.provenance,**options)


class RawCompletions:
    def __init__(self,output):
        self.output=Path(output);self.output.mkdir();self.rows=[]
    async def collect(self,clock,request_id,endpoint,payload,**options):
        # Names are derived from an internal digest, never untrusted request IDs.
        began=clock.now_ns();status=raw=None;error=None;prompt=output=None;usage_error='request_failed'
        try:
            status,raw=await http_body(endpoint,method='POST',payload=payload,**options)
            if status!=200:error='http_'+str(status)
            else:
                prompt,output,usage_error=response_usage(raw)
                if usage_error:error=usage_error
                elif output!=payload['max_tokens']:error='output_token_usage_mismatch'
        except asyncio.CancelledError:error='client_cancelled';raise
        except Exception as exc:error=type(exc).__name__+': '+str(exc)
        finally:
            done=clock.now_ns();path=hashlib.sha256(request_id.encode()).hexdigest()+'.json' if raw is not None else None
            if raw is not None:(self.output/path).write_bytes(raw)
            self.rows.append(dict(request_id=request_id,started_at_ns=began,completed_at_ns=done,http_status=status,error=error,
                response_path=path,response_sha256=None if raw is None else hashlib.sha256(raw).hexdigest(),prompt_tokens=prompt,output_tokens=output))
            (self.output/'receipts.json').write_text(json.dumps(self.rows,indent=2)+'\n')
        return ObservedCompletion(RequestCompletion(request_id,began,done,done,clock.domain,error is None,error),
            prompt if error is None else None,output if error is None else None,None if error is None else error)


async def collect_job(clock,endpoint,binding,schedule,output,*,provenance):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    collector=BoundCollector(endpoint+'/metrics',binding);collector.provenance=provenance
    completions=RawCompletions(output/'requests')
    def closed(window_id,window):window.persist(output/window_id,window_id)
    driver=SchedulePlayback(schedule,clock,endpoint+'/v1/completions',provenance=provenance,
        config=PlaybackConfig(max_inflight=4,request_timeout_s=12,drain_s=15,max_admission_lateness_s=.25,
            window_s=2,grace_s=.25,min_latency_samples=2,sample_interval_s=.5,sample_timeout_s=3),
        server_collector=collector,window_factory=collector.window,completion_collector=completions.collect,on_window=closed)
    try:return await driver.run()
    finally:
        snapshot=driver.snapshot();(output/'playback.json').write_text(json.dumps(snapshot,indent=2)+'\n')
        # Preserve even out-of-window/cancelled-adjacent collected metric receipts.
        for receipt in collector.receipts.values():persist_receipt(output/'raw_metrics',receipt)


def validate_playback(snapshot):
    counts=snapshot['counts']
    if snapshot['status']!='completed' or snapshot['admitted']!=snapshot['offered'] or counts['completed']!=snapshot['offered']:
        raise ValueError('Paired pilot requires every offered request admitted and completed; retain failed/skipped evidence')
    if not all(snapshot['accounting_checks'].values()) or any(snapshot[k] for k in ('live_request_tasks','live_sampling_tasks','telemetry_overflows')):
        raise ValueError('Unclean request/telemetry lifecycle')
    if any(snapshot['sampling_errors'].values()) or any(snapshot['sampling_skips'].values()):raise ValueError('Sampling incomplete')


def adjudication_packet(root,jobs):
    """Artifact manifest only: no supported causes, predictions, rubric passes or locks."""
    root=Path(root);artifacts=[]
    for job in jobs:
        base=root/job['directory']
        for relative,channel in (('collection/requests/receipts.json','request_diagnostics'),
                ('collection/playback.json','server_diagnostics')):
            p=base/relative
            artifacts.append(dict(job_id=job['job_id'],path=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),channel=channel))
        if job['role']=='matched_full_trace':
            p=base/'trace.sqlite'
            if not p.is_file():raise ValueError('Full-trace job lacks parsed trace')
            artifacts.append(dict(job_id=job['job_id'],path=str(p.relative_to(root)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),channel='matched_full_trace'))
    return dict(version='paired_adjudication_packet_v1',record_role='artifact_packet_not_adjudicated_reference',
        status='awaiting_blinded_assessment',references_created=0,references_locked=0,predictions_computed=False,
        jobs=jobs,artifacts=artifacts,required_assessments=['realized_symptoms','alternative_causes','unresolved_or_negative_evidence',
            'full_trace_control_bracketing_and_kernel_coverage','matched_run_latency_and_work_mismatch','clock_and_cohort_coverage'],
        limitations=['low_rate_two_prompt_plumbing_pilot_not_challenging_incidents','trace_is_a_separate_run_not_same_execution_truth',
            'raw_HTTP_and_metrics_are_independent_of_classifier_but_not_independent_proof_of_causality',
            'human_assessor_identity_blinding_and_rationale_required_before_reference_lock'])
