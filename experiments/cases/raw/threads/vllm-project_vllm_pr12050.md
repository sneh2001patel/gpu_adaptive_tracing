# vllm-project/vllm PR #12050: [Bugfix] use right truncation for non-generative tasks
merged_at=2025-01-15T16:31:02Z merge_commit=edce722eaa5e9f0b97bea611531e3341ec2e2e71 author=@joerunde
files: tests/entrypoints/llm/test_encode.py, vllm/config.py, vllm/transformers_utils/tokenizer_group/__init__.py

## body
Currently the `truncation_side` kwarg is always unset when creating a tokenizer, so it defaults to `left` everywhere. This is correct for text generation, but unexpected for other tasks like `embedding` and `score`.

This PR sets the truncation side based on the current task, and only `draft` and `generate` will use left truncation.

FIX #11568

