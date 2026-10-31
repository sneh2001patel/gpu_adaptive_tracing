set -e
mkdir /workspace/gpu_adaptive_tracing_step025
tar -xzf /tmp/step025_source.tar.gz -C /workspace/gpu_adaptive_tracing_step025
cat > /opt/supervisor-scripts/revision-l4-pairs-025.sh <<'SH'
#!/bin/bash
set -e
. /opt/supervisor-scripts/utils/logging.sh
. /opt/supervisor-scripts/utils/environment.sh
cd /workspace/gpu_adaptive_tracing_step025
exec /workspace/envs/vllm/bin/python -u -m revision.scripts.run_l4_pairs --output revision/hardware/l4_20261028/pairs_001 --pairs revision/hardware/l4_20261028/capacity_001/paired_schedules --model-path /dev/shm/hf-cache/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 --device-uuid GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb
SH
chmod 700 /opt/supervisor-scripts/revision-l4-pairs-025.sh
cat > /etc/supervisor/conf.d/revision-l4-pairs-025.conf <<'CONF'
[program:revision-l4-pairs-025]
command=/opt/supervisor-scripts/revision-l4-pairs-025.sh
environment=PROC_NAME="revision-l4-pairs-025"
autostart=false
autorestart=false
stopsignal=INT
stopasgroup=true
killasgroup=true
stdout_logfile=/workspace/gpu_adaptive_tracing_step025/pairs_service.log
stderr_logfile=/workspace/gpu_adaptive_tracing_step025/pairs_service.stderr.log
stdout_logfile_maxbytes=10000000
stderr_logfile_maxbytes=10000000
CONF
supervisorctl reread
supervisorctl update revision-l4-pairs-025
supervisorctl start revision-l4-pairs-025
