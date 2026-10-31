#!/bin/bash
set -e
. /opt/supervisor-scripts/utils/logging.sh
. /opt/supervisor-scripts/utils/environment.sh
cd /workspace/gpu_adaptive_tracing_step033
exec timeout --signal=INT --kill-after=55s 4800s /workspace/envs/vllm/bin/python -u -m revision.scripts.run_l4_challenges_v2 --freeze revision/examples/event_challenges_v2/snapshot_001/FREEZE.json --output revision/hardware/l4_20261028/challenges_v2_001 --model-path /dev/shm/hf-cache/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 --device-uuid GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb
