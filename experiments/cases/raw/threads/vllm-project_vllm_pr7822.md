# vllm-project/vllm PR #7822: [Performance][BlockManagerV2] Mark prefix cache block as computed after schedule
merged_at=2024-08-26T18:24:53Z merge_commit=2deb029d115dadd012ce5ea70487a207cb025493 author=@comaniac
files: tests/core/block/test_prefix_caching_block.py, vllm/core/block/prefix_caching_block.py, vllm/core/block_manager_v2.py

## body
Closes #7619 

With the investigation in #7619, the root cause of block manager v2 low throughput with prefix caching is that block manager v2 doesn't mark prefix cache hit blocks as computed right after scheduling a batch. Specifically, the life cycle of a prefix cache block is as follows:
1. The block is allocated by the first sequence of a batch. At this moment it will be added to  "cached blocks", but won't be marked as computed; otherwise the rest sequences in the same batch will skip the computation of this block and result in incorrect output.
2. When the batch of sequence is finished (prefill+decode), the blocks are freed and added to the evictor.
3. When the sequence of a following batch allocates the same block, it will be activated from the evictor and marked as computed.

Here is a simple illustration. Note that we assume each sequence is in different batch.
```
seq 1: [allocate-block-uncomputed] -- [prefill] --[decode1] --  ... -- [decodeN] -- [free-block]
seq 2:                                [allocate-block-uncomputed] -- ...
...
seq N:                                                                                          [allocate-block-computed] -- ...
``` 
Meanwhile, block manager v1 marks the block as computed right after the prefill is scheduled:
```
seq 1: [allocate-block-uncomputed] -- [prefill] --[decode1] --  ... -- [decodeN] -- [free-block]
seq 2:                                [allocate-block-computed] -- ...
...
``` 

This PR fixes this issue by marking allocated blocks as touched, and let scheduler mark them as computed to achieve the same behavior of block manager v1.

### Benchmark on L4

Command
```
python3 benchmarks/benchmark_prefix_caching.py \
    --model neuralmagic/Meta-Llama-3-8B-Instruct-FP8 \
    --output-len 200 \
    --enable-prefix-caching \
    [--use-v2-block-manager]
```

Branch | Block Manager |Warmup (s) | Processed (s)
--|--|--|--
main | v1 | 14.5 | 13.4
main | v2 | 23.6 | 13.4
PR | v1 | 14.5 | 13.3
PR | v2 | 14.4 | 13.3


cc @cadedaniel @rkooo567 @Yard1 