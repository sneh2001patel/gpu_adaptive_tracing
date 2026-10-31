#!/usr/bin/env python3
"""CPU fixtures for counter intervals and actual controller snapshot export."""
import argparse
from dataclasses import asdict,replace
import json
from pathlib import Path
from revision.tracing.interval_metrics import CounterStamp,WaitHistogram,PhaseCounters,wait_p95,prefill_fraction,phase_unavailable
from revision.tracing.measured_evidence import Acquisition,KernelObservation,MeasuredObservation
from revision.tracing.controller import ControllerConfig,StreamingController
from revision.tracing.policies import PolicyConfig
from revision.tracing.profiler import FakeProfilerBackend,FakeCapturePlan,CaptureFailed
from revision.tracing.timing import ManualClock,TimingRecorder
from revision.tracing.windows import CheapWindow,HealthyBaseline
from revision.evaluation.controller_export import export_initial_stops
from revision.scripts.play_arrivals import write_sources


def counter_cases():
    a=CounterStamp('a','fixture-server','generation-0','fixture_wait_admission',0,0,'fixture-clock')
    b=replace(a,sample_id='b',sampled_at_ns=100,available_at_ns=110)
    first=WaitHistogram(a,(.01,.1,1.,float('inf')),(10,20,30,30),30)
    last=WaitHistogram(b,first.upper_seconds,(12,30,50,50),50)
    options=dict(now_ns=110,clock_domain='fixture-clock')
    return dict(input_snapshots=dict(previous_histogram=asdict(first)|dict(upper_seconds=[.01,.1,1.,'+Inf']),
        current_histogram=asdict(last)|dict(upper_seconds=[.01,.1,1.,'+Inf']),
        previous_phases=asdict(PhaseCounters(a,0,0,0,0)),current_phases=asdict(PhaseCounters(b,60,30,10,100))),
        valid_wait=asdict(wait_p95(first,last,**options)),
        reset=asdict(wait_p95(first,replace(last,cumulative_counts=(0,0,0,0),count=0),**options)),
        generation_change=asdict(wait_p95(first,replace(last,stamp=replace(b,generation='generation-1')),**options)),
        no_observations=asdict(wait_p95(first,replace(first,stamp=b),**options)),
        phase_not_instrumented=asdict(phase_unavailable(Acquisition(0,100,110,'fixture-clock'))),
        explicit_phase_fixture=asdict(prefill_fraction(PhaseCounters(a,0,0,0,0),PhaseCounters(b,60,30,10,100),**options)))


def controller_case(mode):
    clock=ManualClock();rec=TimingRecorder(clock,provenance='synthetic_simulation');backend=FakeProfilerBackend(rec)
    def start(cid,window):
        if mode=='launch_failure':raise OSError('fixture launch failure')
        backend.start(cid,FakeCapturePlan(startup_s=2 if mode=='timeout' else .1,
            finalization_s=.1,stats_s=.1,parse_s=.1))
    def classify(payload):
        if mode=='diagnosis_failure':raise RuntimeError('fixture diagnosis failure')
        return None
    config=ControllerConfig(policy='stability_stop' if mode=='budget' else 'fixed_burst',
        policy_config=PolicyConfig(max_bursts=2),burst_s=.2,cooldown_s=0,startup_timeout_s=.5)
    controller=StreamingController(backend,HealthyBaseline(100,'fixture-calibration'),classify,start,config)
    def send(end,latency):
        previous=controller.latest
        clock.advance_to(end)
        controller.on_window(CheapWindow('window-'+str(end),0 if previous is None else previous.end_ns,
            end,end,clock.domain,latency,95,1,1))
    def advance(end):
        for _ in range(500):
            wake=controller.next_wakeup_ns()
            if wake is None or wake>end:clock.advance_to(end);return
            clock.advance_to(wake);controller.tick()
        raise RuntimeError('Fixture scheduler failed to progress')
    send(1_000_000_000,100 if mode=='healthy' else 200)
    if mode=='horizon':advance(1_050_000_000)
    else:advance(5_000_000_000)
    if mode=='reactivated':send(6_000_000_000,400);advance(10_000_000_000)
    controller.finish()
    # Instrumented fake range boundaries, not inferred real GPU active time.
    spans={}
    for event in (json.loads(line) for line in rec.jsonl().splitlines()):
        if event['name'] in ('capture_control_window_started','capture_control_window_finished'):
            spans.setdefault(event['scope'],{})[event['name']]=event['timestamp_ns']
    observations={}
    for episode in controller.episodes:
        for cid in episode.attempts:
            try:ready=backend.evidence(cid)
            except (KeyError,CaptureFailed):continue
            bounds=spans[cid]
            a=Acquisition(bounds['capture_control_window_started'],bounds['capture_control_window_finished'],ready.ready_at_ns,clock.domain)
            kernel=KernelObservation(cid,ready.evidence_id,'GPU-synthetic-fixture',(123,),1,.01,
                'single_configured_worker_and_device_verified',a)
            observations[ready.evidence_id]=MeasuredObservation(ready.evidence_id,'synthetic_simulation',a,(),kernel)
    exported=export_initial_stops('fixture-'+mode,controller.snapshot(),observations,
        classifier_version='fixture_abstains_not_calibrated')
    return exported,observations


def main(output):
    output.mkdir(parents=True,exist_ok=False);write_sources(output)
    (output/'counter_cases.json').write_text(json.dumps(counter_cases(),indent=2,allow_nan=False)+'\n')
    counts={}
    for mode in ('unknown','budget','launch_failure','diagnosis_failure','timeout','horizon','reactivated','healthy'):
        exported,observations=controller_case(mode);folder=output/mode;folder.mkdir()
        for name,key in [('predictions.json','predictions'),('controller_snapshot.json','controller_snapshot'),('export_audit.json','export_audit')]:
            (folder/name).write_text(json.dumps(exported[key],indent=2,allow_nan=False)+'\n')
        (folder/'observations.json').write_text(json.dumps({k:asdict(v) for k,v in observations.items()},indent=2)+'\n')
        counts[mode]=len(exported['predictions'])
    summary=dict(provenance='synthetic_simulation',gpu_used=False,initial_stops_by_case=counts,
        note='Actual CPU controller exports and hand-authored counter fixtures; no calibrated diagnosis or GPU metric validation.')
    (output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
