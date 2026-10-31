# Step 002 — Shared stopping semantics, unknown evidence, recovery, and budgets

Date: 2026-10-27. Status: completed for the shared engine, RQ4 replay, and RQ1 label-stability helpers. No GPU experiments or historical table regeneration.

## Completed work

- [x] Added `revision/tracing/policies.py`, an incremental, standard-library-only policy engine with explicit configuration, evidence observations, and decisions. It has no expected-label inputs.
- [x] Reduced default comparisons to five distinct policies: FB, RFB, SS, CR, and HS. `marginal_utility_stop` is a compatibility alias for SS with K=2, even when the general SS configuration uses another K. The alias is excluded from RQ4's default replay and live-fixed-duration job lists.
- [x] Added an explicit concrete-label vocabulary. Unknown, absent, healthy/no-incident, unrecognized, and provisional labels cannot satisfy diagnosis stability. A stable label remains a consistency observation, not proof of correctness.
- [x] Reset stability on unknown or unavailable new evidence. Reusing a diagnosis evidence ID does not count as another diagnostic observation. Repeated decision-window IDs are rejected before they can inflate recovery streaks.
- [x] Required both finite positive latency ratio and valid GPU utilization, plus explicitly observed absence of suspicion, for a recovery window. GPU utilization of zero is valid; a missing reading or zero latency ratio is not recovery. Recovery requires consecutive qualifying windows, default 2, configurable with `--recovery-windows`.
- [x] Applied the hard burst-attempt cap to every policy, including RFB when N exceeds the cap. Unique capture IDs consume budget; cached IDs and cheap-only observations do not. Failed capture attempts should receive an ID and consume budget while providing no fresh diagnosis evidence. A terminal decision is sticky and prevents further attempts.
- [x] Distinguished fixed/repeated completion, diagnosis stability, recovery, hybrid completion, budget exhaustion, and end-of-input. A real policy condition achieved on the final allowed attempt takes priority over exhaustion. Exhaustion and end-of-input do not count as meeting a policy condition.
- [x] Replaced RQ4's independent policy loops with the shared engine. Replay starts at the first suspicious window, keeps intervening windows, and does not activate on an entirely healthy stream.
- [x] Added stop reason, policy version, outcome flags, streaks, and provenance to replay output. Duration is summed over unique charged capture-window proxies. Defaults write corrected replay into `revision/analysis/`, separate from historical outputs.
- [x] Corrected the premature-stop proxy to inspect the final label of an intentional policy stop instead of merely asking whether any earlier label was correct. Kept raw expected-label agreement separate from successful policy completion. Later suspicion is explicitly identified as a proxy; actual reactivation has not been measured.
- [x] Updated both RQ1 runners to use the shared concrete-label stability helper. The microbenchmark runner now records `budget_exhausted` when its existing automatic capture-attempt limit is reached.
- [x] Added CPU-only engine, runner, replay, and command-line integration tests; updated the main plan and cumulative progress file.

## Policy definitions implemented

| Policy | Condition | Notes |
|---|---|---|
| FB | First capture attempt completes at a decision boundary | Can stop unresolved; fixed cost does not establish sufficient evidence. |
| RFB(N) | N unique capture attempts | If the cap is smaller than N, stop at budget exhaustion. |
| SS(K) | K consecutive fresh concrete-label observations agree | Unknown, cached, or missing evidence resets the streak. K must be at least 2. |
| CR | Sustained valid recovery | Does not independently guarantee a concrete or correct diagnosis. |
| HS | Both concrete-label stability and sustained recovery | Both conditions must hold at the same decision point. |

The engine accepts only observations already available to the caller. Its evidence IDs are a bookkeeping boundary, not a verification that an actual T2 capture occurred. The future online controller must supply genuine capture IDs, fresh diagnosis evidence, and availability timestamps.

## Replay interpretation

New results identify `policy_version=stopping_v2` and `evidence_mode=offline_replay`. For legacy CSVs without explicit `capture_id` / `diagnosis_evidence_id`, each replay window is treated as a hypothetical burst and fresh observation. This assumption supports testing stopping mechanics; it does not reconstruct missing kernel evidence, remove truth leakage from historical labels, or measure actual profiler cost.

Explicit blank capture/evidence IDs mean no capture/no new diagnosis. `diagnosis_is_new=0` also marks a cached label. Repeated capture IDs are charged once. Recovery-only windows remain in the timeline. Repeated window updates are disallowed in the engine.

`policy_condition_met` means that the selected policy's rule fired; FB, RFB, and CR can meet their rules without a sufficient diagnosis. `successful_stop` additionally requires a concrete final label matching the controlled expected label. This is still controlled agreement, not independently verified root-cause accuracy. `top1_correct` preserves raw terminal-label agreement even for an inconclusive episode; use the outcome columns when interpreting it.

The legacy field `re_escalation_needed` is retained for existing consumers but equals `later_suspicion_proxy`. It must not be described as actual reactivation. Existing table/figure generators and composite-score interpretations require the broader artifact/metric audit before publication use.

Replay currently evaluates the first episode only. Episode resets, cooldown, changed-cause retriggers, and full multi-episode evaluation remain future controller work.

## Validation

```bash
python3 -m unittest discover -s revision/tests -v
python3 -m py_compile revision/tracing/policies.py RQ4/scripts/analyze_policies.py RQ4/scripts/run_live_policy_validation.py RQ2/scripts/make_baseline_comparison.py RQ1/scripts/run_microbenchmarks.py RQ1/scripts/run_vllm_smoke.py
git diff --check
```

35 CPU-only tests pass: the original classifier suite plus 25 new engine/runner/replay checks. Coverage includes alias equivalence over 256 four-observation label sequences; unknown/cached resets; missing/invalid metrics; sustained recovery and gaps; all-policy budget enforcement; final-burst success; duplicate IDs; horizon censoring; stable-but-wrong labels; healthy nonactivation; matching incremental/replay decisions; and a subprocess CLI replay using temporary CSVs. Temporary outputs are deleted by the tests.

## Remaining limits and next step

No live GPU policy validation has occurred. Cheap-metric runner streaks are still provisional consistency fields; the microbenchmark runner still uses its existing collector rather than the new episode engine. Real capture availability, classifier calibration, independent references, multi-episode behavior, and runtime perturbation are pending. Old six-policy rankings and perfect agreement results remain historical.

**Next: step 003 — artifact-to-claim inventory and timing audit.** Document which claims need replacement, which raw observations can be reused, and which timings include startup/export overhead. Create a new numbered report and update `revision/PROGRESS.md` and `CAIN_REVISION_PLAN.md`.
