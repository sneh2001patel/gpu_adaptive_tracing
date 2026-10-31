"""Read-only step-024 backup audit; uses local files, never GPU execution."""
from dataclasses import asdict
import hashlib,json,tarfile,tempfile
from pathlib import Path
from revision.feasibility.capacity import materialize_pairs
from revision.tracing.arrival_schedule import ArrivalSchedule
from revision.tracing.measured_evidence import MeasuredObservation
from revision.tracing.live_features import load_receipt,ServingBinding,map_receipt
from revision.tracing.feature_collection import response_usage
from revision.tracing.worker_barrier import validate_barrier

BASE=Path(__file__).resolve().parent.parent
ROOT=BASE/'capacity_001';DEPLOY=BASE/'capacity_024_deployment'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result=read(ROOT/'RESULT.json');assert result['pilot_passed'] and not result['errors']
for key in ('calibration_enabled','study_ready','protocol_frozen','saturation_capacity_established'):assert result[key] is False
assert result['capture_count']==0
files=read(ROOT/'artifact_manifest.json')['files']
for name,expected in files.items():assert sha(ROOT/name)==expected,name
archive=DEPLOY/'source_step024.tar.gz';assert sha(archive)==read(DEPLOY/'source_archive.json')['sha256']
sources=read(ROOT/'source_manifest.json')['files']
with tarfile.open(archive) as tar:
 for name,expected in sources.items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
corpus=read(ROOT/'corpus.json');prompt_counts={r['band']:r['tokenizer_prompt_tokens'] for r in corpus['prompts']}
for row in corpus['prompts']:assert hashlib.sha256(row['prompt'].encode()).hexdigest()==row['prompt_utf8_sha256']
for warmup in read(ROOT/'warmups.json'):
 assert warmup['http_status']==200 and warmup['output_tokens']==32 and warmup['prompt_tokens']==warmup['tokenizer_prompt_tokens']
 assert sha(ROOT/warmup['response_path'])==warmup['response_sha256']
cells=read(ROOT/'cells.json');assert len(cells)==6;total=horizon=drained=scrapes=0;rows=[]
for cell in cells:
 directory=ROOT/f'{cell["band"]}-c{cell["concurrency"]}'
 requests=read(directory/'requests.json');assert len(requests)==cell['issued']==cell['terminal_count']<=24
 assert cell['request_errors']==0 and not cell['drain_cancelled'] and cell['peak_inflight']<=cell['concurrency']
 for r in requests:
  assert r['http_status']==200 and r['error'] is None
  assert r['started_at_ns']<cell['horizon_ns'] and r['completed_at_ns']>=r['started_at_ns']
  assert r['completed_in_horizon']==(r['completed_at_ns']<cell['horizon_ns'])
  assert sha(directory/r['response_path'])==r['response_sha256']
  prompt,output,error=response_usage((directory/r['response_path']).read_bytes())
  assert error is None and output==32 and prompt==prompt_counts[cell['band']]
 n=sum(r['completed_in_horizon'] for r in requests);assert n==cell['successful_in_horizon']
 assert n/8==cell['successful_in_horizon_rps']
 observation=MeasuredObservation.from_dict(read(directory/'features/observation.json'))
 metrics={m.name:m for m in observation.metrics}
 assert observation.provenance=='live_online' and observation.kernel is None
 assert metrics['completed_rps'].value==n/8
 for name in ('request_wait_p95_ms','prefill_service_fraction','gpu_util_mean'):assert metrics[name].value is None
 audit=read(directory/'features/window_audit.json')
 binding=ServingBinding(**audit['binding']);assert binding.worker_pid==cell['worker_pid'] and binding.generation==cell['generation']
 for relative in audit['receipt_paths']:
  receipt=load_receipt(directory/'features/receipts',relative)
  sample,diagnostic=map_receipt(receipt,binding,now_ns=receipt.received_at_ns)
  assert sample.error is None and sample.queue_depth is not None
  scrapes+=1
 rows.append(dict(band=cell['band'],concurrency=cell['concurrency'],issued=len(requests),successful_in_horizon=n,
  drain_completions=len(requests)-n,observed_horizon_rps=n/8,queue_sample_count=metrics['queue_depth_mean'].valid_samples,
  request_budget_reached=cell['request_budget_reached']))
 total+=len(requests);horizon+=n;drained+=len(requests)-n
quiet=read(ROOT/'quiet_evidence.json');tokens=set()
for row in quiet:
 command=row['barrier_command'];receipt=row['barrier_receipt'];assert command['token'] not in tokens;tokens.add(command['token'])
 validate_barrier(receipt,command,pid=receipt['pid'],device_uuid=receipt['device_uuid'],received_at_ns=row['barrier_received_at_ns'])
 for side in ('before','after'):assert sha(ROOT/row[side+'_path'])==row[side+'_sha256']
assert len(quiet)==20
sessions=read(ROOT/'cleanup_sessions.json');assert not sessions['errors'] and len(sessions['sessions'])==2
assert all(s['closed'] and s['cleanup']['group_absent'] and s['cleanup']['worker_absent'] for s in sessions['sessions'])
pairs=read(ROOT/'paired_schedules/PAIRS.json')
with tempfile.TemporaryDirectory() as temp:
 rebuilt=materialize_pairs(corpus,cells,read(ROOT/'serving_configuration.json')['model'],Path(temp)/'pairs')
 assert rebuilt==pairs
 for row in pairs['schedules']:
  name=row['band']+'_offered.json';assert (Path(temp)/'pairs'/name).read_bytes()==(ROOT/'paired_schedules'/name).read_bytes()
  assert ArrivalSchedule.load(ROOT/'paired_schedules'/name).file_sha256==row['file_sha256']
cleanup=read(BASE/'capacity_post_cleanup_checks.json')
assert all(all(p[k] for k in ('parent_absent','worker_absent','group_absent')) for p in cleanup['processes'])
assert not cleanup['compute']['stdout'].strip() and cleanup['gpu']['stdout'].strip().endswith(', 0')
report=dict(artifact_hash_entries=len(files),source_fingerprint_entries=len(sources),cpu_tests_passed=439,new_cpu_tests=12,
 probe_requests=total,warmups=2,successful_in_horizon=horizon,drain_completions=drained,raw_metric_receipts=scrapes,
 fresh_barriers=len(tokens),cells=rows,prompt_tokens=prompt_counts,paired_jobs=len(pairs['jobs']),
 candidate_pairs_executed=False,post_cleanup_verified=True,capture_count=0,study_ready=False)
(BASE/'CAPACITY_VALIDATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
