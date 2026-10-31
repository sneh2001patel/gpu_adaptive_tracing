"""Evaluator-only preparation and availability inventory; no fitting or labels.

The packet is not a reference lock and cannot make the study ready. Interventions
are collection instructions, never adjudicated reference causes.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from revision.scripts.prepare_protocol import validate
from revision.tracing.measured_evidence import MeasuredObservation, METRICS, fields_only, identity

VERSION = 'independent_calibration_preparation_v1'


def prepare(config, entries, root):
    validate(config)
    if type(entries) is not list: raise ValueError('Observation entries must be a list')
    root = Path(root).resolve(); rows = []; seen = set(); domains = set()
    for entry in entries:
        fields_only(entry, {'run_id', 'split', 'observation_path'})
        identity(entry['run_id'], 'run_id')
        if entry['split'] != 'calibration': raise ValueError('Development/confirmation data cannot enter calibration inventory')
        relative = Path(entry['observation_path'])
        if relative.is_absolute() or '..' in relative.parts: raise ValueError('Relative observation path required')
        path = root/relative
        if path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size > 1048576:
            raise ValueError('Observation path escape or size limit')
        raw = path.read_bytes(); observation = MeasuredObservation.from_dict(json.loads(raw))
        key = (entry['run_id'], observation.observation_id)
        if key in seen: raise ValueError('Duplicate calibration observation')
        seen.add(key); domains.add(observation.provenance)
        metrics = {m.name: m for m in observation.metrics}
        rows.append(dict(run_id=entry['run_id'], observation_id=observation.observation_id,
            provenance=observation.provenance, observation_path=entry['observation_path'],
            sha256=hashlib.sha256(raw).hexdigest(), acquisition=asdict(observation.acquisition),
            features={name: dict(value=None, coverage='unavailable', reason='metric_absent') if name not in metrics else
                dict(value=metrics[name].value, coverage=metrics[name].coverage,
                     valid_samples=metrics[name].valid_samples, attempted_samples=metrics[name].attempted_samples,
                     reason=metrics[name].missing_reason) for name in METRICS},
            has_parsed_kernel=observation.kernel is not None))
    if len(domains) > 1: raise ValueError('Synthetic and live observations require separate inventories')
    jobs = []; evaluator = []
    for seed in config['splits']['calibration']['seeds']:
        for index, intervention in enumerate(('healthy_control', 'arrival_pressure_only', 'long_prompt_only')):
            pair = f'cal-{seed}-{index}'
            for role in ('feature_collection', 'matched_full_trace'):
                jobs.append(dict(run_id=pair+'-'+role, pair_id=pair, split='calibration', role=role,
                    fresh_owned_restart=True, exact_offered_file_required=True,
                    source_and_artifact_hashes_required=True, schedule_resolved=False))
            evaluator.append(dict(pair_id=pair, seed=seed, intended_intervention=intervention,
                status='collection_instruction_not_reference_truth', adjudication_status='not_started',
                required_channels=['server_diagnostics', 'request_diagnostics', 'matched_full_trace'],
                required_assessments=['symptom_realized_and_reversed', 'alternative_causes',
                    'clock_and_interval_coverage', 'matched_run_mismatch', 'unresolved_or_negative_evidence'],
                blinded_to_predictions_and_policy_required=True, lock_required_before_scoring=True))
    return dict(version=VERSION, status='preparation_only_not_executable',
        calibration_enabled=False, fitting_supported=False, launch_supported=False,
        study_ready=False, protocol_frozen=False, source_protocol_sha256=hashlib.sha256(
            json.dumps(config, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        observed_feature_inventory=rows, collection_jobs=jobs, evaluator_only=evaluator,
        blockers=['measured_capacity_and_prompt_corpus_hashes_missing',
            'exact_offered_schedules_and_counterbalanced_order_unresolved',
            'candidate_feature_contract_and_coverage_not_frozen',
            'independent_reference_collection_and_lock_missing',
            'threshold_fitting_and_heldout_validation_not_implemented'],
        unsupported_features=['request_wait_p95_ms', 'prefill_service_fraction'],
        note='Sample completeness is not time coverage. Interventions are not labels. No reference records or thresholds are fabricated.')
