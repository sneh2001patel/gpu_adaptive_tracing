"""Independent CPU audit of the off-host step-028 receipts and frozen source."""
import hashlib,json,tarfile
from pathlib import Path
from revision.feasibility.event_commission import validate_join
from revision.tracing.live_features import ServingBinding
from revision.tracing.server_events import validate_snapshot
from revision.tracing.worker_barrier import validate_barrier
BASE=Path(__file__).resolve().parent.parent;DEPLOY=Path(__file__).resolve().parent;ROOT=BASE/'events_001'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
result=read(ROOT/'RESULT.json');assert result['commission_passed'] and not result['errors']
assert result['total_request_attempts']==result['joined_requests']==8
for key in ('capture_count','references_created','challenge_cases_executed'):assert result[key]==0
for key in ('calibration_enabled','study_ready','protocol_frozen','runtime_wait_metric_enabled','GPU_phase_mapping_enabled'):assert result[key] is False
files=read(ROOT/'artifact_manifest.json')['files']
for name,expected in files.items():assert sha(ROOT/name)==expected,name
source=read(DEPLOY/'source_archive.json');assert sha(DEPLOY/'source_step028.tar.gz')==source['sha256']
with tarfile.open(DEPLOY/'source_step028.tar.gz') as tar:
 for name,expected in source['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
 for name,expected in read(ROOT/'source_manifest.json')['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
 pins=read(ROOT/'installed_source_pins.json')['files']
 for name,expected in pins.items():
  parent='revision/protocol/sources/vllm_0_10_2/'
  filename='events/arg_utils.py.txt' if name=='vllm/engine/arg_utils.py' else 'event_ids/'+('utils_init.py.txt' if name=='vllm/utils/__init__.py' else Path(name).name+'.txt')
  assert hashlib.sha256(tar.extractfile(parent+filename).read()).hexdigest()==expected,name
 for name,expected in read(ROOT/'input_hashes.json').items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
initial=read(ROOT/'initial_probe.json');final=read(ROOT/'final_probe.json');binding=ServingBinding(**final['data']['binding'])
assert initial['command']['token']!=final['command']['token']
assert not validate_snapshot(initial['data'],initial['command'],binding,initial['received_at_ns'])
rows=read(ROOT/'requests.json');joined=validate_join(rows,final,binding)
assert joined==read(ROOT/'joined_requests.json') and len(final['data']['events'])==24
plan=read(ROOT/'request_plan.json');assert plan['max_total_attempts']==8 and len(plan['requests'])==8
for row,planned in zip(rows,plan['requests']):
 for key in ('index','expected_prompt_tokens','payload'):assert row[key]==planned[key]
 assert sha(ROOT/row['response_path'])==row['raw_sha256']
 assert read(ROOT/row['response_path'])==row['response']
startup=read(ROOT/'session-0/scheduler-events/startup.json');worker=read(next((ROOT/'session-0').glob('worker-*.json')))
assert startup['binding']==final['data']['binding'] and worker['pid']==binding.worker_pid
assert startup['scheduler_source_sha256']=='2bd28fc32cea71370298bb8da0d9a0bbd163ab315b2c6428540131e3999a255f'
assert startup['effective_config']==dict(enable_prefix_caching=False,max_num_seqs=16,async_scheduling=False)
tokens=set()
for row in read(ROOT/'quiet_evidence.json'):
 command=row['barrier_command'];assert command['token'] not in tokens;tokens.add(command['token'])
 validate_barrier(row['barrier_receipt'],command,pid=binding.worker_pid,device_uuid=binding.device_uuid,received_at_ns=row['barrier_received_at_ns'])
 for phase in ('before','after'):assert sha(ROOT/row[phase+'_path'])==row[phase+'_sha256']
assert len(tokens)==4
exit=read(ROOT/'session-0/exit.json');assert exit['group_absent'] and exit['worker_absent']
post=read(BASE/'events_post_cleanup_checks.json');assert all(row['parent_absent'] and row['worker_absent'] and row['group_absent'] for row in post['processes'])
assert not post['compute']['stdout'].strip() and post['gpu']['stdout'].strip().endswith(', 0')
validation=dict(passed=True,artifact_hashes_verified=len(files),archived_source_entries_verified=len(source['files']),
 runtime_source_entries_verified=len(read(ROOT/'source_manifest.json')['files']),installed_ID_CLI_pins_verified=len(pins),
 requests_joined=len(joined),lifecycle_events=24,fresh_idle_probes=2,barriers_verified=4,
 worker_pid=binding.worker_pid,device_uuid=binding.device_uuid,prefix_caching=False,
 wait_lower_ms=[r['wait_lower_ms'] for r in joined],wait_upper_ms=[r['wait_upper_ms'] for r in joined],
 cleanup_verified=True,study_ready=False,protocol_frozen=False)
(BASE/'EVENTS_VALIDATION.json').write_text(json.dumps(validation,indent=2)+'\n');print(json.dumps(validation,indent=2))
