"""Incremental stopping rules shared by replay and the future live controller.

Callers supply only evidence available at the decision point. Capture IDs count
attempts (including failed attempts); diagnosis evidence IDs identify fresh
observations, not cached labels. No expected labels enter the policy engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace


POLICY_VERSION = "stopping_v3"
POLICIES = (
    "fixed_burst", "repeated_fixed_burst", "stability_stop",
    "counter_recovery_stop", "hybrid_stop",
)
CONCRETE_LABELS = frozenset({
    "compute_bound", "launch_overhead_or_small_kernel", "mixed",
    "vllm_queue_pressure", "vllm_long_prompt", "vllm_long_output",
    "vllm_compute_saturation", "vllm_kv_cache_pressure",
})


# Study rule (rule_diagnosis.py) labels: '+'-joined causes; healthy/unknown are never concrete.
STUDY_RULE_CAUSES = frozenset({"queue_pressure", "kv_pressure", "host_bound"})


def is_concrete_label(label: str | None) -> bool:
    if label in CONCRETE_LABELS:
        return True
    if not label:
        return False
    return all(part in STUDY_RULE_CAUSES or (part.startswith("kernel_hotspot:") and len(part) > 15)
               for part in label.split("+"))


def advance_stability(previous: str | None, streak: int, label: str | None,
                      *, fresh: bool) -> tuple[str | None, int]:
    if not fresh or not is_concrete_label(label):
        return None, 0
    return label, streak + 1 if previous == label else 1


@dataclass(frozen=True)
class PolicyConfig:
    stability_windows: int = 2
    repeated_bursts: int = 3
    max_bursts: int = 6
    recovery_windows: int = 2
    recovery_latency_ratio: float = 1.10
    recovery_gpu_util: float = 60.0

    def __post_init__(self):
        for name in ("stability_windows", "repeated_bursts", "max_bursts", "recovery_windows"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.stability_windows < 2:
            raise ValueError("stability_windows must be at least 2")
        if not math.isfinite(self.recovery_latency_ratio) or self.recovery_latency_ratio <= 0:
            raise ValueError("recovery_latency_ratio must be positive and finite")
        if not math.isfinite(self.recovery_gpu_util) or not 0 <= self.recovery_gpu_util <= 100:
            raise ValueError("recovery_gpu_util must be between 0 and 100")


def canonical_policy(policy: str, config: PolicyConfig) -> tuple[str, PolicyConfig]:
    if policy == "marginal_utility_stop":
        return "stability_stop", replace(config, stability_windows=2)
    if policy not in POLICIES:
        raise ValueError(f"Unsupported policy: {policy}")
    return policy, config


@dataclass(frozen=True)
class PolicyEvidence:
    window_id: str
    diagnosis_label: str | None = None
    capture_id: str | None = None
    diagnosis_evidence_id: str | None = None
    latency_ratio: float | None = None
    gpu_util: float | None = None
    suspicious: bool | None = None
    recovery_evidence_id: str | None = None


def recovery_observed(evidence: PolicyEvidence, config: PolicyConfig) -> bool:
    latency, gpu = evidence.latency_ratio, evidence.gpu_util
    return (
        evidence.suspicious is False
        and latency is not None and math.isfinite(latency) and 0 < latency <= config.recovery_latency_ratio
        and gpu is not None and math.isfinite(gpu) and 0 <= gpu <= config.recovery_gpu_util
    )


@dataclass(frozen=True)
class PolicyDecision:
    stop: bool
    reason: str
    policy: str
    bursts: int
    diagnosis_streak: int
    recovery_streak: int
    diagnosis_label: str | None
    policy_condition_met: bool = False


class StoppingPolicy:
    """One episode; terminal decisions are sticky and never consume more budget."""

    def __init__(self, policy: str, config: PolicyConfig):
        self.policy, self.config = canonical_policy(policy, config)
        self.capture_ids: set[str] = set()
        self.window_ids: set[str] = set()
        self.evidence_ids: set[str] = set()
        self.recovery_ids: set[str] = set()
        self.previous: str | None = None
        self.diagnosis_streak = 0
        self.recovery_streak = 0
        self.label: str | None = None
        self.terminal: PolicyDecision | None = None

    @property
    def can_capture(self) -> bool:
        return self.terminal is None and len(self.capture_ids) < self.config.max_bursts

    def _decision(self, reason: str, *, stop: bool = True, met: bool = False) -> PolicyDecision:
        decision = PolicyDecision(stop, reason, self.policy, len(self.capture_ids),
                                  self.diagnosis_streak, self.recovery_streak, self.label, met)
        if stop:
            self.terminal = decision
        return decision

    def observe_recovery(self, evidence: PolicyEvidence) -> None:
        """Consume chronological cheap windows without inventing new diagnoses.

        A capture decision may reuse the latest cheap window; charge its recovery
        contribution once. Background cheap windows must all be delivered so a
        non-recovered gap cannot disappear between capture decisions.
        """
        if self.terminal is not None:
            return
        identity = evidence.recovery_evidence_id or evidence.window_id
        if identity in self.recovery_ids:
            return
        self.recovery_ids.add(identity)
        self.recovery_streak = self.recovery_streak + 1 if recovery_observed(evidence, self.config) else 0

    def observe(self, evidence: PolicyEvidence) -> PolicyDecision:
        if self.terminal is not None:
            return self.terminal
        if evidence.window_id in self.window_ids:
            raise ValueError("A decision window may only be observed once")
        self.window_ids.add(evidence.window_id)
        if evidence.capture_id:
            self.capture_ids.add(evidence.capture_id)
        fresh = bool(evidence.diagnosis_evidence_id and evidence.diagnosis_evidence_id not in self.evidence_ids)
        if evidence.diagnosis_evidence_id:
            self.evidence_ids.add(evidence.diagnosis_evidence_id)
        self.label = evidence.diagnosis_label
        self.previous, self.diagnosis_streak = advance_stability(
            self.previous, self.diagnosis_streak, self.label, fresh=fresh,
        )
        self.observe_recovery(evidence)
        bursts = len(self.capture_ids)
        stable = self.diagnosis_streak >= self.config.stability_windows
        recovered = self.recovery_streak >= self.config.recovery_windows
        # A genuine condition reached on the final allowed burst takes priority
        # over exhaustion. No policy can consume an additional burst afterward.
        if bursts:
            if self.policy == "fixed_burst":
                return self._decision("fixed_burst_complete", met=True)
            if self.policy == "repeated_fixed_burst" and bursts >= self.config.repeated_bursts:
                return self._decision("repeated_bursts_complete", met=True)
            if self.policy == "stability_stop" and stable:
                return self._decision("diagnosis_stable", met=True)
            if self.policy == "counter_recovery_stop" and recovered:
                return self._decision("counters_recovered", met=True)
            if self.policy == "hybrid_stop" and stable and recovered:
                return self._decision("stable_and_recovered", met=True)
        if bursts >= self.config.max_bursts:
            return self._decision("budget_exhausted")
        return self._decision("continue", stop=False)

    def finish(self) -> PolicyDecision:
        return self.terminal or self._decision("horizon_ended")
