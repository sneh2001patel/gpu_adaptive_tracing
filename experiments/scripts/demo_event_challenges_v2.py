#!/usr/bin/env python3
"""Save hand-authored CPU evidence cases; no model, target server or GPU is run."""
import argparse,json
from dataclasses import asdict
from pathlib import Path
from experiments.feasibility.challenge_protocol_v2 import NS,load_prepared,select_pressure,sha
from experiments.tracing.live_features import ServingBinding,MetricReceipt
from experiments.scripts.demo_live_feasibility import metric_text


def main(args):
    plan,bank=load_prepared(args.packet);schedule=bank['rate_ladder'];job=plan['jobs'][0]
    root=args.output;root.mkdir(parents=True,exist_ok=False)
    binding=ServingBinding('CPU-fixture-v2',0,43,'GPU-fixture',schedule.requests[0].payload['model'],'0','CPU-fixture-clock')
    work=[dict(request_id=r.request_id,admitted_at_ns=NS+r.offset_ns,completed_at_ns=NS+r.offset_ns+1,
        http_status=200,error=None,prompt_tokens=1072,output_tokens=32) for r in schedule.requests]
    results=[]
    for name,levels in (('zero_queue',()),('isolated_spike',()),('candidate_3rps',(3,4)),('candidate_4rps',(4,)),('metric_gap',(3,4)),('missing_work',(4,))):
        receipts=[]
        for i in range(80):
            t=NS+i*NS//2+1;positive=i//16 in levels or (name=='isolated_spike' and i==65)
            receipts.append(MetricReceipt(str(i),binding,t,t+1,200,metric_text(model=binding.model,waiting=int(positive)),None))
        if name=='metric_gap':receipts.pop(60)
        actual=work[:-1] if name=='missing_work' else work
        result=select_pressure(receipts,binding,case_start_ns=NS,request_rows=actual,schedule=schedule,job=job)
        directory=root/name;directory.mkdir()
        for filename,data in (('work.json',actual),('receipts.json',[asdict(r)|dict(raw=r.raw.decode()) for r in receipts]),('selection.json',result)):
            (directory/filename).write_text(json.dumps(data,indent=2)+'\n')
        results.append(dict(case=name,result=result))
    assert [r['result']['status'] for r in results]==['no_sampled_pressure_candidate','no_sampled_pressure_candidate',
        'engineering_candidate','engineering_candidate','incomplete_evidence','incomplete_work']
    (root/'RESULT.json').write_text(json.dumps(dict(provenance='synthetic_simulation',GPU_used=False,live_validation=False,
        role='hand_authored_evidence_gate_cases_not_model_outputs',protocol_version=plan['version'],cases=results,
        references_created=0,calibration_enabled=False,protocol_frozen=False),indent=2)+'\n')
    (root/'artifact_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(root)):sha(p.read_bytes())
        for p in sorted(root.rglob('*')) if p.is_file()}),indent=2)+'\n')
    print(json.dumps(dict(CPU_cases=len(results),GPU_used=False,live_validation=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packet',type=Path,default=Path('experiments/examples/event_challenges_v2/prepared_001'))
    p.add_argument('--output',type=Path,required=True);main(p.parse_args())
