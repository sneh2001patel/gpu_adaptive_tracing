# Submitted-paper claim audit

Audit date: 2026-10-27. Authoritative document: `paper/ICSE_GPU_Adaptive_Tracing (2).pdf`, 11 pages. The audit groups the paper's implementation, setup, empirical, interpretation, and scope claims into 40 entries. It does not independently verify the cited literature or production root causes.

The editable [claim registry](claim_registry.json) records each claim's paper location, source scripts, analysis artifacts, raw-artifact patterns, finding, and next action. The generated [claim inventory](generated/artifact_audit.csv) is the reviewable spreadsheet version. Every registry artifact pattern currently matches local files; matching a file does not establish validity, and LFS pointers are not the underlying data.

## Main findings

1. **Profiler-duration savings use the wrong clock for the stated claim.** The arithmetic is often reproducible, but the underlying durations measure the complete `nsys profile` subprocess, not active capture. Startup, target execution/shutdown, and report finalization are mixed. Separate `nsys stats` execution is excluded. See [the timing audit](TIMING_AUDIT.md).
2. **Historical diagnosis results need replacement.** Serving labels and score floors used workload truth; microbenchmark labels used workload identity. Steps 001–002 fix future input/policy behavior, not the validity of historical accuracy, stopping, or signal results. Microbenchmark profiling also launches a new reproduction workload in a child process rather than attaching to the original workload's incident.
3. **Several paper numbers do not match the artifacts.** These discrepancies are independent of the broader methodological problems and need correction.
4. **Cheap-polling runtime measurements are independently recomputable.** They remain useful within their original narrow scope, not as evidence for full adaptive-controller overhead or a streaming aggregation implementation.

## Numerical reconciliation

| Paper claim | Artifact finding | Disposition |
|---|---|---|
| Table V microbenchmark durations and 31.6–48.5% savings | Displayed values reproduce from the L4/A100 aggregates | Historical profile-process wall time only; not validated evidence-sufficiency savings. |
| Queue pressure 104.6 vs 133.5 s, 21.7% saved | Corresponding aggregate matches | Relabel wall time; active capture remains unknown. |
| Table VI 402 records | 36 canonical scenario/mode CSVs contain **201** rows; deduplicated analysis also totals 201. Earlier analysis totals 402 and includes duplicate CSV representations | Use unique identities; correct the paper's record count. |
| Table VI profiling-time totals | All six scenario totals agree to displayed rounding | Clock remains mislabeled. |
| Table VI kernel counts | All six scenario pairs disagree with saved comparison summaries | Replace cells from a frozen provenance chain and verify original profiler reports when available. |
| 23.8% time savings overall | 1,858.482 vs 2,437.731 profile-process seconds gives **23.762%** | Arithmetic matches; active-capture interpretation does not. |
| 47.1% fewer kernels overall | 1,460,211 vs 2,759,441 summary instances gives **47.083%** | Prose matches summary totals, but Table VI does not; different workload lengths confound attribution. |
| Table VIII diagnosis-change F1 = 0.635 | Archived diagnosis-change F1 is **0.000**; **0.635 belongs to diagnosis_confident** | Correct signal identity; independently rerun the analysis. |
| All windows 10 s; automatic/fixed bursts approximately 10–12 / 17–24 s | All five available L4 microbenchmark manifests specify **5 s** windows and **2 s / 8 s** requested workload segments | Correct configuration reporting and distinguish requested segments from measured clocks. |

Table VI reconciliation, using kernel counts transcribed from the submitted PDF and comparisons summed across its three seeds:

| Scenario | PDF auto kernels | Saved auto kernels | PDF fixed kernels | Saved fixed kernels |
|---|---:|---:|---:|---:|
| healthy | 730,000 | 189,945 | 1,380,000 | 344,715 |
| queue_pressure | 748,000 | 292,230 | 1,380,000 | 525,031 |
| long_prompt | 732,000 | 172,668 | 1,380,000 | 345,336 |
| long_output | 729,000 | 293,334 | 1,380,000 | 586,477 |
| compute_saturation | 757,000 | 264,744 | 1,380,000 | 463,302 |
| kv_cache_pressure | 731,000 | 247,290 | 1,380,000 | 494,580 |

These are saved summary counts, not a new binary-level re-extraction. [Machine-readable Table VI comparison](generated/table_vi_reconciliation.csv).

## Results that can be retained with a narrower interpretation

Raw per-request CSVs reproduce the eight dedicated polling-perturbation repetitions:

| Scenario | Independent runs | Mean p95 change | Historical 95% normal-approximation half-width |
|---|---:|---:|---:|
| queue_pressure | 5 | −3.555926% | 6.267170 percentage points |
| healthy | 3 | +0.645937% | 1.938640 percentage points |

The raw-versus-saved p95-change differences are below 1e-13 percentage points. Throughput changes and request-success percentages are also recomputed in [the raw-request checks](generated/raw_request_overhead_checks.csv). This validates the archived arithmetic; it does not prove zero overhead, establish production reliability, or validate overhead from profiler bursts. Window aggregation in the historical runner occurs after requests finish, so its concurrent cost was not measured by this comparison. The interval formula is the original 1.96×s/√n convention, not a newly justified small-sample statistical analysis.

Historical kernel summaries and request/GPU observations can support descriptive workload analysis. Their labels, confidence scores, and derived stopping targets must not be treated as independently validated diagnoses. Corrected replay may illustrate policy mechanics but cannot manufacture the T2 observations an alternative live policy would have collected.

## Artifact availability and reproducibility

- **817 local profiler files are LFS pointers:** 409 `.nsys-rep` paths and 408 `.sqlite` paths. None of these local files is the actual profiler blob. File presence is therefore insufficient for binary-level verification.
- The audit records each pointer's declared object SHA-256 and original size in [profiler availability](generated/profiler_availability.csv). Retrieving existing LFS objects, if accessible, does not require a new GPU experiment. No retrieval was performed in this step.
- **405 timing records** are indexed: 124 serving-mode records, 64 microbenchmark workload/mode records, and 217 live captures at replay-selected durations. These include diagnostic/archive runs and are not 405 independent experimental repetitions. Each row retains its source path and family.
- **1,554 inputs** were fingerprinted for this audit, and each was checked unchanged before writing audit products. The audit reads original data; it does not regenerate their analyses, overwrite paper tables, or fix old results in place.
- The summary records the PDF hash and repository HEAD. The tracked baseline is `3ee0a1dfcef1fb6498e303decb42e39a1b1a24bb`. Per-run executable/source commits are absent, so the code/artifact mapping reconstructs plausible provenance; it cannot prove the exact source revision executed for every historical run. Current corrected scripts are distinct from the original run semantics.

## Disposition by result family

| Family | Reuse permitted by this audit | Required before revised claims |
|---|---|---|
| RQ1 timing | Descriptive process wall-time comparisons and saved run configuration | Actual capture boundaries, equal-workload controls, multi-burst online decisions. |
| RQ2 diagnosis | Raw requests/GPU observations; canonical window identities | Independent reference diagnoses and truth-free evidence classification; genuine evidence-availability timing. |
| RQ3 polling | Historical cheap-polling p95/throughput/success arithmetic, with original limitations | Separate full streaming-controller and profiler perturbation measurements. |
| RQ3 kernel volume | Saved summary-instance counts, with provenance caveats | Original profiler blob validation and consistent workload/horizon comparison. |
| RQ4 | Synthetic mechanics examples; historical replay inputs explicitly labeled | Distinct policies, corrected missingness/budget semantics, independent evidence, actual reactivation events. |
| RQ5 | Descriptive raw signal distributions | Explicit field availability, no zero-filled missing readings, independent stop targets, real ambiguity. |
| Workflow/novelty | Intended design and research questions | Actual operator evidence report; primary-source related-work comparison; no unmeasured human-benefit claims. |

The RQ5 analyzer and historical paper-table generators still require their own metric/availability rewrite; this audit identifies their limitations without changing their archived outputs. RQ5 currently zero-fills missing inputs and filters suspicious windows, while the paper's “undefined” availability interpretation is not encoded in those archived table outputs.

## Reproduce the audit

```bash
python3 revision/scripts/audit_artifacts.py
```

Generated files live under `revision/audit/generated/`. The script is restricted to writing within `revision/`; input hashes, lookup checks, raw-request recomputation, timing inventory, and the numerical reconciliation are included. The registry is a human audit of 40 claim groups, not an automatic verifier of every sentence or citation. No historical artifact is edited, and no GPU or internet access is required.
