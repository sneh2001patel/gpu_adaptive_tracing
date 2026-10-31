#!/bin/bash
# Proposal §10 step 7: calibration sessions (CALIBRATION_PLAN.md §3). Only toggle-off (fixed) sides and controlled
# cases run here; no bug side is ever started. Every non-baseline session is arm NT with four scheduled calibration
# bursts in the intervention phase (75, 105, 135, 165 s), which never reach the controller.
#   ./queue_calibration.sh prerun   seed 100: controlled conditions only, to check each intervention (never used for θ)
#   ./queue_calibration.sh main     seeds 101-103: controlled conditions, then the five real cases' fixed sides
#   ./queue_calibration.sh main "7619"   the same, for the listed units only
# Start with: nohup setsid ./queue_calibration.sh <phase> > queue_calibration_<phase>.log 2>&1 < /dev/null &
cd /workspace/cases
# Models in RAM (/dev/shm); environments on disk, hardlinked into one uv cache (see queue_case_symptoms.sh).
export HF_HOME=/dev/shm/hf-cache HF_XET_CHUNK_CACHE_SIZE_BYTES=0 UV_CACHE_DIR=/workspace/uv-cache UV_LINK_MODE=hardlink
unset UV_NO_CACHE
log() { echo "$(date -u +%FT%TZ) $*"; }
PHASE=$1
case $PHASE in
  prerun) SEEDS="100"; ROOT=calibration_prerun; UNITS="controlled" ;;
  main)   SEEDS="101 102 103"; ROOT=calibration; UNITS="controlled 6240 7619 7592 25418 3087" ;;  # disk: v051 goes before v055/v060
  *) echo "usage: $0 prerun|main [units]" >&2; exit 1 ;;
esac
[ -n "$2" ] && UNITS="$2"  # e.g. rerun one unit; finished sessions are skipped
CTL=${CTL:-"ctl_overload ctl_kv ctl_engine_stall ctl_lull ctl_shift ctl_overlap"}
SHAPE="--warmup 60 --incident 120 --tail 60"
CAL="--calibration-bursts 75,105,135,165"
mkdir -p $ROOT
cp symptoms/thresholds_provisional.json $ROOT/
field() { python3 -c "import case_workloads as c; print(c.config('$1', '$2').get('$3') or '')"; }
envs_of() { for s in bug fixed; do python3 -c "import case_workloads as c, sys; s='$s'; k='$1'
d = c.CASES.get(k) or c.CONTROLLED[k]
print(c.config(k, s)['env'] if s in d['configs'] else '')"; done | sort -u | grep .; }
unit_case() { [ $1 = controlled ] && echo ctl_healthy || echo $1; }
free() { echo "disk $(df -h --output=avail / | tail -1 | tr -d ' '), shm $(df -h --output=avail /dev/shm | tail -1 | tr -d ' ')"; }

prune_reports() {  # keep the exported SQLite (all analysis reads it); drop raw reports only if disk runs short
  if [ $(df --output=avail / | tail -1) -lt 3000000 ]; then
    find $ROOT -name 'burst_*.nsys-rep' -delete && log "disk below 3 GB: removed raw .nsys-rep files ($(free))"
  fi
}

session() {  # <case> <out dir> <done file> <run_episode args...>; skipped when the done file exists
  local case=$1 out=$2 done=$3; shift 3
  [ -f "$done" ] && return 0
  log "  $case -> $out"
  python3 run_case.py --case $case --side fixed --out $out "$@"
  grep -q '"episode": {' $out/summary.json 2>/dev/null && touch $out/done
  prune_reports
}

for unit in $UNITS; do
  key=$(unit_case $unit)
  log "unit $unit: start ($(free))"
  for env in $(envs_of $key); do
    if [ ! -x $env/bin/python ]; then
      log "unit $unit: building $env ($(free))"
      ./setup_case_env.sh $env >> $ROOT/setup.log 2>&1 || { log "unit $unit: env $env failed"; rm -rf $env; continue 2; }
    fi
  done
  model=$(field $key fixed model); env=$(field $key fixed env)
  if ! HF_HUB_OFFLINE=1 $env/bin/python -c "from huggingface_hub import snapshot_download as s; s('$model')" 2>/dev/null; then
    log "unit $unit: downloading $model"
    $env/bin/python -c "from huggingface_hub import snapshot_download as s; s('$model')" >> $ROOT/setup.log 2>&1 \
      || { log "unit $unit: download failed"; continue; }
  fi
  export HF_HUB_OFFLINE=1
  for seed in $SEEDS; do
    D=$ROOT/$seed/$unit
    mkdir -p $D
    if [ $unit = controlled ]; then
      python3 make_schedule.py --model $model --seed $seed $SHAPE --pattern healthy --base-rate 1 --out $D/healthy.jsonl > /dev/null
      session ctl_healthy $D/baseline $D/baseline.json --schedule $D/healthy.jsonl --baseline-out $D/baseline.json --drain-seconds 10
      [ -f $D/baseline.json ] || { log "unit $unit seed $seed: no baseline, skipped"; continue; }
      for c in $CTL; do
        python3 make_schedule.py --model $model --seed $seed $SHAPE $(python3 -c "import case_workloads as w; print(w.CONTROLLED['$c']['schedule'])") \
          --out $D/$c.jsonl > /dev/null
        session $c $D/$c $D/$c/done --schedule $D/$c.jsonl --arm NT --thresholds $ROOT/thresholds_provisional.json \
          --baseline $D/baseline.json --drain-seconds 60 $CAL
      done
    else
      python3 make_schedule.py --case $unit --side fixed --seed $seed $SHAPE --pattern healthy --out $D/healthy.jsonl > /dev/null
      python3 make_schedule.py --case $unit --side fixed --seed $seed $SHAPE --pattern overload --out $D/incident.jsonl > /dev/null
      session $unit $D/baseline $D/baseline.json --schedule $D/healthy.jsonl --baseline-out $D/baseline.json --drain-seconds 10
      [ -f $D/baseline.json ] || { log "unit $unit seed $seed: no baseline, skipped"; continue; }
      session $unit $D/incident $D/incident/done --schedule $D/incident.jsonl --arm NT --thresholds $ROOT/thresholds_provisional.json \
        --baseline $D/baseline.json --drain-seconds 60 $CAL
    fi
    log "unit $unit seed $seed: done ($(free))"
  done
  unset HF_HUB_OFFLINE
  # free what no later unit needs: this unit's environments (except v0110, the commissioning environment, which
  # is slow to rebuild) and its model. Both are rebuilt or re-downloaded by the setup steps if needed again.
  later=$(echo $UNITS | tr ' ' '\n' | sed "1,/^$unit\$/d")
  keep_envs=$(for u in $later; do envs_of $(unit_case $u); done | sort -u)
  keep_models=$(for u in $later; do field $(unit_case $u) fixed model; done | sort -u)
  removed=0
  for env in $(envs_of $key); do
    [ $env = v0110 ] || echo "$keep_envs" | grep -qx $env || { rm -rf $env; removed=1; log "removed env $env"; }
  done
  [ $removed = 1 ] && uv cache clean -q && log "cleared uv cache ($(free))"
  echo "$keep_models" | grep -qx $model || { rm -rf "$HF_HOME/hub/models--${model//\//--}"; log "removed model $model"; }
done
log "queue finished"
