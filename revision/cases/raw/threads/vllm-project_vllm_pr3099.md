# vllm-project/vllm PR #3099: [Fix] Don't deep-copy LogitsProcessors when copying SamplingParams
merged_at=2024-02-29T19:20:43Z merge_commit=29a8d6a554a87292f05b62078976b43a899691e3 author=@njhill
files: vllm/engine/llm_engine.py, vllm/sampling_params.py

## body

Fixes #3087