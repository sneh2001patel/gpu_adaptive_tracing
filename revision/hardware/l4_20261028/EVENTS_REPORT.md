# L4 scheduler-event commissioning — step 028

Completed 2026-10-28 on the authorized NVIDIA L4, UUID `GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb`. **Commissioning passed.** This is an instrumentation feasibility check with eight sequential requests; it does not establish diagnostic accuracy or scientific results for the paper.

## Observed results

| Check | Actual result |
|---|---|
| Serving stack | vLLM 0.10.2; Qwen2.5-7B-Instruct revision `a09a35458c702b33eeacc393d103063234e8bc28`; single synchronous worker |
| Owner | Fresh serving parent 6983, CUDA owner/scheduler 7200; matching nonce/generation/UUID/clock |
| Effective config | Prefix caching false; maximum 16 sequences; async scheduling false |
| Inference budget | Exactly 8 attempts, all HTTP 200; concurrency 1; zero extra warmups or inference probe triggers |
| Actual work | Four 17-token and four 1,072-token prompts; every response produces exactly 32 tokens |
| Lifecycle | All 8 admissions, 8 first-positive schedules and 8 length-capped terminal events; zero drops/faults |
| Client/engine join | Exact submitted `B` → response `cmpl-B` → engine `cmpl-B-0`; every hook bracket inside its client request bracket |
| Source probes | Two fresh fixed idle RPC probes; initial history empty, final history complete; source clock within each parent request/receipt bracket |
| Quiet checks | Four fresh token-bound CUDA barriers with surrounding raw zero running/queue gauges |
| Captures/references | Zero new profiler captures; zero references created; no calibration or classifier execution |
| Cleanup | Parent/worker/process group absent; empty compute process list; GPU memory 0 MiB; supervisor EXITED |

The descriptive engine-admission-to-first-CPU-scheduling lower bounds span 0.308289–0.759223 ms; upper bounds span 0.424267–1.160948 ms. These are host hook interval bounds, not GPU start times or the existing `request_wait_p95_ms` metric. Eight sequential completions cannot satisfy the prospective twenty-completion p95-review floor, demonstrate pressure/recovery, or measure observer overhead. Quiet checks describe their observation brackets only.

## Artifacts and verification

- [Raw result](events_001/RESULT.json), [request plan](events_001/request_plan.json), [responses/usage and client times](events_001/requests.json), [exact ID joins](events_001/joined_requests.json).
- [Initial probe](events_001/initial_probe.json), [final probe](events_001/final_probe.json), [delay bounds](events_001/scheduler_delay_bounds.json), [actual startup config](events_001/session-0/scheduler-events/startup.json).
- [Quiet receipts](events_001/quiet_evidence.json), [owned exit receipt](events_001/session-0/exit.json), [independent cleanup checks](events_post_cleanup_checks.json).
- [Artifact manifest](events_001/artifact_manifest.json), [source archive fingerprints](events_028_deployment/source_archive.json), [independent backup audit](EVENTS_VALIDATION.json), [CPU test log](events_028_deployment/cpu_suite.log).
- [Installed ID/CLI source review](../../protocol/sources/vllm_0_10_2/event_ids/SOURCE_MANIFEST.json), [audit script](events_028_deployment/validate_backup.py), [service log](events_028_deployment/events_service.log).

All 494 CPU tests pass, including ten new checks. Independent local verification checks 46 artifact hashes, 142 frozen archive entries, 81 runtime source entries and eight installed ID/CLI source pins. Installed supervisor wrapper/config copies match the preserved deployment files. Source archive SHA-256: `00fcdcebaeae192b524d30744926d300c3abe315386256982c44021e538e5f4b`.

The isolated `/workspace/gpu_adaptive_tracing_step028` deployment uses a one-shot supervisor service with restart disabled. The owned runner closes only its serving group; management services and earlier deployments are preserved. Raw outputs, service files, logs and the exact archive are backed up off-host in this repository. The rental itself remains running.

## Remaining work

Step 029 must prepare exact prospective challenge schedules, a deterministic pressure-selection rule, paired observer-on/off/cache controls and a safe incomplete-evidence control before further GPU execution. The CPU event collector is now commissioned for the tested configuration; its effects under concurrency, event/probe budget exhaustion on hardware, aborts and challenging pressure/lull/recovery behavior remain unvalidated. Streaming, multiple prompts/choices, other APIs and distributed workers are outside the validated ID join.

No GPU phase attribution, frontend/later-preemption waiting, active-capture duration, calibrated diagnosis, reference adjudication or main-study freeze follows from this check. Scientific precision/mismatch/repetition limits remain unset. Existing paper results and sparse prior pilots gain no new diagnostic validity from commissioning.
