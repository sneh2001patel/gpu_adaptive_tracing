#!/usr/bin/env python3
"""Offline mapping audit of saved L4 quiet receipts; never a live controller run."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from revision.tracing.live_features import ServingBinding, MetricReceipt, map_receipt, persist_receipt, load_receipt


def audit(pilot, output):
    config=json.loads((pilot/'configuration.json').read_text())
    quiet=json.loads((pilot/'quiet_evidence.json').read_text())
    output.mkdir(parents=True,exist_ok=False);rows=[]
    for row in quiet:
        barrier=row['barrier_receipt'];generation=barrier['generation']
        worker=json.loads((pilot/f'session-{generation}'/f'worker-{barrier["pid"]}.json').read_text())
        for name in ('session_nonce','generation','clock_domain','device_uuid'):
            if worker[name]!=barrier[name]:raise ValueError('Saved worker/barrier mismatch')
        scope=ServingBinding(worker['session_nonce'],worker['generation'],worker['pid'],worker['device_uuid'],config['model'],config['engine'],worker['clock_domain'])
        for side in ('before','after'):
            raw=(pilot/row[side+'_path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=row[side+'_sha256']:raise ValueError('Saved raw metric hash mismatch')
            requested=row['requested_at_ns'] if side=='before' else row['barrier_received_at_ns']
            received=row['before_received_at_ns'] if side=='before' else row['observed_at_ns']
            receipt=MetricReceipt(f'{row["label"]}-{row["index"]}-{side}',scope,requested,received,200,raw,None)
            path=persist_receipt(output/'receipts',receipt)
            restored=load_receipt(output/'receipts',path)
            sample,diagnostic=map_receipt(restored,scope,now_ns=received)
            rows.append(dict(receipt_path=path,source_path=str(pilot/row[side+'_path']),
                source_sha256=row[side+'_sha256'],mapped_sample=asdict(sample),diagnostic=diagnostic))
    report=dict(processing_mode='offline_mapping_audit_of_previously_collected_live_bytes',
        new_gpu_activity=False,online_decisions_executed=False,calibration_data_created=False,
        feature_windows_reconstructed=False,rows=rows,
        note='Historical parent acquisition brackets are reused only for receipt validation. No online window close/availability or controller decision is invented.')
    (output/'AUDIT.json').write_text(json.dumps(report,indent=2)+'\n')
    files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*')) if p.is_file()}
    (output/'artifact_manifest.json').write_text(json.dumps(dict(files=files),indent=2)+'\n')
    print(json.dumps(dict(mapped_receipts=len(rows),new_gpu_activity=False,processing_mode=report['processing_mode'])))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pilot',type=Path,default=Path('revision/hardware/l4_20261028/activity_002'))
    p.add_argument('--output',type=Path,required=True);args=p.parse_args();audit(args.pilot,args.output)
