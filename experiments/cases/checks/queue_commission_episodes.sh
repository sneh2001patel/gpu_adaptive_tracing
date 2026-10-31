#!/bin/bash
# Commissioning check 4 (EXTERNAL_INSTRUMENT_AND_DIAGNOSIS_RULE.md §5): healthy baseline, then one overload
# episode per arm on vLLM 0.11.0 with PROVISIONAL thresholds. Commissioning only: not calibration, not a study
# session, not used to set any frozen value.
# Start with: nohup setsid ./queue_commission_episodes.sh > queue_commission_episodes.log 2>&1 < /dev/null &
cd /workspace/cases
export HF_HOME=/dev/shm/hf-cache HF_XET_CHUNK_CACHE_SIZE_BYTES=0
log() { echo "$(date -u +%FT%TZ) $*"; }
OUT=episodes_commission
mkdir -p $OUT

log "download model"
v0110/bin/python -c "from huggingface_hub import snapshot_download; print(snapshot_download('Qwen/Qwen2.5-7B-Instruct', allow_patterns=['*.json','*.safetensors','*.txt','tokenizer*','merges.txt','vocab.json']))" > $OUT/model_path.txt
M=$(tail -1 $OUT/model_path.txt)
log "model at $M"

python3 make_schedule.py --pattern healthy --model "$M" --base-rate 1 --warmup 40 --incident 40 --tail 40 --seed 1 --out $OUT/healthy.jsonl
python3 make_schedule.py --pattern overload --model "$M" --base-rate 1 --high-rate 6 --warmup 60 --incident 90 --tail 60 --seed 2 --out $OUT/overload.jsonl
cat > $OUT/thresholds_provisional.json <<'EOF'
{"latency_ratio": 1.5, "waiting_requests": 4, "kv_usage": 0.9, "preemptions_per_s": 0.5, "gpu_util": 0.6,
 "busy_fraction": 0.5, "kernel_share_increase": 0.15, "version": "commissioning_provisional_not_calibrated"}
EOF

COMMON="--env v0110 --version 0.11.0 --model $M --port 8123"
[ -f $OUT/baseline.json ] || { log "baseline"; python3 run_episode.py $COMMON --schedule $OUT/healthy.jsonl --out $OUT/baseline --baseline-out $OUT/baseline.json --drain-seconds 10; }
log "baseline: $(head -c 300 $OUT/baseline.json)"

for spec in "NT" "FIX 3" "SS" "HS"; do
  set -- $spec; arm=$1; n=${2:-3}; tag=$arm$([ $arm = FIX ] && echo $n)
  [ -f $OUT/$tag/summary.json ] && grep -q '"episode"' $OUT/$tag/summary.json && continue
  log "arm $tag"
  python3 run_episode.py $COMMON --schedule $OUT/overload.jsonl --out $OUT/$tag --arm $arm --fixed-bursts $n \
    --thresholds $OUT/thresholds_provisional.json --baseline $OUT/baseline.json --drain-seconds 30
  log "arm $tag done"
done
log "queue finished"
