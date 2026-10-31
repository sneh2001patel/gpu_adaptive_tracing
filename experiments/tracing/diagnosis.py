"""Uncalibrated measured-evidence adapter; deliberately emits no concrete labels."""
from dataclasses import dataclass

from experiments.tracing.measured_evidence import MeasuredObservation

VERSION = 'uncalibrated_measured_adapter_v1'
# Reference vocabulary is not itself a policy label. Prefill mapping is unvalidated.
REFERENCE_TO_POLICY = (('queue_pressure', 'vllm_queue_pressure'),
                       ('prefill_dominated_service', None))
REQUIRED_METRICS = ('request_p95_ms', 'completed_rps', 'prompt_tokens_mean',
                    'output_tokens_mean', 'queue_depth_mean', 'request_wait_p95_ms',
                    'prefill_service_fraction', 'gpu_util_mean')


@dataclass(frozen=True)
class DiagnosisResult:
    observation_id: str
    evidence_id: str | None
    provenance: str
    available_at_ns: int
    decision_at_ns: int
    policy_label: None
    cause_set: tuple
    reasons: tuple[str, ...]
    classifier_version: str = VERSION


class UncalibratedClassifier:
    """No fitting or concrete diagnosis. Required names are a collection contract.

    A future calibrated implementation must separately version thresholds,
    support/coverage requirements and reference-to-policy mapping. No score or
    confidence is invented here, even for complete synthetic input.
    """
    def classify(self, observation, *, now_ns, clock_domain):
        if type(observation) is not MeasuredObservation:
            raise ValueError('Only strict measured observations accepted')
        observation.require_visible(now_ns, clock_domain)
        metrics={m.name:m for m in observation.metrics}
        reasons=['calibration_unavailable']
        for name in REQUIRED_METRICS:
            metric=metrics.get(name)
            if metric is None or metric.value is None:
                reasons.append('missing:'+name)
            elif metric.coverage != 'complete':
                reasons.append('partial:'+name)
        if observation.kernel is None:
            reasons.append('kernel_evidence_unavailable')
        reasons.append('prefill_policy_mapping_unvalidated')
        return DiagnosisResult(observation.observation_id,
            None if observation.kernel is None else observation.kernel.evidence_id,
            observation.provenance, observation.acquisition.available_at_ns, now_ns,
            None, (), tuple(reasons))
