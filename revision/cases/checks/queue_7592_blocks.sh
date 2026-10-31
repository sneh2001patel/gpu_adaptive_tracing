#!/bin/bash
# vllm#7592 confirmation (proposal §4.1, §10 step 2b): 5 blocks; each block runs v0.5.5 and v0.6.0 once, in a
# counterbalanced order (ab, ba, ab, ba, ab), with a fresh engine process per run. (A seeded random draw gave 'ba' for
# all five blocks, so it was replaced before any block completed.) Same benchmark as the round-1 check.
# Start with: nohup setsid ./queue_7592_blocks.sh > queue_7592_blocks.log 2>&1 < /dev/null &
cd /workspace/cases
export HF_HUB_OFFLINE=1
M=/dev/shm/hf-cache/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28
log() { echo "$(date -u +%FT%TZ) $*"; }
done_json() { [ -f "$1" ] && tail -1 "$1" | grep -q '^{'; }

for e in v055 v060; do [ -x $e/bin/python ] || { log "build $e"; ./setup_case_env.sh $e; }; done

ORDERS="ab ba ab ba ab"
log "block orders (a=v055, b=v060): $ORDERS"
b=0
for order in $ORDERS; do
  b=$((b+1))
  for c in $(echo $order | fold -w1); do
    e=$([ $c = a ] && echo v055 || echo v060)
    out=7592_block${b}_$e.json
    done_json $out && continue
    log "block $b run $e"
    $e/bin/python check_7592_chunked.py --model $M > $out 2> ${out%.json}.err
    log "block $b $e: $(tail -1 $out)"
  done
done
log "queue finished"
