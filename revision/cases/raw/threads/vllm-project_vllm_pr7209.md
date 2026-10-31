# vllm-project/vllm PR #7209: [Performance][Core] Optimize the performance of evictor v1 and v2 by applying a priority queue and lazy deletion
merged_at=2024-12-14T19:38:11Z merge_commit=886936837ca89e5645bc1f71cc0e1492b65b1590 author=@llsj14
files: vllm/core/evictor.py

## body
FIX #6923

## Summary
- I discovered that the eviction logic with the `OrderedDict` `free_table` in Evictor V1 and V2 slows down overall performance (especially `TTFT`) when using prefix caching mode.
- In some scenarios, utilizing prefix caching mode makes the system slower compared to when prefix caching is not used.
- The evict function is frequently called when allocating a new block, as no block is evicted until the block space is full in prefix caching mode.
- The eviction logic was slow because free_table is declared as an OrderedDict, which is a linked list, and it tries to find a block with `content hash` (Evictor V1) or `block ID` (Evictor V2) in this free_table.
- Utilizing a priority queue and lazy deletion helps find the block faster.

## Result Verification
- As shown in the following output, the block ID and content hash had the same value between the as-is and to-be states (which is expected).
- With this change, I could make the duration of the evict function much faster.

```
===============================
evicted_block_id compare:  12010   12010
content_hash_compare:  -7334740008364413937   -7334740008364413937
as-is evict duration:  7.0807114243507385 ms
to-be evict duration:  0.012848526239395142 ms
===============================
evicted_block_id compare:  12038   12038
content_hash_compare:  -7008894356950570757   -7008894356950570757
as-is evict duration:  7.1028973907232285 ms
to-be evict duration:  0.008581206202507019 ms
===============================
```

## Performance
- I checked the TTFT performance using llmperf and the Llama3-8B model with an A100 GPU.
- I benchmarked with 1536 input token length (512 same prefix + 1024 random input) and 512 output token length.
- By applying this commit, I can make the system faster while utilizing prefix caching.
- The speed-up metric is calculated based on the performance without prefix caching mode.

### as-is
Model | Num Clients | Block Manager | Prefix Caching | TTFT (mean) | Speed Up
-- | -- | -- | -- | -- | --
Llama3-8B | 16 | v2 | X | 841 ms |  
Llama3-8B | 32 | v2 | X | 1441 ms |  
Llama3-8B | 64 | v2 | X | 2619 ms |  
Llama3-8B | 128 | v2 | X | 4729 ms |  
Llama3-8B | 16 | v2 | O | 1962 ms | 0.43 (slowed down)
Llama3-8B | 32 | v2 | O | 8382 ms | 0.17 (slowed down)
Llama3-8B | 64 | v2 | O | 12665 ms | 0.21 (slowed down)
Llama3-8B | 128 | v2 | O | 22439 ms | 0.21 (slowed down)

### to-be
Model | Num Clients | Block Manager | Prefix Caching | TTFT (mean) | Speed Up
-- | -- | -- | -- | -- | --
Llama3-8B | 16 | v2 | O | 541 ms | 1.55
Llama3-8B | 32 | v2 | O | 901 ms | 1.60
Llama3-8B | 64 | v2 | O | 1563 ms | 1.68
Llama3-8B | 128 | v2 | O | 2947 ms | 1.60