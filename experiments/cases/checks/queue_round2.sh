#!/bin/bash
# Round-2 checks queued on the L4 host so they run without the controlling laptop.
# Start with: nohup setsid ./queue_round2.sh > queue_round2.log 2>&1 &
# Each step is skipped if its result file already ends in a JSON line, so the queue can be restarted safely.
cd /workspace/cases
export HF_HOME=/dev/shm/hf-cache HF_XET_CHUNK_CACHE_SIZE_BYTES=0

done_json() { [ -f "$1" ] && tail -1 "$1" | grep -q '^{'; }
log() { echo "$(date -u +%FT%TZ) $*"; }

# Wait for any check started from the laptop session to finish.
while pgrep -f check_25418_mm_kwargs.py > /dev/null; do sleep 30; done

# vllm#25418 before fix (rerun only if the laptop-session run did not finish)
for k in none per_request; do
  done_json 25418_v0110_$k.json || { log "run 25418 v0110 $k"; v0110/bin/python check_25418_mm_kwargs.py --kwargs $k > 25418_v0110_$k.json 2> 25418_v0110_$k.err; }
done
rm -rf v0110

# vllm#25418 after fix
log "build v0111"; ./setup_case_env.sh v0111
for k in none per_request; do
  done_json 25418_v0111_$k.json || { log "run 25418 v0111 $k"; v0111/bin/python check_25418_mm_kwargs.py --kwargs $k > 25418_v0111_$k.json 2> 25418_v0111_$k.err; }
done
rm -rf v0111

# vllm#19732: xgrammar 0.1.19 (vLLM 0.9.2 pin) then 0.1.21 (fix), same environment
log "build v092"; ./setup_case_env.sh v092
done_json 19732_xg0119.json || { log "run 19732 xgrammar 0.1.19"; v092/bin/python check_19732_xgrammar.py > 19732_xg0119.json 2> 19732_xg0119.err; }
VIRTUAL_ENV=$PWD/v092 uv pip install -q --no-deps "xgrammar==0.1.21"
done_json 19732_xg0121.json || { log "run 19732 xgrammar 0.1.21"; v092/bin/python check_19732_xgrammar.py > 19732_xg0121.json 2> 19732_xg0121.err; }

log "queue finished"
df -h / /dev/shm
