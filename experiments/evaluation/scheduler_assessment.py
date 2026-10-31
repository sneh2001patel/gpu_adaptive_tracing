"""Evaluator-only criteria declarations and gap worksheets. No reference export."""
from dataclasses import asdict
from datetime import datetime,timezone
import json,math
from pathlib import Path
from experiments.evaluation.evidence_assessment import Bundle,digest
from experiments.evaluation.references import ReferenceArtifact,INDEPENDENT_CHANNELS
from experiments.tracing.measured_evidence import Acquisition,fields_only,identity
from experiments.tracing.live_features import ServingBinding,load_receipt

VERSION='scheduler_assessment_workflow_v1'
MEASURAND='host_engine_admission_to_first_positive_CPU_schedule_decision_interval'
COHORT='schedule_bracket_wholly_inside_half_open_window'
SPEC={
 'max_hook_bracket_width_ms':('number','ms'),
 'max_wait_interval_width_ms':('number','ms'),
 'relative_uncertainty_normalizer':('text','definition'),
 'max_relative_wait_uncertainty':('nonnegative','relative_fraction'),
 'max_boundary_ambiguous_fraction':('fraction','fraction'),
 'min_scheduler_requests_per_window':('integer','requests'),
 'target_percentile_precision':('number','ms'),
 'target_confidence_level':('probability','probability'),
 'max_evidence_readiness_latency_ms':('number','ms'),
 'max_source_probe_gap_ms':('number','ms'),
 'max_pair_work_mismatch':('fraction','mismatched_request_fraction'),
 'max_pair_latency_mismatch':('nonnegative','relative_fraction'),
 'min_independent_repetitions':('integer','repetitions'),
 'reference_agreement_requirement':('text','definition')}
FAMILIES={'host_schedule_event_history':'server_diagnostics','server_queue_gauges':'server_diagnostics',
 'client_response_timing':'request_diagnostics','matched_full_trace':'matched_full_trace',
 'intervention_record':'intervention_log'}
REVIEW_FIELDS=('measurand_cohort_rationale','precision_missingness_rationale','independence_alternatives',
 'negative_evidence_limits','readiness_and_mismatch_rationale','additional_evidence_needed')


def prepare_packet(campaign,audit_root,campaign_pin,audit_pin):
    source=Bundle(campaign,campaign_pin);derived=Bundle(audit_root,audit_pin)
    audit=derived.json('AUDIT.json')
    if audit['version']!='scheduler_bound_precision_audit_v1' or audit['campaign_manifest_sha256']!=campaign_pin:
        raise ValueError('Audit and campaign differ')
    if audit['classifier_activated'] or audit['references_created'] or audit['calibration_enabled']:
        raise ValueError('Collection-only development audit required')
    catalog={};cases=[]
    def artifact(path,family,channel,acquisition):
        if path not in source.files:raise ValueError('Unmanifested assessment artifact')
        aid='a-'+digest(dict(path=path,acquisition=asdict(acquisition),family=family))
        typed=ReferenceArtifact(aid,path,source.files[path],channel,acquisition)
        record=dict(artifact=asdict(typed),family=family,
            availability_scope='conservative_after_job_cleanup_not_online_receipt_time')
        if aid in catalog and catalog[aid]!=record:raise ValueError('Artifact identity collision')
        catalog[aid]=record;return aid
    for job in audit['jobs']:
        prefix=job['job_id']+'/';binding=ServingBinding(**source.json(prefix+'binding.json'))
        if asdict(binding)!=job['binding']:raise ValueError('Audit job binding differs')
        gates=source.json(prefix+'consumer_windows.json')
        cleanup=source.json(prefix+'RESULT.json')['cleanup']
        if not cleanup['confirmed_absent'] or cleanup['clock_domain']!=binding.clock_domain:
            raise ValueError('Bound job cleanup checkpoint required')
        available=cleanup['completed_at_ns']
        requests=[json.loads(line) for line in source.read(prefix+'requests/receipts.jsonl').splitlines()]
        request_path=prefix+'requests/receipts.jsonl'
        request_interval=Acquisition(min(r['admitted_at_ns'] for r in requests),max(r['completed_at_ns'] for r in requests),
            available,binding.clock_domain)
        request_artifact=artifact(request_path,'client_response_timing','request_diagnostics',request_interval)
        metrics=[]
        for name in sorted(source.files):
            if not name.startswith(prefix+'raw_metrics/') or not name.endswith('.json'):continue
            meta=source.json(name);raw_name=str(Path(name).parent/meta['raw_path'])
            if raw_name not in source.files or source.files[raw_name]!=meta['raw_sha256']:raise ValueError('Metric bytes not bound')
            receipt=load_receipt(source.root/Path(name).parent,Path(name).name)
            if receipt.binding!=binding:raise ValueError('Foreign metric binding')
            interval=Acquisition(receipt.requested_at_ns,receipt.received_at_ns,available,binding.clock_domain)
            metrics.append((receipt.requested_at_ns,receipt.received_at_ns,
                artifact(name,'server_queue_gauges','server_diagnostics',interval),
                artifact(raw_name,'server_queue_gauges','server_diagnostics',interval)))
        for i,window in enumerate(job['windows']):
            recorded=gates[i]
            if any(recorded[k]!=window[v] for k,v in [('start_ns','start_ns'),('end_ns','end_ns'),('status','consumer_status'),('reason','consumer_reason')]):
                raise ValueError('Recorded gate differs from audit')
            interval=Acquisition(window['start_ns'],window['end_ns'],recorded['owner_observed_at_ns'],binding.clock_domain)
            gate_interval=Acquisition(gates[0]['start_ns'],gates[-1]['end_ns'],available,binding.clock_domain)
            allowed=[request_artifact,artifact(prefix+'consumer_windows.json','consumer_gate_record','server_diagnostics',gate_interval)]
            for start,end,metadata,raw in metrics:
                if window['start_ns']<=start<=end<window['end_ns']:allowed.extend((metadata,raw))
            if window['selected_probe'] is not None:
                probe=source.json(window['selected_probe']);data=probe['data']
                if data['binding']!=asdict(binding):raise ValueError('Foreign event binding')
                source_interval=Acquisition(data['epoch_ns'],data['source_probe_ns'],available,binding.clock_domain)
                allowed.append(artifact(window['selected_probe'],'host_schedule_event_history','server_diagnostics',source_interval))
            cases.append(dict(case_id=f'window-{len(cases):03d}',job_id=job['job_id'],window_index=i,
                interval=asdict(interval),consumer_status=window['consumer_status'],consumer_reason=window['consumer_reason'],
                gate_json_pointer='/'+str(i),artifact_availability_upper_bound_ns=available,
                allowed_artifact_ids=sorted(set(allowed)),role='offline_assessment_not_classifier_input',
                source_gate_and_request_files_contain_whole_job_history=True))
    return dict(version=VERSION,record_role='evaluator_only_gap_assessment_packet',
        campaign_manifest_sha256=campaign_pin,audit_manifest_sha256=audit_pin,audit_sha256=derived.files['AUDIT.json'],
        verified_campaign_artifacts=len(source.files),verified_audit_artifacts=len(derived.files),
        cases=cases,catalog=catalog,metadata_disclosed=True,
        disclosure='Job names, roles and raw IDs may disclose workload/policy information; no blinding is asserted.',
        source_access='original_whole_campaign_and_audit_roots_required_not_a_self_contained_blinded_bundle',
        references_created=0,references_locked=0,reference_export_enabled=False,calibration_enabled=False,
        study_ready=False,protocol_frozen=False)


def criteria_template(packet):
    return dict(version=VERSION,record_role='scientific_criteria_declaration_not_acceptance',
        source_audit_sha256=packet['audit_sha256'],campaign_manifest_sha256=packet['campaign_manifest_sha256'],
        measurand=MEASURAND,cohort=COHORT,
        scientific_limits={key:dict(value=None,unit=unit,definition=None,rationale=None) for key,(_,unit) in SPEC.items()},
        decision_provenance=dict(author=None,decided_at_utc=None,development_data_informed=None,rationale=None,
            confirmation_scope='future_disjoint_collection_only'),
        evidence_separation=dict(classifier_evidence_families=None,reference_evidence_families=None,rationale=None))


def optional_text(value,path,missing):
    if value is None:missing.append(path)
    else:identity(value,path)


def families(value,path,missing):
    if value is None:missing.append(path);return None
    if type(value) is not list or any(type(v) is not str or v not in FAMILIES for v in value) or len(set(value))!=len(value):
        raise ValueError('Known unique evidence families required: '+path)
    return set(value)


def validate_criteria(criteria,packet):
    fields_only(criteria,criteria_template(packet))
    template=criteria_template(packet)
    for key in ('version','record_role','source_audit_sha256','campaign_manifest_sha256','measurand','cohort'):
        if criteria[key]!=template[key]:raise ValueError('Stale or unsupported criteria scope: '+key)
    fields_only(criteria['scientific_limits'],SPEC);missing=[]
    for key,(kind,unit) in SPEC.items():
        row=criteria['scientific_limits'][key];fields_only(row,{'value','unit','definition','rationale'})
        if row['unit']!=unit:raise ValueError('Explicit criterion unit differs: '+key)
        for name in ('definition','rationale'):optional_text(row[name],key+'.'+name,missing)
        value=row['value']
        if value is None:missing.append(key+'.value');continue
        if kind=='text':identity(value,key)
        else:
            if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite numeric criterion required: '+key)
            if kind=='integer' and (type(value) is not int or value<1):raise ValueError('Positive integer criterion required')
            if kind=='number' and value<=0:raise ValueError('Positive precision/duration criterion required')
            if kind=='nonnegative' and value<0:raise ValueError('Nonnegative criterion required')
            if kind=='fraction' and not 0<=value<=1:raise ValueError('Fraction outside [0,1]')
            if kind=='probability' and not 0<value<1:raise ValueError('Confidence probability outside (0,1)')
    provenance=criteria['decision_provenance'];fields_only(provenance,template['decision_provenance'])
    for key in ('author','rationale','decided_at_utc'):optional_text(provenance[key],'decision_provenance.'+key,missing)
    if provenance['decided_at_utc'] is not None:
        if not provenance['decided_at_utc'].endswith('Z'):raise ValueError('UTC decision declaration must end in Z')
        parsed=datetime.fromisoformat(provenance['decided_at_utc'].replace('Z','+00:00'))
        if parsed.utcoffset()!=timezone.utc.utcoffset(parsed):raise ValueError('UTC decision declaration required')
    if provenance['development_data_informed'] is None:missing.append('decision_provenance.development_data_informed')
    elif type(provenance['development_data_informed']) is not bool:raise ValueError('Actual development-data declaration required')
    if provenance['confirmation_scope']!='future_disjoint_collection_only':raise ValueError('Existing development data cannot become held-out confirmation')
    separation=criteria['evidence_separation'];fields_only(separation,template['evidence_separation'])
    inputs=families(separation['classifier_evidence_families'],'classifier_evidence_families',missing)
    references=families(separation['reference_evidence_families'],'reference_evidence_families',missing)
    optional_text(separation['rationale'],'evidence_separation.rationale',missing)
    if inputs is not None and references is not None and inputs&references:raise ValueError('Classifier and independent-reference evidence families overlap')
    if references is not None and not any(FAMILIES[v] in INDEPENDENT_CHANNELS for v in references):
        raise ValueError('Independent non-intervention reference channel required')
    return dict(version=VERSION,criteria_sha256=digest(criteria),structure_complete=not missing,
        status='blocked_incomplete_criteria' if missing else 'complete_declarations_only_not_scientific_acceptance',
        missing_fields=missing,development_data_informed=provenance['development_data_informed'],
        scientific_adequacy_verified=False,decision_provenance_authenticated=False,existing_development_data_confirmed=False,
        reference_export_enabled=False,references_created=0,references_locked=0,calibration_enabled=False,study_ready=False)


def review_template(packet,criteria):
    return dict(version=VERSION,record_role='evaluator_only_gap_worksheet_not_reference',
        packet_sha256=digest(packet),criteria_sha256=digest(criteria),assessor_id=None,
        blinded_to_predictions_and_policy=None,blinding_scope_statement=None,independence_statement=None,limitations=[],
        cases=[dict(case_id=c['case_id'],outcome=None,reviewed_artifacts=[],**{key:None for key in REVIEW_FIELDS}) for c in packet['cases']])


def validate_review(review,packet,criteria):
    template=review_template(packet,criteria);fields_only(review,template)
    for key in ('version','record_role','packet_sha256','criteria_sha256'):
        if review[key]!=template[key]:raise ValueError('Stale or unsupported worksheet: '+key)
    gate=validate_criteria(criteria,packet);missing=[]
    for key in ('assessor_id','blinding_scope_statement','independence_statement'):optional_text(review[key],key,missing)
    if review['blinded_to_predictions_and_policy'] is None:missing.append('blinded_to_predictions_and_policy')
    elif type(review['blinded_to_predictions_and_policy']) is not bool:raise ValueError('Actual blinding boolean required')
    if type(review['limitations']) is not list:raise ValueError('Limitations must be a list')
    if not review['limitations']:missing.append('limitations')
    for value in review['limitations']:identity(value,'limitation')
    if type(review['cases']) is not list:raise ValueError('Worksheet cases must be a list')
    wanted={c['case_id']:c for c in packet['cases']};seen=set()
    for row in review['cases']:
        fields_only(row,{'case_id','outcome','reviewed_artifacts',*REVIEW_FIELDS})
        case_id=row['case_id']
        identity(case_id,'worksheet case identity')
        if case_id not in wanted or case_id in seen:raise ValueError('Unknown or repeated worksheet case')
        seen.add(case_id)
        if row['outcome'] is None:missing.append(case_id+'.outcome')
        elif row['outcome'] not in ('unresolved','needs_more_evidence'):raise ValueError('Gap worksheets cannot assert supported/healthy cause labels')
        for key in REVIEW_FIELDS:optional_text(row[key],case_id+'.'+key,missing)
        links=row['reviewed_artifacts']
        if type(links) is not list:raise ValueError('Reviewed artifacts must be a list')
        if not links:missing.append(case_id+'.reviewed_artifacts')
        linked=set()
        for link in links:
            fields_only(link,{'artifact_id','purpose'});aid=link['artifact_id']
            identity(aid,'reviewed artifact identity')
            if aid not in wanted[case_id]['allowed_artifact_ids'] or aid in linked:raise ValueError('Wrong-scope, unknown or repeated artifact')
            linked.add(aid)
            if link['purpose'] not in ('context','limitation','candidate_reference'):raise ValueError('Unknown artifact use')
            record=packet['catalog'][aid];ReferenceArtifact.from_dict(record['artifact'])
            if link['purpose']=='candidate_reference':
                separation=criteria['evidence_separation'];family=record['family']
                if family not in (separation['reference_evidence_families'] or []) or family in (separation['classifier_evidence_families'] or []):
                    raise ValueError('Candidate reference conflicts with declared evidence separation')
                if FAMILIES.get(family) not in INDEPENDENT_CHANNELS:raise ValueError('Context record is not independent reference evidence')
    if seen!=set(wanted):raise ValueError('Exactly one worksheet row per packet case required')
    return dict(version=VERSION,review_sha256=digest(review),criteria_sha256=digest(criteria),
        review_structure_complete=not missing,criteria_structure_complete=gate['structure_complete'],missing_fields=missing,
        status='gap_review_structure_complete_not_adjudication' if not missing and gate['structure_complete'] else 'blocked_missing_criteria_or_assessor_input',
        assessor_identity_authenticated=False,actual_blinding_verified=False,causal_reference_validated=False,
        references_created=0,references_locked=0,reference_export_enabled=False,calibration_enabled=False,study_ready=False)
