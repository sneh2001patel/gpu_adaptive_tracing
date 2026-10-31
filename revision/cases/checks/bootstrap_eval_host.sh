#!/bin/bash
# Prepare a fresh vast.ai L4 for queue_evaluation.sh: checks the GPU and Nsight version, unpacks the case code
# (cases_code.tgz + queue_evaluation.sh, copied to /workspace beforehand), and reports disk and /dev/shm.
set -e
mkdir -p /workspace/cases && cd /workspace/cases
tar xzf /workspace/cases_code.tgz && mv /workspace/queue_evaluation.sh . && chmod +x *.sh
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
if ! nsys --version 2>/dev/null | grep -q 2026.3.1; then
  echo "installing Nsight 2026.3.1 (current: $(nsys --version 2>&1 | head -1))"
  apt-get update -qq && apt-get install -y -qq nsight-compute-2026.3.1 > /dev/null
  ln -sf /opt/nvidia/nsight-compute/2026.3.1/host/target-linux-x64/nsys /usr/local/bin/nsys
fi
nsys --version
command -v uv > /dev/null || pip install -q uv
uv --version
python3 --version
df -h --output=avail,size / /dev/shm
mount | grep -q '/dev/shm.*noexec' && echo "shm noexec (models only, as on the first host)" || true
