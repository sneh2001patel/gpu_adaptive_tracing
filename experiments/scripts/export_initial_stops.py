#!/usr/bin/env python3
"""Export measured initial stops from a finalized controller snapshot, offline.

No reference input is accepted. Missing observations reject ready decisions;
missing/censored evidence remains absent, never reconstructed from wall time.
"""
import argparse
import hashlib
import json
from pathlib import Path
from experiments.evaluation.controller_export import export_initial_stops
from experiments.evaluation.reference_store import read_regular,sha
from experiments.tracing.arrival_schedule import unique_object
from experiments.tracing.measured_evidence import MeasuredObservation
from experiments.scripts.play_arrivals import write_sources


def main(args):
    raw=read_regular(args.controller_snapshot);observed=read_regular(args.observations)
    snapshot=json.loads(raw,object_pairs_hook=unique_object)
    data=json.loads(observed,object_pairs_hook=unique_object)
    if type(data) is not dict:raise ValueError('Evidence-ID keyed measured observations required')
    observations={k:MeasuredObservation.from_dict(v) for k,v in data.items()}
    result=export_initial_stops(args.run_id,snapshot,observations,classifier_version=args.classifier_version)
    args.output.mkdir(parents=True,exist_ok=False);write_sources(args.output)
    for filename,key in [('predictions.json','predictions'),('controller_snapshot.json','controller_snapshot'),('export_audit.json','export_audit')]:
        (args.output/filename).write_text(json.dumps(result[key],indent=2,allow_nan=False)+'\n')
    (args.output/'input_manifest.json').write_text(json.dumps(dict(controller_input_sha256=sha(raw),
        observations_input_sha256=sha(observed),exporter_sha256=sha(Path(__file__).read_bytes()),
        note=result['note']),indent=2)+'\n')
    print(json.dumps(dict(initial_stops=len(result['predictions']),output=str(args.output))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for option in ('controller-snapshot','observations','output'):p.add_argument('--'+option,type=Path,required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--classifier-version',required=True)
    main(p.parse_args())
