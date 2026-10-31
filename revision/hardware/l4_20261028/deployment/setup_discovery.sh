set -e
mkdir /workspace/gpu_adaptive_tracing_step021
tar -xzf /tmp/step021_source.tar.gz -C /workspace/gpu_adaptive_tracing_step021
mkdir -p /workspace/gpu_adaptive_tracing_step021/revision/hardware/l4_20261028
cat > /opt/supervisor-scripts/revision-l4-discovery-021.sh <<'EOF'
#!/bin/bash
set -e
. /opt/supervisor-scripts/utils/logging.sh
. /opt/supervisor-scripts/utils/environment.sh
cd /workspace/gpu_adaptive_tracing_step021
export HF_HOME=/dev/shm/hf-cache
export HF_HUB_DISABLE_XET=1
export HF_HUB_DOWNLOAD_TIMEOUT=60
exec /workspace/envs/vllm/bin/python -u -m revision.scripts.run_l4_discovery --output revision/hardware/l4_20261028/discovery_001 --device-uuid GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb
EOF
chmod 700 /opt/supervisor-scripts/revision-l4-discovery-021.sh
cat > /etc/supervisor/conf.d/revision-l4-discovery-021.conf <<'EOF'
[program:revision-l4-discovery-021]
command=/opt/supervisor-scripts/revision-l4-discovery-021.sh
environment=PROC_NAME="revision-l4-discovery-021"
autostart=false
autorestart=false
stopsignal=INT
stopasgroup=true
killasgroup=true
stdout_logfile=/workspace/gpu_adaptive_tracing_step021/revision/hardware/l4_20261028/discovery_service.log
stderr_logfile=/workspace/gpu_adaptive_tracing_step021/revision/hardware/l4_20261028/discovery_service.stderr.log
stdout_logfile_maxbytes=10000000
stderr_logfile_maxbytes=10000000
EOF
supervisorctl reread
supervisorctl update revision-l4-discovery-021
supervisorctl start revision-l4-discovery-021
