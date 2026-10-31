#!/usr/bin/env python3
"""Persist explicit CPU fixtures for selection and consumer receipt withholding."""
import argparse,hashlib,json
from dataclasses import asdict,replace
from pathlib import Path
from experiments.feasibility.challenge_protocol import NS,make_schedule,select_pressure,event_window
from experiments.tracing.live_features import ServingBinding,MetricReceipt
from experiments.tracing.server_events import EventJournal
from experiments.scripts.demo_live_feasibility import metric_text


def main(args):
    root=args.output;root.mkdir(parents=True,exist_ok=False)
    def save(path,data):path.write_text(json.dumps(data,indent=2)+'\n')
    binding=ServingBinding('CPU-fixture',0,43,'GPU-fixture','fixture-model','0','fixture-clock')
    schedule=make_schedule('rate_ladder','Explicit synthetic prompt; no model is run.','fixture-model')
    work=[dict(request_id=r.request_id,admitted_at_ns=NS+r.offset_ns,completed_at_ns=NS+r.offset_ns+1,
        http_status=200,error=None,prompt_tokens=1072,output_tokens=32) for r in schedule.requests]
    job=dict(job_id='rate_ladder-b0-off',event_instrumentation=False,prefix_caching=False)
    cases=[]
    for name in ('all_zero','isolated_spike','lowest_candidate_2rps','metric_gap','work_missing','foreign_scope'):
        receipts=[]
        for i in range(80):
            positive=(name in ('lowest_candidate_2rps','metric_gap','work_missing','foreign_scope') and i//16 in (2,4)) or (name=='isolated_spike' and i==33)
            t=NS+i*NS//2+1
            receipts.append(MetricReceipt(str(i),binding,t,t+1,200,metric_text(model=binding.model,waiting=int(positive)),None))
        if name=='metric_gap':receipts.pop(60)
        if name=='foreign_scope':receipts[0]=replace(receipts[0],binding=replace(binding,generation=1))
        actual=work[:-1] if name=='work_missing' else work
        directory=root/name;directory.mkdir()
        save(directory/'receipts.json',[asdict(r)|dict(raw=r.raw.decode()) for r in receipts]);save(directory/'work.json',actual)
        try:result=select_pressure(receipts,binding,case_start_ns=NS,request_rows=actual,schedule=schedule,job=job)
        except ValueError as exc:result=dict(status='rejected_foreign_input',error=str(exc),selected_rate_rps=None)
        cases.append(dict(case=name,result=result));save(directory/'selection.json',result)
    journal=EventJournal(binding,lambda:0);journal.now_ns=lambda:60*NS
    journal.record('engine_admitted','synthetic-r',2*NS,2*NS+1)
    journal.record('first_positive_schedule','synthetic-r',3*NS,3*NS+1)
    journal.record('scheduler_finished','synthetic-r',4*NS,4*NS+1,terminal_status='FINISHED_LENGTH_CAPPED')
    command=dict(token='a'*32,binding=asdict(binding),requested_at_ns=59*NS)
    receipt=dict(command=command,data=journal.probe(command),received_at_ns=61*NS)
    save(root/'raw_event_receipt.json',receipt)
    windows=[]
    for start in range(0,60,10):
        windows.append(dict(start_ns=start*NS,end_ns=(start+10)*NS,**event_window(receipt,binding,
            start_ns=start*NS,end_ns=(start+10)*NS,decision_ns=62*NS,withheld_interval=(10*NS,40*NS))))
    save(root/'consumer_windows.json',windows)
    assert [c['result']['status'] for c in cases]==['no_sampled_pressure_candidate','no_sampled_pressure_candidate',
        'engineering_candidate','incomplete_evidence','incomplete_work','rejected_foreign_input']
    assert [w['status'] for w in windows]==['bounds_available','unresolved','unresolved','unresolved','bounds_available','bounds_available']
    save(root/'RESULT.json',dict(provenance='synthetic_simulation',GPU_used=False,live_validation=False,
        classifier_run=False,references_created=0,cases=cases,consumer_withheld_windows=3,
        note='Hand-authored queue/work receipts; event windows are evaluated offline at 62s, not claimed online decisions.'))
    save(root/'artifact_manifest.json',dict(files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob('*')) if p.is_file()}))
    print(json.dumps(dict(synthetic_cases=len(cases),consumer_withheld_windows=3,GPU_used=False,live_validation=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
