# vllm-project/vllm#42520: [Performance]: performance drop between versions 0.19.1 and 0.20.1 for embedding models
state=closed reason=completed created=2026-05-13T10:37:13Z closed=2026-05-15T10:58:20Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/42709']

## body (@jpiaseck)
### Proposal to improve performance

Noticed a performance drop between version 0.19.1 and 0.20.1 both in terms of troughput and latency. 

VLLM was deployed using bellow command:

python3 -m vllm.entrypoints.openai.api_server --model BAAI/bge-base-en-v1.5 --dtype $VLLM_DTYPE --download-dir /data --host 0.0.0.0 --port 8108

and those variables:
   EMBEDDING_VLLM_MODEL_NAME: BAAI/bge-base-en-v1.5                                                                                                                                                                                                                                               
   EMBEDDING_VLLM_PORT: "8108"                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          
   VLLM_DTYPE: bfloat16                                                                                                                                                                                                                                                                           
   VLLM_TARGET_DEVICE: cpu                                                                                                                                                                                                                                                                        
   XDG_CACHE_HOME: /tmp  

First think that shows up in warnings and seems easy fix:

When loading VLLM I can see:
**vllm-embedding (APIServer pid=1) WARNING 05-13 06:34:59 [utils.py:134] To make v1/embeddings API fast, please install orjson by `pip install orjson`**
can we update image and install this pkg?

Results of comparison (different root cause that missing orjson) on in section Report of performance regression.

### Report of performance regression

comparing version 0.19.1 and 0.20.1 deployed:

python3 -m vllm.entrypoints.openai.api_server --model BAAI/bge-base-en-v1.5 --dtype $VLLM_DTYPE --download-dir /data --host 0.0.0.0 --port 8108

and those variables:
   EMBEDDING_VLLM_MODEL_NAME: BAAI/bge-base-en-v1.5                                                                                                                                                                                                                                               
   EMBEDDING_VLLM_PORT: "8108"                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          
   VLLM_DTYPE: bfloat16                                                                                                                                                                                                                                                                           
   VLLM_TARGET_DEVICE: cpu                                                                                                                                                                                                                                                                        
   XDG_CACHE_HOME: /tmp  

When uploading file trough embedding (using ENTERPRISE_RAG , file is text file there embedding takes 99% of upload time) seem:
around 12 000 tokens/sec on embedding when using version 0.19.1 
6000 tokens/sec when using version 0.20.1 

In addition in test #2 --> running 32 concurrent users that are only sending questions trough entire ERAG pipeline noticed embedding (which should be light component is becoming bottleneck). 

when using version 0.19.1 latency is around 60ms

<img width="2538" height="326" alt="Image" src="https://github.com/user-attachments/assets/b5c1e0ed-5164-47ed-b223-f074b0a1bff1" />

when using version 0.20.1 getting latency in minutes:

<img width="2540" height="230" alt="Image" src="https://github.com/user-attachments/assets/994d008b-b022-400c-9613-4dd4b50cf103" />

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @noooop 2026-05-14T03:50:33Z
https://github.com/noooop/snippet/blob/main/benchmarks/embed3/v1_online_high.py

0.20.1 and 0.19.1 have almost the same performance, if not better



<img width="1272" height="596" alt="Image" src="https://github.com/user-attachments/assets/a2fdaa61-acbf-4a22-8621-708be4ad21d4" />

The results above are from the NVIDIA device test.

## comment @noooop 2026-05-14T04:11:57Z
VLLM_TARGET_DEVICE: cpu

cc @bigPYJ1151

## comment @bigPYJ1151 2026-05-15T06:24:33Z
It is because CPU model complie was moved to ```determine_available_memory```. But for embedding models it will not be called, so the compile will be included in the benchmark phase and take more time.

Opened a fix #42709

## comment @jpiaseck 2026-05-15T10:16:41Z
@bigPYJ1151 , I think fix https://github.com/vllm-project/vllm/pull/42709 seems reasonable,
btw installing orjson might speed-up orjson is a drop-in (mostly) replacement for Python’s JSON module optimized for speed, do you also plan to add this pkg to VLLM image?

## comment @bigPYJ1151 2026-05-16T10:23:11Z
@jpiaseck l think it's good to include it. Maybe you can help to open a PR : )