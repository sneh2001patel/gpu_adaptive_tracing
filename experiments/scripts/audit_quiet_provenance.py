#!/usr/bin/env python3
"""Write a separate provenance index; never repair or relabel saved live evidence."""
import argparse,json
from pathlib import Path
from experiments.evaluation.quiet_provenance import build_index,digest


def audit(campaign,output):
    campaign=Path(campaign).resolve();output=Path(output).resolve()
    if output.is_relative_to(campaign):raise ValueError('Index must be outside the immutable campaign')
    index=build_index(campaign)
    output.mkdir(parents=True,exist_ok=False)
    (output/'INDEX.json').write_text(json.dumps(index,indent=2)+'\n')
    (output/'artifact_manifest.json').write_text(json.dumps(dict(files={'INDEX.json':digest((output/'INDEX.json').read_bytes())}),indent=2)+'\n')
    return {k:index[k] for k in ('version','jobs','unique_barriers','observed_rows','historical_rows','campaign_artifact_hashes_verified')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.campaign,args.output),indent=2))
