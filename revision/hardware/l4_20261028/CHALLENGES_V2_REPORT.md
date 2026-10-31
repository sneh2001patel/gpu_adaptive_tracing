# Fresh v2 L4 engineering validation — step 033

Completed 2026-10-28. The exact step-032 engineering archive was deployed to a fresh `/workspace/gpu_adaptive_tracing_step033` and executed once through `revision-l4-challenges-v2-033`, with automatic restart disabled. No runtime source, offered schedule, threshold, budget or frozen descriptor was changed. The earlier v1 failure remains failed and unchanged.

## Results

**All sixteen jobs pass the frozen engineering checks.** All **1,536 scheduled offers** complete, together with sixteen warmups: **1,552 successful attempts** against the 1,932-attempt maximum. There are zero capacity/scheduler/horizon skips, request errors, censors or aborted offers. Exact response IDs, model, 1,072 prompt tokens and 32 output tokens verify; matched-pair admissions and completion deadlines pass.

| Family | Jobs | Offers per job | Scheduled completions |
|---|---:|---:|---:|
| Rate ladder | 4 | 84 | 336 |
| Pressure then removal | 4 | 95 | 380 |
| Lull then recurrence | 4 | 110 | 440 |
| Consumer evidence-gap control | 4 | 95 | 380 |

The first collector-off ladder selects **3 requests/s**, the lowest fixed level with the required sampled-positive queue streak. Each of its five levels has sixteen scoped receipts and passes coverage. The 0.5/1/2 levels lack a qualifying streak; 3/4 qualify. The first ladder's whole offered denominator is complete. This is a new eligible development outcome, not a repair of v1 or independent confirmation.

The campaign saves **1,920 queue receipts**, **ninety real event probes**, and **2,904 events in the ten collector-on final histories**, with zero event drops/faults. Actual worker RPCs verify cache disabled in every role. All sixteen jobs use distinct fresh workers. The source history and client/engine ID/clock joins pass under these loads. These are host scheduler events, not exclusive GPU phase measurements.

Descriptive phase checks show 49/60 positive queue receipts during every thirty-second pressure phase. Each recurrence case has 19/30 positive receipts during initial pressure and 29/40 during recurrence. Positive samples persist briefly into the lull/removal periods, so their names must not be treated as measured healthy recovery. Peak client inflight is at most 28; no requests remain pending at the sixty-second horizon and no completions occur after it. These are observations from this campaign, not new selection criteria.

Across 96 consumer windows, **54 have bounds available**, **36 collector-off windows stay unresolved for missing event receipts**, and **six deliberately withheld windows stay unresolved**. Raw history remains complete in the withheld runs. No consumer diagnosis is emitted, no late/future receipt is used to repair a deadline, and these outcomes do not establish diagnostic accuracy.

All eight paired reviews are recomputed: six collector-off/on pairs and two complete/withheld consumer pairs. Of 48 offered ten-second cohort windows, **22 contain at least twenty matched requests**; the other 26 cannot supply the prescribed p95 comparison. No evaluable window exceeds the preset symmetric ratio flag of 1.25; the largest ratio is **1.0528**. The two consumer pairs have collection enabled in both roles and are not additional off/on comparisons. Two reversed blocks and no review flags do not establish statistical equivalence or a negligible observer effect.

## Audit, backup and cleanup

The [independent audit](CHALLENGES_V2_VALIDATION.json) verifies **6,142 result artifact hashes**, **184 frozen entries**, **1,520 runtime source-manifest entries**, twelve installed vLLM source pins, eleven full model-file hashes, exact work accounting, source prefixes/final lifecycles, consumer deadlines, all paired results and **64 unique quiet barriers**. Each job has four barriers from its own worker. Raw response bodies and metrics remain preserved. [Machine summary](CHALLENGES_V2_SUMMARY.json); [descriptive phase delivery](CHALLENGES_V2_DELIVERY.json); [raw campaign](challenges_v2_001/RESULT.json).

An independent post-exit check confirms all sixteen parent processes, workers and process groups absent, an empty compute-process list and **0 MiB GPU memory** at 17:07:48 UTC. The one-shot service is EXITED. The rental remains running; no rental stop or destruction was performed. No new profiler capture, calibration, classifier output or reference is created.

The full output and installed service files are copied off-host in [the backup](challenges_v2_033_deployment/results_backup.tar.gz). Its remote/local SHA-256 matches: `90fff5eb8864fddf66d23c345a1bec08841469f10a9ae8a291e8bbc7d751aa54`. Source archive SHA-256 remains `a90db959b3abc2f2c472c0b450c68e8fcc89cb0ef7ecb06810ec892421f8aa51`; descriptor remains `60587c553e979b1103497f10685241dbfe282980565e19b723bfc59cf8972ec9`. Deployment, audit programs, installed wrapper/configuration, preflight and cleanup receipts are in [the deployment directory](challenges_v2_033_deployment/).

## Persistence limitation discovered during validation

The frozen `OwnedLiveActivity.quiet_evidence` list accumulates across jobs. Later per-job `quiet_evidence.json` files therefore contain historical rows whose raw metric filenames are relative to their original job. There are **480 repeated historical rows**, in addition to 64 unique barriers. Treating all those rows as current-job evidence would be incorrect; copying a later job alone would not make its historical relative paths self-contained.

No saved bytes were repaired. The independent audit resolves every row through its original session nonce, generation and worker PID, verifies repeated rows are identical, validates each barrier against that original binding, and checks the raw hashes/zero queue gauges in the original directory. All original directories are present in the backed-up whole campaign, so these rows remain verifiable. This passes whole-campaign provenance review with an explicit packaging limitation; it does not validate per-job isolation. A CPU regression and source fix are required before future campaigns, followed by a new snapshot if executing again.

## Limits and next step

This is one development-informed campaign on one L4, one pinned model and serving stack, with only two reversed-order blocks. Complete delivery at the specified rates/durations establishes this bounded outcome, not a universal capacity guarantee. Point queue samples do not prove continuous pressure, healthy recovery or causal diagnosis. Scientific precision/mismatch tolerances, independent reference adjudication, feature acceptance, classifier calibration, capture-active timing, sensitivity and main-study freeze remain pending.

**Step 034 is CPU-only:** isolate quiet evidence by owned episode, add a meaningful multi-job regression with distinct bindings/raw filenames, and audit the untouched step-033 history through an explicit provenance index. Then assess scheduler-bound precision and cohort semantics against separately declared scientific criteria before reference/calibration work. A GPU is not needed for this next fix. The frozen runtime's earlier 549-test pass is carried forward; this step validates unchanged execution with live artifacts and checks new deployment/audit syntax, rather than claiming another full CPU-suite run.
