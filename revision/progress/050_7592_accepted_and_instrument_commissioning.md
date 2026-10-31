# Step 050: vllm#7592 accepted; external instrument commissioned on V0 and V1

Date: 2026-10-29. Host: vast.ai L4.

## vllm#7592

- 5 counterbalanced blocks.
- Mean paired gain of v0.6.0 over v0.5.5: **+0.147 req/s (+10.6%)**.
- 95% CI: [0.141, 0.153] (t); [0.144, 0.151] (bootstrap). 5/5 blocks favour the fix.
- **Accepted.** The tally is now **6 accepted cases across 4 cause types** (GPU kernel, redundant GPU work, host CPU, scheduling/preemption).
- Details: [REPRODUCTION.md](../cases/REPRODUCTION.md).

## External instrument commissioning

Details are in [EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §6](../protocol/EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md).

- **It works on both engine families with no vLLM hooks:** v0.5.5 (V0) and v0.11.0 (V1, engine-core subprocess followed).
- **Four extraction bugs found and fixed against real captures, each with a test:**
  - start-only Nsight options;
  - relative vs absolute clocks;
  - CUDA graph replays (node-level tracing adopted);
  - in-flight records at the window edges.
- **Kernel identity** now uses `shortName` plus the configuration template argument.
- **Cost:** `nsys stop` takes 6–8 s per 2-second burst.

## Tests and scope

- Full suite 629 → 634 tests, all OK (new tests for graphs, window clipping, clock base and kernel identity).
- About 2 L4 GPU-hours (the #7592 blocks plus commissioning).
- Raw captures: 40 MB, local and git-ignored.

## Next

1. Build the episode runner, the controller loop that connects the external instrument, the rule and the policies.
2. Commissioning check 4 (one episode per policy).
3. Calibration sessions (healthy, controlled cases, real cases with the toggle off). Then the author reviews and freezes the thresholds.
