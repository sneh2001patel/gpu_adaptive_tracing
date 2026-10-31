#!/usr/bin/env python3
"""Explicit CPU fixtures for scheduler-hook history; no vLLM/GPU import or launch."""
import argparse,hashlib,json
from dataclasses import asdict
from pathlib import Path
from experiments.tracing.live_features import ServingBinding
from experiments.tracing.server_events import EventJournal,scheduler_wait_bounds


def demo(output):
    output.mkdir(parents=True,exist_ok=False);summary=[]
    for mode in ('complete_batch','boundary_uncertain','budget_drop','pending_and_aborted','foreign_snapshot'):
        clock=[0];binding=ServingBinding('synthetic-owned',1,43,'GPU-synthetic','fixture','0','synthetic-clock')
        journal=EventJournal(binding,lambda:clock[0],max_events=2 if mode=='budget_drop' else 4096)
        def record(kind,rid,start,end,status=None):
            clock[0]=end*1_000_000;journal.record(kind,rid,start*1_000_000,end*1_000_000,terminal_status=status)
        record('engine_admitted','r1',1,2);record('engine_admitted','r2',3,4)
        if mode=='pending_and_aborted':record('scheduler_finished','r1',10,11,'FINISHED_ABORTED')
        else:
            clock[0]=30_000_000;journal.scheduled(['r1','r2'],25_000_000,30_000_000)
            record('scheduler_finished','r1',100,101,'FINISHED_STOPPED');record('scheduler_finished','r2',110,111,'FINISHED_STOPPED')
        command=dict(token='a'*32,binding=asdict(binding),requested_at_ns=290_000_000);clock[0]=300_000_000
        snapshot=journal.probe(command)
        if mode=='foreign_snapshot':snapshot['binding']=snapshot['binding']|dict(worker_pid=44)
        result=None;error=None
        try:result=scheduler_wait_bounds(snapshot,command,binding,received_at_ns=310_000_000,start_ns=0,end_ns=28_000_000 if mode=='boundary_uncertain' else 50_000_000)
        except ValueError as exc:error=str(exc)
        path=output/mode;path.mkdir()
        for name,data in (('snapshot.json',snapshot),('command.json',command),('RESULT.json',dict(provenance='synthetic_simulation',mode=mode,validation_error=error,result=result,live_validation_passed=False))):
            (path/name).write_text(json.dumps(data,indent=2)+'\n')
        summary.append(dict(mode=mode,history_complete=snapshot['history_complete'],dropped=snapshot['dropped'],accepted=result is not None,
            eligible_wait_bounds=0 if result is None else len(result['observations']),live_validation_passed=False))
    (output/'SUMMARY.json').write_text(json.dumps(dict(provenance='synthetic_simulation',GPU_used=False,cases=summary),indent=2)+'\n')
    (output/'artifact_manifest.json').write_text(json.dumps(dict(files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}),indent=2)+'\n')
    print(json.dumps(summary))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args();demo(args.output)
