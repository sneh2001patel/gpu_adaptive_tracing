# Calibration plan (proposal §10 steps 6–7)

Status: **approved by the author, 2026-10-29 (step 054):** the §4 rules (including the 2.0 ceiling for θ_r and the 1.25 multiplier) and the host-stall controlled case (§3.2). These are now fixed; any change makes a new plan version.

This plan fixes three things **before any instrumented data exists**:

1. the step 6 gate criterion;
2. the calibration sessions and their seeds;
3. the rule that turns calibration data into each threshold (θ).

Writing the rules first means the thresholds cannot be tuned after looking at results. It follows the data split in [EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §3.4](EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md):
- calibration uses healthy sessions, controlled cases, and the real cases' **toggle-off (fixed)** side only;
- the **bug** side of every real case is evaluation data.

Code: [case_workloads.py](../cases/checks/case_workloads.py) (case registry and request bodies), [case_server.py](../cases/checks/case_server.py) (in-server patches), [run_case.py](../cases/checks/run_case.py), [make_schedule.py](../cases/checks/make_schedule.py), [queue_case_symptoms.sh](../cases/checks/queue_case_symptoms.sh), [summarize_case_symptoms.py](../cases/checks/summarize_case_symptoms.py).

## 1. Cases as serving workloads

All six accepted cases now run as serving sessions through the same runner and the same external instrument.

| Case | Environment | Model | Bug side | Fixed side | Requests | Rates (healthy / incident), provisional | Reference (§3.5) |
|---|---|---|---|---|---|---|---|
| #6240 | v051 (0.5.1 image build) | Llama-3-8B-Instruct-FP8 | CUTLASS FP8 selected | `6240_cutlass_off` patch | 256 tokens, greedy, `ignore_eos` | 0.3 / 1.0 req/s | kernel_hotspot:gemm |
| #7619 | v055 | Llama-3-8B-Instruct-FP8 | `--use-v2-block-manager` | block manager v1 | groups of 32 sharing a fresh ~1.4k-char table prefix; 200 tokens | 0.03 / 0.1 groups/s | vocabulary gap |
| #3087 | v032 vs v033 | TinyLlama-1.1B | 0.3.2 | 0.3.3 | issue prompt, 128 tokens; outlines JSON processor attached in the server | 0.5 / 1.0 req/s | host_bound |
| #25418 | v0110 | Qwen2.5-VL-3B | per-request `mm_processor_kwargs` | none | chat, one unique 448×448 PNG, 112 tokens | 1.0 / 1.0 req/s | host_bound |
| #19732 | v092 | Qwen2.5-1.5B | xgrammar 0.1.19 | xgrammar 0.1.21 (swapped in place) | the issue's schema via `guided_json`, 512 max tokens | 0.5 / 1.5, then 4.0 req/s | host_bound — **dropped at step 6** (§2.1) |
| #7592 | v055 vs v060 | Qwen2.5-7B | 0.5.5 | 0.6.0 | `"hi"*511`, 512 tokens, `ignore_eos`, temperature 1 | 0.3 / 1.45, then **3.0** req/s | kv_pressure |

**Deviations from the reproduction checks** (all the same for both sides of a toggle):
- Every case is served over HTTP with open-loop Poisson arrivals, instead of offline batches.
- **#7619:** the benchmark's fixed table prompt becomes a generated table of similar length. Each group gets a fresh prefix, so every group is a cold start, the condition the bug affects.
- **#3087:** v0.3.2's server has no structured-output option, so the issue's processor is attached inside the server, in `LLMEngine.add_request`, ahead of the deep copy. One processor is shared by all requests, as in the issue.
- **#25418:** uses the chat API with generated PNGs, distinct per request, instead of random-noise images through the offline engine.
- **#7592:** Poisson arrivals at 1.45 req/s, which sits between the two releases' offline capacities (1.397 and 1.539 req/s), instead of 1,000 requests at once.

**Rates.** Rates are provisional, chosen from offline capacities.
- The healthy rate must keep the fixed side healthy with at least 3 requests in flight, since the in-flight latency needs 3 samples.
- If the step 6 gate fails, the incident rate is adjusted once (§2).

## 2. Step 6: symptom gate under the instrument

**Sessions per case:**

| Session | Side | Schedule | Arm |
|---|---|---|---|
| baseline | fixed | healthy rate for 240 s | none (`--baseline-out`, one burst mid-load) |
| NT fixed | fixed | 60 s healthy, 120 s at the incident rate, 60 s healthy, 60 s drain | NT |
| NT bug | bug | same arrival times | NT |

**Pre-declared criterion.** Only requests sent during the 120 s incident phase are compared. The symptom is shown when either holds:
- the bug side's p50 latency is at least 1.1× the fixed side's; or
- its generated-token throughput is at most 0.9×.

If the symptom is not shown:
1. the incident rate is changed once, upward if neither side is saturated, downward if both are;
2. the case is rerun;
3. if it still fails, it is recorded as "not reproduced under serving". It is kept in the report and excluded from evaluation.

**Sealing the bug side.** The gate summary reports only symptom measures for the bug side: latency, throughput, completions and errors. It never reports the rule's inputs or diagnoses. Raw files are kept but are excluded from calibration. Evaluation uses fresh seeds after the freeze, so the gate's bug sessions are development data.

**Also covered by this run:**
- commissioning check 3 (metric names and update rate) for v0.3.x and v0.9.2;
- the first serving runs of the v0.5.1 image build.

**Cost:** 18 sessions at about 7 min each is about 2 h, plus about 1.5–2 h of environment builds and model downloads. **About 4 L4 hours in total.** Disk is tight (32 GB disk, about 13 GB free; `/dev/shm` 31 GB, noexec). The queue removes what no later case needs. Actual: about 3 L4 hours, including three restarts for setup faults (step 055).

### 2.1 Result (step 055, 2026-10-29)

**Gate passed for 5 of 6 cases.** Results: [cases/checks/symptoms/](../cases/checks/symptoms/), one `symptom.json` per case. The bug side is reported only by its symptom measures, as declared above.

| Case | Incident rate | Bug ÷ fixed, p50 latency | Bug ÷ fixed, tokens/s | Incident requests completed (fixed / bug) | Outcome |
|---|---|---|---|---|---|
| #25418 | 1.0 req/s | 45.5 | n/a¹ | 115 / 39 of 115 | **shown** |
| #3087 | 1.0 req/s | 132.6 | 0.49 | 107 / 107 | **shown** |
| #7619 | 0.1 groups/s | 2.29 | 0.81 | 416 / 416 | **shown** |
| #6240 | 1.0 req/s | 1.84 | 0.95 | 105 / 105 | **shown** |
| #7592 | 1.45 req/s | 1.07 | 0.97 | 164 / 164 | not shown; neither side saturated (fixed side: no queue, no preemption, KV 55%) |
| #7592 | **3.0 req/s** (one change, upward) | 1.14 | 0.90 | 277 / 252 of 348 | **shown**; matches the offline 10.6% throughput gap |
| #19732 | 1.5 req/s | 0.96 | 1.00 | 181 / 181 | not shown; unsaturated |
| #19732 | **4.0 req/s** (one change, upward) | 1.00 | 1.00 | 466 / 466 | **not shown → not reproduced under serving; excluded from evaluation** |

¹ #25418's bug side blocks the API server's event loop, so `/metrics` stops answering and token throughput cannot be computed (§2.2).

**#19732 is genuine, not a setup error:**
- the installed xgrammar version was checked on each side (`case.json`);
- both server logs show the token-bitmask kernel being compiled, so the grammar was active.

The 2.1× offline slowdown (8 batched requests through `LLM.chat`) does not carry over to serving at 1.5 or 4 req/s.

**The remaining set: 5 cases, 4 cause types:**
- kernel: #6240;
- redundant prefill (vocabulary gap): #7619;
- host-side: #3087, #25418;
- KV pressure: #7592.

### 2.2 What step 6 changed or revealed (carried into step 7)

- **#25418: cheap telemetry goes dark.** The host-side stall blocks `/metrics`. The runner now records a failed scrape as a window with all measures missing, instead of aborting (`--scrape-timeout`, default 5 s). The preemption rate is now computed over the real gap between scrapes. For RQ1, cheap telemetry can be unavailable exactly when a host-side incident is under way.
- **#3087: the healthy rate is too low for a latency reference.** At 0.5 req/s with 0.75 s responses, fewer than 3 requests are ever in flight, so `p95_base_s` is missing. The seed-100 pre-run sets a higher healthy rate (about 4 req/s).
- **#6240: the baseline burst is thin.** It saw only 79 tokens, so per-token kernel time rests on few tokens. The FIX(4) calibration sessions (§3.1) supply more bursts per configuration.
- **Model loading:** servers load each model from its local snapshot, with `--served-model-name` keeping the requested name. Old releases (0.3.x) query the Hub when given a model name, which fails offline.
- **Host setup:** the vast.ai image sets `UV_NO_CACHE=1`, which the queue unsets, so that environments hardlink into one uv cache. `/dev/shm` is mounted noexec, so it holds models only. `v051` pins `outlines==0.0.46`: the date cutoff otherwise admits a pre-release that breaks 0.5.1's OpenAI server.

## 3. Step 7: calibration sessions

**Seeds:**
- 100 is for rate-setting pre-runs, which are never used for θ;
- **101–103 are for calibration**;
- 201 and up are for evaluation.

Threshold derivation reads only the calibration directory.

### 3.1 Real cases, fixed side only

Each case gets 3 seeds × 2 sessions, so 6 cases × 3 × 2 = **36 sessions**:
- **healthy baseline** (`--baseline-out`);
- **incident-load session**, arm FIX(4). This gives four bursts per session at matched load. These are the non-kernel reference values for per-token kernel time, measured against the healthy baseline and seed against seed.

### 3.2 Controlled cases

These run on vLLM 0.11.0 with Qwen2.5-7B, the commissioning setup. Each gets 3 seeds: 7 × 3 = **21 sessions**. Every non-healthy session is arm NT with four scheduled calibration bursts at 75, 105, 135 and 165 s, instead of FIX(4). FIX(4) bursts only after the latency trigger fires, and that trigger uses an uncalibrated θ; a healthy fixed side might never fire it, leaving no matched-load evidence. The same applies to §3.1.

| Condition | Intervention | Provisional setting (set on seed 100) |
|---|---|---|
| healthy | none | 1 req/s |
| overload | arrivals above capacity | 1 → 20 req/s |
| KV pressure | long prompts and outputs at moderate rate | 1,500 prompt words, 1,024 tokens; **3 req/s** (1.5 req/s on seed 100 filled the KV cache only after ~150 s and never preempted) |
| **host stall (engine)** | `engine_stall_v1:<ms>`: CPU spin on every engine step, in `Scheduler.schedule`, between GPU steps | **40 ms per step at 1 → 2 req/s** |
| lull/recurrence | `--pattern lull` | 1 → 20 req/s, 30 s lull |
| changing bottleneck | `--pattern shift`: short-request overload, then prefill-heavy requests | 20 req/s, then 2,000 words at 3 req/s |
| overlap | overload plus long prompts | 20 req/s, 1,500 words |

**Seed-100 change to the host stall.** As first planned, the stall was a CPU spin per request on the API server's event loop (300 ms at 4 req/s). On seed 100 it raised latency 2.7×, but GPU utilization stayed at 0.96 and burst busy fraction at 0.95: vLLM V1 runs the engine in its own process, so it kept decoding the admitted requests. That gives θ_g and θ_b nothing to separate. The stall therefore moved into the engine loop, between GPU steps. The front-end variant was removed at the author's request; its seed-100 session is kept under `calibration_prerun/100/controlled/ctl_frontend_stall` as a recorded observation.

**Host stall is new in this plan.** Without it, no calibration condition is host-bound. Then θ_g (GPU utilization) and θ_b (busy fraction) could only be set from the real cases' bug sides, which §3.4 forbids. It is a generic intervention, CPU work per request ahead of the engine. It is not any case's mechanism. It does belong to the same broad class as #25418 (threat T3).

**Not run for calibration:** incomplete evidence (`--withhold`) and persistent incident. They test decisions, not thresholds, and run only in evaluation.

**Cost:** 57 sessions at about 7 min each is about 6.7 h, plus about 2 h of setup. **About 9 L4 hours.** Together with step 6, that is **about 13 L4 hours.**

## 4. Threshold derivation rules (pre-declared)

**Definitions:**
- **Healthy windows:** windows of all healthy sessions, after the first 25% of each.
- **Condition windows:** windows inside the intervention phase of a controlled session.
- **Bursts of a condition:** bursts taken inside that phase.
- p99 is taken over pooled windows from the three seeds.

| θ | Rule | Margin reported |
|---|---|---|
| θ_L (latency ratio) | p99 of L over healthy windows, rounded up to 0.05 | overload median L ÷ θ_L |
| θ_w (waiting requests) | p99 of waiting requests over healthy windows, plus 1 | overload median ÷ θ_w |
| θ_u (KV usage) | midpoint of the healthy p99 and the KV-pressure median | gap ÷ θ_u |
| θ_p (preemptions/s) | max(p99 of healthy windows, 0.5) | KV-pressure median ÷ θ_p |
| θ_g (GPU utilization) | midpoint of the host-stall median and the overload median | gap |
| θ_b (busy fraction) | midpoint of the host-stall burst median and the overload burst median | gap |
| θ_r (kernel time ratio) | ordered fallback below | — |

**θ_r fallback.** Use the first option whose θ_r is at most **2.0**. A rule that cannot flag a 2× per-token kernel regression is not useful to an operator.
1. **Healthy-load baseline:** θ_r = 1.25 × the largest family ratio over all calibration bursts. That covers every family and every condition, including the real fixed sides at incident load.
2. **Load-matched baseline:** the baseline per-token time comes from the same configuration at the same schedule, as the median of fixed-side seeds. θ_r = 1.25 × the largest seed-against-seed ratio. Operationally, this is a profile of the last known-good version at similar load, as in a canary or A/B comparison.
3. **Per-family θ_r,f:** 1.25 × the largest ratio of family f, under option 2's baseline.
4. **None qualifies:** `kernel_hotspot` is reported as not separable from load on this hardware. That is a finding for RQ1/RQ2, and the rule keeps the option-3 values.

Step 053's attention ratio of 1.5–2.3 under overload suggests option 1 will exceed 2.0. Whether option 2 or 3 brings θ_r below 2.0 is what calibration decides, not this plan.

**When a rule finds no gap:** if a separating rule (θ_u, θ_g, θ_b) finds no gap between its two conditions, the threshold is still set by the rule. Its margin is reported as negative, and the cause it gates is flagged as "not separable by cheap telemetry" in the results.

**Robustness check (feeds RQ4):** every θ is recomputed six more times, each leaving out one real case's fixed-side data, and seven more times, each leaving out one controlled condition. The range of each θ is reported.

**Freeze:**
- all θ are written to a thresholds JSON with version `study_rule_v2_calibrated_<date>` and its digest;
- the author reviews it;
- after that, any change makes a new version, and anything evaluated before the change becomes exploratory.

The trigger settings (latency ratio 1.5 over 2 windows) stay at the proposal defaults and are swept in RQ4.

## 4.1 Result and freeze (step 056, 2026-10-29)

Derived from 51 sessions (seeds 101–103): θ_L 1.95, θ_w 1, θ_u 0.5768, θ_p 0.5, θ_g 0.769, θ_b 0.7373.

**θ_r: none of the options qualifies.** Option 4 applies: `kernel_hotspot` is not separable from load. The author chose to freeze θ_r = ∞, so the label never fires (rather than keeping the option-3 values of 20–114×).

**Accepted by the author:**
- the θ_p margin of 0 (no preemptions under KV pressure);
- the pooled θ_L, which #7619 and #3087 set.

Deviations, faults and margins: [step 056](../progress/056_calibration_and_freeze.md). Frozen file: `cases/checks/thresholds_study_rule_v2_calibrated_2026-10-29.json`.

## 5. Threats specific to calibration

- **T1:** calibration uses the fixed sides of the same cases that are evaluated. This is by design (§3.4): the evaluated contrast, the bug side, is never seen. The leave-one-case-out ranges show how much each case moves the thresholds.
- **T2:** the author and I have seen the offline reproductions (REPRODUCTION.md). The rules above are fixed before any instrumented bug-side data exists, and the gate hides the bug side's rule inputs.
- **T3:** the host-stall intervention was designed in this study, and it is in the same broad class as the host-side cases. Its results are reported separately, so readers can discount it.
- **T4:** a single GPU type (L4). A100 transfer comes after the freeze (proposal §10 step 8).

## 6. Decisions for the author

1. **Approve or edit the pre-declared rules in §4**, especially the 2.0 ceiling for θ_r and the 1.25 multiplier. They must be settled before step 7 data exists.
2. **Approve adding the host-stall controlled case** (§3.2).
3. **GPU time:** about 4 h for step 6, then about 9 h for step 7. Step 6 can start as soon as the instance is up; it needs no decision from the list above.
