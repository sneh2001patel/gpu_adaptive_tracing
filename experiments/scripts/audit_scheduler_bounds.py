#!/usr/bin/env python3
"""Audit saved scheduler bounds into a fresh separate offline output directory."""
import argparse,json
from pathlib import Path
from experiments.evaluation.scheduler_bound_audit import audit_campaign,assessment_draft,sha


def audit(campaign,output,expected_manifest_sha256):
    campaign=Path(campaign).resolve();output=Path(output).resolve()
    if output.is_relative_to(campaign):raise ValueError('Audit output must be outside the immutable campaign')
    if output.exists():raise FileExistsError(output)
    result=audit_campaign(campaign,expected_manifest_sha256)
    output.mkdir(parents=True,exist_ok=False)
    (output/'AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    (output/'SUMMARY.json').write_text(json.dumps(result['summary'],indent=2)+'\n')
    (output/'CRITERIA_DRAFT.json').write_text(json.dumps(assessment_draft(),indent=2)+'\n')
    (output/'artifact_manifest.json').write_text(json.dumps(dict(files={name:sha((output/name).read_bytes()) for name in ('AUDIT.json','SUMMARY.json','CRITERIA_DRAFT.json')}),indent=2)+'\n')
    return result['summary']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-manifest-sha256',required=True)
    args=parser.parse_args();print(json.dumps(audit(args.campaign,args.output,args.expected_manifest_sha256),indent=2))
