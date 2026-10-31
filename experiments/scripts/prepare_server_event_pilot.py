#!/usr/bin/env python3
"""Prepare prospective engineering guards/phase templates, never GPU jobs or labels."""
import argparse,hashlib,json
from pathlib import Path


def specification(corpus_bytes,source_manifest_bytes):
    corpus=json.loads(corpus_bytes);source=json.loads(source_manifest_bytes)
    if source['vllm_version']!='0.10.2':raise ValueError('Pinned source required')
    if {p['band'] for p in corpus['prompts']}!={'short','long'}:raise ValueError('Pinned corpus bands required')
    for p in corpus['prompts']:
        if hashlib.sha256(p['prompt'].encode()).hexdigest()!=p['prompt_utf8_sha256']:raise ValueError('Actual prompt bytes differ')
    return dict(version='server_event_instrumentation_pilot_spec_v1',status='prospective_engineering_preparation_not_executable',
        corpus_sha256=hashlib.sha256(corpus_bytes).hexdigest(),source_manifest_sha256=hashlib.sha256(source_manifest_bytes).hexdigest(),
        scope='next_bounded_instrumentation_pilot_only_not_reference_or_main_study',
        engineering_guards=dict(event_drops_allowed=0,event_faults_allowed=0,clock_probe_outside_parent_bracket_allowed=False,
            source_or_instance_mismatch_allowed=False,ambiguous_boundary_events='retain_separately_never_zero_fill',
            requested_window_s=10,min_successful_completions_for_p95_review=20,
            metric_sample_interval_s=.5,max_metric_receipt_gap_s=.75,matched_ID_and_actual_token_work='exact',
            paired_latency_ratio_flag=1.25,latency_flag_role='engineering_mismatch_review_only_not_equivalence_or_significance',
            low_sample_windows='unavailable_do_not_lower_guard_after_observing_results'),
        budget=dict(max_requests_per_case=512,max_client_inflight=32,server_max_num_seqs=16,
            max_case_horizon_s=60,max_drain_s=30,max_journal_events=4096,max_journal_requests=512,max_probes_per_session=32),
        cache_policy='disable_prefix_cache_in_both_roles_and_save_verified_effective_configuration',
        server_event_semantics='engine_admission_first_CPU_schedule_and_scheduler_terminal_hooks_not_GPU_start_or_HTTP_completion',
        correlation_requirement='verify_engine_request_ID_to_client_response_ID_mapping_from_pinned_source_and_live_receipts_before_join',
        clock_requirement='fresh_nonce_generation_PID_UUID_bound_parent_bracketed_probe_with_complete_history',
        commissioning_first=dict(request_count_limit=8,one_fresh_owned_server=True,goal='validate_hooks_clock_and_ID_mapping_before_any_challenge',
            failure_action='retain_outputs_stop_without_calibration_or_challenge_launch'),
        cases=[dict(case_id='rate_ladder',duration_s=60,rate_levels_rps=[.5,1,2,4,8],level_duration_s=8,
                    final_removal_s=20,selection_rule='record_realized_queue_and_bounds_select_candidate_rate_independently_of_predictions_or_stop_if_no_candidate'),
               dict(case_id='pressure_then_removal',duration_s=60,phases=[['baseline',10],['selected_pressure',30],['removal',20]]),
               dict(case_id='lull_then_recurrence',duration_s=60,phases=[['baseline',10],['selected_pressure',15],['temporary_lull',5],['selected_pressure',20],['removal',10]]),
               dict(case_id='unresolved_source_gap_control',duration_s=60,goal='deliberately_incomplete_event_evidence_must_remain_unresolved_no_inferred_cause')],
        unresolved_before_launch=['source_plugin_GPU_startup_and_hook_commissioning','engine_to_client_ID_mapping',
            'effective_cache_flag_validation','measured_pressure_candidate_selection_rule_and_exact_arrival_files',
            'observer_perturbation_on_off_control_design','source_gap_injection_implementation'],
        scientific_limits=dict(reference_latency_mismatch_tolerance=None,precision_or_power_target=None,independent_reference_repetitions=None),
        calibration_enabled=False,reference_export_enabled=False,launch_supported=False,protocol_frozen=False,
        note='Guards are prospective engineering choices, not fitted scientific thresholds, proof of healthy behavior or percentile precision. They are never applied retrospectively to step-025 reference eligibility.')


def main(args):
    corpus=args.corpus.read_bytes();source=args.source_manifest.read_bytes();spec=specification(corpus,source)
    args.output.mkdir(parents=True,exist_ok=False)
    for name,data in (('SPECIFICATION.json',spec),('corpus_input.json',json.loads(corpus)),('source_input.json',json.loads(source))):
        (args.output/name).write_text(json.dumps(data,indent=2)+'\n')
    (args.output/'artifact_manifest.json').write_text(json.dumps(dict(files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(args.output.iterdir()) if p.is_file()}),indent=2)+'\n')
    print(json.dumps(dict(status=spec['status'],launch_supported=False,new_GPU_activity=False)))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',type=Path,default=Path('experiments/hardware/l4_20261028/capacity_001/corpus.json'))
    p.add_argument('--source-manifest',type=Path,default=Path('experiments/protocol/sources/vllm_0_10_2/events/SOURCE_MANIFEST.json'))
    p.add_argument('--output',type=Path,required=True);main(p.parse_args())
