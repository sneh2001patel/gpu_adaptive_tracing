"""Evaluator-only adjudicated references. Never imported by the classifier.

Validation checks structure/provenance declarations, not scientific truth or
whether an assessor actually remained blinded. A schedule is not a reference.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from revision.tracing.measured_evidence import Acquisition, fields_only, identity, integer, PROVENANCES

CAUSES = frozenset({'queue_pressure', 'prefill_dominated_service'})
CHANNELS = frozenset({'server_diagnostics', 'request_diagnostics', 'matched_full_trace', 'intervention_log'})
INDEPENDENT_CHANNELS = CHANNELS - {'intervention_log'}


def strings(values, name):
    if type(values) is not tuple:
        raise ValueError(f'{name} must be a tuple of unique strings')
    for value in values:
        identity(value, name)
    if len(values) != len(set(values)):
        raise ValueError(f'{name} must be unique')


@dataclass(frozen=True)
class ReferenceArtifact:
    artifact_id: str
    path: str
    sha256: str
    channel: str
    acquisition: Acquisition

    def __post_init__(self):
        identity(self.artifact_id, 'artifact_id')
        identity(self.path, 'artifact path')
        if Path(self.path).is_absolute() or '..' in Path(self.path).parts:
            raise ValueError('Artifact path must be relative without parent traversal')
        if not isinstance(self.sha256, str) or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise ValueError('Artifact needs a lowercase SHA-256 identity')
        if self.channel not in CHANNELS or type(self.acquisition) is not Acquisition:
            raise ValueError('Unsupported reference channel or acquisition')

    @classmethod
    def from_dict(cls, data):
        fields_only(data, cls.__dataclass_fields__)
        return cls(**(data | {'acquisition': Acquisition.from_dict(data['acquisition'])}))

    def verify_content(self, root):
        root=Path(root).resolve();target=(root/self.path).resolve()
        if not target.is_relative_to(root):
            raise ValueError('Artifact symlink escapes the artifact root')
        if hashlib.sha256(target.read_bytes()).hexdigest() != self.sha256:
            raise ValueError('Reference artifact hash mismatch')


@dataclass(frozen=True)
class ReferenceCriterion:
    criterion_id: str
    cause: str | None
    passed: bool
    artifact_ids: tuple[str, ...]
    rationale: str

    def __post_init__(self):
        identity(self.criterion_id, 'criterion_id');identity(self.rationale, 'rationale')
        if self.cause is not None and self.cause not in CAUSES or type(self.passed) is not bool:
            raise ValueError('Unknown cause or nonboolean criterion outcome')
        strings(self.artifact_ids, 'artifact_ids')
        if not self.artifact_ids:
            raise ValueError('Criteria require linked evidence')

    @classmethod
    def from_dict(cls, data):
        fields_only(data, cls.__dataclass_fields__)
        if type(data['artifact_ids']) is not list:
            raise ValueError('artifact_ids must be a JSON list')
        return cls(**(data | {'artifact_ids': tuple(data['artifact_ids'])}))


@dataclass(frozen=True)
class ReferenceRecord:
    record_role: str
    run_id: str
    reference_version: str
    provenance: str
    interval: Acquisition
    status: str
    supported_causes: tuple[str, ...]
    contradicted_causes: tuple[str, ...]
    cause_set_complete: bool
    criteria: tuple[ReferenceCriterion, ...]
    artifacts: tuple[ReferenceArtifact, ...]
    alternatives: tuple[str, ...]
    matched_reference_run_id: str | None
    reference_run_mismatch: str | None
    assessor_ids: tuple[str, ...]
    blinded_to_predictions_and_policy: bool
    adjudicated_at_ns: int
    locked_at_ns: int | None
    limitations: tuple[str, ...]

    def __post_init__(self):
        if self.record_role != 'adjudicated_reference':
            raise ValueError('Template/injection records cannot be scored as references')
        identity(self.run_id, 'run_id');identity(self.reference_version, 'reference_version')
        if self.provenance not in PROVENANCES or type(self.interval) is not Acquisition:
            raise ValueError('Explicit provenance and typed interval required')
        if self.status not in ('supported', 'healthy', 'unresolved'):
            raise ValueError('Unsupported reference status')
        for name in ('supported_causes', 'contradicted_causes', 'alternatives', 'assessor_ids', 'limitations'):
            strings(getattr(self, name), name)
        if self.matched_reference_run_id is not None:
            identity(self.matched_reference_run_id, 'matched_reference_run_id')
            if self.matched_reference_run_id == self.run_id:
                raise ValueError('Matched full trace must identify a separate run')
            identity(self.reference_run_mismatch, 'reference_run_mismatch assessment')
        elif self.reference_run_mismatch is not None:
            raise ValueError('Mismatch assessment requires a matched reference run')
        if not self.assessor_ids:
            raise ValueError('An assessor identity is required, including single-author adjudication')
        if not set(self.supported_causes + self.contradicted_causes) <= CAUSES:
            raise ValueError('Unknown reference cause')
        if set(self.supported_causes) & set(self.contradicted_causes):
            raise ValueError('A cause cannot be both supported and contradicted')
        if type(self.cause_set_complete) is not bool or type(self.blinded_to_predictions_and_policy) is not bool:
            raise ValueError('Completeness/blinding must be explicit booleans')
        if self.status == 'supported' and not self.supported_causes:
            raise ValueError('Supported references need a supported cause')
        if self.status != 'supported' and self.supported_causes:
            raise ValueError('Only supported records may assert active causes')
        if self.status == 'unresolved' and self.cause_set_complete:
            raise ValueError('Unresolved reference cannot claim complete cause coverage')
        if self.status == 'healthy' and not self.cause_set_complete:
            raise ValueError('Healthy reference requires an explicit complete negative adjudication')
        if type(self.artifacts) is not tuple or any(type(a) is not ReferenceArtifact for a in self.artifacts):
            raise ValueError('Typed immutable artifacts required')
        if type(self.criteria) is not tuple or any(type(c) is not ReferenceCriterion for c in self.criteria):
            raise ValueError('Typed immutable criteria required')
        by_id={a.artifact_id:a for a in self.artifacts}
        if len(by_id) != len(self.artifacts) or len({c.criterion_id for c in self.criteria}) != len(self.criteria):
            raise ValueError('Duplicate artifact or criterion identity')
        integer(self.adjudicated_at_ns, 'adjudicated_at_ns')
        if self.adjudicated_at_ns < self.interval.available_at_ns:
            raise ValueError('Adjudication precedes interval availability')
        for artifact in self.artifacts:
            artifact.acquisition.require_visible(self.adjudicated_at_ns, self.interval.clock_domain)
        if any(a.channel == 'matched_full_trace' for a in self.artifacts) and self.matched_reference_run_id is None:
            raise ValueError('Matched trace evidence needs a separate run and mismatch assessment')
        if self.locked_at_ns is not None:
            integer(self.locked_at_ns, 'locked_at_ns')
            if self.locked_at_ns < self.adjudicated_at_ns:
                raise ValueError('Lock precedes adjudication')
        for criterion in self.criteria:
            if not set(criterion.artifact_ids) <= set(by_id):
                raise ValueError('Criterion links an unknown artifact')
        targets=[(cause,True) for cause in self.supported_causes]+[(cause,False) for cause in self.contradicted_causes]
        if self.status == 'healthy':targets.append((None,True))
        for cause,passed in targets:
            linked={identifier for c in self.criteria if c.cause == cause and c.passed == passed for identifier in c.artifact_ids}
            channels={by_id[i].channel for i in linked} & INDEPENDENT_CHANNELS
            if len(channels) < 2:
                raise ValueError('Cause/healthy assertions need two corroborating channels beyond the intervention log')
        if (not self.blinded_to_predictions_and_policy or len(self.assessor_ids) < 2) and not self.limitations:
            raise ValueError('Single-assessor or unblinded reference needs recorded limitations')

    @classmethod
    def from_dict(cls, data):
        fields_only(data, cls.__dataclass_fields__)
        values=dict(data)
        for key in ('supported_causes','contradicted_causes','alternatives','assessor_ids','limitations','criteria','artifacts'):
            if type(values[key]) is not list:
                raise ValueError(f'{key} must be a JSON list')
            values[key]=tuple(values[key])
        values['interval']=Acquisition.from_dict(values['interval'])
        values['criteria']=tuple(ReferenceCriterion.from_dict(c) for c in values['criteria'])
        values['artifacts']=tuple(ReferenceArtifact.from_dict(a) for a in values['artifacts'])
        return cls(**values)

    def require_joinable(self, *, run_id, provenance, join_at_ns, clock_domain):
        self.interval.require_visible(join_at_ns, clock_domain)
        if self.run_id != run_id or self.provenance != provenance:
            raise ValueError('Cross-run or cross-provenance reference join')
        if self.locked_at_ns is None or self.locked_at_ns > join_at_ns:
            raise ValueError('Reference must be locked before prediction join')
