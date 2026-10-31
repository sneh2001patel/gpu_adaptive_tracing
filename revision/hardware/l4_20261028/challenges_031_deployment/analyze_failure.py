"""Descriptive first-ladder audit; never selects a rate or repairs eligibility."""
import json,statistics
from collections import Counter
from pathlib import Path
from revision.feasibility.metrics import inspect,GAUGES
from revision.tracing.live_features import load_receipt
BASE=Path(__file__).resolve().parent.parent;DIRECTORY=BASE/'challenges_001/rate_ladder-b0-off'
playback=json.loads((DIRECTORY/'playback.json').read_text());start=playback['start_ns'];NS=1_000_000_000
rows=[json.loads(line) for line in (DIRECTORY/'requests/receipts.jsonl').read_text().splitlines()]
metrics=[load_receipt(p.parent,p.name) for p in (DIRECTORY/'raw_metrics').glob('*.json')]
metrics.sort(key=lambda r:r.requested_at_ns)
points=[]
for receipt in metrics:
 report=inspect(receipt.raw,model='Qwen/Qwen2.5-7B-Instruct',engine='0')['gauges']
 assert all(v['available'] for v in report.values())
 points.append(dict(requested_at_ns=receipt.requested_at_ns,received_at_ns=receipt.received_at_ns,
  queued=report[GAUGES[0]]['value'],running=report[GAUGES[1]]['value']))
levels=[]
for lo,hi,rate in ((0,8,.5),(8,16,1),(16,24,2),(24,32,4),(32,40,8),(40,60,0)):
 offered=[r for r in playback['ledger'] if lo*NS<=r['offset_ns']<hi*NS]
 samples=[r for r in points if start+lo*NS<=r['requested_at_ns']<=r['received_at_ns']<start+hi*NS]
 levels.append(dict(start_s=lo,end_s=hi,offered_rate_rps=rate,offered=len(offered),states=dict(Counter(r['state'] for r in offered)),
  wholly_contained_queue_receipts=len(samples),positive_queue_receipts=sum(r['queued']>0 for r in samples),
  maximum_sampled_queue=max((r['queued'] for r in samples),default=None),maximum_sampled_running=max((r['running'] for r in samples),default=None)))
scheduled=[r for r in rows if r['request_id']!='challenge-warmup'];latencies=[(r['completed_at_ns']-r['admitted_at_ns'])/NS for r in scheduled]
positive=[r for r in points if r['queued']>0]
report=dict(scope='descriptive_failed_ladder_audit_not_selection_or_diagnosis',case_start_ns=start,levels=levels,
 max_sampled_queue=max(r['queued'] for r in points),positive_queue_receipts=len(positive),total_queue_receipts=len(points),
 first_positive_receipt_offset_s=None if not positive else (positive[0]['received_at_ns']-start)/NS,
 last_positive_receipt_offset_s=None if not positive else (positive[-1]['received_at_ns']-start)/NS,
 max_receipt_gap_s=max((b['received_at_ns']-a['received_at_ns'])/NS for a,b in zip(points,points[1:])),
 admitted_cohort_latency_min_s=min(latencies),admitted_cohort_latency_median_s=statistics.median(latencies),
 admitted_cohort_latency_max_s=max(latencies),post_horizon_completions=playback['post_horizon_completed'],
 pending_at_horizon=playback['pending_at_horizon_reconstructed'],
 actual_scheduled_prompt_tokens=sum(r['prompt_tokens'] for r in scheduled),actual_scheduled_output_tokens=sum(r['output_tokens'] for r in scheduled),
 raw_selection_status='not_run_incomplete_offered_work',selected_rate_rps=None,eligibility_repaired=False,
 caution='Queue receipt timestamps are point observations; no continuous pressure duration, causal diagnosis, healthy recovery or observer comparison is established.')
(BASE/'CHALLENGES_FAILURE_ANALYSIS.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
