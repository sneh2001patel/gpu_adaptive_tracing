#!/usr/bin/env python3
"""Audit measured pilot artifacts without interpreting abstention as diagnosis."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import tarfile
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from experiments.tracing.aggregation import p95


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(directory,remote_root=Path('/workspace/gpu_adaptive_tracing')):
    directory=Path(directory).resolve()
    directory.relative_to(ROOT/'experiments')
    rows=[];proofs=[];integrity=[];source_integrity=[]
    manifest_path=directory/'source_manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        archive_path=directory/'executed_source.tar.gz'
        archive=tarfile.open(archive_path,'r:gz') if archive_path.exists() else None
        try:
            for relative,expected in manifest['files'].items():
                local=ROOT/relative
                current=hashlib.sha256(local.read_bytes()).hexdigest() if local.is_file() else None
                archived=archive.extractfile(relative).read() if archive is not None else None
                actual=hashlib.sha256(archived).hexdigest() if archived is not None else current
                source_integrity.append(dict(path=relative,expected=expected,actual=actual,unchanged=actual==expected,
                    source_basis='executed_source_archive' if archive else 'current_working_tree',
                    current_tree_matches_execution=current==expected))
        finally:
            if archive is not None:archive.close()
    for path in sorted(directory.glob('*-seed*-*/results.json')):
        result=json.loads(path.read_text())
        producer_events=jsonl(path.parent/'producer_events.jsonl')
        windows=[r['window'] for r in jsonl(path.parent/'windows.jsonl')]
        completions=[e['record'] for e in producer_events if e['type']=='RequestCompletion']
        starts=[e['record'] for e in producer_events if e['type']=='RequestStarted']
        observation=result['aggregation']['config']
        accepted=[e['record'] for e in producer_events if e['type']=='RequestCompletion' and e['accepted']]
        capture_timings=list(result['controller']['capture_timings'].values())
        summaries=[]
        # Attempt identity is present in backend command events; SQL summaries
        # stay in the session's nonce directories and are joined via stored hashes.
        report_paths=set()
        for event in result['backend']['events']:
            if event['event']=='command_started' and event.get('stage')=='export':
                report_paths.add(event['argv'][-1])
        for summary_path in (directory/'session'/'attempts').glob('*/kernel_summary.json'):
            summary=json.loads(summary_path.read_text())
            if not report_paths.intersection(summary['artifact_hashes']):continue
            summaries.append(summary)
            for original,expected in summary['artifact_hashes'].items():
                original_path=Path(original)
                local=ROOT/original_path.relative_to(remote_root)
                actual=hashlib.sha256(local.read_bytes()).hexdigest() if local.is_file() else None
                integrity.append(dict(path=str(local.relative_to(ROOT)),expected=expected,actual=actual,unchanged=actual==expected))
        decisions=[]
        for episode in result['controller']['episodes']:
            for decision in episode['decisions']:
                before=decision['evidence_ready_at_ns'];at=decision['decision_ready_at_ns']
                proof=dict(run=path.parent.name,capture_id=decision['capture_id'],status=decision['status'],
                    evidence_before_decision=before is not None and before<=at,
                    decision_before_observation_end=at<observation['horizon_ns'],
                    later_admissions=sum(r['start_ns']>at for r in starts),
                    later_completions=sum(r['end_ns']>at for r in completions),
                    diagnosis_label=decision['decision']['diagnosis_label'],
                    reason=decision['decision']['reason'])
                proofs.append(proof);decisions.append(proof)
        row=dict(case=result['case'],policy=result['policy'],seed=result['seed'],
            attempts=len(result['backend']['attempts']),
            valid_captures=sum(a['state']=='ready' for a in result['backend']['attempts'].values()),
            failed_captures=sum(a['state']=='failed' for a in result['backend']['attempts'].values()),
            captured_kernel_instances=sum(s['kernel_count'] for s in summaries),
            capture_control_s=sum(t['capture_control_window_s'] or 0 for t in capture_timings),
            evidence_collection_s=sum(t['evidence_collection_s'] or 0 for t in capture_timings),
            stats_export_s=sum(t['stats_command_s'] or 0 for t in capture_timings),
            parse_s=sum(t['summary_parse_s'] or 0 for t in capture_timings),
            capture_active_s=None,admitted=result['producer']['admitted'],completed=result['producer']['completed'],
            skipped_capacity=result['producer']['skipped_capacity'],skipped_scheduler=result['producer']['skipped_scheduler'],
            request_errors=result['producer']['errors'],sampling_errors=result['producer']['sampler_errors'],
            gpu_missing_windows=sum(w['gpu_util'] is None for w in windows),
            observed_completion_p95_ms=p95([(r['end_ns']-r['start_ns'])/1e6 for r in accepted]),
            late_completions=result['aggregation']['late_completions'],late_gpu_samples=result['aggregation']['late_gpu_samples'],
            drain_completions=result['aggregation']['drain_completions'],
            unresolved_decisions=sum(d['diagnosis_label'] is None for d in decisions),
            reactivations=sum(e['reactivation_attempts'] for e in result['controller']['episodes']),
            stop_reasons=';'.join(e['stop_reason'] or 'none' for e in result['controller']['episodes']),
            source=str(path.relative_to(ROOT)))
        rows.append(row)
    output=directory/'analysis';output.mkdir(exist_ok=True)
    if rows:
        with (output/'run_metrics.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    checks=dict(completed_runs=len(rows),valid_captures=sum(r['valid_captures'] for r in rows),
        failed_captures=sum(r['failed_captures'] for r in rows),request_errors=sum(r['request_errors'] for r in rows),
        sampling_errors=sum(r['sampling_errors'] for r in rows),gpu_missing_windows=sum(r['gpu_missing_windows'] for r in rows),
        runs_with_missing_gpu=sum(r['gpu_missing_windows']>0 for r in rows),
        decisions=len(proofs),successful_decisions=sum(p['status']=='ok' for p in proofs),
        readiness_violations=sum(p['status']=='ok' and not p['evidence_before_decision'] for p in proofs),
        source_files_checked=len(source_integrity),source_mismatches=sum(not x['unchanged'] for x in source_integrity),
        current_tree_changes_since_execution=sum(not x['current_tree_matches_execution'] for x in source_integrity),
        decisions_using_ready_evidence=sum(p['evidence_before_decision'] for p in proofs),
        decisions_followed_by_admissions=sum(p['later_admissions']>0 for p in proofs),
        decisions_followed_by_completions=sum(p['later_completions']>0 for p in proofs),
        decisions_before_observation_end=sum(p['decision_before_observation_end'] for p in proofs),
        artifact_hashes_checked=len(integrity),artifact_mismatches=sum(not x['unchanged'] for x in integrity),
        capture_active_measurement='unavailable',diagnostic_accuracy='not_assessed_classifier_abstains',
        role='engineering_pilot_not_confirmatory_study')
    (output/'validity_checks.json').write_text(json.dumps(dict(checks=checks,decisions=proofs,artifact_integrity=integrity,source_integrity=source_integrity),indent=2)+'\n')
    lines=['# L4 live engineering pilot','',
        ('**Telemetry incomplete: preserve as a failure/limitation, not a clean policy comparison.**' if checks['gpu_missing_windows'] or checks['sampling_errors'] else 'GPU telemetry coverage checks passed for these completed runs.'),'',
        'These are actual vLLM/NVML/Nsight observations. The classifier deliberately abstains; no diagnosis accuracy, stopping safety, human benefit, or GPU capture-active savings is established. Synchronous report flushing can pause the CUDA worker and is part of the measured control/evidence latency.','',
        '| Case | Policy | Runs | Valid captures | Failures | Request errors | Mean capture-control seconds/run |',
        '|---|---|---:|---:|---:|---:|---:|']
    for case,policy in sorted({(r['case'],r['policy']) for r in rows}):
        group=[r for r in rows if r['case']==case and r['policy']==policy]
        lines.append(f'| {case} | {policy} | {len(group)} | {sum(r["valid_captures"] for r in group)} | {sum(r["failed_captures"] for r in group)} | {sum(r["request_errors"] for r in group)} | {statistics.fmean(r["capture_control_s"] for r in group):.3f} |')
    lines+=['','Capture-control seconds include control/RPC/flush latency; they are not GPU capture-active seconds. Kernel counts are actual captured instances, not estimates of all workload kernels. Report/export/parse delays are recorded separately; overlapping timing scopes must not be added.','',
        f'Telemetry: {checks["sampling_errors"]} sampling errors; {checks["gpu_missing_windows"]} missing GPU windows across {checks["runs_with_missing_gpu"]} runs.',
        f'Integrity: {checks["artifact_hashes_checked"]} artifact hashes checked; {checks["artifact_mismatches"]} mismatches.',
        f'Readiness: {checks["decisions_using_ready_evidence"]}/{checks["decisions"]} decisions had parsed evidence available.',
        f'Continuation: {checks["decisions_followed_by_admissions"]}/{checks["decisions"]} decisions were followed by new admissions; {checks["decisions_followed_by_completions"]}/{checks["decisions"]} by completions.','',
        'The three repetition/seed labels do not establish statistical independence: arms share a persistent server, greedy generation, cache state and one calibration cohort. Offered arrival slots can be skipped at the in-flight cap; consult admissions/skips/drain before claiming equal realized workloads. No confidence intervals or effect-significance claims are made.','',
        'Next: independent reference evidence and T2 classification/calibration; changed/lull/overlap cases; matched no-profiler and cheap-only controls; active-capture boundary validation; then a frozen held-out protocol.']
    (output/'PILOT_REPORT.md').write_text('\n'.join(lines)+'\n')
    return checks


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--remote-root',type=Path,default=Path('/workspace/gpu_adaptive_tracing'))
    args=parser.parse_args()
    print(json.dumps(analyze(args.run_dir,args.remote_root),indent=2))
