"""Audit local step-025 backup; no GPU, classification or reference adjudication."""
import hashlib,json,tarfile
from pathlib import Path
from revision.tracing.nsys_backend import parse_kernel_database
from revision.tracing.arrival_schedule import ArrivalSchedule
from revision.feasibility.paired_collection import load_pairs,validate_playback
from revision.tracing.measured_evidence import MeasuredObservation
from revision.tracing.feature_collection import response_usage
from revision.tracing.live_features import load_receipt,ServingBinding,map_receipt
from revision.tracing.worker_barrier import validate_barrier
BASE=Path(__file__).resolve().parent.parent;ROOT=BASE/'pairs_001';DEPLOY=BASE/'pairs_025_deployment'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result=read(ROOT/'RESULT.json');assert result['pilot_passed'] and not result['errors'] and result['jobs_completed']==4 and result['trace_attempts']==2
assert result['references_created']==result['references_locked']==0
for key in ('study_ready','calibration_enabled','protocol_frozen','classifier_run'):assert result[key] is False
assert result['capture_active_s'] is None
files=read(ROOT/'artifact_manifest.json')['files']
for name,expected in files.items():assert sha(ROOT/name)==expected,name
assert sha(DEPLOY/'source_step025.tar.gz')==read(DEPLOY/'source_archive.json')['sha256']
source_count=0
with tarfile.open(DEPLOY/'source_step025.tar.gz') as tar:
 for manifest in [ROOT/'source_manifest.json',*ROOT.glob('job-*/source_manifest.json')]:
  for name,expected in read(manifest)['files'].items():
   assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
   source_count+=1
original,planned=load_pairs(BASE/'capacity_001/paired_schedules');jobs=read(ROOT/'jobs.json');assert len(jobs)==4
packet=read(ROOT/'ADJUDICATION_PACKET.json');assert packet['references_created']==packet['references_locked']==0
assert packet['record_role']=='artifact_packet_not_adjudicated_reference' and packet['status']=='awaiting_blinded_assessment'
for artifact in packet['artifacts']:assert sha(ROOT/artifact['path'])==artifact['sha256']
assert len(packet['artifacts'])==10 and len(packet['matched_run_differences'])==2
request_count=metric_count=window_count=0;traces=[];workers=[];nonces=[]
for job,(expected,schedule) in zip(jobs,planned):
 directory=ROOT/job['directory'];actual=ArrivalSchedule.load(directory/'offered.json')
 assert actual.file_sha256==schedule.file_sha256==job['schedule_sha256']
 assert job['pair_id']==expected['pair_id'] and job['role']==expected['role'] and job['order_in_pair']==expected['order_in_pair']
 workers.append(job['worker_pid']);nonces.append(job['session_nonce'])
 playback=read(directory/'collection/playback.json');validate_playback(playback)
 assert playback['offered']==playback['counts']['completed']==2 and playback['schedule_file_sha256']==schedule.file_sha256
 receipts=read(directory/'collection/requests/receipts.json');assert len(receipts)==2
 expected_prompt=17 if job['pair_id']=='short' else 1072
 warmup_prompt,warmup_output,warmup_error=response_usage((directory/'warmup.json').read_bytes())
 assert warmup_error is None and warmup_prompt==expected_prompt and warmup_output==32
 for r in receipts:
  p=directory/'collection/requests'/r['response_path'];assert sha(p)==r['response_sha256']
  prompt,output,error=response_usage(p.read_bytes());assert error is None and prompt==expected_prompt and output==32
  assert r['http_status']==200 and r['error'] is None
  request_count+=1
 for observation_path in sorted((directory/'collection').glob('window-*/observation.json')):
  observation=MeasuredObservation.from_dict(read(observation_path));assert observation.provenance=='live_online' and observation.kernel is None
  metrics={m.name:m for m in observation.metrics}
  for name in ('request_wait_p95_ms','prefill_service_fraction','gpu_util_mean'):assert metrics[name].value is None
  window_count+=1
 for path in (directory/'collection/raw_metrics').glob('*.json'):
  receipt=load_receipt(path.parent,path.name);assert receipt.binding.worker_pid==job['worker_pid'] and receipt.binding.generation==job['generation']
  sample,_=map_receipt(receipt,receipt.binding,now_ns=receipt.received_at_ns);assert sample.error is None
  metric_count+=1
 if job['has_trace']:
  trace=read(directory/'trace_receipt.json');assert trace['capture_active_s'] is None
  backend=read(directory/'backend.json');assert backend['ordinal']==1 and len(backend['attempts'])==1
  assert all(a['state']=='ready' and a['error'] is None and a['cleanup_complete'] for a in backend['attempts'].values())
  assert max(trace['start_ack_ns'],trace['start_callback_ns'])<=playback['start_ns']<=playback['finished_at_ns']<=trace['stop_ack_ns']<=trace['parsed_ready_ns']
  parsed=parse_kernel_database(directory/'trace.sqlite',expected_uuid=trace['device_uuid'],expected_pids=[job['worker_pid']])
  assert parsed['kernel_count']==trace['kernel_evidence']['kernel_count']
  traces.append(dict(job_id=job['job_id'],worker_pid=job['worker_pid'],kernel_count=parsed['kernel_count']))
 else:assert not (directory/'trace.sqlite').exists() and not list(directory.glob('session-*/*.nsys-rep'))
assert len(set(workers))==len(set(nonces))==4 and len(traces)==2 and request_count==8 and window_count==16
quiet=read(ROOT/'quiet_evidence.json');tokens=set()
for row in quiet:
 command=row['barrier_command'];receipt=row['barrier_receipt'];assert command['token'] not in tokens;tokens.add(command['token'])
 validate_barrier(receipt,command,pid=receipt['pid'],device_uuid=receipt['device_uuid'],received_at_ns=row['barrier_received_at_ns'])
 for side in ('before','after'):assert sha(ROOT/row[side+'_path'])==row[side+'_sha256']
assert len(quiet)==24
cleanup=read(ROOT/'cleanup_sessions.json');assert not cleanup['errors'] and len(cleanup['sessions'])==4
assert all(s['closed'] and s['cleanup']['group_absent'] and s['cleanup']['worker_absent'] for s in cleanup['sessions'])
post=read(BASE/'pairs_post_cleanup_checks.json');assert len(post['processes'])==4
assert all(all(r[k] for k in ('parent_absent','worker_absent','group_absent')) for r in post['processes'])
assert not post['compute']['stdout'].strip() and post['gpu']['stdout'].strip().endswith(', 0')
report=dict(cpu_tests_passed=451,new_tests=12,artifact_hash_entries=len(files),source_fingerprint_entries=source_count,
 jobs_completed=4,offered_per_job=2,total_successful_playback_requests=request_count,warmups=4,raw_metric_receipts=metric_count,
 measured_windows=window_count,fresh_barriers=len(tokens),validated_traces=traces,packet_artifacts=10,
 references_created=0,references_locked=0,post_cleanup_verified=True,study_ready=False)
(BASE/'PAIRS_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
