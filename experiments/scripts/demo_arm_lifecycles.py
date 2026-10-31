#!/usr/bin/env python3
"""Eight owned CPU-fixture arms plus retained quiescence/startup/reset failures."""
import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import random

from experiments.scripts.play_arrivals import write_sources
from experiments.tracing.arrival_schedule import ArrivalSchedule
from experiments.tracing.arm_session import SessionConfig
from experiments.tracing.experiment_arms import ARMS, CpuArmRunner, require_comparable
from experiments.tracing.schedule_playback import PlaybackConfig


def offered_bytes():
    return (json.dumps(dict(version='offered_arrivals_v1',duration_ns=400000000,requests=[
        dict(request_id=f'opaque-{i}',offset_ns=i*20000000,payload=dict(model='fixture',prompt='Actual fixture text',
            max_tokens=32,stream=False,temperature=0,seed=i)) for i in range(18)]),indent=2)+'\n').encode()


async def main(output):
    output.mkdir(parents=True,exist_ok=False);write_sources(output)
    raw=offered_bytes();(output/'offered_arrivals.json').write_bytes(raw);schedule=ArrivalSchedule.from_bytes(raw)
    playback=PlaybackConfig(window_s=.05,grace_s=.005,min_latency_samples=1,drain_s=.05,
        request_timeout_s=1,max_admission_lateness_s=.05,sample_interval_s=.01)
    session=SessionConfig(work_s=.05)
    order=list(ARMS);random.Random(20261027).shuffle(order)
    (output/'matrix_plan.json').write_text(json.dumps(dict(role='cpu_fixture_only',arms=order,
        schedule_file_sha256=schedule.file_sha256,playback_config=asdict(playback),session_config=asdict(session)),indent=2)+'\n')
    results=[]
    for name in order:
        runner=CpuArmRunner(output/name,name,schedule,playback_config=playback,session_config=session)
        result=await runner.run();results.append(result)
        print(json.dumps(dict(arm=name,status=result['status'],target=result['session']['instance'],
            captures=0 if result['capture_backend'] is None else len(result['capture_backend']['attempts']),
            quiescence=result['post_workload_quiescent'] is not None,group_alive=result['session']['cleanup']['group_alive'])))
    require_comparable(results)
    failed=[]
    for fault in ('missing_metric','stuck_busy','stale_reset','startup_fail'):
        runner=CpuArmRunner(output/('failure-'+fault),'cheap_only',schedule,playback_config=playback,
            session_config=SessionConfig(work_s=.05,quiescence_s=.1),target_fault=fault)
        try:await runner.run()
        except Exception as exc:
            failed.append(dict(fault=fault,error=type(exc).__name__,result='retained',cleanup=runner.session.cleanup))
        else:raise AssertionError('Fixture fault unexpectedly accepted: '+fault)
    summary=dict(validation='cpu_fixture_only',gpu_used=False,completed_arms=len(results),same_workload_contract=True,
        distinct_target_instances=len({r['session']['instance'] for r in results}),
        distinct_sampler_instances=len({r['sampler']['instance'] for r in results if r['sampler'] is not None}),
        reset_quiescence_passed=sum(r['post_workload_quiescent'] is not None for r in results),retained_failures=failed,
        note='No GPU, profiler perturbation, diagnosis accuracy, or experimental hardware baseline validated.')
    (output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    lines=['# CPU experiment-arm lifecycle validation','','All values below are CPU-fixture mechanics; no GPU, diagnostic accuracy, profiler overhead or hardware baseline is established.','',
        '| Arm | Target capture mode | Fresh cheap sampler | Captures | Server quiet/reset passed | Owned group absent |',
        '|---|---|---|---:|---|---|']
    for r in results:
        lines.append(f"| {r['arm']['name']} | {r['arm']['capture_mode']} | {r['sampler'] is not None} | {0 if r['capture_backend'] is None else len(r['capture_backend']['attempts'])} | {r['post_workload_quiescent'] is not None and r['session']['generation']==3} | {not r['session']['cleanup']['group_alive']} |")
    lines+=['',f"All eight arms reuse offered-file SHA-256 `{schedule.file_sha256}` and the same comparison contract.",'',
        'Four injected failures are retained: missing server metric, persistent busy status, stale reset acknowledgement and startup failure. Each fails its gate and still closes its owned process group.','',
        'Source/report fingerprints, raw playback and status observations, generation/nonce checks, reset acknowledgements and timing scopes are retained. Capture-control spans include RPC/report latency; active GPU time and persisted total lifecycle remain unknown. Policy diagnoses deliberately abstain.','',
        'Next: durable blinded reference locking/scoring and additional interval instrumentation; validate the corresponding real GPU session/queue/reset semantics before confirmation.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    asyncio.run(main(parser.parse_args().output))
