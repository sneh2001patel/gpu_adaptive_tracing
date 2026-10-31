# Scheduler event instrumentation and prospective pilot rules — steps 027–028

Step 027 prepared the opt-in vLLM 0.10.2 instrumentation path on CPU. Step 028 commissions it in one fresh owned L4 server: eight successful requests, complete 24-event history, two fresh idle probes and effective prefix caching disabled. [Hardware results](../hardware/l4_20261028/EVENTS_REPORT.md) retain the raw receipts and limitations. Observer perturbation and challenging-case behavior remain unvalidated. No installed package is patched.

## Reviewed source and event meanings

[Installed-source manifest](sources/vllm_0_10_2/events/SOURCE_MANIFEST.json) fingerprints five preserved files, with Apache-2.0 headers/license retained. This establishes the installed bytes inspected, not equality with an upstream Git tag.

| Hook | Source observation | Explicit limit |
|---|---|---|
| `Scheduler.add_request` | Adds an engine request to waiting queue and request registry | Not HTTP/frontend arrival; excludes time before engine admission |
| `Scheduler.schedule` | Returns `num_scheduled_tokens`; first positive entry is recorded once | CPU scheduling decision, not GPU execution start; subsequent decode scheduling is ignored |
| `Scheduler._free_request` | Handles a request already in a finished status, including aborts | Scheduler terminal/resource handling, not client delivery or guaranteed GPU idle |

The [scheduler source](sources/vllm_0_10_2/events/scheduler.py.txt), [engine core](sources/vllm_0_10_2/events/engine_core.py.txt) and [argument plumbing](sources/vllm_0_10_2/events/arg_utils.py.txt) establish the hook locations and custom `--scheduler-cls` path. Engine core initializes its executor/KV caches before constructing the scheduler. The config can replace the class for async scheduling, which this adapter therefore rejects.

`EventScheduler` requires the exact reviewed scheduler SHA-256 and package version, synchronous scheduling and tensor/pipeline/data parallel sizes of one. It requires one current worker record whose PID matches the actual scheduler process and whose nonce/generation/clock match the owned session. Different process layouts fail rather than inventing a mapping. Step 028 verifies that binding on live worker 7200; this does not validate other executor layouts.

No installed source is edited. `OwnedLiveActivity.start(event_instrumentation=True)` explicitly opts in via:

```text
--scheduler-cls revision.tracing.vllm_event_scheduler.EventScheduler
--no-enable-prefix-caching
```

The owned launcher sets `REVISION_ENABLE_EVENTS=1` only for this opt-in. It clears an inherited event flag on ordinary launches. The commissioning runner verifies actual scheduler cache/sequence/async settings from startup evidence; ordinary arm defaults do not enable this collector.

## Bounded history and time uncertainty

The CUDA-free `EventJournal` stores at most 512 distinct requests, 4,096 events and 32 probe tokens per session. It records engine request IDs, ordered event sequence, hook entry/return brackets, observation time and terminal status. It stores no prompt, workload truth or cause label. Shared batch and nested hook brackets are valid; global observation order and each request lifecycle are checked. First-schedule events are deduplicated across decode calls.

Overflow, invalid lifecycle/clock input and persistence/probe faults are explicit. Any drop or fault invalidates complete-history claims. Missing/aborted-before-schedule requests are not assigned zero wait. First admission-to-scheduling delay is an **interval bound**, from scheduling-entry minus admission-return through scheduling-return minus admission-entry. It includes host scheduling uncertainty and is not the existing `request_wait_p95_ms` statistic. It excludes frontend waiting, later preemption/resumption waits and GPU execution timing. No prefill fraction is inferred.

For half-open windows, only a first-schedule bracket wholly inside the window contributes bounds. A bracket crossing/touching an uncertain boundary is retained separately. Pending/aborted lists describe state at the **source probe**, not reconstructed historical window-end state. No point estimate or quantile is silently manufactured.

## Parent/source probe

The parent writes a fresh 32-hex token, exact binding and monotonic request time into `scheduler-events/probe_command.json`. The next scheduler hook writes an atomic, bounded snapshot with the token, source epoch/probe time, complete history and drop/fault accounting. The parent reader requires its clock domain to match the binding and validates request ≤ source probe ≤ parent receipt, identity, sequence and history. A timeout cannot become successful or zero evidence; the trigger is cancelled/awaited.

Step 028 adds the fixed `/revision/events/probe` route and `revision_event_probe` worker RPC. They access the registered scheduler journal in the same interpreter/PID and verify UUID, nonce, generation and clock. A missing registry, foreign identity or active capture fails. The RPC invokes no inference or CUDA synchronization. Hooks and RPCs observing the same unchanged command return the original receipt; they cannot refresh its timestamp or consume the journal token twice. A changed command under a consumed token fails. The initial and final live probes need zero inference triggers, so all eight requests are available for commissioning. An inference-triggered hook snapshot can still precede that request's terminal event and must never imply its completion.

Snapshot persistence occurs at probes, not for every event, but hook bookkeeping, command-file reads and serialization still perturb the system and require on/off measurement. Source history is memory-resident until a snapshot; a crash before a valid snapshot leaves evidence unavailable. This is a same-host source probe, not GPU clock calibration or cryptographic identity authentication.

[Installed ID/CLI source pins](sources/vllm_0_10_2/event_ids/SOURCE_MANIFEST.json) bind eight reviewed installed files. For the commissioned nonstreaming completion API with a single string prompt, `n=1`, no beam search/best-of and no `X-Request-Id` override, payload `request_id=B` produces response ID `cmpl-B` and engine ID `cmpl-B-0`. `AsyncLLM.add_request` and the processor forward the ID without child fan-out for `n=1`. All eight live responses exactly match this rule, token counts and complete lifecycle/client time brackets. Arbitrary suffix stripping, streaming, multiple prompts, multiple choices and other APIs remain unsupported. Raw journal snapshots retain their conservative `client_request_ID_mapping=not_validated` field; the separate hash-bound commissioning join establishes this narrower validation.

## Saved CPU checks and prospective guards

[CPU fixture results](../examples/server_events/REPORT.md) cover complete shared-batch history, boundary ambiguity, overflow, pending/aborted requests and foreign scope. All remain `synthetic_simulation` with live validation false. Fake-module tests exercise the actual subclass's forwarding and probe code without importing real vLLM/Torch or using a GPU.

[Prospective specification](../examples/server_events/prospective_001/SPECIFICATION.json) binds the pinned corpus and source-manifest hashes and sets engineering choices for the **next instrumentation pilot only**:

- Ten-second review windows; twenty successful completions required for p95 review. Low-volume windows remain unavailable. This is a review floor, not a percentile precision guarantee or a change to the existing runtime classifier.
- Half-second metric cadence, a 0.75-second receipt-gap flag, exact matched IDs/actual token work and a 1.25 latency-ratio flag for engineering mismatch review. These are not scientific equivalence/significance criteria and are never applied retrospectively to the earlier paired pilot.
- Zero allowed event drops/faults; reject foreign scopes or clock probes outside their parent bracket; retain ambiguous boundaries separately.
- At most 512 total engine requests per case/session, including warmup and probe-trigger requests; future offered files must reserve that control-request allowance. There are at most 32 client requests in flight versus 16 server sequences, 60-second horizons and 30-second drain. A higher client bound permits server backlog rather than ensuring the client always prevents it; all skips/censoring must still be reported.
- Disable prefix caching in both roles and save the effective setting. The existing repeat-prompt cache behavior is not reused as a prefill reference.

The plan requires commissioning with **at most eight requests in one fresh server first**, before any challenge. Candidate challenges include a bounded 0.5/1/2/4/8 requests/s ladder with removal, selected-pressure/removal, a five-second lull followed by recurrence and an incomplete-evidence unresolved control. Rates do not establish causes; if no pressure is realized, record that outcome rather than labeling it pressure. The exact candidate selection rule/offered files, observer controls and failure injection remain unresolved. `launch_supported`, reference export, calibration and main-protocol freeze remain false. Scientific mismatch/precision/repetition limits remain unset.

```bash
python3 -m revision.scripts.demo_server_events --output /tmp/new_server_event_fixtures
python3 -m revision.scripts.prepare_server_event_pilot --output /tmp/new_server_event_spec
python3 -m unittest revision.tests.test_server_events -v
```

## Live commissioning and subsequent challenge preparation

The supervisor-owned [runner](../scripts/run_l4_events.py) reserves exactly eight attempts before sending, uses concurrency one, takes two idle event probes and four quiet barriers, and always closes its owned process group. It has a 240-second work deadline and 45-second cleanup deadline. The saved run takes zero profiler captures and creates no reference labels or fit. All 494 CPU tests pass (ten added in step 028).

Steps 029–030 prepare [v1 challenge controls](EVENT_CHALLENGE_PROTOCOL.md) and the [owned runner](CHALLENGE_EXECUTION.md). Step 031 [audits the frozen L4 attempt](../hardware/l4_20261028/CHALLENGES_REPORT.md): thirty-four arrivals hit the client cap, while all ninety admitted requests and the warmup succeed; fifteen later jobs remain uncompleted. Step 032 prepares a [separate development-informed v2 protocol](EVENT_CHALLENGE_PROTOCOL_V2.md), with a 4 requests/s ceiling, strict unchanged gates and 549 passing CPU tests. The failed v1 run is preserved. Step 033 [validates the exact snapshot fresh](../hardware/l4_20261028/CHALLENGES_V2_REPORT.md): sixteen jobs pass, all 1,536 offers plus sixteen warmups complete, and the first-off rule selects 3 requests/s. Ninety source probes pass under load; all six withheld consumer windows remain unresolved. Eight pair reviews have no flags in 22 evaluable windows, without establishing equivalence. Off-host audit/cleanup passes, with a cumulative quiet-log persistence defect explicitly resolved by original session provenance and retained for CPU-only correction in step 034. Scientific precision/mismatch limits, independent adjudication, calibration, GPU phases and capture-active savings remain unresolved.


Step 034 [corrects working-source quiet persistence](../examples/quiet_evidence_isolation/REPORT.md), preserving intentional same-episode reset history while isolating separate job outputs and rejecting overwrites. All 565 CPU tests pass (sixteen new); an archived-source regression reproduces the leak. A separate provenance index resolves all 544 historical row occurrences to 64 original barriers and their raw files; original step-033 bytes and its reproduced audit report remain unchanged. The old freeze rejects the new working source, so changed-source hardware confirmation needs a new snapshot. No GPU/SSH is used. Next step 035 audits scheduler-bound precision/cohort semantics and exposes scientific acceptance/reference criteria on CPU.

Step 035 [audits the saved bounds and cohort semantics](SCHEDULER_BOUND_ASSESSMENT.md) without new GPU use. All ninety probes/958 case lifecycles and 6,142 artifact hashes verify; 798 observations are consumer-accepted and 160 withheld observations remain offline-only. Scheduling differs from admission/completion cohorts in 40/60 and 52/60 source windows. Thirty-two raw cohorts are below twenty requests and eight are empty; a valid history does not guarantee a usable percentile. Median/max wait-bound widths are 0.2362/0.7692 ms; fourteen scientific choices stay null. Probe-time pending state is distinct from retrospective window-end reconstruction. All 579 CPU tests pass (fourteen new), with two older CPU timing fixtures stabilized and failure logs retained. Existing wait/phase mappings remain unsupported. Next step 036 implements criterion-completion and independent-assessment worksheet contracts on CPU before labels/calibration.
