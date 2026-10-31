# Step 024 — bounded capacity/corpus runner and live L4 pilot

Completed: 2026-10-28. CPU implementation/tests followed by one supervised six-cell L4 engineering pilot.

## Completed checklist

- [x] Pin actual prompt bytes, tokenizer counts/options, token-ID hashes and tokenizer/config fingerprints.
- [x] Implement bounded closed-loop concurrency 1/2/4 probes, eight-second horizons, 24-request caps, request deadlines and drain/cancellation cleanup.
- [x] Validate actual token usage, retain raw responses and distinguish horizon completions from drain completions.
- [x] Collect real scoped raw metric receipts and client completions into persisted live feature windows with unsupported fields unavailable.
- [x] Use two fresh owned workers, declared warmups and repeated server/worker quiet checks; preserve cache/state limits.
- [x] Materialize deterministic exact offered files shared by paired job roles with seeded order, without executing reference jobs.
- [x] Pass 439 CPU tests, including 12 new bounds, token-mismatch, cancellation/drain, horizon accounting and paired-byte checks.
- [x] Freeze deployed source, run the bounded pilot, independently verify cleanup and back up/audit all raw outputs.
- [x] Update progress and the CAIN revision plan.

## Implementation and evidence

[Runner primitives](../feasibility/capacity.py), [CLI](../scripts/run_l4_capacity.py), [operating protocol](../protocol/CAPACITY_AND_CORPUS_PILOT.md), [hardware report](../hardware/l4_20261028/CAPACITY_REPORT.md), [validation](../hardware/l4_20261028/CAPACITY_VALIDATION.json), [raw result](../hardware/l4_20261028/capacity_001/RESULT.json).

The corpus contains 17-token and 1,072-token prompts. Actual response usage matches pinned tokenization and 32 output tokens for every request. All six cells pass: **68 probe requests plus two warmups**, zero request errors or drain cancellations. **54 completions occur before horizon and 14 during drain**. Six live windows persist **96 raw metric receipts**, actual client usage/statistics and explicit missing interval/phase/GPU-utilization fields. No classifier, policy or profiler capture runs in this step.

Observed horizon rates at concurrency 1/2/4 are 0.5/1.0/2.0 requests/s for the short prompt and 0.5/1.0/1.75 for the long prompt. The rate still increases through concurrency 4; no maximum capacity is established. Prefix caching is enabled, prompts are repeated, and cells share the band worker in ascending order. These are bounded throughput/collection observations, not diagnostic or representative performance findings.

The [pair manifest](../hardware/l4_20261028/capacity_001/paired_schedules/PAIRS.json) materializes **four jobs** over two exact offered files, each with two requests over eight seconds. The candidate offered rate is 0.25 requests/s, derived prospectively from the probe-rate rule. The feature and full-trace roles within each pair share exact bytes/hash and require fresh resets. Jobs are **not executed**, and these low-rate candidates are for collection plumbing rather than challenging incidents or calibrated capacity fractions.

The audit verifies **379 recorded artifact hashes**, **70 source fingerprints**, all actual response usage/denominators, 96 raw metrics, 20 fresh worker barriers and deterministic paired bytes. Both serving parents/groups/workers are absent and GPU memory returned to 0 MiB. Artifacts/source/service files are backed up locally. The rental itself remains running.

## Limits

Closed-loop finite probes, two repeated prompts, prefix caching, fixed cell order, short horizons and sparse completions do not establish saturation, SLO capacity, percentile precision, independence or generality. No independent reference, fitted classifier, threshold sensitivity, diagnostic effectiveness, capture-active savings or operator benefit is claimed. The wider eighteen-job calibration collection proposal is still a preparation plan, not a completed dataset. Main-study readiness and protocol freeze remain false.

## Next step — 025

1. Bind candidate pair jobs to the owned exact-arrival arm runner with unchanged offered files, fresh resets and measured live windows.
2. Collect independent request/server/full-trace evidence and prepare a blinded adjudication packet, retaining run mismatch, alternative causes and unresolved outcomes.
3. CPU-test that paired collection path, then execute one bounded L4 paired pilot. Reference locking and fitting follow evidence adjudication; do not start the main matrix yet.

The owned GPU jobs are stopped. The rental remains running, and the next live paired pilot will need GPU access again.
