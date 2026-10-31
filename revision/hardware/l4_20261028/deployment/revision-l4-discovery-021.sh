#!/bin/bash
set -e
. /opt/supervisor-scripts/utils/logging.sh
. /opt/supervisor-scripts/utils/environment.sh
cd /workspace/gpu_adaptive_tracing_step021
export HF_HOME=/dev/shm/hf-cache
export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=60
exec /workspace/envs/vllm/bin/python -u -m revision.scripts.run_l4_discovery --output revision/hardware/l4_20261028/discovery_001 --device-uuid GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb
