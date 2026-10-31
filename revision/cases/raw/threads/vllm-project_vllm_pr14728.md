# vllm-project/vllm PR #14728: [V1] Move OOM check into sampler run
merged_at=2025-03-14T03:40:23Z merge_commit=ad19c8a00313e9d3f6016ac16333ce0d817a9c2a author=@ywang96
files: vllm/v1/worker/gpu_model_runner.py, vllm/v1/worker/gpu_worker.py

## body
Move the OOM check from model warmup into `_dummy_sampler_run` since OOM can also happen during `profile_run`.

FIXES #12529 



