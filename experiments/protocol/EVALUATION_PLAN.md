# Evaluation plan (proposal §10 step 8)

Status: **frozen 2026-10-29**, before any evaluation session existed. Thresholds and rule settings below may not change without a new version; anything evaluated before a change becomes exploratory (CALIBRATION_PLAN.md §4).

## 1. Frozen configuration

| Item | Value |
|---|---|
| Thresholds | `cases/checks/thresholds_study_rule_v2_calibrated_2026-10-29.json`, SHA-256 `6cd8becf0bc9f45330875cd5dc523252d0794edb1613f90263d3d01f443f961a` |
| θ_L, θ_w, θ_u, θ_p | 1.95, 1, 0.5768, 0.5 |
| θ_g, θ_b | 0.769, 0.7373 |
| θ_r | ∞: `kernel_hotspot` not separable from load (§4 option 4), so the label never fires |
| Trigger | latency ratio ≥ 1.5 for 2 consecutive 1 s windows (proposal default) |
| Policies | SS K = 2; CR M = 2, recovery latency ratio ≤ 1.10 and GPU utilization ≤ 60%; HS = SS ∧ CR; cap B = 6 bursts of 2 s |
| Seeds | 201 and up, one seed per block |

Author decisions at the freeze (2026-10-29):
1. θ_r is not separable. No kernel-hotspot label; this is reported as an RQ1/RQ2 finding.
2. θ_L stays pooled (1.95), although #7619 and #3087 set it and the controlled engine stall (median L 1.81) rarely passes it.
3. θ_p margin 0 is accepted: vLLM 0.11 queues rather than preempts under KV pressure, so KV pressure is detected through KV usage only.

## 2. Units and arms

**Units per block:**
- **Real cases, bug side:** #6240, #7619, #7592, #25418, #3087. #19732 is excluded, as it was not reproduced under serving.
- **Controlled conditions:**
  - the six calibration conditions (overload, KV, engine stall, lull, shift, overlap);
  - persistent incident: overload until the horizon, with no recovery tail;
  - incomplete evidence: overload with heavy evidence withheld from the controller.

Each unit gets its own healthy baseline per block, recorded on the same host as its arms. Real cases take theirs on the **fixed side** at the healthy rate: the last known-good version, as in steps 6 and 7.

**Correction (2026-10-29, 6:30 PM EDT, before any analysis).** The first version of this plan said "bug side". On #25418 that baseline was unusable: p95 was 95 s, 158 of 258 requests were censored and `/metrics` was blocked, because the bug saturates the server even at the healthy rate. The sessions run against bug-side baselines (#7619, #25418 and #3087, block 201, a few sessions each) are kept under `evaluation_superseded_bugside_baseline/` and are not analysed.

**Hosts.** To finish within the author's deadline, blocks 201–202 ran on four L4 hosts:
- the calibration host, with driver 615.71;
- three hosts with driver 595.x.

All four used Nsight 2026.3.1. Each block directory records its host in `hosts.txt`. Block 203 and further blocks are not run (author decision, 2026-10-29). **Revised at 11:55 PM EDT, before any analysis:** block 203 runs, on the same four hosts, once blocks 201–202 finish. Blocks 204–205 are decided after writing, under the rule in §4: on between-block variance, not on the direction of results. Block 203 splits its controlled conditions across all four hosts, each with its own baseline:
- #4: overload, KV, engine stall, lull;
- #3: persistent, shift;
- calibration host: overlap;
- #1: withhold.

**Runner fault (2026-10-29, 8:55 PM EDT, before any analysis).** On host #4 the server of #3087's block-202 fixed-side baseline outlived its session: `nsys shutdown` and the kill of nsys left it orphaned, holding 20 GB of GPU memory. Every later session on that host failed at server start (out of memory): 201/3087/SS, all seven 202/3087 arms, and the 202 controlled baseline. The failed sessions are kept under `evaluation_failed_orphan_server/` on host #4. From then on, the queue waits for the GPU to be free before each session and kills a leftover server after 60 s (`gpu_clear`). The reruns:
- **#3087:** reruns on host #1. Block 202 runs there in full, with a new baseline. 201/3087/SS runs there against host #4's 201 baseline; its other six 201 arms ran on #4.
- **202 controlled, part B:** restarts on host #4.
- **201/7592/FIX3:** reruns on host #1. It failed with a server-start timeout.

**Second orphan (9:05 PM EDT, on host #1).** An orphaned v055 engine worker from 202/7592/CR held the GPU there. The first `gpu_clear` pattern matched only server command lines, so it missed the worker, and the queued reruns failed at start. The pattern now matches any process run from a case environment's Python. The worker was killed at 10:02 PM, and the reruns restarted with 202/7592/CR added.

The same worker had also failed both #6240 baselines, at 9:16 PM, so #6240 had no arms at all. Separately, 201/3087/CR had failed on host #4 at 6:45 PM; the first rerun script wrongly marked it done. Both reran on host #1 from 11:34 PM, and #6240's failed baselines are kept under `evaluation_failed_orphan_server/`.

**Arms**, each on a fresh server with the same offered schedule:

| Arm | Meaning |
|---|---|
| U | unprofiled: no nsys, no controller |
| NT | cheap telemetry only |
| FIX1 | fixed budget of 1 burst |
| FIX3 | fixed budget of 3 bursts |
| SS | stability stop |
| CR | recovery stop |
| HS | stability and recovery |

Arm order is shuffled per (seed, unit) with `random.Random("<seed>:<unit>")` and recorded in `arm_order.txt`.

**Not run live:**
- FIX(2) and FIX(6), and the REF full-horizon capture: no full-horizon capture is implemented in the external runner.
- The two prior-work comparators (§5.1): not implemented.

Each of these is reported as not run.

**Per block:** 13 units, about 97 sessions, about 10 L4 hours.

**Baseline integrity exclusion (2026-10-30, 10:44 AM EDT, before any arm's diagnosis was examined).** #7592's block-201 baseline was unusable:
- p95 was 114.6 s, against 32.7–36.0 s for this case's other five baselines (calibration 101–103, blocks 202 and 203);
- up to 41 requests were waiting while the profiled burst saw the GPU busy only 7% of the time, so the server stalled rather than served the healthy load;
- as a result, none of the six profiled arms triggered.

The whole unit-block (baseline and all seven arms, same seed) was rerun on host #1. The original is kept under `evaluation_failed_baseline_integrity/201_7592/` and is not analysed. This is the only baseline outside the unit's calibration range in the evaluation.

**Reference labels the frozen rule cannot produce (author decision, 2026-10-30, before analysis):**
- #6240 (`kernel_hotspot:gemm`): θ_r = ∞, so the label never fires.
- #7619 (`vocabulary_gap:redundant_prefill`): outside the rule's label set by design.

For these two cases, agreement is reported separately as `reference_unavailable`, together with what each arm diagnosed. They are excluded from the primary agreement comparison and kept in the cost and serving-impact comparisons.

**Analysis clarifications (2026-10-30, about 11 AM EDT).** These were made while checking the analysis script against a draft of the tables, so after some results were seen. Each is stated with its reason:
1. **ctl_shift after the shift is `reference_unavailable`.** Its post-shift reference is `prefill_heavy`, which is not in the frozen rule's label set. This applies the #6240/#7619 decision to the same situation. Pre-shift evidence is scored against `queue_pressure`.
2. **Time is measured from the episode trigger, not the scheduled onset (60 s).** Units whose load runs from t = 0 (ctl_kv and the real cases) trigger before 60 s, so the onset is not a common origin. An unsupported stop is censored at 240 s, the schedule length.
3. **Load-generator validity is reported, not corrected.** Under overload the load generator falls behind schedule in every arm, U included. About 3,600 scheduled requests per arm were never sent before the horizon, almost all in overload units. One session stalled for longer: HS on ctl_withhold, block 203, with 324 fewer completions than U. Per-session `unsent` and send lateness are reported beside the serving comparisons.

4. **RQ1 scores cheap evidence with the rule in its in-episode mode.** This was found after seeing the draft RQ1 table. The window classifier logged online re-checks the latency ratio against θ_L = 1.95, while the trigger fires at 1.5, so at the trigger window it reports `healthy` by construction (29 of 32 adjudicable NT sessions). Every heavy burst is labelled by the same frozen rule without that re-check (`assume_elevated`), because the trigger has already established the incident. For a like-for-like comparison, NT's cheap evidence at the trigger window is relabelled offline by the frozen rule in that same mode (identical code to the hosts' copy, recorded inputs only, no later evidence). Both the logged label and the relabelled one are reported, together with the modal label over the first 10 episode windows as a sensitivity check.

Analysis script: `cases/checks/analyze_evaluation.py`.

## 3. Pre-declared comparisons

**Primary.** SS, CR and HS each against FIX3, paired by block and unit:
- profiler cost: bursts and profiler wall time;
- diagnosis agreement with the unit's reference label;
- time to a supported diagnosis.

Report paired differences with cluster-bootstrap 95% CIs (block as cluster), Wilcoxon signed-rank tests with Holm correction over the three comparisons, and Vargha–Delaney A12. Report Wilson intervals for agreement proportions.

**Secondary (descriptive):**
- **NT against FIX1:** is heavy evidence needed at all? (RQ1)
- **Serving impact of each arm against U:** p95 latency, throughput, completions.
- **Results per cause type.** The engine-stall condition is reported separately (threat T3).

**Not scored as correct:** `horizon_ended`, `budget_exhausted`, `profiler_failed` and `evidence_missing` outcomes, and any unknown diagnosis.

## 4. Block count

The first three blocks (201–203) are run first. Their between-block variance in the primary measures sets the final block count, against the planning floor of 10 (§7). The author decides the count. Blocks are never dropped or rerun for their results. A session that fails with a runner error is rerun in the same block, and the failure is kept.
