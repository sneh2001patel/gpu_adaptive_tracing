"""Decision logic for one serving session (EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §3; proposal §5).

Pure logic, no I/O: the runner delivers one cheap window per tick and the result of each heavy burst, and this
class decides when an incident episode starts, when to request a burst, what the rule concludes, and when the
stopping policy ends the episode. Arms:
  NT          cheap telemetry only; never captures; the cheap-only diagnosis is recorded every window
  FIX(n)      repeated_fixed_burst with repeated_bursts=n (FIX(1) = fixed_burst)
  SS, CR, HS  stability_stop, counter_recovery_stop, hybrid_stop
One episode per session. Windows after the stop keep being recorded so recurrence can be scored offline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

try:
    from revision.tracing.policies import PolicyConfig, PolicyEvidence, StoppingPolicy
    from revision.tracing.rule_diagnosis import CheapWindow, HeavyBurst, RuleThresholds, diagnose
except ImportError:  # flat copy on the GPU host
    from policies import PolicyConfig, PolicyEvidence, StoppingPolicy
    from rule_diagnosis import CheapWindow, HeavyBurst, RuleThresholds, diagnose

ARMS = {'NT': None, 'FIX': 'repeated_fixed_burst', 'SS': 'stability_stop', 'CR': 'counter_recovery_stop',
        'HS': 'hybrid_stop'}


@dataclass(frozen=True)
class ArmConfig:
    arm: str                          # key of ARMS
    fixed_bursts: int = 3             # n for FIX(n)
    trigger_latency_ratio: float = 1.5
    trigger_windows: int = 2          # consecutive elevated windows before an episode starts
    policy: PolicyConfig = field(default_factory=PolicyConfig)

    def __post_init__(self):
        if self.arm not in ARMS:
            raise ValueError(f'Unknown arm {self.arm}')
        if self.trigger_windows < 1 or self.fixed_bursts < 1:
            raise ValueError('trigger_windows and fixed_bursts must be positive')

    def stopping_policy(self):
        name = ARMS[self.arm]
        if name is None:
            return None
        if name == 'repeated_fixed_burst':
            if self.fixed_bursts == 1:
                return StoppingPolicy('fixed_burst', self.policy)
            return StoppingPolicy(name, replace(self.policy, repeated_bursts=self.fixed_bursts,
                                                max_bursts=max(self.policy.max_bursts, self.fixed_bursts)))
        return StoppingPolicy(name, self.policy)


class EpisodeController:
    """States: idle -> active (episode running) -> done (policy stopped or horizon ended)."""

    def __init__(self, arm: ArmConfig, thresholds: RuleThresholds, baseline_ns_per_token: dict | None):
        self.arm, self.thresholds, self.baseline_ns_per_token = arm, thresholds, baseline_ns_per_token
        self.state, self.elevated_streak = 'idle', 0
        self.policy = None
        self.burst_pending = False
        self.latest_window = None
        self.events: list[dict] = []
        self.episode = dict(started_window=None, stopped_window=None, decision=None, bursts=0)

    # -- inputs ---------------------------------------------------------------------------------------------
    def on_window(self, window_id: str, t: float, cheap: CheapWindow) -> dict:
        """One cheap window. Returns the controller's action: {'capture': bool}."""
        self.latest_window = (window_id, t, cheap)
        cheap_dx = diagnose(cheap, self.thresholds)
        event = dict(kind='window', window_id=window_id, t=t, state=self.state, cheap=asdict(cheap),
                     cheap_diagnosis=cheap_dx.label, cheap_causes=list(cheap_dx.causes))
        if self.state == 'idle':
            elevated = cheap.latency_ratio is not None and cheap.latency_ratio >= self.arm.trigger_latency_ratio
            self.elevated_streak = self.elevated_streak + 1 if elevated else 0
            if self.elevated_streak >= self.arm.trigger_windows:
                self.state = 'active'
                self.policy = self.arm.stopping_policy()
                self.episode['started_window'] = window_id
                event['episode_started'] = True
        elif self.state == 'active' and self.policy is not None:
            self.policy.observe_recovery(self._evidence(window_id, cheap, None, None, None))
        action = dict(capture=self.state == 'active' and self.policy is not None and not self.burst_pending
                      and self.policy.can_capture)
        if action['capture']:
            self.burst_pending = True
        event['action'] = action
        self.events.append(event)
        return action

    def on_burst(self, capture_id: str, activity: dict | None, failure: str | None = None) -> dict:
        """Result of the requested burst. `activity` holds busy_fraction, family_ns_per_token (None when the token
        count is unavailable) and family_top_kernel, or is None on failure."""
        if not self.burst_pending:
            raise ValueError('No burst was requested')
        self.burst_pending = False
        window_id, t, cheap = self.latest_window
        self.episode['bursts'] += 1
        if activity is None:
            dx, evidence_id = None, None
        else:
            heavy = HeavyBurst(capture_id, activity['busy_fraction'], activity.get('family_ns_per_token'),
                               self.baseline_ns_per_token, activity.get('family_top_kernel'))
            dx, evidence_id = diagnose(cheap, self.thresholds, heavy, assume_elevated=True), capture_id
        decision = self.policy.observe(self._evidence(f'{window_id}/burst/{capture_id}', cheap,
                                                      None if dx is None else dx.label, capture_id, evidence_id))
        event = dict(kind='burst', capture_id=capture_id, window_id=window_id, t=t, failure=failure,
                     heavy_diagnosis=None if dx is None else dx.label,
                     heavy_causes=None if dx is None else list(dx.causes), kernel=None if dx is None else dx.kernel,
                     top_kernel=None if dx is None else dx.top_kernel,
                     reasons=None if dx is None else list(dx.reasons), decision=asdict(decision))
        if decision.stop:
            self._stop(window_id, decision)
        self.events.append(event)
        return event

    def finish(self) -> dict:
        if self.state == 'active' and self.policy is not None:
            self._stop(None, self.policy.finish())
        elif self.state == 'active':
            self.episode['decision'] = dict(stop=True, reason='horizon_ended', policy='NT')
            self.state = 'done'
        return dict(self.episode, final_state=self.state)

    # -- helpers --------------------------------------------------------------------------------------------
    def _stop(self, window_id, decision):
        self.state = 'done'
        self.episode['stopped_window'] = window_id
        self.episode['decision'] = asdict(decision)

    def _evidence(self, window_id, cheap, label, capture_id, evidence_id):
        util = None if cheap.gpu_util is None else cheap.gpu_util * 100  # PolicyConfig uses percent
        suspicious = None if cheap.latency_ratio is None else cheap.latency_ratio >= self.arm.trigger_latency_ratio
        return PolicyEvidence(window_id=window_id, diagnosis_label=label, capture_id=capture_id,
                              diagnosis_evidence_id=evidence_id, latency_ratio=cheap.latency_ratio, gpu_util=util,
                              suspicious=suspicious, recovery_evidence_id=f'cheap:{self.latest_window[0]}')
