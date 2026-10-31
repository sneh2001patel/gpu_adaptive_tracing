# Step 048: Full CPU suite cleared; pilot blockers identified

Date: 2026-10-29.

## Full suite (proposal §10 step 4)

- `python3 -m unittest discover -s revision/tests -q` on the author's MacBook (Python 3.13.7, load average about 7–10).
- **597 tests, OK, twice** (83.3 s and 82.2 s). Logs: [validation/step048_full_suite/](../validation/step048_full_suite/).
- This clears the step-036 gate.
- It is consistent with the earlier failures being timing checks starved under host load averages up to about 89. This run does not prove that every earlier failure was harmless.
- No source or test changes were made.

## Pilot blockers found while preparing §10 step 5

1. **No diagnosis rule exists.**
   - `revision/tracing/diagnosis.py` is `UncalibratedClassifier`: it emits no labels by design.
   - Stability (SS) and hybrid (HS) stops need concrete diagnoses, so the pilot cannot compare them yet. Step 037 already required a transparent, frozen rule calibrated on development data.
2. **The instrument is tied to the vLLM V1 engine.**
   - `vllm_cuda_worker.py` subclasses `vllm.v1.worker.gpu_worker.Worker`; `vllm_event_scheduler.py` subclasses the V1 `Scheduler`; Nsight bursts go through `/start_profile` and `/stop_profile`. It is built and tested against vLLM 0.10.2.
   - Accepted cases #6240, #7619 and #3087 run on V0-engine releases (0.3.x–0.5.x), where these hooks do not exist.
   - #19732 (0.9.2) and #25418 (0.11.0) are V1, but on releases other than 0.10.2.
   - Author decision needed: a release-agnostic external instrument, or per-release ports.

## In progress

vllm#7592 confirmation blocks are running on the L4 ([queue_7592_blocks.sh](../cases/checks/queue_7592_blocks.sh)).
