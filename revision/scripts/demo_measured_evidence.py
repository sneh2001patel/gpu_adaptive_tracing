#!/usr/bin/env python3
"""Synthetic CPU example of separate measured inputs and evaluator references."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from revision.evaluation.references import ReferenceArtifact, ReferenceCriterion, ReferenceRecord
from revision.tracing.diagnosis import UncalibratedClassifier
from revision.tracing.measured_evidence import Acquisition, MeasuredMetric, MeasuredObservation, KernelObservation, METRICS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    stamp=Acquisition(0,2_000_000_000,3_000_000_000,'synthetic-demo-clock')
    values={'request_p95_ms':200,'completed_rps':5,'prompt_tokens_mean':30,'output_tokens_mean':32,
            'queue_depth_mean':4,'request_wait_p95_ms':100,'prefill_service_fraction':.1,'gpu_util_mean':90}
    metrics=tuple(MeasuredMetric(name,source,unit,values[name],10,10,'complete',None,stamp)
                  for name,(source,unit) in METRICS.items())
    kernel=KernelObservation('synthetic-capture','synthetic-evidence','GPU-synthetic',(123,),20,.1,
        'single_configured_worker_and_device_verified',stamp)
    observation=MeasuredObservation('synthetic-observation','synthetic_simulation',stamp,metrics,kernel)
    # These records deliberately contain no real GPU or independent human evidence.
    artifacts=[]
    for name,channel in [('server','server_diagnostics'),('requests','request_diagnostics')]:
        path=args.output/f'{name}.json'
        path.write_text(json.dumps(dict(provenance='synthetic_simulation',channel=channel,
            note='Generated fixture, not measured incident evidence'))+'\n')
        artifacts.append(ReferenceArtifact(name,path.name,hashlib.sha256(path.read_bytes()).hexdigest(),channel,stamp))
    reference=ReferenceRecord('adjudicated_reference','synthetic-run','synthetic-rubric-v1',
        'synthetic_simulation',stamp,'supported',('queue_pressure',),(),True,
        (ReferenceCriterion('fixture-criterion','queue_pressure',True,('server','requests'),
            'Fixture assertion for contract testing only'),),tuple(artifacts),
        ('Synthetic alternative mechanism',),None,None,('synthetic-assessor',),
        True,4_000_000_000,5_000_000_000,('Synthetic single-assessor fixture, not experimental ground truth',))
    for artifact in reference.artifacts:artifact.verify_content(args.output)
    reference.require_joinable(run_id='synthetic-run',provenance='synthetic_simulation',
        join_at_ns=5_000_000_000,clock_domain=stamp.clock_domain)
    prediction=UncalibratedClassifier().classify(observation,now_ns=3_000_000_000,clock_domain=stamp.clock_domain)
    # No reference or intervention object is passed into classification.
    for name,value in [('measured_input',observation),('prediction',prediction),('evaluator_reference',reference)]:
        (args.output/f'{name}.json').write_text(json.dumps(asdict(value),indent=2)+'\n')
    print(json.dumps(dict(provenance='synthetic_simulation',gpu_used=False,
        policy_label=prediction.policy_label,reasons=prediction.reasons,reference_used_by_classifier=False),indent=2))


if __name__=='__main__':main()
