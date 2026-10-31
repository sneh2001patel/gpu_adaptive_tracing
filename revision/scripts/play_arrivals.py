#!/usr/bin/env python3
"""Replay an exact request file against an existing HTTP service; no GPU setup."""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from revision.tracing.arrival_schedule import ArrivalSchedule
from revision.tracing.schedule_playback import PlaybackConfig, SchedulePlayback
from revision.tracing.feature_collection import QueueGaugeCollector
from revision.tracing.diagnosis import UncalibratedClassifier
from revision.tracing.measured_evidence import MeasuredObservation
from revision.tracing.timing import MonotonicClock

ROOT=Path(__file__).resolve().parents[2]


def write_sources(output):
    paths=[p for folder in ('revision/tracing','revision/evaluation','revision/feasibility','revision/scripts') for p in (ROOT/folder).glob('*.py')]
    (output/'source_manifest.json').write_text(json.dumps(dict(role='uncommitted_CPU_driver_snapshot',
        files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}),indent=2)+'\n')


async def main_async(args):
    raw=args.schedule.read_bytes();schedule=ArrivalSchedule.from_bytes(raw)
    if (args.queue_endpoint is None)!=(args.queue_series is None):
        raise ValueError('Queue endpoint and exact series must be supplied together')
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'offered_arrivals.json').write_bytes(raw);write_sources(args.output)
    clock=MonotonicClock();classifier=UncalibratedClassifier();observations=[];predictions=[]
    def on_window(identity,window):
        observation=MeasuredObservation(identity,args.provenance,window.metrics[0].acquisition,window.metrics,None)
        observations.append(asdict(observation))
        predictions.append(asdict(classifier.classify(observation,now_ns=clock.now_ns(),clock_domain=clock.domain)))
    collector=None if args.queue_endpoint is None else QueueGaugeCollector(args.queue_endpoint,args.queue_series)
    config=PlaybackConfig(max_inflight=args.max_inflight,request_timeout_s=args.request_timeout,drain_s=args.drain,
        max_admission_lateness_s=args.max_lateness,window_s=args.window,grace_s=args.grace,min_latency_samples=args.min_latency_samples)
    driver=SchedulePlayback(schedule,clock,args.endpoint,provenance=args.provenance,config=config,
        server_collector=collector,on_window=on_window)
    try:
        await driver.run()
    finally:
        result=driver.snapshot()|dict(observations=observations,predictions=predictions,
            gpu_probe_or_capture_launched=False,role='request_driver_not_experimental_arm_runner')
        (args.output/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:result[k] for k in ('status','offered','admitted','counts','schedule_file_sha256','accounting_checks')},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule',type=Path,required=True)
    parser.add_argument('--endpoint',required=True)
    parser.add_argument('--provenance',choices=('synthetic_simulation','live_online'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--queue-endpoint');parser.add_argument('--queue-series')
    parser.add_argument('--max-inflight',type=int,default=8)
    parser.add_argument('--request-timeout',type=float,default=2)
    parser.add_argument('--drain',type=float,default=.5)
    parser.add_argument('--max-lateness',type=float,default=.02)
    parser.add_argument('--window',type=float,default=.1)
    parser.add_argument('--grace',type=float,default=.01)
    parser.add_argument('--min-latency-samples',type=int,default=2)
    asyncio.run(main_async(parser.parse_args()))
