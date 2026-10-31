#!/usr/bin/env python3
"""CPU-only calibration packet preparation; never SSH, launch, fit or freeze."""
import argparse
import hashlib
import json
from pathlib import Path
from experiments.evaluation.calibration_preparation import prepare


def main(args):
    config=json.loads(args.config.read_text())
    entries=[] if args.entries is None else json.loads(args.entries.read_text())
    packet=prepare(config,entries,args.artifact_root)
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'PREPARATION.json').write_text(json.dumps(packet,indent=2)+'\n')
    (args.output/'protocol_input.json').write_bytes(args.config.read_bytes())
    (args.output/'entries_input.json').write_text(json.dumps(entries,indent=2)+'\n')
    (args.output/'artifact_manifest.json').write_text(json.dumps(dict(files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.output.iterdir()) if p.is_file()}),indent=2)+'\n')
    print(json.dumps(dict(status=packet['status'],planned_jobs=len(packet['collection_jobs']),
        observed_windows=len(packet['observed_feature_inventory']),launch_supported=False,calibration_enabled=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,default=Path('experiments/configs/l4_protocol_draft.json'))
    p.add_argument('--entries',type=Path);p.add_argument('--artifact-root',type=Path,default=Path('.'))
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
