#!/bin/bash
# Proposal §10 step 8: evaluation blocks under the frozen thresholds (EVALUATION_PLAN.md). Real cases run their
# bug side against a healthy baseline of their fixed side (the last known-good version, as in steps 6 and 7);
# controlled cases their only side. A block is one seed: per unit, a healthy baseline, then every arm on
# the same offered schedule in a per-(seed, unit) random order, each on a fresh server. Units run one after another
# (all seeds of a unit before the next), so each environment is built once; several hosts split the units.
#   ./queue_evaluation.sh "201 202"                blocks 201-202, all units
#   ./queue_evaluation.sh "201" "controlled 6240"   the listed units only; finished sessions are skipped
#   CTL="ctl_overload ctl_kv" ./queue_evaluation.sh "202" controlled    a subset of the controlled conditions
# Start with: nohup setsid ./queue_evaluation.sh "<seeds>" > queue_evaluation.log 2>&1 < /dev/null &
cd /workspace/cases
export HF_HOME=${HF_HOME:-/dev/shm/hf-cache} HF_XET_CHUNK_CACHE_SIZE_BYTES=0 UV_CACHE_DIR=/workspace/uv-cache UV_LINK_MODE=hardlink
unset UV_NO_CACHE
log() { echo "$(date -u +%FT%TZ) $*"; }
SEEDS=${1:?usage: $0 "<seeds>" [units]}
UNITS=${2:-"controlled 6240 7619 7592 25418 3087"}  # #19732 excluded (not reproduced under serving)
CTL=${CTL:-"ctl_overload ctl_kv ctl_engine_stall ctl_lull ctl_shift ctl_overlap ctl_persistent ctl_withhold"}
ARMS="U NT FIX1 FIX3 SS CR HS"
ROOT=evaluation
TH=thresholds_study_rule_v2_calibrated_2026-10-29.json
SHAPE="--warmup 60 --incident 120 --tail 60"
[ "$(python3 -c "import hashlib,json;print(hashlib.sha256(json.dumps(json.load(open('$TH')),sort_keys=True).encode()).hexdigest())")" \
  = "$(cat ${TH%.json}.sha256)" ] || { log "thresholds digest mismatch: $TH"; exit 1; }
mkdir -p $ROOT
cp $TH ${TH%.json}.sha256 $ROOT/
field() { python3 -c "import case_workloads as c; print(c.config('$1', '$2').get('$3') or '')"; }
envs_of() { python3 -c "import case_workloads as c; print(c.config('$1', '$2')['env'])"; }
unit_case() { [ $1 = controlled ] && echo ctl_healthy || echo $1; }
unit_side() { [ $1 = controlled ] && echo fixed || echo bug; }
free() { echo "disk $(df -h --output=avail / | tail -1 | tr -d ' '), shm $(df -h --output=avail /dev/shm | tail -1 | tr -d ' ')"; }
arm_args() {
  case $1 in
    U) echo "--arm NT --unprofiled" ;; NT) echo "--arm NT" ;; FIX1) echo "--arm FIX --fixed-bursts 1" ;;
    FIX3) echo "--arm FIX --fixed-bursts 3" ;; SS|CR|HS) echo "--arm $1" ;;
  esac
}
arm_order() {  # deterministic per (seed, unit): reruns keep the order; recorded beside the sessions
  python3 -c "import random; a='$ARMS'.split(); random.Random('$1:$2').shuffle(a); print(' '.join(a))"
}

prune_reports() {  # keep the exported SQLite; drop raw reports only if disk runs short
  if [ $(df --output=avail / | tail -1) -lt 3000000 ]; then
    find $ROOT -name 'burst_*.nsys-rep' -delete && log "disk below 3 GB: removed raw .nsys-rep files ($(free))"
  fi
}

SERVER='^/workspace/cases/v[0-9]+/bin/python'  # the server and its engine workers run from a case env
gpu_clear() {  # a server orphaned by `nsys shutdown` keeps its GPU memory and would starve every later session
  local i
  for i in $(seq 45); do
    [ -z "$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)" ] && return 0
    if [ $i = 30 ]; then
      log "  GPU still in use 60 s after the last session: killing $(pgrep -f -d ' ' "$SERVER")"
      pkill -9 -f "$SERVER"
    fi
    sleep 2
  done
  log "  GPU still in use; starting anyway"
}

session() {  # <case> <side> <out dir> <done file> <run_episode args...>; skipped when the done file exists
  local case=$1 side=$2 out=$3 done=$4; shift 4
  [ -f "$done" ] && return 0
  gpu_clear
  log "  $case/$side -> $out"
  python3 run_case.py --case $case --side $side --out $out "$@"
  case $done in */done) ;; *) prune_reports; return 0 ;; esac  # a baseline's done file is its baseline.json
  # done = finished without a runner error (a failed session is kept and logged; rerunning the queue retries it)
  python3 -c "import json,sys; d=json.load(open('$out/summary.json')); sys.exit('episode' not in d or 'error' in d)" 2>/dev/null \
    && touch $out/done || log "  $out: not done (runner error or no summary)"
  prune_reports
}

arms() {  # <case> <side> <dir> <schedule>
  local case=$1 side=$2 D=$3 sched=$4 order
  order=$(arm_order $seed $case); echo "$order" > $D/arm_order.txt
  for a in $order; do
    session $case $side $D/$a $D/$a/done --schedule $sched $(arm_args $a) --thresholds $ROOT/$TH \
      --baseline $D/../baseline.json --drain-seconds 60
  done
}

for unit in $UNITS; do
  key=$(unit_case $unit); side=$(unit_side $unit)
  log "unit $unit: start ($(free))"
  env=$(envs_of $key $side); envs=$(echo $env $(envs_of $key fixed) | tr ' ' '\n' | sort -u)
  for e in $envs; do
    if [ ! -x $e/bin/python ]; then
      log "unit $unit: building $e ($(free))"
      ./setup_case_env.sh $e >> $ROOT/setup.log 2>&1 || { log "unit $unit: env $e failed"; rm -rf $e; continue 2; }
    fi
  done
  model=$(field $key $side model)
  if ! HF_HUB_OFFLINE=1 $env/bin/python -c "from huggingface_hub import snapshot_download as s; s('$model')" 2>/dev/null; then
    log "unit $unit: downloading $model"
    $env/bin/python -c "from huggingface_hub import snapshot_download as s; s('$model')" >> $ROOT/setup.log 2>&1 \
      || { log "unit $unit: download failed"; continue; }
  fi
  export HF_HUB_OFFLINE=1
  for seed in $SEEDS; do
    log "block $seed unit $unit: start"
    D=$ROOT/$seed/$unit
    mkdir -p $D
    echo "$(hostname) $(nvidia-smi --query-gpu=name,uuid --format=csv,noheader) CTL=$CTL" >> $D/hosts.txt
    if [ $unit = controlled ]; then
      python3 make_schedule.py --model $model --seed $seed $SHAPE --pattern healthy --base-rate 1 --out $D/healthy.jsonl > /dev/null
      session ctl_healthy fixed $D/baseline $D/baseline.json --schedule $D/healthy.jsonl --baseline-out $D/baseline.json --drain-seconds 10
      if [ -f $D/baseline.json ]; then
        for c in $CTL; do
          mkdir -p $D/$c
          python3 make_schedule.py --model $model --seed $seed $SHAPE $(python3 -c "import case_workloads as w; print(w.CONTROLLED['$c']['schedule'])") \
            --out $D/$c/schedule.jsonl > /dev/null
          arms $c fixed $D/$c $D/$c/schedule.jsonl
        done
      else
        log "block $seed unit $unit: no baseline, skipped"
      fi
    else
      python3 make_schedule.py --case $unit --side fixed --seed $seed $SHAPE --pattern healthy --out $D/healthy.jsonl > /dev/null
      python3 make_schedule.py --case $unit --side bug --seed $seed $SHAPE --pattern overload --out $D/incident.jsonl > /dev/null
      session $unit fixed $D/baseline $D/baseline.json --schedule $D/healthy.jsonl --baseline-out $D/baseline.json --drain-seconds 10
      if [ -f $D/baseline.json ]; then
        mkdir -p $D/incident
        arms $unit bug $D/incident $D/incident.jsonl
      else
        log "block $seed unit $unit: no baseline, skipped"
      fi
    fi
    log "block $seed unit $unit: done ($(free))"
  done
  unset HF_HUB_OFFLINE
  # Free this unit's environment (except v0110) and model before the next unit.
  for e in $envs; do [ $e = v0110 ] || { rm -rf $e; log "removed env $e"; }; done; uv cache clean -q
  [ $unit = controlled ] || { rm -rf "$HF_HOME/hub/models--${model//\//--}"; log "removed model $model ($(free))"; }
done
log "queue finished"
