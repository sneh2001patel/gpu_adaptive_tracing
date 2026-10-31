#!/bin/sh
exec /workspace/envs/vllm/bin/python /workspace/gpu_adaptive_tracing/revision/scripts/nsys_callback.py /workspace/gpu_adaptive_tracing/revision/hardware/l4_20261027/smoke_002/session report_ready
