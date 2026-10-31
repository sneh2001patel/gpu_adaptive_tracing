# Bounded capacity/corpus pilot — step 024

This pilot measures finite closed-loop throughput on the pinned single-worker L4 stack, pins actual prompt bytes/tokenization, exercises live metric-to-window collection and materializes candidate paired offered schedules. It does not establish saturation capacity, fit a classifier, collect independent references or execute the main matrix.

## Procedure

1. Validate the local model revision, tool versions, selected GPU UUID and sole CUDA worker using the existing inventory gate. Own the serving process group through a one-shot supervisor service.
2. Pin two deterministic pilot prompts: a short request and a repeated technical note. Save UTF-8 prompt hashes, actual tokenizer token counts/options, token-ID hashes and tokenizer/config file hashes. Require prompt plus 32 output tokens to fit the 2,048-token context.
3. Start a fresh engine/worker for each prompt band. Require session/generation/reset acknowledgement and before/after quiet evidence. Reuse model files/OS cache; engine/KV state is fresh. Within each band, run concurrency levels 1, 2 and 4 in ascending order; these cells share the band session and may have cache/order effects. Prefix-cache settings are inherited from the pinned serving stack and retained in its startup log; repeated prompts can benefit from caching.
4. Submit one declared warmup per fresh session, preserve its raw response and validate actual token usage against the pinned tokenizer. Warmup is excluded from probe throughput.
5. For each cell, admit closed-loop requests for eight seconds with at most 24 issued requests and at most the configured concurrency. Each request has a 12-second deadline and requests exactly 32 output tokens. Preserve every response/error and actual client timestamps. Allow 15 seconds for drain; cancel and await all owned clients on timeout/cancellation. A drain failure cannot pass the pilot.
6. During the eight-second horizon, collect scoped raw metrics approximately every 0.5 seconds. Persist a `LiveFeatureWindow` with actual client completions/usage and receipt-assigned queue samples. Both interval/phase metrics and GPU-utilization sampling are unavailable in this pilot. Wait through the configured window grace before closure. Sampling completeness covers accepted records, not continuous time.
7. Count only successful client completions before the horizon in throughput; retain later drain completions separately. Verify actual response prompt/output tokens for every successful request. Recheck worker barriers/zero gauges after each cell. There are at most 144 probe requests plus two warmups, two owned serving sessions, zero profiler captures, a 420-second work deadline and a separate 45-second cleanup deadline.
8. Generate candidate eight-second offered files from half the minimum positive observed cell rate, capped at 1.5 requests/s, then an integer count between 1 and 12. Save both candidate and realized offered rates. These are candidate planning inputs relative to observed probes, not calibrated capacity fractions or a guarantee of stability.
9. Each short/long pair names one immutable offered file shared by feature-collection and matched-full-trace jobs. Seed 2101 determines order within pairs. Validate exact file/content hashes through `ArrivalSchedule`. Materialize four jobs but do not execute them in this step.
10. Close every owned session, verify worker/group absence, independently inspect GPU compute/memory state and back up all artifacts/source/service files off-host.

## Interpretation and limits

The workload is closed-loop: a client slot issues its next request only after its prior request terminates. Concurrency, request caps, warmup, sequential cell order, short duration and cache effects can limit observed throughput. A flat or increasing rate does not by itself demonstrate saturation. Completion-cohort horizon rates exclude successful drain completions, while the raw records retain them. This pilot does not estimate an SLO-qualified maximum rate or percentile precision.

The repeated long note is a reproducible instrumentation workload, not a representative/disjoint calibration/confirmation corpus. Corpus hashes establish bytes, not workload representativeness. The candidate schedules are executable request files, but the paired collection jobs still need an owned arm runner and independently collected/adjudicated evidence. Intended prompt bands never become diagnostic reference causes.

The current classifier remains uncalibrated; unsupported fields remain null. No calibrated policy, reference lock, diagnostic accuracy, capture-active savings or operator benefit is established. Do not freeze the main protocol from these measurements.

## Invocation

Run in the pinned GPU environment through supervisor, with a fresh output directory:

```bash
python -m revision.scripts.run_l4_capacity --output /workspace/results/capacity_new --model-path /path/to/pinned/model --device-uuid GPU-UUID
```

CPU checks:

```bash
python3 -m unittest revision.tests.test_capacity_probe -v
```

A nonzero CLI exit retains failures and raw responses. Do not overwrite failed runs or silently retry them. Archive the exact deployed source before launch. Read `RESULT.json`, `cells.json`, `corpus.json`, `warmups.json`, each cell's request/features/audit files, `paired_schedules/PAIRS.json`, quiet receipts and cleanup records together.

## Subsequent paired validation and next step

Step 025 implements [owned paired live collection](PAIRED_LIVE_COLLECTION.md) and passes four fresh-server L4 jobs, eight scheduled requests and two full traces. The ten-artifact packet awaits actual assessment; no reference is created/locked and no threshold fitted. The original candidate files remain immutable.

Next step 026 establishes an assessment/rubric workflow and explicit coverage/mismatch limits, identifies narrower feature-profile and additional instrumentation/challenge gaps, and preserves unresolved outcomes before reference locking or fitting. The main study remains unfrozen.
