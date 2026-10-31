"""CPU-testable streaming episode controller; no workload-truth inputs.

on_window() accepts already aggregated observations, not whole completed runs.
tick() services the backend without sleeping. The caller owns event scheduling.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field, replace
from typing import Callable

from experiments.tracing.evidence_gate import EvidenceDecisionGate, TimedDecision
from experiments.tracing.policies import POLICY_VERSION, PolicyConfig, PolicyEvidence, StoppingPolicy, is_concrete_label, recovery_observed
from experiments.tracing.profiler import StreamingProfilerBackend
from experiments.tracing.timing import seconds_to_ns
from experiments.tracing.windows import CheapWindow, HealthyBaseline


@dataclass(frozen=True)
class ControllerConfig:
    policy: str = "stability_stop"
    policy_config: PolicyConfig = field(default_factory=PolicyConfig)
    latency_trigger_ratio: float = 1.5
    gpu_trigger_percent: float = 85.0
    gpu_trigger_windows: int = 2
    burst_s: float = 2.0
    startup_timeout_s: float = 5.0
    evidence_timeout_s: float = 30.0
    cooldown_s: float = 5.0
    change_ratio_factor: float = 1.5
    change_gpu_points: float = 20.0
    retry_unresolved: bool = False
    reactivation_enabled: bool = True

    def __post_init__(self):
        StoppingPolicy(self.policy, self.policy_config)
        if not isinstance(self.reactivation_enabled, bool):
            raise ValueError("reactivation_enabled must be boolean")
        for value in (self.burst_s, self.startup_timeout_s, self.evidence_timeout_s):
            if seconds_to_ns(value) <= 0:
                raise ValueError("Burst and timeout durations must be positive")
        seconds_to_ns(self.cooldown_s)
        if not math.isfinite(self.latency_trigger_ratio) or self.latency_trigger_ratio <= 1:
            raise ValueError("Latency trigger must exceed the healthy baseline")
        if not math.isfinite(self.gpu_trigger_percent) or not 0 <= self.gpu_trigger_percent <= 100:
            raise ValueError("Invalid GPU trigger")
        if not isinstance(self.gpu_trigger_windows, int) or self.gpu_trigger_windows < 1:
            raise ValueError("GPU streak must be a positive integer")
        if not math.isfinite(self.change_ratio_factor) or self.change_ratio_factor <= 1:
            raise ValueError("Change ratio factor must exceed one")
        if not math.isfinite(self.change_gpu_points) or not 0 < self.change_gpu_points <= 100:
            raise ValueError("Change GPU threshold must be in (0, 100]")


@dataclass
class _Episode:
    episode_id: str
    started_at_ns: int
    attempts: list[str] = field(default_factory=list)
    decisions: list[TimedDecision] = field(default_factory=list)
    round_number: int = 0
    reactivation_attempts: int = 0
    recovery_streak: int = 0
    last_diagnosis: str | None = None
    stop_reason: str | None = None
    stopped_at_ns: int | None = None
    stop_signature: tuple | None = None
    ended_at_ns: int | None = None
    end_reason: str | None = None


class StreamingController:
    def __init__(self, backend: StreamingProfilerBackend, baseline: HealthyBaseline,
                 classifier: Callable[[dict], str | None],
                 start_attempt: Callable[[str, CheapWindow], None],
                 config: ControllerConfig | None = None):
        self.backend, self.recorder = backend, backend.recorder
        self.baseline, self.classifier, self.start_attempt = baseline, classifier, start_attempt
        self.config = config or ControllerConfig()
        self.state = "idle"
        self.finished = False
        self._finishing = False
        self.latest: CheapWindow | None = None
        self.latency_ratio: float | None = None
        self.suspicious: bool | None = None
        self._high_gpu_streak = 0
        self._window_ids: set[str] = set()
        self._episode: _Episode | None = None
        self.episodes: list[_Episode] = []
        self.gate: EvidenceDecisionGate | None = None
        self.events: list[dict] = []
        self._attempt_started_ns: int | None = None
        self._capture_started_ns: int | None = None
        self._cooldown_until_ns = 0

    def _event(self, name: str, **details) -> None:
        scope = self._episode.episode_id if self._episode else "stream"
        event = self.recorder.mark(name, scope, status=self.state)
        self.events.append(dict(sequence=len(self.events), event=name, timestamp_ns=event.timestamp_ns,
                                clock_domain=event.clock_domain, provenance=event.provenance,
                                state=self.state, episode_id=self._episode.episode_id if self._episode else None,
                                **details))

    def _state(self, state: str) -> None:
        if state != self.state:
            previous, self.state = self.state, state
            self._event("state_changed", previous_state=previous)

    def _counters(self) -> PolicyEvidence:
        return PolicyEvidence(window_id=self.latest.window_id,
                              recovery_evidence_id=self.latest.window_id,
                              latency_ratio=self.latency_ratio, gpu_util=self.latest.gpu_util,
                              suspicious=self.suspicious)

    def _signature(self) -> tuple:
        return self.latency_ratio, self.latest.gpu_util, self.latest.throughput_rps

    def _changed(self, previous: tuple) -> bool:
        current = self._signature()
        for index in (0, 2):
            old, new = previous[index], current[index]
            if old is not None and new is not None:
                if (old == 0) != (new == 0):
                    return True
                if min(old, new) > 0 and max(old, new) / min(old, new) >= self.config.change_ratio_factor:
                    return True
        return (previous[1] is not None and current[1] is not None
                and abs(previous[1] - current[1]) >= self.config.change_gpu_points)

    def on_window(self, window: CheapWindow) -> None:
        if self.finished:
            raise RuntimeError("Stream is finished")
        if window.clock_domain != self.recorder.clock.domain:
            raise ValueError("Cheap window uses a different clock domain")
        if window.available_at_ns > self.recorder.clock.now_ns():
            raise ValueError("Cheap window is not available yet")
        if window.window_id in self._window_ids or (self.latest and window.start_ns < self.latest.end_ns):
            raise ValueError("Cheap windows must be unique, chronological, and nonoverlapping")
        self._window_ids.add(window.window_id)
        self.latest = window
        self.latency_ratio = window.p95_latency_ms / self.baseline.p95_latency_ms if window.p95_latency_ms is not None else None
        high = window.gpu_util is not None and window.gpu_util >= self.config.gpu_trigger_percent
        self._high_gpu_streak = self._high_gpu_streak + 1 if high else 0
        reasons = []
        if window.request_error_count:
            reasons.append("request_errors")
        pending_ratio = window.oldest_pending_ms / self.baseline.p95_latency_ms if window.oldest_pending_ms is not None else None
        if pending_ratio is not None and pending_ratio >= self.config.latency_trigger_ratio:
            reasons.append("long_pending_request")
        if self.latency_ratio is not None and self.latency_ratio >= self.config.latency_trigger_ratio:
            reasons.append("latency_regression")
        if (self.latency_ratio is not None and self.latency_ratio > self.config.policy_config.recovery_latency_ratio
                and self._high_gpu_streak >= self.config.gpu_trigger_windows):
            reasons.append("sustained_gpu_saturation_with_elevated_latency")
        if reasons:
            self.suspicious = True
        else:
            self.suspicious = False if self.latency_ratio is not None and window.gpu_util is not None else None
            if pending_ratio is not None and pending_ratio > self.config.policy_config.recovery_latency_ratio:
                self.suspicious = None
        self._event("cheap_window_available", window_id=window.window_id,
                    window_start_ns=window.start_ns, window_end_ns=window.end_ns,
                    available_at_ns=window.available_at_ns, sample_count=window.sample_count,
                    request_count=window.request_count, request_error_count=window.request_error_count,
                    gpu_sample_count=window.gpu_sample_count,
                    outstanding_request_count=window.outstanding_request_count,
                    oldest_pending_ms=window.oldest_pending_ms,
                    p95_latency_ms=window.p95_latency_ms, gpu_util=window.gpu_util,
                    throughput_rps=window.throughput_rps, latency_ratio=self.latency_ratio,
                    suspicious=self.suspicious, suspicion_reasons=reasons)
        if self._episode is None and self.suspicious is True:
            if self.recorder.clock.now_ns() < self._cooldown_until_ns:
                self._event("activation_suppressed", reason="cooldown")
            else:
                episode = _Episode(f"episode-{len(self.episodes) + 1}", self.recorder.clock.now_ns())
                self.episodes.append(episode)
                self._episode = episode
                self._event("episode_started", window_id=window.window_id)
                episode.started_at_ns = self.events[-1]["timestamp_ns"]  # One authoritative activation stamp.
                self._new_round()
        if self._episode is not None:
            counters = self._counters()
            self._episode.recovery_streak = self._episode.recovery_streak + 1 if recovery_observed(counters, self.config.policy_config) else 0
            self.gate.policy.observe_recovery(counters)
            if self.state == "monitoring":
                if self._episode.recovery_streak >= self.config.policy_config.recovery_windows:
                    self._close("workload_recovered")
                elif self.suspicious is True:
                    self._maybe_reactivate()
        self.tick()

    def _new_round(self) -> None:
        episode = self._episode
        remaining = self.config.policy_config.max_bursts - len(episode.attempts)
        if remaining <= 0:
            return
        episode.round_number += 1
        episode.stop_reason = None
        policy = StoppingPolicy(self.config.policy, replace(self.config.policy_config, max_bursts=remaining))
        self.gate = EvidenceDecisionGate(self.backend, policy, self.classifier)
        self._state("suspicious")

    def _maybe_reactivate(self) -> None:
        if not self.config.reactivation_enabled:
            return
        episode = self._episode
        if len(episode.attempts) >= self.config.policy_config.max_bursts:
            return
        if self.recorder.clock.now_ns() < episode.stopped_at_ns + seconds_to_ns(self.config.cooldown_s):
            return
        reason = "changed_cheap_evidence" if self._changed(episode.stop_signature) else None
        if reason is None and self.config.retry_unresolved and not is_concrete_label(episode.last_diagnosis):
            reason = "unresolved_diagnosis"
        if reason:
            episode.reactivation_attempts += 1
            self._event("tracing_reactivation_requested", reason=reason)
            self._new_round()

    def _launch(self) -> None:
        episode = self._episode
        capture_id = f"{episode.episode_id}:capture-{len(episode.attempts) + 1}"
        episode.attempts.append(capture_id)
        self._attempt_started_ns = self.recorder.clock.now_ns()
        self._capture_started_ns = None
        window = self.latest
        self._state("starting")
        self._event("capture_requested", capture_id=capture_id, window_id=window.window_id,
                    round_number=episode.round_number)
        self.gate.start_capture(capture_id, lambda: self.start_attempt(capture_id, window))

    def _evaluate(self) -> None:
        episode = self._episode
        result = self.gate.evaluate(f"{episode.episode_id}:decision-{len(episode.decisions) + 1}",
                                    latency_ratio=self.latency_ratio, gpu_util=self.latest.gpu_util,
                                    suspicious=self.suspicious, recovery_evidence_id=self.latest.window_id)
        episode.decisions.append(result)
        episode.last_diagnosis = result.decision.diagnosis_label
        self._event("policy_decision", capture_id=result.capture_id, reason=result.decision.reason,
                    decision_status=result.status, evidence_ready_at_ns=result.evidence_ready_at_ns,
                    diagnosis_label=result.decision.diagnosis_label)
        if result.decision.stop:
            episode.stop_reason = result.decision.reason
            episode.stopped_at_ns = self.recorder.clock.now_ns()
            episode.stop_signature = self._signature()
            self._state("monitoring")
            self._event("heavy_tracing_stopped", reason=episode.stop_reason)
            if not self._finishing and episode.recovery_streak >= self.config.policy_config.recovery_windows:
                self._close("workload_recovered")
        else:
            self._state("suspicious")

    def tick(self) -> None:
        cleanup = getattr(self.backend, "service_cleanup", None)
        if cleanup is not None:
            cleanup()
        if self.finished or self._episode is None:
            return
        if self.gate.pending:
            capture_id = self.gate.pending
            if self.gate.pending_start_failed:
                self._evaluate()
            else:
                now = self.recorder.clock.now_ns()
                state = self.backend.state(capture_id)
                timeout = None
                if state == "starting" and now >= self._attempt_started_ns + seconds_to_ns(self.config.startup_timeout_s):
                    timeout = "startup_timeout"
                elif state not in {"ready", "failed"} and now >= self._attempt_started_ns + seconds_to_ns(self.config.evidence_timeout_s):
                    timeout = "evidence_timeout"
                if timeout:
                    self.backend.cancel(capture_id, timeout)
                    self._event("capture_cancelled", capture_id=capture_id, reason=timeout)
                else:
                    self.backend.poll(capture_id)
                state = self.backend.state(capture_id)
                if state == "capturing":
                    if self._capture_started_ns is None:
                        self._capture_started_ns = self.recorder.clock.now_ns()
                        self._state("tracing")
                    if now >= self._capture_started_ns + seconds_to_ns(self.config.burst_s):
                        self.backend.stop(capture_id)
                        state = self.backend.state(capture_id)
                if state in {"finalizing", "exporting", "parsing"}:
                    self._state("evaluating")
                if state in {"ready", "failed"}:
                    self._evaluate()
        if (self._episode is not None and not self._finishing and self.state != "monitoring"
                and self.gate.pending is None and self.gate.policy.can_capture
                and getattr(self.backend, "can_start_capture", lambda: True)()):
            self._launch()

    def next_wakeup_ns(self) -> int | None:
        if self.finished or self.gate is None:
            return None
        if self.gate.pending is None:
            if self.state == "suspicious" and self.gate.policy.can_capture:
                if getattr(self.backend, "can_start_capture", lambda: True)():
                    return self.recorder.clock.now_ns()
                return getattr(self.backend, "next_cleanup_deadline_ns", lambda: None)()
            return None
        now = self.recorder.clock.now_ns()
        if self.gate.pending_start_failed:
            return now
        capture_id = self.gate.pending
        state = self.backend.state(capture_id)
        if state in {"ready", "failed"}:
            return now
        if state == "capturing" and self._capture_started_ns is None:
            return now
        candidates = [self._attempt_started_ns + seconds_to_ns(self.config.evidence_timeout_s)]
        deadline = self.backend.next_deadline_ns(capture_id)
        if deadline is not None:
            candidates.append(deadline)
        if state == "starting":
            candidates.append(self._attempt_started_ns + seconds_to_ns(self.config.startup_timeout_s))
        if state == "capturing" and self._capture_started_ns is not None:
            candidates.append(self._capture_started_ns + seconds_to_ns(self.config.burst_s))
        return max(now, min(candidates))

    def _close(self, reason: str) -> None:
        episode = self._episode
        episode.ended_at_ns, episode.end_reason = self.recorder.clock.now_ns(), reason
        self._event("episode_ended", reason=reason, stop_reason=episode.stop_reason)
        self._cooldown_until_ns = episode.ended_at_ns + seconds_to_ns(self.config.cooldown_s)
        self._episode, self.gate = None, None
        self._state("idle")

    def finish(self) -> None:
        if self.finished:
            return
        self._finishing = True
        if self._episode is not None:
            if self.gate.pending:
                capture_id = self.gate.pending
                if not self.gate.pending_start_failed and self.backend.state(capture_id) not in {"ready", "failed"}:
                    self.backend.cancel(capture_id, "horizon_ended")
                    self._event("capture_cancelled", capture_id=capture_id, reason="horizon_ended")
                self._evaluate()
            if self._episode.stop_reason is None:
                self._episode.stop_reason = self.gate.policy.finish().reason
            self._close("horizon_ended")
        self.finished = True
        self._event("stream_finished")

    def snapshot(self) -> dict:
        return dict(controller_version="streaming_v4", policy_version=POLICY_VERSION,
                    evidence_mode=self.recorder.provenance,
                    clock_domain=self.recorder.clock.domain, state=self.state, finished=self.finished,
                    baseline=asdict(self.baseline), config=asdict(self.config),
                    episodes=[asdict(episode) for episode in self.episodes],
                    capture_timings={capture_id: self.recorder.metrics(capture_id)
                                     for episode in self.episodes for capture_id in episode.attempts},
                    events=list(self.events))

    def jsonl(self) -> str:
        return "".join(json.dumps(event, allow_nan=False) + "\n" for event in self.events)
