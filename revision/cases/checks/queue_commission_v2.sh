#!/bin/bash
# Commissioning check 4, rule v2 (step 053): new healthy baseline (in-flight age, per-token family time), then the
# 20 req/s overload for every arm. Provisional thresholds; commissioning only, not calibration.
# Start with: nohup setsid ./queue_commission_v2.sh > queue_commission_v2.log 2>&1 < /dev/null &
cd /workspace/cases
export HF_HOME=/dev/shm/hf-cache HF_HUB_OFFLINE=1
log() { echo "$(date -u +%FT%TZ) $*"; }
D=episodes_commission_v2
mkdir -p $D
M=$(tail -1 episodes_commission/model_path.txt)
cp episodes_commission/healthy.jsonl episodes_commission/overload20.jsonl $D/
cat > $D/thresholds_provisional.json <<'EOF'
{"latency_ratio": 1.5, "waiting_requests": 4, "kv_usage": 0.9, "preemptions_per_s": 0.5, "gpu_util": 0.6,
 "busy_fraction": 0.5, "kernel_time_ratio": 1.3, "version": "commissioning_provisional_not_calibrated_v2"}
EOF
COMMON="--env v0110 --version 0.11.0 --model $M --port 8123"
[ -f $D/baseline.json ] || { log "baseline"; python3 run_episode.py $COMMON --schedule $D/healthy.jsonl --out $D/baseline --baseline-out $D/baseline.json --drain-seconds 10; }
log "baseline: $(python3 -c "import json;d=json.load(open('$D/baseline.json'));print({k:d.get(k) for k in ('p95_base_s','n_windows','completed_p95_s','baseline_ns_per_token','baseline_tokens','baseline_busy_fraction')})")"
for spec in "NT" "FIX 3" "SS" "HS"; do
  set -- $spec; arm=$1; n=${2:-3}; tag=$arm$([ $arm = FIX ] && echo $n)
  [ -f $D/$tag/summary.json ] && grep -q '"episode"' $D/$tag/summary.json && continue
  log "arm $tag"
  python3 run_episode.py $COMMON --schedule $D/overload20.jsonl --out $D/$tag --arm $arm --fixed-bursts $n \
    --thresholds $D/thresholds_provisional.json --baseline $D/baseline.json --drain-seconds 60
done
log "queue finished"
