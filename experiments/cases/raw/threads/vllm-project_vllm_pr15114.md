# vllm-project/vllm PR #15114: [Bugfix] Fix size calculation of processing cache
merged_at=2025-03-19T12:53:19Z merge_commit=3d446433ec0b1d6bb187966af9b70553ce2349c2 author=@DarkLight1337
files: tests/multimodal/test_processing.py, vllm/multimodal/processing.py

## body
The processing cache incorrectly calculated the item size as basically zero because it failed to recurse into the individual tensors, resulting in effectively infinite capacity.

FIX #15105
FIX #15085