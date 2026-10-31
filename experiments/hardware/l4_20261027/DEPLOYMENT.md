# L4 rental deployment

This is the user-provided Vast.ai L4 container, accessed through the supplied SSH configuration. No private SSH keys or account API credentials are included here.

- Project: `/workspace/gpu_adaptive_tracing`.
- Serving environment: `/workspace/envs/vllm` (created separately from the image's default environment).
- Public model cache: `/dev/shm/hf-cache`, revision `a09a35458c702b33eeacc393d103063234e8bc28`. RAM-backed and expendable; lost if the RAM filesystem/container is reset.
- Experiment artifacts: `/workspace/gpu_adaptive_tracing/revision/hardware/l4_20261027/`, mirrored to this local directory.
- Owned supervisor programs: `revision-l4-smoke` and `revision-l4-pilot`, both with autostart/autorestart disabled. The instance's existing management services are preserved.
- Serving binds only `127.0.0.1:8010`. Existing Jupyter/portal/SSH settings are not repurposed.
- `deployment/` retains the pilot's wrapper/configuration, while each pilot’s `source_manifest.json`, `packages.txt` and `executed_source.tar.gz` identify/archive the executed code and dependencies.

Useful on-instance inspection:

```bash
supervisorctl status revision-l4-smoke revision-l4-pilot
tail -20 /workspace/gpu_adaptive_tracing/revision/hardware/l4_20261027/pilot_service.log
nvidia-smi --query-gpu=name,memory.used,utilization.gpu --format=csv,noheader
```

The pilot owns and stops its Nsight/vLLM session after completion or failure; stopping a policy capture does not stop the serving session. Rental lifecycle is separate: stopped experiment services do not by themselves stop GPU instance billing. Preserve raw artifacts outside the rental before recycling/destroying it. Current backup/cleanup checks are recorded in step 011 and the final pilot analysis.

`pilot_001` has incomplete GPU telemetry and is retained as a failed comparison. `pilot_002` repeats the engineering matrix with fresh per-episode NVML ownership and explicit coverage checks.

The corrected matrix completed and is mirrored locally: 18 runs, 39 captures, clean telemetry/readiness/integrity audit. `pilot_002/cleanup_verified.json` records session exit 0, all sampler workers closed, absent serving worker, empty Nsight sessions and no GPU compute processes. This does not stop rental billing. `deployment/revision-l4-pilot-002.sh` retains the rerun wrapper.
