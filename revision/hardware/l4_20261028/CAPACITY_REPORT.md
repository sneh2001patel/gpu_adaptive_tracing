# Bounded L4 capacity/corpus pilot — step 024

Completed 2026-10-28. [Raw result](capacity_001/RESULT.json) passes the declared six-cell engineering pilot. This adds live client/queue feature collection to the previous [discovery](REPORT.md) and [capture feasibility](ACTIVITY_REPORT.md) checks. It is not maximum-capacity calibration or the main experiment.

## Configuration and corpus

Same NVIDIA L4 UUID `GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb`, pinned vLLM 0.10.2/Nsight 2026.3.1 and Qwen2.5-7B-Instruct revision `a09a35458c702b33eeacc393d103063234e8bc28`. No profiler capture was started. Model files from the earlier pinned cache were reused; this step hashes tokenizer/config files rather than rehashing all model weights. Exact source/service configuration is in [the deployment archive record](capacity_024_deployment/source_archive.json).

[Corpus](capacity_001/corpus.json): actual UTF-8 prompts, prompt hashes, tokenizer options/counts and token-ID hashes. Short prompt: **17 input tokens**. Long repeated technical note: **1,072 input tokens**. [Tokenizer file hashes](capacity_001/tokenizer_files.json). Every successful response, including the two warmups, matched the tokenizer count and reported **32 output tokens**.

Two fresh owned servers were used, workers **3926 → 4387**, with different nonces/generations/reset acknowledgements. Each band had one warmup followed by concurrency 1, 2 and 4 in ascending order. Cells within a band shared the worker. Each cell had an eight-second horizon, a 24-request cap, a 12-second request deadline and a 15-second drain/window grace. The inherited serving configuration had **prefix caching enabled**; repeated prompts can reuse cached prefixes. Fresh engine/KV state is created per band, not per cell; model/OS cache is reused.

## Observed client completions

[Cell records](capacity_001/cells.json); raw requests/responses and persisted feature windows are in each band/concurrency directory.

| Prompt band | Concurrency | Issued / succeeded | Successful before horizon | Successful drain completions | Horizon completion rate |
|---|---:|---:|---:|---:|---:|
| Short | 1 | 5 / 5 | 4 | 1 | 0.50 requests/s |
| Short | 2 | 10 / 10 | 8 | 2 | 1.00 requests/s |
| Short | 4 | 20 / 20 | 16 | 4 | 2.00 requests/s |
| Long | 1 | 5 / 5 | 4 | 1 | 0.50 requests/s |
| Long | 2 | 10 / 10 | 8 | 2 | 1.00 requests/s |
| Long | 4 | 18 / 18 | 14 | 4 | 1.75 requests/s |

All **68 probe requests plus two warmups succeeded**, with zero request errors or drain cancellations. **54** probe completions fell before their horizon and **14** finished during drain. No cell reached its 24-request cap. All six windows persisted measured request usage/completion statistics and 16 accepted queue samples each: **96 raw metric receipts** total. Unsupported wait/phase fields and GPU-utilization measurements remain null. The classifier and stopping policies were not run.

Rates increase through concurrency 4, so this grid does **not establish a capacity ceiling**. Closed-loop admission, short windows, fixed cell order, warmed repeated prompts and prefix caching limit interpretation. This is not an SLO-qualified capacity estimate, representative prompt corpus, diagnostic result or precision/sensitivity study. In particular, a long prompt does not establish prefill-dominated service.

## Candidate paired schedules

[Pair manifest](capacity_001/paired_schedules/PAIRS.json) materializes two immutable eight-second offered files, with two arrivals each (0.25 requests/s). The rule is half the minimum positive observed completion rate, capped and converted to a bounded integer request count. These are candidate plumbing workloads, not stress conditions normalized to calibrated capacity.

Each prompt band has feature-collection and matched-full-trace jobs referencing exactly the same file hash; seed 2101 determines within-pair order. **Four jobs are materialized but none executed**. There is no independent adjudicated reference, calibration fit, classifier threshold or frozen main protocol.

## Integrity and cleanup

[Saved audit](CAPACITY_VALIDATION.json) verifies **379 artifact hashes**, **70 deployed source fingerprints** against the frozen archive, all response hashes/usage, horizon/drain denominators, measured missingness, 96 raw scoped metrics and **20 fresh barrier receipts**. Candidate schedules regenerate byte-identically and pass `ArrivalSchedule` validation. [Audit script](capacity_024_deployment/validate_backup.py). All **439 CPU tests pass**, including **12 new checks**; [suite](capacity_024_deployment/cpu_suite.log), [focused tests](capacity_024_deployment/cpu_focused.log).

[Independent cleanup proof](capacity_post_cleanup_checks.json) confirms both parents/groups/workers absent, an empty compute inventory and **0 MiB GPU memory**. Source, raw results, corpus, schedules, supervisor configuration and logs are backed up locally. Owned jobs are stopped; **the rental instance remains running**. No driver/management service changes were made.

Next: bind the candidate pairs to the owned exact-arrival runner and collect independent request/server/full-trace artifacts for a bounded paired pilot. Resolve mismatch and adjudication/locking before fitting; do not launch the main matrix from these probe rates.
