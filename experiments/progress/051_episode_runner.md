# Step 051: Episode runner (external instrument + rule + policies)

Date: 2026-10-29. CPU only.

## Done

- **`experiments/tracing/episode_controller.py`:** pure decision logic for one session.
  - Arms: NT, FIX(n), SS, CR, HS.
  - Trigger: consecutive elevated-latency windows.
  - At most one outstanding burst; one episode per session.
  - Windows after the stop are still recorded, so recurrence can be scored offline.
- **Rule semantics fix:** during an episode, heavy-burst diagnoses use `assume_elevated`, keeping cause and recovery as separate signals. Without it, a hybrid stop can never be reached, because a recovered window always reads `healthy`. The design doc §3.3 records the consequence that an idle GPU after a load drop can read as `host_bound`; RQ3 reports it.
- **[run_episode.py](../cases/checks/run_episode.py):** the I/O runner, standard library only, on the host's system Python.
  - Starts the server under `nsys launch` (or `--unprofiled`).
  - Open-loop dispatcher; records lateness and censoring at the horizon.
  - 1-second windows: p95 end-to-end latency / p95_base, `/metrics`, `nvidia-smi` utilization.
  - Background external bursts; `--baseline-out` records a healthy calibration session, with the baseline burst taken mid-load.
- **[make_schedule.py](../cases/checks/make_schedule.py):** seeded Poisson schedules (healthy, overload, lull).
- **Local smoke kit:** [smoke/run_smoke.sh](../cases/checks/smoke/run_smoke.sh) runs a fake vLLM server end to end.
  - Baseline p95 0.41 s.
  - The episode triggers two windows after the overload starts.
  - Dispatch lateness ≤ 55 ms.
  - 112 requests censored at the horizon.

## Tests

- **14 new controller tests;** 648 tests in total.
- **Three full runs:** two had one failure each, in different pre-existing timing tests (`test_arm_lifecycles` post-drain, `test_schedule_playback` fixed-schedule). The third passed 648/648.
- Each failing test passes in isolation. None involves the new code.
- This is the step-036 timing sensitivity under moderate host load (about 6–8). **Step 048's gate is therefore not robust:** the suite passes only intermittently on a loaded host.

## Next (needs the L4)

1. Copy the runner to the host.
2. Commissioning check 4: one healthy baseline, then one overload episode per arm (NT, FIX(3), SS, HS) on v0.11.0, with provisional thresholds labelled commissioning-only. These are not calibration.
