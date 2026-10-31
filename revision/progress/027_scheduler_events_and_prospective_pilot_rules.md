# Step 027 — scheduler events and prospective pilot rules

Completed: 2026-10-28. CPU implementation/tests and read-only installed-source retrieval; no GPU workload, profiler capture or service/package modification.

## Completed checklist

- [x] Inspect/preserve five pinned installed vLLM source files and hashes for engine admission, first positive CPU scheduling, terminal cleanup and custom scheduler configuration.
- [x] Implement opt-in source-hash/version/config-bound scheduler subclass hooks, without changing existing runners/defaults or installed packages.
- [x] Add bounded request/event history, shared/nested hook brackets, first-schedule deduplication and explicit drop/fault accounting.
- [x] Add fresh scoped same-host probes, atomic snapshots, parent acquisition/identity checks and bounded trigger/timeout cleanup.
- [x] Derive scheduler-delay interval bounds with boundary ambiguity and pending/aborted accounting, without substituting GPU start, HTTP completion, admission-window p95 or prefill fraction.
- [x] Save five synthetic CPU cases and hash-bound prospective engineering rules for commissioning, volume/cadence/mismatch and bounded challenge templates.
- [x] Pass 484 CPU tests, including 17 new journal/adapter/probe/specification checks.
- [x] Update progress and the CAIN revision plan; retain unvalidated live/ID/perturbation and scientific-reference limits.

## Implementation and artifacts

[Journal/reader](../tracing/server_events.py), [opt-in scheduler](../tracing/vllm_event_scheduler.py), [preparation CLI](../scripts/prepare_server_event_pilot.py), [source manifest](../protocol/sources/vllm_0_10_2/events/SOURCE_MANIFEST.json), [operating contract](../protocol/SERVER_EVENT_INSTRUMENTATION.md), [saved checks](../examples/server_events/REPORT.md).

The source confirms `add_request` enters the engine queue, positive `num_scheduled_tokens` identifies a CPU scheduling decision, and `_free_request` handles a terminal status including aborts. None is an HTTP arrival/delivery or GPU execution timestamp. The plugin rejects different source bytes/version, async/distributed configurations, ambiguous workers or scheduler/CUDA-owner PID mismatch. Source initialization and hook semantics are inspected; actual live startup remains unvalidated.

Each session bounds history to 512 requests/4,096 events and 32 probe tokens. Drops/faults invalidate complete history. Repeated decode scheduling is not new first-service evidence; shared batch/nested timestamps are accepted correctly. Probe tokens bind full PID/UUID/nonce/generation/clock identity and parent request/source/receipt brackets. Idle source probing may require a declared diagnostic request outside the measured case. A hook may acknowledge before that trigger finishes, so final complete-history probe/idle-RPC wiring remains a commissioning requirement.

The reducer returns first-scheduling delay bounds only for brackets wholly in the half-open window. Ambiguous boundaries, pending requests and aborts without scheduling are explicit. Pending state is as of the probe, not historical window end. The existing wait/phase metrics remain unavailable; no classifier contract is changed and no engine/client ID mapping is inferred.

The prospective engineering specification pins source/corpus hashes, ten-second review windows, a twenty-completion p95-review floor, half-second metric cadence, a 0.75-second gap flag, exact ID/token work and a 1.25 latency-ratio mismatch flag. These are engineering review choices for the next pilot, not statistical guarantees or retrospective reference eligibility rules. Scientific tolerances remain unset. Budgets cover 512 total requests/case/session including warmup/probe triggers, 32 client in-flight versus 16 server sequences, 60-second horizons and 30-second drain, with explicit prefix-cache disable/verification required. Eight-request commissioning precedes rate-ramp/removal/lull/unresolved challenges; exact pressure selection/offered files and observer-control execution are still unresolved.

## Validation and limits

All **484 CPU tests pass**, including **17 new checks**: bounded history/faults, duplicate/foreign/lifecycle/clock rejection, first-schedule deduplication, shared/nested brackets, pending/aborted and uncertain-boundary accounting, pinned subclass forwarding/config guards, parent file-probe binding and cancelled trigger cleanup, and corpus/specification bounds. Five saved demos remain synthetic and never claim live validation.

Source retrieval was read-only; no GPU load, serving restart, package patch, reference label/lock or fit was created. The prospective plan is non-executable and does not freeze the main study. Actual plugin startup, source/client ID correlation, new event observer effects, effective cache configuration and challenging-case realization require subsequent hardware validation. Memory history can be lost before a valid snapshot; clock/identity checks are conditional on owned same-host execution. First-schedule delay excludes frontend time, later preemption waits and GPU execution/phase attribution. The previous sparse zero-queue pilot is not retroactively calibrated.

## Next step — 028

1. Wire the opt-in scheduler into a bounded owned commissioning runner and verify real source/PID/session/clock binding and effective cache settings.
2. Execute at most eight L4 requests, validate complete hook lifecycle/probes and actual engine/client ID mapping; preserve failures and stop before challenges if commissioning fails.
3. Resolve observer on/off controls and exact prospective pressure selection/arrival files before the larger bounded challenge cases, reference adjudication or fitting.

The next live commissioning needs the L4. No rental-state change or GPU job was launched in this step.
