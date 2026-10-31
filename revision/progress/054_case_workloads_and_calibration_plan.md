# Step 054: Real cases as serving workloads; calibration plan

Date: 2026-10-29. No GPU time used.

## Implemented

- **[case_workloads.py](../cases/checks/case_workloads.py):** a registry of the six accepted cases. For each side of a toggle (`bug` / `fixed`) it holds:
  - the environment and model;
  - the server flags and in-server patch;
  - the request body;
  - provisional healthy and incident rates;
  - the expected reference.

  Standard library only. It includes a PNG encoder, so #25418 gets a distinct 3 KB image per request.
- **[case_server.py](../cases/checks/case_server.py):** starts the case environment's OpenAI server with a patch applied in the server process:
  - `6240_cutlass_off` (fixed side of #6240);
  - `3087_json_processor` (the issue's outlines processor on every request, attached before v0.3.2's deep copy);
  - `host_stall_v1:<ms>` (new controlled case).
- **[run_case.py](../cases/checks/run_case.py):** resolves a case and side into `run_episode.py` arguments.
  - Swaps xgrammar in place for #19732 and checks the installed version.
  - Refuses a schedule whose model name differs from the served model.
  - Records installed component versions in `case.json`.
- **[make_schedule.py](../cases/checks/make_schedule.py):**
  - `--case/--side` presets; both sides get identical arrival times, from separate random streams for arrivals and bodies;
  - request groups (#7619);
  - `shift` pattern (controlled "changing bottleneck").
- **[run_episode.py](../cases/checks/run_episode.py):**
  - `--case-patch`;
  - `--withhold` (controlled "incomplete evidence"): named inputs, or `heavy`, are hidden from the controller, while the observed values are still logged.
- **[queue_case_symptoms.sh](../cases/checks/queue_case_symptoms.sh) and [summarize_case_symptoms.py](../cases/checks/summarize_case_symptoms.py):** the step 6 gate run, with a disk-aware case order. The bug side's summary is limited to symptom measures.
- **Tests:** 11 new in `test_case_workloads.py`; the smoke kit now covers the case path and withholding. The full suite ran 666 tests, OK ([log](../validation/step054_full_suite/full_run1.log)).

## Plan

[protocol/CALIBRATION_PLAN.md](../protocol/CALIBRATION_PLAN.md) pre-declares, before any instrumented data:
- the step 6 criterion;
- the calibration sessions (36 real fixed-side + 21 controlled, seeds 101–103);
- one derivation rule per threshold, including an ordered fallback for θ_r with a 2.0 ceiling;
- leave-one-out ranges and threats.

Estimated L4 time: about 4 h for step 6 and about 9 h for step 7.

## Found while planning

- **No host-bound calibration condition.** No calibration condition was host-bound, so θ_g and θ_b could only have been set from bug sides, which §3.4 forbids. Fix: a generic host-stall controlled case (approved).
- **Bug-side data is evaluation data, even in the step 6 gate.** The gate therefore reports only the bug side's symptom measures.

## Not verified yet (needs the GPU)

- Both patches are untested against the real releases:
  - `3087_json_processor` in the v0.3.2/v0.3.3 servers;
  - `6240_cutlass_off` in the v0.5.1 server.
- `mm_processor_kwargs` and `guided_json` acceptance in the 0.11.0 and 0.9.2 chat APIs is also unchecked.
- Metric names and update rate in v0.3.x and v0.9.2 (commissioning check 3).

## Author decisions (2026-10-29)

- §4 threshold rules approved as written, including the 2.0 ceiling for θ_r and the 1.25 multiplier.
- Host-stall controlled case approved.
