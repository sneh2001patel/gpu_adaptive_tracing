#!/usr/bin/env python3
"""Persist the actual episode runner using the explicit CPU test transport."""
import argparse,asyncio,hashlib,json
from pathlib import Path
from experiments.feasibility.challenge_runner import CampaignBudget,EpisodeOptions,run_episode
from experiments.tests.test_challenge_runner import FakeTarget,fixture_schedule
from experiments.tracing.timing import MonotonicClock


async def main(args):
    root=args.output;root.mkdir(parents=True,exist_ok=False);budget=CampaignBudget(root);results=[]
    options=EpisodeOptions(window_s=.04,grace_s=.02,drain_s=.05,timeout_s=.2,metric_interval_s=.02,max_inflight=2,max_lateness_s=.05,tick_s=.001)
    entry=dict(schedule_id='explicit_CPU_fixture',event_probe_offsets_ns=[40_000_000,80_000_000,120_000_000])
    for generation,case in enumerate(('collector_on','collector_off','bad_response_ID')):
        clock=MonotonicClock();target=FakeTarget(clock);target.bad_id=case=='bad_response_ID'
        job=dict(job_id=case,event_instrumentation=case!='collector_off',prefix_caching=False,
            evidence_withheld_offsets_ns=[40_000_000,80_000_000] if case=='collector_on' else None)
        error=None
        try:await run_episode(target,clock,job,entry,fixture_schedule(),root/case,budget,generation,options=options)
        except RuntimeError as exc:error=str(exc)
        if (case=='bad_response_ID')!=(error is not None):raise RuntimeError('Unexpected fixture outcome')
        results.append(dict(case=case,expected_failure=case=='bad_response_ID',error=error,owned_target_closed=target.closed,
            active_requests_after_cleanup=len(target.active),event_probes=target.probes))
    (root/'RESULT.json').write_text(json.dumps(dict(provenance='synthetic_simulation',GPU_used=False,live_validation=False,
        scaled_horizon_s=.12,cases=results,classifier_run=False,references_created=0,protocol_frozen=False),indent=2)+'\n')
    (root/'artifact_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob('*')) if p.is_file()}),indent=2)+'\n')
    print(json.dumps(dict(CPU_fixture_episodes=3,expected_failed_episodes=1,GPU_used=False,live_validation=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    asyncio.run(main(args))
