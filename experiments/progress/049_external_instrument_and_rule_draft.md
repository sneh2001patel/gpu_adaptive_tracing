# Step 049: External instrument and diagnosis rule (draft)

Date: 2026-10-29.

**Author decisions:**
1. Use an external, release-agnostic instrument for all cases.
2. Draft the diagnosis rule with the categories queue pressure, KV-cache pressure, host-bound, kernel hotspot, healthy, unknown.

## Done (CPU only)

- **Design draft:** [EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md](../protocol/EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md).
  - Instrument: `nsys launch/start/stop`, a Prometheus name map checked at each case's release tag, and NVML.
  - Rule: conditions with named thresholds, three-valued handling of missing inputs, a calibration-only fitting plan, and reference mappings for the real cases fixed before any evaluation data exists.
- **`experiments/tracing/rule_diagnosis.py`:** the rule.
  - Every threshold is in a hashed `RuleThresholds`; an unset threshold yields `unknown`.
  - Also: busy fraction as an interval union, kernel-name normalization, and kernel shares.
- **`experiments/tracing/external_instrument.py`:** per-release metric map, Prometheus parser, an `ExternalBursts` controller with separate timing stamps, and GPU activity extraction from Nsight SQLite. The busy-fraction denominator is the capture window (`ANALYSIS_DETAILS`), with a flagged envelope fallback.
- **`policies.is_concrete_label`:** also accepts study-rule labels. `healthy` and `unknown` are never concrete. Old labels are unchanged.
- **Tests:** 32 new tests (`test_rule_diagnosis.py`, `test_external_instrument.py`). Full suite: **629/629 OK**.
- **Ready but not yet run:** [commission_external.py](../cases/checks/commission_external.py), commissioning checks 1–3. It waits for the GPU.

## Open for the author

- Add a `prefill_heavy` category before freezing, or keep vllm#7619 as a documented vocabulary-gap case.
- Review the rule before calibration. No thresholds are set.

## Scope of this step

No GPU use. The V1-internal tracer path is unchanged apart from `is_concrete_label`. No paper or bib changes.
