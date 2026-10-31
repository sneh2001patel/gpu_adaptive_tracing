# vllm-project/vllm#31961: [Performance]: EPD Disaggregation Performance Testing Scripts
state=closed reason=not_planned created=2026-01-08T10:25:17Z closed=2026-07-18T02:16:00Z labels=['performance', 'stale']
cross-referenced PRs: none

## body (@Adenialzz)
### Proposal to improve performance

Hi, I noticed that epd disaggregation is now ready in vLLM. And the [blog](https://blog.vllm.ai/2025/12/15/vllm-epd.html) shows encouraging results. But we failed to get the expected performance improvement and want to troubleshoot the potential errors. Could you please provide complete testing scripts for reproduction? Thanks in advance.

### Report of performance regression

_No response_

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

_No response_

### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @NickLucche 2026-02-17T19:44:26Z
Cc @fake0fan 

## comment @fake0fan 2026-02-23T04:01:16Z
Sorry for the late reply. I just came back from vacation. However, the other colleagues and the machines storing the data won't be able to work until tomorrow. I will organize the test scripts and send them out ASAP.

## comment @fake0fan 2026-02-24T02:15:32Z
@Adenialzz  The following is the testing scripts.

# 1️⃣ Non‑Disaggregated Serving (Single Unified Instance)

This configuration runs **vLLM in unified mode**, where encoding, prefill, and decode are handled within the same server instance using data parallelism.

## Launch Command

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 vllm serve /workspace/models/Qwen3-VL-4B-Instruct/ \
    --gpu-memory-utilization 0.8 \
    --trust-remote-code \
    --data-parallel-size 4 \
    --enforce-eager \
    --max-num-seqs 64
```
---

# 2️⃣ EPD Disaggregated Serving (Encoder–Prefill–Decode Separation)

## 2.1 Encoder Worker (Producer)

```bash
CUDA_VISIBLE_DEVICES="$GPU_E" vllm serve "$MODEL" \
    --gpu-memory-utilization 0.5 \
    --port "$E_PORT" \
    --enforce-eager \
    --enable-request-id-headers \
    --no-enable-prefix-caching \
    --max-num-batched-tokens 65536 \
    --max-num-seqs $NUM_SEQ \
    --ec-transfer-config '{
        "ec_connector": "ECSharedStorageConnector",
        "ec_role": "ec_producer",
[... 3 lines truncated ...]
    >"${ENC_LOG}" 2>&1 &
```

## 2.2 Prefill+Decode Workers (Consumers)

Each worker runs on a separate GPU.

```bash
CUDA_VISIBLE_DEVICES="$GPU_PD" VLLM_NIXL_SIDE_CHANNEL_PORT=6000 vllm serve "$MODEL" \
    --gpu-memory-utilization 0.8 \
    --port "$PD_PORT" \
    --enforce-eager \
    --enable-request-id-headers \
    --max-num-seqs $NUM_SEQ \
    --ec-transfer-config '{
        "ec_connector": "ECSharedStorageConnector",
        "ec_role": "ec_consumer",
        "ec_connector_extra_config": {
            "shared_storage_path": "'"$EC_SHARED_STORAGE_PATH"'"
[... 1 lines truncated ...]
    >"${PD_LOG}" 2>&1 &
```

```bash
CUDA_VISIBLE_DEVICES="$GPU_PD2" VLLM_NIXL_SIDE_CHANNEL_PORT=6001 vllm serve "$MODEL" \
    --gpu-memory-utilization 0.8 \
    --port "$PD2_PORT" \
    --enforce-eager \
    --enable-request-id-headers \
    --max-num-seqs $NUM_SEQ \
    --ec-transfer-config '{
        "ec_connector": "ECSharedStorageConnector",
        "ec_role": "ec_consumer",
        "ec_connector_extra_config": {
            "shared_storage_path": "'"$EC_SHARED_STORAGE_PATH"'"
[... 1 lines truncated ...]
    >"${PD2_LOG}" 2>&1 &
```

```bash
CUDA_VISIBLE_DEVICES="$GPU_PD3" VLLM_NIXL_SIDE_CHANNEL_PORT=6002 vllm serve "$MODEL" \
    --gpu-memory-utilization 0.8 \
    --port "$PD3_PORT" \
    --enforce-eager \
    --enable-request-id-headers \
    --max-num-seqs $NUM_SEQ \
    --ec-transfer-config '{
        "ec_connector": "ECSharedStorageConnector",
        "ec_role": "ec_consumer",
        "ec_connector_extra_config": {
            "shared_storage_path": "'"$EC_SHARED_STORAGE_PATH"'"
[... 1 lines truncated ...]
    >"${PD3_LOG}" 2>&1 &
```

## 2.3 Proxy Layer

```bash
python disagg_epd_proxy.py \
    --host "0.0.0.0" \
    --port "$PROXY_PORT" \
    --encode-servers-urls "http://localhost:$E_PORT" \
    --prefill-servers-urls "disable" \
    --decode-servers-urls "http://localhost:$PD_PORT,http://localhost:$PD2_PORT,http://localhost:$PD3_PORT" \
    >"${PROXY_LOG}" 2>&1 &
```

# 3️⃣ Benchmark Script (Load Testing)

The following script runs systematic benchmarking over:

- Request rate: 4–32
- Input length: 400–2000
- Image count per request: 1–4
- 1000 prompts per configuration

```bash
for request_rate in 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32; do
  for input_len in 400 800 1200 1600 2000; do
    for image_num in 1 2 3 4; do

      echo "Running experiment: request_rate=${request_rate}, input_len=${input_len}, image_num=${image_num}"

      vllm bench serve \
        --dataset-name random-mm \
        --model /workspace/models/Qwen3-VL-4B-Instruct/ \
        --endpoint /v1/chat/completions \
        --backend openai-chat \
[... 15 lines truncated ...]
done
```

If you have any further questions, please feel free to contact me.

## comment @NickLucche 2026-02-24T09:56:25Z
Thank you @fake0fan !

## comment @rmccorm4 2026-02-24T16:11:53Z
Thank you @fake0fan!

Just curious, why do you use `--enforce-eager` in this setup?

## comment @Adenialzz 2026-02-25T02:38:28Z
Thank you all. We will conduct the test again with this script.

## comment @fake0fan 2026-02-25T03:21:58Z
> Thank you [@fake0fan](https://github.com/fake0fan)!
> 
> Just curious, why do you use `--enforce-eager` in this setup?

I remember that at the time, if we didn't turn this on, the Encoder instance seemed to fail during profiling. However, I don't remember why the PD side was also enabled; it should be removable.  

## comment @dikongfeixing8 2026-03-02T03:01:23Z
> Thank you all. We will conduct the test again with this script.

Hello, Have you successfully reproduced it?
@Adenialzz 

## comment @Adenialzz 2026-03-03T07:15:34Z
Not yet. busy with other works recently :(

## comment @kunxiongzhu 2026-03-05T21:28:12Z
> > Thank you all. We will conduct the test again with this script.
> 
> Hello, Have you successfully reproduced it? [@Adenialzz](https://github.com/Adenialzz)

I ran experiments using Qwen2.5-VL-7B-Instruct on 4× A6000 GPUs. I tested request rates 4, 8, 16, and 32, and kept the other settings the same as described above. In addition, each request contains 4 images, which should further increase the encoding cost and theoretically make EPD more beneficial. The vLLM version is 0.14.1.

With input length = 400 tokens, the results show that the baseline configuration (vLLM DP=4) performs better in most cases.

I also tested input length = 2000 tokens to increase the encoding workload, but EPD performs even worse in this case.

Below is my script.

```
#!/bin/bash
set -euo pipefail

MODE="${1:-}"

############################################
# Global experiment config (edit here)
############################################
MODEL="Qwen/Qwen2.5-VL-7B-Instruct"

NUM_PROMPTS=1000
[... 243 lines truncated ...]
esac
```

Below are the experiment results (red indicates performance degradation, green indicates improvement).

<img width="1236" height="430" alt="Image" src="https://github.com/user-attachments/assets/0645d576-b9b0-458f-9245-be19ad43db27" />

@fake0fan Could you plz tell me why is there such a large discrepancy compared to the results shown in the blog above? The blog claims that EPD outperforms the baseline in almost all cases.

## comment @fake0fan 2026-03-06T01:59:52Z
@kunxiongzhu  Thank you for your testing. I reviewed the experimental data at the time and found that the performance of both EPD and DP4 did not quite match up. I’m not sure whether this is due to hardware differences or some configuration misalignment. I’ve asked my colleagues to start looking into this issue, and I will provide feedback as soon as we have any results.

## comment @kunxiongzhu 2026-03-09T05:32:18Z
> [@kunxiongzhu](https://github.com/kunxiongzhu) Thank you for your testing. I reviewed the experimental data at the time and found that the performance of both EPD and DP4 did not quite match up. I’m not sure whether this is due to hardware differences or some configuration misalignment. I’ve asked my colleagues to start looking into this issue, and I will provide feedback as soon as we have any results.

Thank you! May I know are there any updates?

## comment @fake0fan 2026-03-14T09:17:03Z
> > [@kunxiongzhu](https://github.com/kunxiongzhu) Thank you for your testing. I reviewed the experimental data at the time and found that the performance of both EPD and DP4 did not quite match up. I’m not sure whether this is due to hardware differences or some configuration misalignment. I’ve asked my colleagues to start looking into this issue, and I will provide feedback as soon as we have any results.
> 
> Thank you! May I know are there any updates?

Sorry for the late reply. I’ve been on a business trip all week. However, my colleagues have conducted some tests. I will sync up with them next week and provide an update.

## comment @herotai214 2026-03-16T12:54:32Z
@Adenialzz @kunxiongzhu 

Hi, thank you for the detailed report and for sharing your scripts – this is very helpful for the community. I am one of the authors of the initial EPD PR #25233 commit.

**In short:** We can reproduce the expected EPD gains in **v0.11.1**; but in **v0.14.1** the degradation you observe is partly due to the fact that the baseline has improved significantly, narrowing the gap.

EPD still achieves TTFT gain in some scenario.
Indeed, we should continue working on optimizing EPD to keep pace with baseline advancements.

## Version differences

The blog results were obtained with vLLM **v0.11.1** (the first release containing EPD, via PR #25233).
I ran your script with that version on 4×A100 80G with vLLM **v0.11.1** and successfully reproduced the performance gains – no degradation in any scenario.

<img width="734" height="248" alt="Image" src="https://github.com/user-attachments/assets/4e9ef26e-1e1d-419e-a6c1-28c3048a2033" />

(**Model: Qwen2.5-VL-7B-Instruct**, same as your script)


However, when I upgraded to **v0.14.1**, I also observed that the baseline (DP=4) has improved considerably over the past few months, making the relative EPD advantage smaller. This likely explains the discrepancy you see.

## One more factor: CPU contention
With multimodal models (especially when processing images), CPU contention can introduce instability. I found that limiting the number of CPU threads helps stabilise performance. A simple workaround is to patch the multimodal processor as follows:
```python
def apply(self, prompt, mm_data, hf_processor_mm_kwargs, ...) -> MultiModalInputs:
    # Manually add these 2 lines	
    num_threads = int(os.environ.get("OMP_NUM_THREADS", "1"))
    with set_default_torch_num_threads(num_threads):
        # original function codes
```
Adding this before launching vLLM helps reduce performance variability. We will soon propose this approach in vLLM to see if this is suitable to be merged.

## v0.14.1 - Looking deeper: distributions vs. aggregates
Aggregate metrics (mean, p99) can be heavily influenced by outliers. I therefore extracted per-request data (using --save-detailed) and plotted the full distributions.
```
# Add below flags to your vllm bench serve
      --save-result \
      --save-detailed \
      --result-dir $RESULT_DIR \
      --result-filename $RESULT_FILENAME.json \
```

(Note: Below shows both with/without CPU limitation can achieve similar results; The CPU limitation setting is just to ensure stability.)

(Note2: Cannot get TPOT distribution for the moment: For some reasons, the result json file only gives TTFT and inter-token latency. I have to manually calcuate the per-request TPOT , but somehow the statistics (median) does not align with the mean/median returned from `vllm bench`...)  

### Table figures with **v0.14.1:**
**No CPU limitation:**
<img width="782" height="240" alt="Image" src="https://github.com/user-attachments/assets/12bdbc9b-7ae5-44c2-a66a-c84777d107a2" />

**OMP_NUM_THREADS=1:**
<img width="782" height="239" alt="Image" src="https://github.com/user-attachments/assets/e03aea5d-dde4-4325-8ace-5a41530f4bf1" />

### Detailed distribution (TTFT):
**No CPU limitation:**
<img width="2400" height="1200" alt="ttft_no_cpu" src="https://github.com/user-attachments/assets/9c71dbb1-a608-40f2-9286-f4251902ca28" />

**OMP_NUM_THREADS=1:**
<img width="2400" height="1200" alt="ttft_cpu" src="https://github.com/user-attachments/assets/14893b7c-1d40-4590-8632-39f3b2ba7545" />



### Findings
At **v0.14.1**...
- TTFT: At low rates (4, 8) EPD’s TTFT is similar or slightly higher; at higher rates (16, 32) EPD shows better TTFT distributions.
- The mean/p99 values in tables are pulled upward by long-tail outliers (points beyond the whiskers). 
- My results is not as worse as @kunxiongzhu 's. Hardware difference may be the reason, but setting the CPU limitation mentioned above may also help reduce instability and reach this result. I consistently achieve gain at rates (16, 32)

It is also noticeable that, the EPD figures do not vary much compared to **v0.11.1**, but the baseline has improved a lot, especially the TTFT part.

## Conclusion
I believe that the EPD code itself is not broken. The performance gain reported in the blog is reproducible in **v0.11.1.** The reduced gain in later versions comes from baseline improvements, not EPD regressions.
I would encourage everyone to:

1. Try **v0.11.1** to confirm the original gain. (To see if hardware difference matters significantly, etc…) 
2. Apply the CPU thread limit workaround and see if helps performance.
3. Provide ideas or even commit codes to further optimize the current EPD.

Thank you again for raising this – it highlights the importance of tracking performance across releases. Together, we can work on optimizing EPD to keep pace with baseline advancements.


## comment @github-actions[bot] 2026-06-17T02:21:52Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2026-07-18T02:15:59Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!