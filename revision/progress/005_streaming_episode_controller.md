# Step 005 — CPU-only streaming episode controller

Date: 2026-10-27. Status: completed for chronological cheap-window input and the fake profiler. This is a development harness, not a CPU experimental baseline or a real serving deployment.

## Completed work

- [x] Added `revision/tracing/windows.py`: immutable `CheapWindow` observations and an explicit `HealthyBaseline` latency calibration reference. Rejects truth keywords, invalid metrics, insufficient sample counts for latency, inconsistent bounds, and unavailable/future timestamps at ingestion.
- [x] Added `revision/tracing/controller.py`: event-driven anomaly episodes that consume already closed windows as they become available. `on_window`, `tick`, and `next_wakeup_ns` connect observation arrival, asynchronous startup/capture/export/parse, evidence-readiness checks, classification, and the shared policy engine without sleeps.
- [x] Implemented latency-regression and sustained-GPU-with-elevated-latency triggers using an explicit supplied healthy p95 reference. Missing metrics do not establish health or recovery. Thresholds remain uncalibrated engineering settings, not validated detection rules.
- [x] Implemented idle → suspicious → starting → tracing → evaluating → monitoring transitions. `monitoring` means heavy capture has stopped while the incident can remain open; it does not mean workload recovery. Two observed recovery windows close an incident by default.
- [x] Separated cheap-window recovery updates from fresh parsed-diagnosis observations. Every cheap window is delivered to recovery accounting, while repeated use of the latest cheap window by capture decisions is deduplicated. This prevents false recovery from multiple decisions and preserves intervening non-recovery gaps.
- [x] Extended the shared engine to `stopping_v3` with optional recovery evidence IDs. Older callers without those IDs retain their decision-window fallback; no historical results were regenerated. Diagnosis observations and recovery observations have distinct identities.
- [x] Implemented configurable cooldown and measured-change reactivation. Persistent unchanged suspicion does not automatically recapture. Optional unresolved-diagnosis retries are disabled by default. All capture rounds share the original episode budget; reactivation cannot reset it.
- [x] Implemented startup and total evidence-availability timeouts, unique attempts, failed-launch accounting, and end-of-stream cancellation. Cancellation closes pending fake-backend phases and prevents later evidence publication. Deadlines take priority over an unfinished stage at the deadline; evidence already ready can still be consumed.
- [x] Added a backend streaming protocol and fake-backend cancellation for every pending phase. This is not real CUDA worker/process cleanup.
- [x] Added controller event JSONL and result snapshots with version, baseline provenance, configuration, episode/attempt/decision records, capture timings, observed symptoms, and stop/end reasons. Expected/reference labels remain outside controller inputs.
- [x] Added a runnable streaming demo with six synthetic fixtures and configurable profiling policy. Saved `stable` and `changing` example outputs, separate from historical artifacts and research measurements.
- [x] Added 24 tests (23 streaming tests plus cancellation coverage) and updated the main plan, README, and cumulative tracker.

## CPU and baseline terminology

The CPU runs the simulator, timing checks, and policy code. It is not compared to GPU inference as a baseline. Actual experimental baselines are competing profiling strategies evaluated under the same GPU workload, hardware, and observation horizon.

`HealthyBaseline` is a detector calibration reference: current p95 latency is divided by a supplied healthy p95. The demo's 100 ms reference is synthetic. It is not a CPU latency measurement and does not demonstrate a valid healthy reference for real deployment.

## Observed simulation behavior

- Healthy-only windows trigger no capture.
- The stable fixture takes two parsed captures to meet SS(K=2), stops heavy collection while the incident remains suspicious, and closes only on later sustained cheap recovery.
- An unknown first summary requires two subsequent matching concrete summaries (three captures total) to meet SS.
- The changing fixture triggers a second round after a measured latency change and cooldown. It uses four total attempts within one incident and the same global cap.
- Unknown-only or timeout cases terminate tracing inconclusively at the episode budget. A failed attempt consumes budget without adding diagnosis stability.
- Cheap windows can arrive during export/parsing; evidence is not used before readiness. Missing data and duplicate/foreign/future windows do not create false recovery.

These are deterministic correctness checks. They provide no measured GPU cost savings, diagnostic accuracy, or production incident validation. The tiny demo classifier maps synthetic kernel names and is not the research classifier.

## Validation

```bash
python3 -m unittest discover -s revision/tests -q
python3 revision/scripts/demo_streaming_controller.py --scenario stable
python3 revision/scripts/demo_streaming_controller.py --scenario changing
python3 -m py_compile revision/tracing/controller.py revision/tracing/windows.py revision/tracing/policies.py revision/tracing/profiler.py revision/tracing/evidence_gate.py revision/scripts/demo_streaming_controller.py revision/tests/test_streaming_controller.py
git diff --check
```

The full suite passes **89 CPU-only tests** (65 previous, 24 added). After adding symptom details to event serialization, the 23 streaming tests were also rerun successfully. New checks cover healthy nonactivation, missing evidence, sustained saturation, stop/recovery separation, changing/unknown diagnoses, unique cheap-window recovery, intermediate recovery gaps, persistence without recapture, shared budgets across rounds, new-episode budgets, cooldown, launch failures, startup/export timeouts, horizon cancellation, chronological input validation, truth-free interfaces, readiness ordering, JSON serialization, the CLI, and cancellation of every pending fake phase.

## Remaining limits

The controller currently consumes already aggregated windows. The legacy serving runner still aggregates retrospectively; it is not wired to this controller. Raw request/GPU sample windowing, real capture integration, worker coverage, cancellation cleanup, independent classifier validation, trigger/recovery calibration, and end-to-end perturbation measurement remain unfinished.

The caller must schedule `tick()` service as well as window arrivals. Late service cannot backdate stage completion. Healthy recovery and changed-symptom thresholds are explicit rules rather than proven causal diagnoses. Persistent missing observations can leave an incident unresolved until stream end; no successful diagnosis is inferred.

## Next step

**Step 006: streaming request/sample window aggregation on CPU.** Build a truth-free adapter that accepts timestamped request completions and GPU samples, emits chronological `CheapWindow` objects with explicit availability/sample counts, and feeds this controller as windows close. Test boundary requests, empty/missing samples, late data, request errors/drain, and healthy calibration separation. Then connect actual serving/NVML and a real profiler backend on GPU. Create a new step report and update the plan/tracker.
