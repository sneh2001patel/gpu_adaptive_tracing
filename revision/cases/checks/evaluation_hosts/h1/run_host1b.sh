#!/bin/bash
# Host #1 after its own cases: #3087's sessions that failed on host #4 (orphaned server), then #7592 block 201 FIX3 retry.
# 201/3087/SS runs here against host #4's 201 baseline (copied); the other six 201 arms ran on #4 and are only
# marked done here by placeholders, which are removed afterwards. Block 202 of #3087 runs here in full.
cd /workspace/cases
while kill -0 2872 2>/dev/null; do sleep 30; done
export HF_HOME=/dev/shm/hf-cache
D=evaluation/201/3087
mkdir -p $D/incident && cp /workspace/h4_3087_201_baseline.json $D/baseline.json
for a in U NT FIX1 FIX3 CR HS; do mkdir -p $D/incident/$a && echo "ran on host #4" > $D/incident/$a/PLACEHOLDER && touch $D/incident/$a/done; done
echo "baseline.json copied from host #4 (the six other 201 arms ran there)" > $D/BASELINE_FROM_HOST4
./queue_evaluation.sh "201 202" 3087
for a in U NT FIX1 FIX3 CR HS; do [ -f $D/incident/$a/PLACEHOLDER ] && rm -rf $D/incident/$a; done
./queue_evaluation.sh "201" 7592
