# vllm-project/vllm PR #49153: [Frontend] Parallelize preprocessing within the same request for pooling models online serving.
merged_at=2026-07-22T10:56:23Z merge_commit=61c9ef986a807aa3b9c6ccd25bb223b8f4116ac7 author=@noooop
files: tests/entrypoints/pooling/embed/test_io_processor.py, tests/entrypoints/pooling/scoring/test_cross_encoder_offline.py, tests/entrypoints/serve/lora/test_serving_models.py, vllm/entrypoints/pooling/base/io_processor.py, vllm/entrypoints/pooling/base/serving.py, vllm/entrypoints/pooling/classify/api_router.py, vllm/entrypoints/pooling/embed/api_router.py, vllm/entrypoints/pooling/embed/io_processor.py, vllm/entrypoints/pooling/embed/protocol.py, vllm/entrypoints/pooling/embed/serving.py, vllm/entrypoints/pooling/offline.py, vllm/entrypoints/pooling/pooling/api_router.py, vllm/entrypoints/pooling/pooling/io_processor.py, vllm/entrypoints/pooling/scoring/api_router.py, vllm/entrypoints/pooling/scoring/io_processor.py, vllm/entrypoints/pooling/scoring/serving.py, vllm/entrypoints/pooling/typing.py

## body
## TL;DR 
- Use multithreading to accelerate preprocessing. You can specify the number of threads using renderer_num_workers.

note:
- We have not implemented tiling to overlap preprocessing and computation for online serving as we did for offline inference (#47699), in order to avoid unnecessary complexity. Therefore, it is not recommended to submit an extremely large number of requests at once. You can use multiple concurrent requests for manual tiling.
- Sadly, because of the GIL, multithreading can only speed up the tokenizer and can hardly accelerate multimodal preprocessing at all. We are looking for ways to use multiprocessing to speed up multimodal preprocessing.

## Purpose

Following #47699

Previously, the approach “Use multithreading to accelerate preprocessing for pooling models.” only provided acceleration when handling multiple concurrent requests. (#39763)

This PR, however, introduces parallelized preprocessing within a single request .

Fixes #43444

```
#vllm serve BAAI/bge-m3 --renderer-num-workers 8 --max_num_seqs 8

import time
import requests

prompt = "hello "
n_prompt = 100
model="BAAI/bge-m3"
api_url = "http://localhost:8000/v1/embeddings"


[... 14 lines truncated ...]
    print(n, elapsed_time)
```
<img width="1509" height="955" alt="image" src="https://github.com/user-attachments/assets/222c7923-43ea-4891-9abc-37cfb8e59332" />

We have not implemented tiling to overlap preprocessing and computation for online serving as we did for offline inference(#47699), in order to avoid unnecessary complexity. Therefore, it is not recommended to submit an extremely large number of requests at once. So currently, offline inference is a little bit faster than online serving — only by a little bit.

## Test Plan

keep ci green

## Test Result

---
<details>
<summary> Essential Elements of an Effective PR Description Checklist </summary>

- [ ] The purpose of the PR, such as "Fix some issue (link existing issues this PR will resolve)".
- [ ] The test plan, such as providing test command.
- [ ] The test results, such as pasting the results comparison before and after, or e2e results
- [ ] (Optional) The necessary documentation update, such as updating `supported_models.md` and `examples` for a new model.
</details>

