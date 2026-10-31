"""Offline initial-stop scoring against verified locked reference intervals.

Never imported by the controller/classifier. Scores explicit cause assertions;
no scenario-to-label mapping, fitted classification or operator benefit inferred.
"""
from dataclasses import dataclass
import json
from pathlib import Path

from experiments.evaluation.references import CAUSES, strings
from experiments.evaluation.reference_store import ReferenceStore, sha, read_regular
from experiments.tracing.arrival_schedule import unique_object
from experiments.tracing.measured_evidence import Acquisition, fields_only, identity, integer, PROVENANCES
from experiments.tracing.policies import POLICIES, is_concrete_label

REASONS={'fixed_burst_complete','repeated_bursts_complete','diagnosis_stable','counters_recovered',
         'stable_and_recovered','budget_exhausted','horizon_ended','capture_failed','diagnosis_failed','timeout'}
STABLE={'diagnosis_stable','stable_and_recovered'}
STATUSES={'ok','capture_failed','diagnosis_failed','timeout','horizon_censored'}
OUTCOMES=('supported_complete','supported_partial','unsupported_concrete','unresolved','reference_unavailable')


@dataclass(frozen=True)
class InitialStopPrediction:
    record_kind: str
    prediction_id: str
    run_id: str
    episode_id: str
    policy: str
    provenance: str
    evidence_interval: Acquisition | None
    decision_at_ns: int
    evidence_id: str | None
    policy_label: str | None
    cause_set: tuple[str,...]
    classifier_version: str
    mapping_version: str
    terminal_reason: str
    decision_status: str

    def __post_init__(self):
        if self.record_kind!='initial_episode_stop':raise ValueError('Score one explicit initial stop per activated episode')
        for key in ('prediction_id','run_id','episode_id','classifier_version','mapping_version'):identity(getattr(self,key),key)
        if self.policy not in POLICIES or self.provenance not in PROVENANCES:
            raise ValueError('Unsupported policy/provenance')
        if self.evidence_interval is not None and type(self.evidence_interval) is not Acquisition:raise ValueError('Typed evidence interval or explicit absence required')
        integer(self.decision_at_ns,'decision_at_ns')
        if self.evidence_interval is not None:self.evidence_interval.require_visible(self.decision_at_ns,self.evidence_interval.clock_domain)
        elif self.evidence_id is not None or self.policy_label is not None or self.cause_set:raise ValueError('Diagnosis assertions require an acquisition interval')
        strings(self.cause_set,'cause_set')
        if not set(self.cause_set)<=CAUSES:raise ValueError('Cause outside the adjudicated target vocabulary')
        if self.policy_label is not None and not is_concrete_label(self.policy_label):raise ValueError('Unsupported concrete policy label')
        if self.evidence_id is not None:identity(self.evidence_id,'evidence_id')
        if self.terminal_reason not in REASONS or self.decision_status not in STATUSES:raise ValueError('Unknown stop/failure category')
        if self.cause_set and (self.policy_label is None or self.evidence_id is None):raise ValueError('Cause assertions require an explicit concrete diagnosis/evidence ID')
        if self.decision_status!='ok' and (self.cause_set or self.policy_label is not None):raise ValueError('Failed/censored decisions cannot assert a diagnosis')
        failures={'capture_failed':'capture_failed','diagnosis_failed':'diagnosis_failed','timeout':'timeout','horizon_censored':'horizon_ended'}
        if self.decision_status in failures and self.terminal_reason not in {failures[self.decision_status],'budget_exhausted','fixed_burst_complete','repeated_bursts_complete','counters_recovered'}:raise ValueError('Failure status/reason mismatch')
        if self.decision_status=='ok' and self.terminal_reason in {'capture_failed','diagnosis_failed','timeout'}:
            raise ValueError('Failure stop cannot masquerade as successful evidence')
        if self.terminal_reason in STABLE and (not is_concrete_label(self.policy_label) or self.evidence_id is None):
            raise ValueError('Unknown/missing evidence cannot establish a stability stop')

    @classmethod
    def from_dict(cls,data):
        fields_only(data,cls.__dataclass_fields__)
        if type(data['cause_set']) is not list:raise ValueError('Cause set must be a JSON list')
        return cls(**(data|dict(cause_set=tuple(data['cause_set']),evidence_interval=None if data['evidence_interval'] is None else Acquisition.from_dict(data['evidence_interval']))))


def activation_cohort(raw,locked):
    """Cross-check episode list against episode-start events in a run wrapper.

    Completeness is relative to this hashed controller snapshot, not proof that
    detection found all actual incidents. No missing stop can silently disappear.
    """
    wrapper=json.loads(raw,object_pairs_hook=unique_object)
    fields_only(wrapper,{'run_id','controller'})
    if wrapper['run_id']!=locked.run_id:raise ValueError('Activation snapshot belongs to another run')
    controller=wrapper['controller']
    if type(controller) is not dict or controller.get('evidence_mode')!=locked.provenance or controller.get('clock_domain')!=locked.clock_domain:
        raise ValueError('Activation snapshot provenance/domain differs from reference lock')
    if type(controller.get('episodes')) is not list or type(controller.get('events')) is not list:
        raise ValueError('Controller episodes/events required')
    episodes=[]
    for episode in controller['episodes']:
        identity(episode.get('episode_id'),'episode_id');episodes.append(episode['episode_id'])
    starts={}
    for event in controller['events']:
        if event.get('event')!='episode_started':continue
        identifier=event.get('episode_id');identity(identifier,'activation episode_id')
        integer(event.get('timestamp_ns'),'activation timestamp')
        if event.get('clock_domain')!=locked.clock_domain or event.get('provenance')!=locked.provenance:
            raise ValueError('Foreign activation event')
        if identifier in starts:raise ValueError('Duplicate episode-start event')
        starts[identifier]=event['timestamp_ns']
    if len(episodes)!=len(set(episodes)) or set(episodes)!=set(starts):raise ValueError('Activation episodes and start events disagree')
    return starts


def classify_agreement(prediction,records):
    interval=prediction.evidence_interval
    if interval is None:
        return dict(reference_status='no_acquired_evidence',supported_causes_covered=[],supported_causes_omitted=[],unsupported_causes=[],reference_cause_set_complete=None,diagnosis_outcome='reference_unavailable')
    matches=[r for r in records if r.interval.start_ns<=interval.start_ns and interval.end_ns<=r.interval.end_ns]
    overlaps=[r for r in records if r.interval.start_ns<interval.end_ns and interval.start_ns<r.interval.end_ns]
    base=dict(reference_status=None,supported_causes_covered=[],supported_causes_omitted=[],unsupported_causes=[],
              reference_cause_set_complete=None)
    if len(matches)!=1:
        reason='reference_transition' if len(overlaps)>1 else ('reference_gap' if overlaps else 'no_reference_interval')
        return base|dict(diagnosis_outcome='reference_unavailable',reference_status=reason)
    record=matches[0];supported=set(record.supported_causes);predicted=set(prediction.cause_set)
    base.update(reference_status=record.status,reference_cause_set_complete=record.cause_set_complete,
        supported_causes_covered=sorted(predicted&supported),supported_causes_omitted=sorted(supported-predicted))
    if record.status=='unresolved':return base|dict(diagnosis_outcome='reference_unavailable',reference_status='unresolved_reference')
    if not predicted:return base|dict(diagnosis_outcome='unresolved')
    unsupported=predicted&set(record.contradicted_causes)
    if record.cause_set_complete:unsupported|=predicted-supported
    if unsupported:return base|dict(diagnosis_outcome='unsupported_concrete',unsupported_causes=sorted(unsupported))
    if predicted-supported:return base|dict(diagnosis_outcome='reference_unavailable',reference_status='incomplete_reference_for_asserted_cause')
    outcome='supported_complete' if record.cause_set_complete and predicted==supported else 'supported_partial'
    return base|dict(diagnosis_outcome=outcome)


def evaluate(store,anchor,prediction_bytes,activation_bytes,*,clock):
    if type(store) is not ReferenceStore:raise ValueError('Verified reference store required')
    # Re-read and verify the lock chain before decoding any prediction input.
    locked=store.load(anchor)
    now=clock.now_ns();integer(now,'join_at_ns')
    if clock.domain!=locked.clock_domain or now<locked.locked_at_ns:raise ValueError('Join precedes lock or uses an unmapped clock')
    for record in locked.records:record.require_joinable(run_id=locked.run_id,provenance=locked.provenance,join_at_ns=now,clock_domain=clock.domain)
    cohort=activation_cohort(activation_bytes,locked)
    data=json.loads(prediction_bytes,object_pairs_hook=unique_object)
    if type(data) is not list:raise ValueError('Prediction file must be a JSON list')
    predictions=[InitialStopPrediction.from_dict(row) for row in data]
    if len({p.prediction_id for p in predictions})!=len(predictions):raise ValueError('Duplicate prediction ID')
    if len({p.episode_id for p in predictions})!=len(predictions) or {p.episode_id for p in predictions}!=set(cohort):
        raise ValueError('Every activated episode needs exactly one initial-stop record, including failures/unresolved stops')
    rows=[]
    for p in predictions:
        if (p.run_id,p.provenance)!=(locked.run_id,locked.provenance) or (p.evidence_interval is not None and p.evidence_interval.clock_domain!=locked.clock_domain):
            raise ValueError('Cross-run/provenance/domain prediction join')
        if p.decision_at_ns<cohort[p.episode_id] or p.decision_at_ns>now:raise ValueError('Decision precedes activation or is not yet available at join')
        agreement=classify_agreement(p,locked.records);outcome=agreement['diagnosis_outcome']
        rows.append(dict(prediction_id=p.prediction_id,episode_id=p.episode_id,policy=p.policy,
            terminal_reason=p.terminal_reason,decision_status=p.decision_status,policy_label=p.policy_label,
            asserted_causes=list(p.cause_set),classifier_version=p.classifier_version,mapping_version=p.mapping_version,
            label_unknown=p.policy_label is None,abstained=p.decision_status=='ok' and not p.cause_set,
            unmapped_concrete_label=p.policy_label is not None and not p.cause_set,
            evidence_ready_at_ns=None if p.evidence_interval is None else p.evidence_interval.available_at_ns,decision_at_ns=p.decision_at_ns,
            stable_unsupported=p.terminal_reason in STABLE and outcome=='unsupported_concrete',
            stable_incomplete=p.terminal_reason in STABLE and outcome=='supported_partial',
            stable_unadjudicable=p.terminal_reason in STABLE and outcome=='reference_unavailable',**agreement))
    outcomes={name:sum(r['diagnosis_outcome']==name for r in rows) for name in OUTCOMES}
    terminal={reason:sum(r['terminal_reason']==reason for r in rows) for reason in sorted(REASONS)}
    adjudicable=len(rows)-outcomes['reference_unavailable']
    return dict(version='locked_initial_stop_scoring_v2',run_id=locked.run_id,provenance=locked.provenance,
        reference_lock_sha256=anchor,prediction_file_sha256=sha(prediction_bytes),activation_file_sha256=sha(activation_bytes),
        scorer_sha256=sha(Path(__file__).read_bytes()),
        join_at_ns=now,clock_domain=clock.domain,initial_stop_rows=rows,
        denominators=dict(all_logged_activated_episodes=len(cohort),all_initial_stops=len(rows),
            reference_adjudicable_stops=adjudicable,reference_unavailable_stops=outcomes['reference_unavailable']),
        outcomes=outcomes,terminal_reasons=terminal,
        decision_statuses={s:sum(r['decision_status']==s for r in rows) for s in sorted(STATUSES)},
        abstentions=sum(r['abstained'] for r in rows),unmapped_concrete_labels=sum(r['unmapped_concrete_label'] for r in rows),
        stable_unsupported=sum(r['stable_unsupported'] for r in rows),stable_incomplete=sum(r['stable_incomplete'] for r in rows),
        stable_unadjudicable=sum(r['stable_unadjudicable'] for r in rows),
        complete_agreement_fraction_all=outcomes['supported_complete']/len(rows) if rows else None,
        complete_agreement_fraction_adjudicable=outcomes['supported_complete']/adjudicable if adjudicable else None,
        note='Offline agreement with locked adjudications; not proof of causal truth, blinding, detection recall, stopping safety or operator benefit. Explicit cause assertions do not calibrate a classifier or validate its policy-label mapping.')


def evaluate_files(store,anchor,predictions_path,activation_path,*,clock):
    # Enforce verified lock existence/integrity before opening prediction files.
    store.load(anchor)
    return evaluate(store,anchor,read_regular(predictions_path),read_regular(activation_path),clock=clock)
