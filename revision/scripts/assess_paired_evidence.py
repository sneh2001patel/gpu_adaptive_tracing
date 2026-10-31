#!/usr/bin/env python3
"""CPU-only retrospective audit/rubric/gap-review scaffolding. No reference locks."""
import argparse,hashlib,json
from pathlib import Path
from revision.evaluation.evidence_assessment import audit_bundle,draft_rubric,review_template,validate_gap_review
from revision.scripts.play_arrivals import write_sources


def main(args):
    audit=audit_bundle(args.input,args.expected_manifest_sha256);rubric=draft_rubric()
    review_result=None
    if args.review is not None:
        review=json.loads(args.review.read_text())
        paths=[path for p in audit['pairs'] for path in p['artifact_paths']]
        review_result=validate_gap_review(review,audit,rubric,paths)
    args.output.mkdir(parents=True,exist_ok=False);write_sources(args.output)
    for name,data in (('AUDIT.json',audit),('RUBRIC_DRAFT.json',rubric),('REVIEW_TEMPLATE.json',review_template(audit,rubric))):
        (args.output/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
    if review_result is not None:
        (args.output/'review_input.json').write_bytes(args.review.read_bytes())
        (args.output/'REVIEW_VALIDATION.json').write_text(json.dumps(review_result,indent=2)+'\n')
    (args.output/'artifact_manifest.json').write_text(json.dumps(dict(files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.output.iterdir()) if p.is_file()}),indent=2)+'\n')
    print(json.dumps(dict(jobs=len(audit['jobs']),pairs=len(audit['pairs']),source_artifacts_verified=audit['verified_artifact_entries'],
        references_created=0,references_locked=0,calibration_enabled=False,new_GPU_activity=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,default=Path('revision/hardware/l4_20261028/pairs_001'))
    p.add_argument('--expected-manifest-sha256');p.add_argument('--review',type=Path)
    p.add_argument('--output',type=Path,required=True);main(p.parse_args())
