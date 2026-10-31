#!/usr/bin/env python3
"""Eight CPU arms plus source faults, retained interval receipts and exports."""
import argparse,asyncio,hashlib,json
from pathlib import Path
from revision.tracing.arrival_schedule import ArrivalSchedule
from revision.tracing.experiment_arms import ARMS,CpuArmRunner,require_comparable
from revision.tracing.arm_session import SessionConfig,CpuTargetSession
from revision.tracing.timing import MonotonicClock
from revision.scripts.snapshot_server_metrics import snapshot as snapshot_metrics
from revision.tracing.schedule_playback import PlaybackConfig
from revision.scripts.play_arrivals import write_sources
from revision.scripts.demo_arm_lifecycles import offered_bytes


async def main(output):
    output.mkdir(parents=True,exist_ok=False);write_sources(output)
    raw=offered_bytes();(output/'offered_arrivals.json').write_bytes(raw);schedule=ArrivalSchedule.from_bytes(raw)
    playback=PlaybackConfig(window_s=.05,grace_s=.015,min_latency_samples=1,drain_s=.05,
        request_timeout_s=1,max_admission_lateness_s=.1,sample_interval_s=.01,sample_timeout_s=.15)
    results=[]
    for name in ARMS:
        runner=CpuArmRunner(output/name,name,schedule,playback_config=playback,session_config=SessionConfig(work_s=.05))
        result=await runner.run();results.append(result)
    require_comparable(results)
    faults=[]
    for fault in ('interval_missing','interval_reset','interval_generation','interval_clock','interval_overflow','interval_late'):
        runner=CpuArmRunner(output/fault,'fixed_burst',schedule,playback_config=playback,session_config=SessionConfig(work_s=.05),target_fault=fault)
        result=await runner.run();faults.append(result)
    probe_session=CpuTargetSession(output/'metric-probe-target',MonotonicClock(),'disabled')
    try:
        await probe_session.start()
        await snapshot_metrics(probe_session.endpoint+'/metrics',output/'metric_probe',samples=2,interval_s=0)
    finally:await probe_session.aclose()
    (output/'metric_probe'/'session.json').write_text(json.dumps(probe_session.snapshot(),indent=2)+'\n')
    files_verified=0
    for folder in [output/r['arm']['name'] for r in results]+[output/f for f in ('interval_missing','interval_reset','interval_generation','interval_clock','interval_overflow','interval_late')]:
        manifest=json.loads((folder/'artifact_manifest.json').read_text())
        for name,digest in manifest['files'].items():
            if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('Saved artifact changed')
            files_verified+=1
    def row(r):
        intervals=r['playback']['interval_records'];waits=[x for x in intervals if x['metric']['name']=='request_wait_p95_ms']
        return dict(arm=r['arm']['name'],status=r['status'],
            interval_waits_accepted=sum(x['accepted'] for x in waits),
            valid_interval_waits=sum(x['accepted'] and x['metric']['value'] is not None for x in waits),
            late_or_rejected_intervals=sum(not x['accepted'] for x in waits),
            unavailable_interval_waits=sum(x['metric']['value'] is None for x in waits),
            measured_observations=r['measured_observation_count'],cheap_observations=r['cheap_observation_count'],
            initial_stops=r['evaluation_export']['initial_stops'],owned_group_absent=not r['session']['cleanup']['group_alive'],
            live_interval_tasks=r['playback']['live_interval_tasks'])
    summary=dict(validation='cpu_fixture_only',gpu_used=False,valid_for_paper=False,completed_arms=[row(r) for r in results],
        source_fault_cases={fault:row(r) for fault,r in zip(('interval_missing','interval_reset','interval_generation','interval_clock','interval_overflow','interval_late'),faults)},
        same_offered_and_comparison_contract=True,artifact_hashes_verified=files_verified,
        note='Real CPU HTTP admission waits; synthetic kernel/device reports. Phase attribution unavailable. Classifier abstains. No GPU metrics/cost/diagnosis validation.')
    (output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# CPU arm collection and export checks','',summary['note'],'',
        '| Arm | Valid wait intervals | Measured capture observations | Initial stops | Owned group absent |',
        '|---|---:|---:|---:|---|']
    for r in summary['completed_arms']:lines.append(f"| {r['arm']} | {r['valid_interval_waits']} | {r['measured_observations']} | {r['initial_stops'] if r['initial_stops'] is not None else 'not applicable'} | {r['owned_group_absent']} |")
    lines+=['','Six fault cases retain missing/reset/generation/clock/history-overflow/late source evidence. Late receipts do not rewrite closed windows.','',
        'Policy export uses original capture observations with null cause assertions; cheap windows remain separate intervals. Independent references and calibrated diagnosis remain pending.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);asyncio.run(main(p.parse_args().output))
