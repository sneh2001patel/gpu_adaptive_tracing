"""Summarize independently audited development outcomes without new labels."""
import json
from collections import Counter
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
audit=json.loads((BASE/'CHALLENGES_V2_VALIDATION.json').read_text())
assert audit['audit_passed']
counts=Counter();statuses=Counter();reasons=Counter();windows=[]
for job in audit['jobs']:
 counts.update(job.get('counts',{}));statuses.update(job.get('consumer_status_counts',{}));reasons.update(job.get('consumer_reasons',{}))
for pair in audit['paired_reviews']:windows.extend(pair['windows'])
ratios=[w['symmetric_ratio'] for w in windows if w['symmetric_ratio'] is not None]
summary=dict(scope='fresh_L4_development_engineering_validation_not_main_study',
 campaign_status=audit['campaign_status'],audit_passed=True,completed_jobs=audit['completed_jobs'],
 planned_jobs=16,scheduled_offers=sum(j['offered'] for j in audit['jobs']),scheduled_completed=counts['completed'],
 warmups=16,total_attempts=audit['total_request_attempts'],maximum_attempt_budget=1932,
 scheduled_counts=dict(counts),selected_rate_rps=audit['selection']['selected_rate_rps'],
 metric_receipts=audit['metric_receipts'],event_probes=sum(j['event_probes'] for j in audit['jobs']),
 final_history_events=sum(j.get('latest_event_count',0) for j in audit['jobs']),
 event_drops=sum(j.get('event_drops',0) for j in audit['jobs']),
 consumer_statuses=dict(statuses),consumer_reasons=dict(reasons),paired_reviews=len(audit['paired_reviews']),
 observer_off_on_pairs=6,consumer_complete_withheld_pairs=2,evaluable_paired_windows=len(ratios),
 paired_windows_below_twenty=len(windows)-len(ratios),max_symmetric_p95_ratio=max(ratios),
 review_flags=sum(w['review_flag'] is True for w in windows),equivalence_established=False,
 artifact_hashes_verified=audit['artifact_hashes_verified'],frozen_entries_verified=audit['frozen_entries_verified'],
 runtime_source_entries_verified=audit['runtime_source_entries_verified'],quiet_barriers_verified=audit['quiet_barriers_verified'],
 repeated_historical_quiet_rows=audit['repeated_historical_quiet_rows'],persistence_limitation=audit['persistence_limitation'],
 backup_sha256='90fff5eb8864fddf66d23c345a1bec08841469f10a9ae8a291e8bbc7d751aa54',
 captures=0,classifier_run=False,calibration_enabled=False,references_created=0,study_ready=False,protocol_frozen=False,
 cleanup_verified=True,GPU_memory_mib_after_cleanup=0,rental_stopped=False,
 next_step='034: CPU-only per-job quiet-evidence isolation, multi-job regression and immutable-run provenance audit before scientific feature/reference acceptance')
(BASE/'CHALLENGES_V2_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
