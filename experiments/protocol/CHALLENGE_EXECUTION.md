# Owned event challenge execution — step 030

This adds a bounded engineering launcher for [the step-029 packet](../examples/event_challenges/prepared_001/PLAN.json). CPU fixtures exercise the actual asynchronous episode runner with synthetic transports. **No live challenge job has run in step 030.** Read-only SSH retrieves three installed worker source files to inspect the configuration inheritance path; it neither starts serving nor invokes CUDA. Main-study freeze, calibration and reference creation remain false.

All **531 CPU tests pass** (twenty added in step 030). [Saved runner fixtures and checks](../examples/challenge_runner/REPORT.md) retain two successful synthetic episodes and one expected response-ID failure; every owned fake target closes with no active requests. These are not live GPU results.

## Lifecycle and accounting

`run_campaign` accepts the exact prepared job order and schedule bank. Each job reserves all offered requests plus one warmup before startup. Each HTTP attempt is durably charged before dispatch and never refunded. Repeated reservations, extra attempts and campaign work above 3,612 requests fail. Each job creates a fresh owned server/session/generation with cache explicitly off, verifies inventory and actual worker configuration, sends exactly one declared warmup, checks surrounding quiet, then starts exact offered playback. A failed job stops the campaign without retry; remaining jobs are explicitly uncompleted. Four completed ladders with no eligible primary rate skip all twelve dependent jobs.

The actual `SchedulePlayback` driver preserves 32-client/16-server bounds, 50 ms admission lateness, 30-second request/drain limits, skips, failed/censored terminals and pending-at-horizon accounting. Raw completion records use the actual client coroutine start/receipt times; response ID, model, single terminal choice and 1,072/32/1,104 token counts are checked. The wire overlay is identical in both roles. Every response body is saved with a hash; work normalization does not replace these raw records. No classifier or profiler is invoked.

Each job has a 240-second work deadline and 45-second owned-cleanup deadline. Cancellation and drain failures await request/sampling/probe tasks before closing the owned process group. Job/root manifests retain failed artifacts and cleanup receipts. Unconfirmed cleanup fails the campaign even when all HTTP requests succeeded. Existing deployments/management services and historical source archives are not modified.

## Actual cache configuration

`/experiments/configuration` invokes only `revision_configuration`; arbitrary method names are not accepted. The worker reads its actual `vllm_config.cache_config`, scheduler and parallel settings, rather than returning the launch argv. A fresh bounded token binds nonce/generation/PID/UUID/clock and parent request/worker read/parent receipt times. At most four configuration tokens are accepted per worker. Replay, active capture, foreign scope and non-boolean cache flags fail. The receipt is explicitly **not a CUDA synchronization barrier**; the existing quiet-barrier RPC remains separate.

The installed v1 GPU worker inherits the v1 base, which invokes the shared worker base to retain the configuration. Three read-only source copies are preserved under `sources/vllm_0_10_2/worker_config`; the engineering freeze binds their exact installed hashes together with earlier ID/CLI/scheduler pins. CPU fake-module tests exercise the actual new worker method and fixed route without importing GPU libraries. Live verification of this new RPC remains a step-031 requirement.

## Fixed probes and consumer decisions

An independent asynchronous probe task runs at each prepared offset; dispatch never awaits the probe. No-op markers occupy the off-role offsets without an event RPC. An active previous probe or an offset missed by more than 50 ms fails instead of shifting the next probe. Initial warmup history and final complete warmup-plus-request history are checked against exact IDs and client brackets. Full-source snapshots remain intact in withheld controls.

This execution supplement sets each consumer decision deadline to its ten-second window end **plus 750 ms**. This is an additional prospective engineering choice, saved in the engineering freeze before any GPU execution. Only receipts already received by that fixed deadline can support the decision. Late owner execution beyond 50 ms returns unresolved; it cannot claim an earlier online decision. The 10–40s consumer mask returns null bounds/diagnosis on intersecting windows. Missing, invalid, future and foreign receipts remain unresolved; a final forensic receipt cannot backfill earlier decisions. No availability result is treated as a calibrated diagnosis.

Metric sampling uses the existing serialized half-second horizon sampler, with raw receipts and explicit skips/errors. It ends at the 60-second horizon; there is **no continuous drain metric trajectory**. Work/drain accounting and final surrounding quiet receipts remain available. This limitation is explicit in the freeze supplement; queue removal is sampled during the final in-horizon no-arrival phase. The largest event snapshot is bounded by the existing 512-request/4,096-event budget; final collection includes the warmup. Real under-load RPC latency and observer effects remain unvalidated.

## Paired engineering review

Raw ID/token/admission/hash mismatches make the whole pair ineligible. Fixed ten-second offered-arrival cohorts compare identical complete IDs, including latencies returned in drain. Nearest-rank p95 requires twenty matched successful requests; sparse/no-arrival cohorts and zero denominators are unavailable. A symmetric ratio above 1.25 is a review flag. An unflagged result establishes no equivalence or negligible overhead. Two reversed-order blocks remain engineering controls, not a statistically powered reference design.

The primary uninstrumented ladder alone selects a rate using step 029's scoped raw queue/work gates. Collector-on and later cases cannot change it. If client caps, lateness, metrics or workload failures prevent exact complete work, preserve the failure and stop; do not hide skipped offers or compress arrivals. A no-pressure candidate is a valid engineering outcome and gives no cause label.

## Engineering source snapshot and live handoff

`freeze_event_challenges` requires a passing CPU log, validates the prepared artifact hashes, and creates an immutable source archive plus `FREEZE.json`. The descriptor binds code/tests, configuration, reviewed installed source bytes, protocol/supplement, packet files and CPU log. The launcher checks local source/packet hashes and installed vLLM source pins **before starting a server**. Changed files require a new tested snapshot, not rewriting an old archive. This is an engineering source snapshot; `hardware_validated`, `study_ready` and `protocol_frozen` remain false.

```bash
python3 -m experiments.scripts.demo_challenge_runner --output /tmp/new_runner_fixtures
python3 -m experiments.scripts.run_l4_challenges --help
```

Step 031 should deploy the frozen snapshot through a one-shot supervised service to a fresh workspace, verify idle GPU/model cache and execute the bounded campaign without changing guards. Independently audit every raw response, source/metric/probe/configuration receipt, actual versus offered work, paired review and PID/group/0 MiB cleanup; copy all artifacts off-host. Preserve failures and no-pressure outcomes. No scientific diagnosis, source-loss claim, capture-active saving or main-study result follows from passing the CPU runner checks.
