"""Audit successful or failed frozen campaign artifacts without relabeling outcomes."""
import hashlib,json,tarfile
from collections import Counter
from pathlib import Path
from revision.feasibility.challenge_protocol import load_prepared,event_window,select_pressure
from revision.feasibility.challenge_runner import final_lifecycle,normalized_work
from revision.tracing.live_features import ServingBinding,load_receipt,map_receipt
from revision.tracing.server_events import validate_snapshot
from revision.tracing.worker_configuration import validate_configuration
from revision.tracing.worker_barrier import validate_barrier

BASE=Path(__file__).resolve().parent.parent;DEPLOY=Path(__file__).resolve().parent;ROOT=BASE/'challenges_001'
REPO=BASE.parents[2]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
freeze=read(REPO/'revision/examples/challenge_runner/snapshot_001/FREEZE.json')
archive=REPO/'revision/examples/challenge_runner/snapshot_001/source_step030.tar.gz'
assert sha(archive)==freeze['source_archive_sha256']
plan,bank=load_prepared(REPO/'revision/examples/event_challenges/prepared_001')
preflight=read(DEPLOY/'preflight.json');assert preflight['source_archive_sha256']==sha(archive)
assert preflight['freeze_sha256']==sha(REPO/'revision/examples/challenge_runner/snapshot_001/FREEZE.json')
assert preflight['installed_source_pins_verified']==12
assert preflight['model_files']==read(BASE/'discovery_001/model_files.json')['files']
result=read(ROOT/'RESULT.json');budget=read(ROOT/'request_budget.json');jobs=read(ROOT/'jobs.json')
assert len(jobs)==16 and {j['job_id'] for j in jobs}=={j['job_id'] for j in plan['jobs']}
for key in ('classifier_run','calibration_enabled','study_ready','protocol_frozen'):assert result[key] is False
assert result['references_created']==0
files=read(ROOT/'artifact_manifest.json')['files']
for name,expected in files.items():assert sha(ROOT/name)==expected,name
source_entries=0
with tarfile.open(archive) as tar:
 for name,expected in freeze['files'].items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name
 for p in ROOT.glob('*/source_manifest.json'):
  for name,expected in read(p)['files'].items():
   assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected,name;source_entries+=1
reports=[];all_rows=[];all_metrics=[];all_quiet_tokens=set();sessions=[]
for directory in sorted(p for p in ROOT.iterdir() if p.is_dir()):
 job=read(directory/'job.json');outcome=read(directory/'RESULT.json');assert outcome['cleanup']['confirmed_absent'] is True
 assert not outcome['study_ready'] and not outcome['protocol_frozen']
 row=dict(job_id=job['job_id'],role=job['role'],passed=outcome['passed'],errors=outcome['errors'])
 nested=read(directory/'artifact_manifest.json')['files']
 for name,expected in nested.items():assert sha(directory/name)==expected,(directory.name,name)
 binding=None
 if (directory/'binding.json').exists():
  binding=ServingBinding(**read(directory/'binding.json'))
  cfg=read(directory/'effective_configuration.json');validate_configuration(cfg['receipt'],cfg['command'],binding,cfg['received_at_ns'])
  row.update(worker_pid=binding.worker_pid,prefix_caching=cfg['receipt']['config']['enable_prefix_caching'])
 rows=[]
 if (directory/'requests/receipts.jsonl').exists():
  rows=[json.loads(line) for line in (directory/'requests/receipts.jsonl').read_text().splitlines()]
 assert len(rows)==budget['attempts'][job['job_id']]==outcome['request_attempts']
 assert len({r['request_id'] for r in rows})==len(rows)
 successes=0
 for request in rows:
  assert request['admitted_at_ns']<=request['completed_at_ns']
  if request['response_path'] is not None:
   path=directory/'requests'/request['response_path'];assert sha(path)==request['response_sha256']
  if request['error'] is None:
   raw=read(directory/'requests'/request['response_path']);assert request['http_status']==200
   assert raw['id']=='cmpl-'+request['request_id'] and raw['model']=='Qwen/Qwen2.5-7B-Instruct'
   assert {k:raw['usage'][k] for k in ('prompt_tokens','completion_tokens','total_tokens')}==dict(prompt_tokens=1072,completion_tokens=32,total_tokens=1104)
   assert len(raw['choices'])==1 and raw['choices'][0]['finish_reason']=='length'
   assert request['prompt_tokens']==1072 and request['output_tokens']==32;successes+=1
 all_rows.extend(rows);row.update(request_attempts=len(rows),successful_requests=successes,failed_requests=len(rows)-successes)
 metrics=[]
 for path in (directory/'raw_metrics').glob('*.json'):
  receipt=load_receipt(path.parent,path.name);assert receipt.binding==binding
  sample,_=map_receipt(receipt,binding,now_ns=receipt.received_at_ns)
  metrics.append(receipt)
 metrics.sort(key=lambda r:r.requested_at_ns);all_metrics.extend(metrics)
 row.update(metric_receipts=len(metrics))
 probes=[];tokens=set()
 for path in sorted(directory.glob('probe-*.json')):
  receipt=read(path);validate_snapshot(receipt['data'],receipt['command'],binding,receipt['received_at_ns'])
  token=receipt['command']['token'];assert token not in tokens;tokens.add(token)
  if probes:assert receipt['data']['events'][:len(probes[-1]['data']['events'])]==probes[-1]['data']['events']
  probes.append(receipt)
 assert len(probes)<=32 and (job['event_instrumentation'] or not probes)
 row.update(event_probes=len(probes))
 if probes:
  final=probes[-1]['data'];row.update(latest_event_count=len(final['events']),event_drops=final['dropped'],event_faults=final['faults'])
 if (directory/'playback.json').exists():
  playback=read(directory/'playback.json');assert all(playback['accounting_checks'].values())
  assert playback['live_request_tasks']==playback['live_sampling_tasks']==playback['live_interval_tasks']==0
  schedule=bank[job['schedule_id']];assert playback['schedule_file_sha256']==schedule.file_sha256
  assert playback['offered']==len(schedule.requests)
  ledger=playback['ledger'];assert {r['request_id'] for r in ledger}=={r.request_id for r in schedule.requests}
  assert playback['peak_inflight']<=32
  row.update(playback_status=playback['status'],offered=playback['offered'],admitted=playback['admitted'],
   counts=playback['counts'],peak_inflight=playback['peak_inflight'],sampling_skips=playback['sampling_skips'],
   sampling_errors=playback['sampling_errors'],sampling_cancelled=playback['sampling_cancelled'],telemetry_overflows=playback['telemetry_overflows'])
  if (directory/'consumer_windows.json').exists():
   windows=read(directory/'consumer_windows.json')
   for w in windows:
    available=[r for r in probes if r['received_at_ns']<=w['decision_ns']]
    masked=None if job['evidence_withheld_offsets_ns'] is None else tuple(playback['start_ns']+x for x in job['evidence_withheld_offsets_ns'])
    expected=event_window(available[-1] if available else None,binding,start_ns=w['start_ns'],end_ns=w['end_ns'],decision_ns=w['decision_ns'],withheld_interval=masked)
    if w['owner_late']:expected=dict(status='unresolved',reason='owner_decision_deadline_missed',bounds=None,diagnosis=None)
    assert all(w[k]==v for k,v in expected.items())
   row['consumer_status_counts']=dict(Counter(w['status'] for w in windows));row['consumer_reasons']=dict(Counter(w['reason'] for w in windows if w['reason']))
  if outcome['passed']:
   assert playback['counts']['completed']==len(schedule.requests)
   if job['event_instrumentation']:final_lifecycle(probes[-1],binding,rows)
  if (directory/'selection.json').exists():
   work=normalized_work([r for r in rows if r['request_id']!='challenge-warmup'])
   assert select_pressure(metrics,binding,case_start_ns=playback['start_ns'],request_rows=work,schedule=schedule,job=job)==read(directory/'selection.json')
 for q in read(directory/'quiet_evidence.json') if (directory/'quiet_evidence.json').exists() else []:
  assert q['barrier_command']['token'] not in all_quiet_tokens;all_quiet_tokens.add(q['barrier_command']['token'])
  validate_barrier(q['barrier_receipt'],q['barrier_command'],pid=binding.worker_pid,device_uuid=binding.device_uuid,received_at_ns=q['barrier_received_at_ns'])
  for phase in ('before','after'):assert sha(directory/q[phase+'_path'])==q[phase+'_sha256']
 for path in directory.glob('session-*/exit.json'):
  exit=read(path);assert exit['group_absent'] and exit['worker_absent'];sessions.append(exit['worker_pid'])
 reports.append(row)
assert sum(budget['attempts'].values())==len(all_rows)==result['total_request_attempts']<=3612
assert all(budget['attempts'][k]<=v<=512 for k,v in budget['reserved'].items())
post=read(DEPLOY/'post_cleanup_checks.json')
assert all(all(row[k] for k in row if k.endswith('_absent')) for row in post['processes'])
assert not post['compute']['stdout'].strip() and post['gpu']['stdout'].strip().endswith(', 0')
assert 'EXITED' in post['supervisor']['stdout']
assert not list(ROOT.rglob('*.nsys-rep')) and not list(ROOT.rglob('*.sqlite'))
summary=dict(audit_passed=True,campaign_status=result['status'],campaign_errors=result['errors'],completed_jobs=result['completed_jobs'],
 started_jobs=len(reports),total_planned_jobs=16,total_request_attempts=len(all_rows),successful_requests=sum(r['error'] is None for r in all_rows),
 failed_request_receipts=sum(r['error'] is not None for r in all_rows),metric_receipts=len(all_metrics),
 artifact_hashes_verified=len(files),frozen_entries_verified=len(freeze['files']),runtime_source_entries_verified=source_entries,
 installed_source_pins_verified=preflight['installed_source_pins_verified'],model_files_verified=len(preflight['model_files']),
 quiet_barriers_verified=len(all_quiet_tokens),worker_pids=sessions,jobs=reports,cleanup_verified=True,GPU_memory_mib_after_cleanup=0,
 captures=0,references_created=0,study_ready=False,protocol_frozen=False,rental_stopped=False)
(BASE/'CHALLENGES_VALIDATION.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
