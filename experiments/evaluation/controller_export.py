"""Offline export from controller snapshots; no references or cause inference.

Acquisition intervals come from measured observations, never process wall time.
Later reactivations cannot overwrite the first stop. Open episodes fail export.
"""
from dataclasses import asdict
import copy
from experiments.evaluation.scoring import InitialStopPrediction, activation_cohort
from experiments.tracing.measured_evidence import MeasuredObservation, identity, PROVENANCES
from experiments.tracing.arrival_schedule import canonical


def export_initial_stops(run_id,snapshot,observations,*,classifier_version):
    identity(run_id,'run_id');identity(classifier_version,'classifier_version')
    snapshot=copy.deepcopy(snapshot)
    if snapshot.get('finished') is not True:raise ValueError('Offline export requires a finished controller snapshot')
    if snapshot.get('evidence_mode') not in PROVENANCES:raise ValueError('Explicit controller provenance required')
    # Same activation consistency gate as scoring, without loading any reference.
    class Cohort:
        pass
    cohort=Cohort();cohort.run_id=run_id;cohort.provenance=snapshot['evidence_mode'];cohort.clock_domain=snapshot['clock_domain']
    wrapper=dict(run_id=run_id,controller=snapshot)
    starts=activation_cohort(canonical(wrapper),cohort)
    rows=[];audit=[]
    for episode in snapshot['episodes']:
        eid=episode['episode_id'];decisions=episode['decisions']
        if episode['started_at_ns']!=starts[eid]:raise ValueError('Activation timestamp mismatch')
        selected=next((d for d in decisions if d['decision']['stop']),None)
        interval=evidence_id=label=None
        if selected is not None:
            reason=selected['decision']['reason'];status=selected['status'];when=selected['decision_ready_at_ns']
            if selected['provenance']!=cohort.provenance or selected['clock_domain']!=cohort.clock_domain:raise ValueError('Foreign decision')
            cancels=[e for e in snapshot['events'] if e.get('event')=='capture_cancelled' and e.get('capture_id')==selected['capture_id'] and e['timestamp_ns']<=when]
            if cancels:
                cancellation=cancels[-1]['reason']
                if cancellation=='horizon_ended':status='horizon_censored'
                elif cancellation in ('startup_timeout','evidence_timeout'):status='timeout'
            if status=='ok':
                evidence_id=selected['evidence_id'];label=selected['decision']['diagnosis_label']
                observation=observations.get(evidence_id)
                if type(observation) is not MeasuredObservation or observation.kernel is None:raise ValueError('Ready decisions require their measured observation, not inferred timing')
                kernel=observation.kernel
                if (kernel.evidence_id,kernel.capture_id,observation.provenance,observation.acquisition.clock_domain)!=(evidence_id,selected['capture_id'],cohort.provenance,cohort.clock_domain):raise ValueError('Observation identity/provenance/domain mismatch')
                if kernel.acquisition.available_at_ns!=selected['evidence_ready_at_ns']:raise ValueError('Readiness mismatch')
                observation.require_visible(when,cohort.clock_domain);interval=observation.acquisition
        else:
            if episode.get('ended_at_ns') is None or episode.get('end_reason')!='horizon_ended':raise ValueError('Episode has no initial stop or terminal horizon')
            when=episode['ended_at_ns'];reason='horizon_ended';status='horizon_censored'
        row=InitialStopPrediction('initial_episode_stop',run_id+':'+eid+':initial-stop',run_id,eid,
            snapshot['config']['policy'],cohort.provenance,interval,when,evidence_id,label,(),
            classifier_version,'unmapped_no_cause_assertions_v1',reason,status)
        if when<episode['started_at_ns']:raise ValueError('Decision precedes activation')
        rows.append(asdict(row)|dict(cause_set=[]));audit.append(dict(episode_id=eid,source_stop_reason=reason,
            source_decision_status=None if selected is None else selected['status'],export_status=status,
            source_capture_id=None if selected is None else selected['capture_id']))
    return dict(predictions=rows,controller_snapshot=wrapper,export_audit=audit,
                note='No cause mapping or references used. Absent acquisition stays null; first stops only.')
