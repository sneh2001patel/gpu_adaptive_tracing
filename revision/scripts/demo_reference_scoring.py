#!/usr/bin/env python3
"""Synthetic adjudications, immutable snapshot and explicit counterexample scores.

Candidate assertions below are hand-authored test inputs, not predictions from
our deployed abstaining classifier. There is no GPU data or empirical accuracy.
"""
from dataclasses import asdict
import argparse
import hashlib
import json
from pathlib import Path

from revision.evaluation.references import ReferenceRecord
from revision.evaluation.reference_store import ReferenceStore
from revision.evaluation.scoring import evaluate_files
from revision.scripts.reference_eval import write_report
from revision.scripts.play_arrivals import write_sources
from revision.tracing.timing import ManualClock

DOMAIN='synthetic-reference-demo-clock'


def stamp(start,end,available=650):return dict(start_ns=start,end_ns=end,available_at_ns=available,clock_domain=DOMAIN)


def make_references(root):
    root.mkdir(parents=True,exist_ok=False);artifacts=[]
    for name,channel in [('server','server_diagnostics'),('requests','request_diagnostics')]:
        path=root/(name+'.json');path.write_text(json.dumps(dict(source='synthetic_fixture',channel=channel,note='No real measurements'))+'\n')
        artifacts.append(dict(artifact_id=name,path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),channel=channel,acquisition=stamp(0,500)))
    records=[]
    for start,end,causes,complete,status in [(0,100,['queue_pressure'],True,'supported'),
        (100,200,['queue_pressure','prefill_dominated_service'],True,'supported'),
        (200,300,['queue_pressure'],False,'supported'),(300,400,[],False,'unresolved'),(400,500,[],True,'healthy')]:
        criteria=[dict(criterion_id='fixture-'+str(cause or 'healthy'),cause=cause,passed=True,artifact_ids=['server','requests'],
            rationale='Hand-authored contract fixture, not independent incident evidence') for cause in (causes if causes else ([None] if status=='healthy' else []))]
        records.append(dict(record_role='adjudicated_reference',run_id='synthetic-run',reference_version='synthetic-rubric-v1',
            provenance='synthetic_simulation',interval=stamp(start,end),status=status,supported_causes=causes,contradicted_causes=[],
            cause_set_complete=complete,criteria=criteria,artifacts=artifacts if criteria else [],alternatives=['Fixture alternative'],
            matched_reference_run_id=None,reference_run_mismatch=None,assessor_ids=['synthetic-author'],
            blinded_to_predictions_and_policy=False,adjudicated_at_ns=700,locked_at_ns=None,
            limitations=['Synthetic unblinded single-author fixture; not ground truth or human adjudication evidence']))
    rubric=dict(version='synthetic-rubric-v1',provenance='synthetic_simulation',criterion_ids=['fixture-queue_pressure','fixture-prefill_dominated_service','fixture-healthy'],
        description='Schema/scoring fixture only; no fitted reference thresholds')
    (root/'rubric.json').write_text(json.dumps(rubric,indent=2)+'\n')
    (root/'references.json').write_text(json.dumps(records,indent=2)+'\n')
    return [ReferenceRecord.from_dict(r) for r in records]


def make_predictions():
    # description, acquisition start/end, explicit causes, label, reason, status
    cases=[('complete',10,20,['queue_pressure'],'vllm_queue_pressure','diagnosis_stable','ok'),
        ('partial',120,130,['queue_pressure'],'vllm_queue_pressure','diagnosis_stable','ok'),
        ('wrong_stable',30,40,['prefill_dominated_service'],'vllm_long_prompt','diagnosis_stable','ok'),
        ('unknown_budget',40,50,[],None,'budget_exhausted','ok'),
        ('generic_mixed',150,160,[],'mixed','fixed_burst_complete','ok'),
        ('transition',90,110,['queue_pressure'],'vllm_queue_pressure','diagnosis_stable','ok'),
        ('unresolved_reference',320,330,['queue_pressure'],'vllm_queue_pressure','diagnosis_stable','ok'),
        ('gap',520,530,['queue_pressure'],'vllm_queue_pressure','budget_exhausted','ok'),
        ('incomplete_reference',220,230,['prefill_dominated_service'],'vllm_long_prompt','diagnosis_stable','ok'),
        ('healthy_wrong',420,430,['queue_pressure'],'vllm_queue_pressure','diagnosis_stable','ok'),
        ('capture_failure',40,50,[],None,'capture_failed','capture_failed'),
        ('horizon_censor',350,360,[],None,'horizon_ended','horizon_censored')]
    rows=[];events=[];episodes=[]
    for i,(name,start,end,causes,label,reason,status) in enumerate(cases):
        episode_id=f'episode-{i}'
        rows.append(dict(record_kind='initial_episode_stop',prediction_id=name,run_id='synthetic-run',episode_id=episode_id,
            policy='stability_stop' if reason=='diagnosis_stable' else 'fixed_burst',provenance='synthetic_simulation',
            evidence_interval=stamp(start,end,end+1),decision_at_ns=end+2,evidence_id=f'fixture-{i}' if status=='ok' else None,
            policy_label=label,cause_set=causes,classifier_version='hand_authored_fixture_not_deployed_model',
            mapping_version='synthetic_explicit_assertions_not_validated_policy_mapping',terminal_reason=reason,decision_status=status))
        episodes.append(dict(episode_id=episode_id))
        events.append(dict(event='episode_started',episode_id=episode_id,timestamp_ns=0,clock_domain=DOMAIN,provenance='synthetic_simulation'))
    snapshot=dict(run_id='synthetic-run',controller=dict(controller_version='fixture_only',evidence_mode='synthetic_simulation',
        clock_domain=DOMAIN,episodes=episodes,events=events))
    return rows,snapshot


def main(output):
    output.mkdir(parents=True,exist_ok=False);write_sources(output)
    records=make_references(output/'adjudication');clock=ManualClock(800);clock.domain=DOMAIN
    store=ReferenceStore(output/'store');anchor=store.lock(records,output/'adjudication',output/'adjudication/rubric.json',clock=clock)
    # Anchor is retained outside the mutable store. Predictions are only created
    # and opened after the lock call completed. This does not prove human blinding.
    (output/'LOCK_ANCHOR.json').write_text(json.dumps(dict(reference_lock_sha256=anchor,provenance='synthetic_simulation'),indent=2)+'\n')
    predictions,snapshot=make_predictions()
    (output/'predictions.json').write_text(json.dumps(predictions,indent=2)+'\n')
    (output/'controller_snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
    clock.advance_to(1000)
    result=evaluate_files(store,anchor,output/'predictions.json',output/'controller_snapshot.json',clock=clock)
    (output/'SCORE.json').write_text(json.dumps(result,indent=2)+'\n');write_report(result,output/'REPORT.md')
    print(json.dumps(dict(provenance='synthetic_simulation',gpu_used=False,lock_sha256=anchor,
        denominators=result['denominators'],outcomes=result['outcomes']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
