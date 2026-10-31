# Step 055: Step 6 symptom gate on the L4

Date: 2026-10-29. Host: the same L4 as before (vast.ai host 506934, Xeon Silver 4114), reached first via `ssh7.vast.ai:24271`, then via `185.101.222.15:17499`. About 3 L4 hours.

## Author decisions (start of step)

- §4 threshold rules approved, including the 2.0 ceiling for θ_r and the 1.25 multiplier.
- Host-stall controlled case approved.

## Result

**Gate passed for 5 of 6 cases.** #19732 is not reproduced under serving and is excluded. That leaves 5 cases across 4 cause types.

Full table: [CALIBRATION_PLAN.md §2.1](../protocol/CALIBRATION_PLAN.md). Results are in [cases/checks/symptoms/](../cases/checks/symptoms/); failed and superseded attempts are kept under `*_attempt*` names.

**Pre-declared rate changes used** (one each, both upward, because neither side was saturated):
- #19732: 1.5 → 4 req/s. Still no symptom, so the case was dropped.
- #7592: 1.45 → 3 req/s. Shown: throughput 0.90×, matching the offline 10.6%.

## Faults found and fixed (no measurement affected)

1. **Runner aborted when `/metrics` timed out.** The #25418 bug blocks the server's event loop. A failed scrape is now a window with missing measures, and the preemption rate uses the real time gap. Covered by a new smoke step with a hanging fake server.
2. **Disk (32 GB).** Four attempts:
   - envs in `/dev/shm` failed (noexec);
   - the vast.ai image's `UV_NO_CACHE=1` silently disabled hardlink sharing;
   - the queue re-counted already-removed envs, which cleared the uv cache mid-case.

   Fixed: envs on disk hardlinked into one uv cache, `UV_NO_CACHE` unset, removal tracked once.
3. **#3087 server could not load its model offline.** vLLM 0.3.x queries the Hub when given a model name. Every server now loads the local snapshot and keeps the name through `--served-model-name`.
4. **#6240 server import error.** `v051` had resolved `outlines==0.1.dev0`, a pre-release that lacks `outlines.fsm`. Pinned `outlines==0.0.46` and stubbed `pyairports`.
5. **Two process-handling mistakes of mine:**
   - an overlapping queue ran for a few minutes before I killed it;
   - `pkill -f` and `pgrep -f` with patterns matched my own SSH command and dropped the session.

   No data was lost. Processes are now killed by PID only.

## Carried into step 7

- #3087 needs a higher healthy rate for a latency reference.
- #6240's baseline burst saw only 79 tokens.
- #25418 makes cheap telemetry unavailable (an RQ1 observation).

## Tests

Full suite: 667 tests, OK ([log](../validation/step055_full_suite/full_run1.log)). The smoke kit also covers a hanging `/metrics` endpoint.
