#!/bin/bash
# Proposal §10 step 6 gate: each accepted case shows its symptom under the external instrument with its toggle.
# Per case: one healthy baseline on the fixed side (--baseline-out), then NT sessions on the fixed and the bug side
# with the same incident schedule (warm-up at the healthy rate, 120 s at the incident rate, 60 s tail).
# Provisional thresholds (commissioning values); nothing here calibrates or freezes anything.
# Cases are ordered to fit the disk and reuse environments; an environment or model this queue built or downloaded
# is removed once no later case needs it (32 GB disk, 17 GB /dev/shm).
# Start with: nohup setsid ./queue_case_symptoms.sh [case ...] > queue_case_symptoms.log 2>&1 < /dev/null &
cd /workspace/cases
# Models live in RAM (/dev/shm, 31 GB). Environments stay on disk (/dev/shm is noexec) as hardlinks into a uv cache on
# the same disk, so wheels shared by two releases are stored once; the cache is cleared after environments are removed.
export HF_HOME=/dev/shm/hf-cache HF_XET_CHUNK_CACHE_SIZE_BYTES=0 UV_CACHE_DIR=/workspace/uv-cache UV_LINK_MODE=hardlink
unset UV_NO_CACHE  # the vast.ai image sets UV_NO_CACHE=1 and UV_LINK_MODE=copy in /etc/environment
log() { echo "$(date -u +%FT%TZ) $*"; }
D=symptoms
mkdir -p $D
CASES=${*:-"19732 3087 7619 7592 6240"}  # 7619 and 7592 share v055 (and torch with v060); 7619 and 6240 share a model
cat > $D/thresholds_provisional.json <<'EOF'
{"latency_ratio": 1.5, "waiting_requests": 4, "kv_usage": 0.9, "preemptions_per_s": 0.5, "gpu_util": 0.6,
 "busy_fraction": 0.5, "kernel_time_ratio": 1.3, "version": "commissioning_provisional_not_calibrated_v2"}
EOF
field() { python3 -c "import case_workloads as c; print(c.config('$1', '$2').get('$3') or '')"; }
envs_of() { for s in bug fixed; do field $1 $s env; done | sort -u; }
built_envs="" fetched_models=""

for case in $CASES; do
  log "case $case: start"
  for env in $(envs_of $case); do
    if [ ! -x $env/bin/python ]; then
      log "case $case: building $env (free: disk $(df -h --output=avail / | tail -1 | tr -d " "), shm $(df -h --output=avail /dev/shm | tail -1 | tr -d " "))"
      ./setup_case_env.sh $env >> $D/setup.log 2>&1 || { log "case $case: env $env failed"; rm -rf $env; continue 2; }
      built_envs="$built_envs $env"
    fi
  done
  model=$(field $case fixed model); env=$(field $case fixed env)
  if ! HF_HUB_OFFLINE=1 $env/bin/python -c "from huggingface_hub import snapshot_download as s; s('$model')" 2>/dev/null; then
    log "case $case: downloading $model"
    $env/bin/python -c "from huggingface_hub import snapshot_download as s; s('$model')" >> $D/setup.log 2>&1 \
      || { log "case $case: download failed"; continue; }
    fetched_models="$fetched_models $model"
  fi
  export HF_HUB_OFFLINE=1
  C=$D/$case
  mkdir -p $C
  python3 make_schedule.py --pattern healthy --case $case --side fixed --warmup 60 --incident 120 --tail 60 --out $C/healthy.jsonl
  for side in fixed bug; do
    python3 make_schedule.py --pattern overload --case $case --side $side --warmup 60 --incident 120 --tail 60 --out $C/incident_$side.jsonl
  done
  [ -f $C/baseline.json ] || { log "case $case: baseline"; python3 run_case.py --case $case --side fixed --out $C/baseline \
      --schedule $C/healthy.jsonl --baseline-out $C/baseline.json --drain-seconds 10; }
  if [ ! -f $C/baseline.json ]; then log "case $case: no baseline, skipped"; unset HF_HUB_OFFLINE; continue; fi
  log "case $case: baseline $(python3 -c "import json;d=json.load(open('$C/baseline.json'));print({k:d.get(k) for k in ('p95_base_s','n_windows','baseline_tokens','baseline_busy_fraction')})")"
  for side in fixed bug; do
    [ -f $C/NT_$side/summary.json ] && grep -q '"episode"' $C/NT_$side/summary.json && continue
    log "case $case: NT $side"
    python3 run_case.py --case $case --side $side --out $C/NT_$side --schedule $C/incident_$side.jsonl --arm NT \
      --thresholds $D/thresholds_provisional.json --baseline $C/baseline.json --drain-seconds 60
  done
  python3 summarize_case_symptoms.py $C > $C/symptom.json && log "case $case: $(cat $C/symptom.json | tr -d '\n' | cut -c1-400)"
  unset HF_HUB_OFFLINE
  # free what no later case needs
  later=$(echo $CASES | tr ' ' '\n' | sed "1,/^$case\$/d")
  keep_envs=$(for c in $later; do envs_of $c; done | sort -u)
  keep_models=$(for c in $later; do field $c fixed model; done | sort -u)
  removed=0 still=""
  for env in $built_envs; do
    if echo "$keep_envs" | grep -qx $env; then still="$still $env"; else rm -rf $env; removed=1; log "removed env $env"; fi
  done
  built_envs=$still  # a removed environment must not count again: that would clear the cache a later build shares
  # removing an environment frees nothing while the cache still links its files
  [ $removed = 1 ] && uv cache clean -q && log "cleared uv cache (free: disk $(df -h --output=avail / | tail -1 | tr -d " "))"
  still=""
  for m in $fetched_models; do
    if echo "$keep_models" | grep -qx $m; then still="$still $m"; else rm -rf "$HF_HOME/hub/models--${m//\//--}"; log "removed model $m"; fi
  done
  fetched_models=$still
done
log "queue finished"
