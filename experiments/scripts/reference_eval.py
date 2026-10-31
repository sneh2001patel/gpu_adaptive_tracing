#!/usr/bin/env python3
"""CPU-fixture CLI: lock adjudications separately from loading/scoring predictions.

Live use needs a validated binding to the run's host monotonic clock. This CLI
accepts explicit synthetic clocks/provenance only; the APIs accept a caller clock.
"""
import argparse
import json
import os
from pathlib import Path

from experiments.evaluation.reference_store import ReferenceStore,read_regular,fsync_directory
from experiments.evaluation.references import ReferenceRecord
from experiments.evaluation.scoring import evaluate_files
from experiments.tracing.arrival_schedule import unique_object
from experiments.tracing.timing import ManualClock


def write_report(result,path):
    lines=['# Locked-reference initial-stop scoring','',f"Provenance: `{result['provenance']}`. Offline agreement with declared locked adjudications; not diagnosis validation or stopping safety.",'',
        f"Reference lock: `{result['reference_lock_sha256']}`.",'',
        '| Diagnosis outcome | Initial stops |','|---|---:|']
    lines += [f'| {name} | {count} |' for name,count in result['outcomes'].items()]
    lines += ['',f"All logged activated episodes: {result['denominators']['all_logged_activated_episodes']}; adjudicable references: {result['denominators']['reference_adjudicable_stops']}; unavailable: {result['denominators']['reference_unavailable_stops']}.",
        f"Stable unsupported: {result['stable_unsupported']}; stable incomplete: {result['stable_incomplete']}; stable unadjudicable: {result['stable_unadjudicable']}.",'',
        'Failures, budget exhaustion, recovery and horizon censoring retain distinct reason/status counts in SCORE.json. An unresolved/unavailable result is never silently counted as a correct healthy diagnosis. A generic mixed label supplies no cause coverage.','',
        'The denominator is conditional on the supplied hashed activation snapshot. Missed incident detection, false activations against a full incident census, human benefit, profiler cost and empirical classifier calibration are not established.']
    Path(path).write_text('\n'.join(lines)+'\n')


def main(args):
    clock=ManualClock(args.synthetic_clock_ns);clock.domain=args.clock_domain
    store=ReferenceStore(args.store)
    if args.command=='lock':
        data=json.loads(read_regular(args.references),object_pairs_hook=unique_object)
        if type(data) is not list:raise ValueError('Reference input must be a list')
        records=[ReferenceRecord.from_dict(row) for row in data]
        if any(r.provenance!='synthetic_simulation' for r in records):raise ValueError('CLI synthetic clock cannot lock live references')
        if args.anchor_output.exists():raise FileExistsError('Never overwrite a retained reference lock anchor')
        anchor=store.lock(records,args.artifact_root,args.rubric,clock=clock)
        with args.anchor_output.open('x') as stream:
            stream.write(json.dumps(dict(reference_lock_sha256=anchor,provenance='synthetic_simulation'),indent=2)+'\n')
            stream.flush();os.fsync(stream.fileno())
        args.anchor_output.chmod(0o444);fsync_directory(args.anchor_output.parent)
        print(json.dumps(dict(reference_lock_sha256=anchor,provenance='synthetic_simulation')))
    else:
        locked=store.load(args.lock_sha256)
        if locked.provenance!='synthetic_simulation':raise ValueError('CLI synthetic clock cannot score live runs')
        result=evaluate_files(store,args.lock_sha256,args.predictions,args.controller_snapshot,clock=clock)
        args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'SCORE.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        write_report(result,args.output/'REPORT.md')
        print(json.dumps(dict(denominators=result['denominators'],outcomes=result['outcomes']),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    for name in ('lock','score'):
        command=sub.add_parser(name)
        command.add_argument('--store',type=Path,required=True)
        command.add_argument('--synthetic-clock-ns',type=int,required=True)
        command.add_argument('--clock-domain',required=True)
        if name=='lock':
            command.add_argument('--references',type=Path,required=True);command.add_argument('--artifact-root',type=Path,required=True)
            command.add_argument('--rubric',type=Path,required=True);command.add_argument('--anchor-output',type=Path,required=True)
        else:
            command.add_argument('--lock-sha256',required=True);command.add_argument('--predictions',type=Path,required=True)
            command.add_argument('--controller-snapshot',type=Path,required=True);command.add_argument('--output',type=Path,required=True)
    main(parser.parse_args())
