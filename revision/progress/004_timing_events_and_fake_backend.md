# Step 004 — Timing events, fake capture backend, and evidence readiness

Date: 2026-10-27. Status: complete for CPU-only simulation and the shared timing/readiness interface. No GPU experiments, real profiler capture, or historical data regeneration.

## Completed work

- [x] Implemented `revision/tracing/timing.py`: `MonotonicClock`, deterministic `ManualClock`, immutable event records, ordered JSONL output, explicit clock domains, and scoped phase begin/end records.
- [x] Added explicit timing fields for startup, control windows, profile-process wall time, report finalization, export command, summary parsing, classification, evidence-ready and decision-ready timestamps. Unobserved/incomplete phases stay null; no timing is inferred by subtracting unrelated clocks or by replacing capture time with requested duration.
- [x] Added interval-union accounting for backend-confirmed capture ranges. Cross-domain, negative, and future boundaries are rejected. Fake ranges are synthetic; ordinary control acknowledgements leave capture-active time unavailable.
- [x] Implemented `revision/tracing/profiler.py`: a parsed-evidence readiness interface plus a fake backend with starting → capturing → finalizing → exporting → parsing → ready states. Stage failures are explicit, and evidence is never exposed in a pre-ready state.
- [x] Made fake pipeline progression nonblocking. The test advances a virtual clock and calls `poll()`; no sleeps or GPU dependencies are used. Late polling records completion at the actual observation time, not an earlier scheduled deadline.
- [x] Implemented `revision/tracing/evidence_gate.py`: one pending attempt at a time, capacity checks before launch, readiness validation before classification/policy update, and protection against future timestamps, foreign clock domains/provenance, wrong capture IDs, or repeated evidence consumption.
- [x] Added explicit failed-launch/capture/classification outcomes. Failed attempts consume policy budget and cannot increment diagnosis stability. Existing policy rules still distinguish fixed-count/recovery completion from genuine stable-label conditions.
- [x] Kept backend evidence payloads isolated by copying; callers cannot mutate an already published backend summary.
- [x] Added a runnable two-capture synthetic CLI demo and saved an example event/result pair. The demo reaches SS(K=2) stability using only parsed evidence.
- [x] Added 25 tests and updated the revision README, timing contract, progress index, and main revision plan.

## Timing semantics

The default demo has 1 s startup, a 10 s control window, and 2 s finalization inside a 13 s profile-process span. The separate stats command adds 3 s and parsing adds 0.5 s. Therefore `evidence_collection_s=16.5`, ending at parsed evidence readiness. The default `capture_active_s` remains null because a control window is not a confirmed active-capture interval.

`lifecycle_total_s` also remains null in this harness: it does not measure final persistence or request drain. The timing recorder supports explicitly recording that phase, but the fake backend does not falsely end it at evidence readiness. `evidence_collection_s` is the measured synthetic collector boundary instead. Classification and decision events follow evidence readiness; classification cost is recorded separately.

All metrics/events carry `timing_v1` (in metric output), a named clock domain, and `synthetic_simulation` provenance. Failure costs remain visible with failed phase statuses. No example value is a real GPU or serving measurement.

## Validation

```bash
python3 -m unittest discover -s revision/tests -q
python3 revision/scripts/demo_fake_profiler.py
python3 -m py_compile revision/tracing/timing.py revision/tracing/profiler.py revision/tracing/evidence_gate.py revision/scripts/demo_fake_profiler.py revision/tests/test_timing_and_profiler.py
git diff --check
```

The full suite passes **65 CPU-only tests** (40 existing, 25 added). New coverage includes every pre-parse readiness stage; exact simulated timing decomposition; unknown fields; overlapping capture intervals; cross-domain/future-time rejection; monotonic ordering; late polls; duplicate attempts; zero-delay stage ordering; all simulated backend failure stages; launch/classifier failure accounting; failed-attempt budget exhaustion; payload isolation; classification after readiness; SS convergence; and a CLI test that verifies synthetic provenance and null active-capture time.

The demo's readiness and decision timestamps are both 16.5 s for its first capture because its illustrative classifier consumes no simulated time. A separate test advances the clock by 0.25 s inside classification and verifies the decision cannot precede completion.

## Remaining limits

- This is a capture/readiness harness, not yet a full streaming serving controller. It does not model request arrivals, independent diagnosis references, real cancellation/cleanup, multi-episode resets, or worker capture coverage.
- The readiness interface trusts the backend to supply authentic report availability and capture metadata. Real Nsight integration must validate that claim on GPU.
- No calibrated classifier or stopping-performance result is established. The demo classifier is explicitly illustrative and uses a synthetic kernel summary.
- Existing historical results and the step-003 audit snapshot are unchanged. The examples are separate synthetic artifacts.

## Next step

**Step 005: CPU-only streaming episode controller.** Connect chronological cheap windows, anomaly detection, capture requests, asynchronous readiness, policy decisions, and episode/recovery transitions using the fake backend. Add an episode event log and deterministic evolving/unknown/failure scenarios, including queued evidence and explicit timeout/cancellation behavior. Keep reference/expected labels outside controller inputs. Then prepare the GPU backend behind the validated interface. Create a new step report and update the progress index and main plan.
