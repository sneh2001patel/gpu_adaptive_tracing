#!/usr/bin/env python3
"""Prepare/validate evaluator-only scheduler criteria and gap worksheets."""
import argparse,json
from pathlib import Path
from experiments.evaluation.scheduler_assessment import prepare_packet,criteria_template,validate_criteria,review_template,validate_review
from experiments.tracing.arrival_schedule import unique_object
from experiments.evaluation.quiet_provenance import digest


def prepare(campaign,audit_root,output,campaign_pin,audit_pin,*,criteria_path=None,review_path=None):
    campaign=Path(campaign).resolve();audit_root=Path(audit_root).resolve();output=Path(output).resolve()
    if output.is_relative_to(campaign) or output.is_relative_to(audit_root):raise ValueError('Separate assessment output required')
    if output.exists():raise FileExistsError(output)
    packet=prepare_packet(campaign,audit_root,campaign_pin,audit_pin)
    def read(path):return json.loads(Path(path).read_text(),object_pairs_hook=unique_object)
    criteria=criteria_template(packet) if criteria_path is None else read(criteria_path)
    gate=validate_criteria(criteria,packet)
    worksheet=review_template(packet,criteria) if review_path is None else read(review_path)
    review=validate_review(worksheet,packet,criteria)
    output.mkdir(parents=True,exist_ok=False)
    for name,data in [('PACKET.json',packet),('CRITERIA.json',criteria),('CRITERIA_VALIDATION.json',gate),
                      ('REVIEW_TEMPLATE.json',review_template(packet,criteria)),('REVIEW_INPUT.json',worksheet),('REVIEW_VALIDATION.json',review)]:
        (output/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    (output/'artifact_manifest.json').write_text(json.dumps(dict(files={p.name:digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}),indent=2)+'\n')
    return dict(cases=len(packet['cases']),catalog_artifacts=len(packet['catalog']),criteria_status=gate['status'],
        review_status=review['status'],references_created=0,references_locked=0,calibration_enabled=False,GPU_used=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',type=Path,required=True);parser.add_argument('--audit',type=Path,required=True)
    parser.add_argument('--expected-campaign-manifest-sha256',required=True);parser.add_argument('--expected-audit-manifest-sha256',required=True)
    parser.add_argument('--criteria',type=Path);parser.add_argument('--review',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.campaign,args.audit,args.output,args.expected_campaign_manifest_sha256,args.expected_audit_manifest_sha256,
        criteria_path=args.criteria,review_path=args.review),indent=2))
