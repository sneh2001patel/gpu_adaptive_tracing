"""Descriptive phase summaries; no new rate selection or diagnostic labels."""
import json
from collections import Counter
from pathlib import Path
from revision.feasibility.challenge_protocol_v2 import load_prepared
from revision.feasibility.metrics import inspect,GAUGES
from revision.tracing.live_features import load_receipt

BASE=Path(__file__).resolve().parent.parent
ROOT=BASE/'challenges_v2_001'
REPO=BASE.parents[2]
def read(path):return json.loads(path.read_text())
plan,bank=load_prepared(REPO/'revision/examples/event_challenges_v2/prepared_001')
jobs=[]
for directory in sorted(p for p in ROOT.iterdir() if p.is_dir()):
 if not (directory/'playback.json').exists():continue
 job=read(directory/'job.json');play=read(directory/'playback.json');start=play['start_ns']
 entry=next(e for e in plan['schedules'] if e['schedule_id']==job['schedule_id'])
 points=[]
 for path in (directory/'raw_metrics').glob('*.json'):
  receipt=load_receipt(path.parent,path.name)
  gauges=inspect(receipt.raw,model='Qwen/Qwen2.5-7B-Instruct',engine='0')['gauges']
  assert all(v['available'] for v in gauges.values())
  points.append(dict(requested_at_ns=receipt.requested_at_ns,received_at_ns=receipt.received_at_ns,
   queued=gauges[GAUGES[0]]['value'],running=gauges[GAUGES[1]]['value']))
 points.sort(key=lambda r:r['requested_at_ns'])
 phases=[]
 for phase in entry['phase_table']:
  lo,hi=phase['start_ns'],phase['end_ns']
  offered=[r for r in play['ledger'] if lo<=r['offset_ns']<hi]
  samples=[r for r in points if start+lo<=r['requested_at_ns']<=r['received_at_ns']<start+hi]
  phases.append(dict(name=phase['name'],start_s=lo/1e9,end_s=hi/1e9,offered_rate_rps=phase['rate_rps'],
   offered=len(offered),states=dict(Counter(r['state'] for r in offered)),queue_receipts=len(samples),
   positive_queue_receipts=sum(r['queued']>0 for r in samples),
   max_sampled_queue=max((r['queued'] for r in samples),default=None)))
 jobs.append(dict(job_id=job['job_id'],passed=read(directory/'RESULT.json')['passed'],
  phases=phases,pending_at_horizon=play['pending_at_horizon_reconstructed'],
  post_horizon_completions=play['post_horizon_completed'],peak_inflight=play['peak_inflight']))
report=dict(scope='descriptive_development_phase_audit_not_diagnosis_or_capacity_estimate',jobs=jobs,
 caution='Queue receipts are point observations. No continuous pressure, healthy recovery, exclusive GPU phases, diagnostic accuracy or sustained capacity is established.')
(BASE/'CHALLENGES_V2_DELIVERY.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(jobs_analyzed=len(jobs),output='CHALLENGES_V2_DELIVERY.json')))
