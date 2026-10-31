# vllm-project/vllm#7619: [Performance]: Block manager v2 has low throughput with prefix caching warmup
state=closed reason=completed created=2024-08-17T01:52:21Z closed=2024-08-26T18:24:54Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/6144', 'https://github.com/vllm-project/vllm/pull/7753', 'https://github.com/vllm-project/vllm/pull/7822']

## body (@comaniac)
### Report of performance regression

Benchmark prefix caching with block manager v1 and v2 on L4:

v1:
```
python3 benchmarks/benchmark_prefix_caching.py \
    --model neuralmagic/Meta-Llama-3-8B-Instruct-FP8 \
    --output-len 200 \
    --enable-prefix-caching

------warm up------
cost time 14.582656621932983
------start generating------
cost time 13.347810745239258
```

v2:
```
python3 benchmarks/benchmark_prefix_caching.py \
    --model neuralmagic/Meta-Llama-3-8B-Instruct-FP8 \
    --output-len 200 \
    --enable-prefix-caching \
    --use-v2-block-manager

------warm up------
cost time 24.060877799987793
------start generating------
cost time 13.424522161483765
```
We can see that v2 uses 10 more seconds in the warmup batch, but the latency of the second batch is same as v1. So, if we change the warmup batch size to 1:

v1
```
------warm up------
cost time 2.6070663928985596
------start generating------
cost time 13.225520372390747
```
v2
```
------warm up------
cost time 2.612058162689209
------start generating------
cost time 13.256183385848999
```

## comment @comaniac 2024-08-17T01:54:06Z
cc @cadedaniel @Yard1 @rkooo567 @youkaichao @zhuohan123 @alexm-neuralmagic 

## comment @comaniac 2024-08-17T04:25:26Z
More observations:
1. In general when prefix caching is enabled but cache miss, v2 is much slower than v1 with large batch size. When disabling prefix caching, both are similar. Thus, we could likely locate to https://github.com/vllm-project/vllm/blob/main/vllm/core/block/prefix_caching_block.py#L161-L165
2. However, according to cProfile trace, although evictor v2 does take a bit longer than v1, the major slowdown comes from the model runner. Specifically, evictor v1 takes ~6% of overall execution time but evictor v2 only takes ~5%. It is mystery to me, unless cProfile isn't accurate somehow.

## comment @cadedaniel 2024-08-17T05:47:09Z
some investigation results:
* because of max_batched_total_tokens, the prefill is split into several forward passes of batch size 12
* with bmv1 and bmv2, `computed_block_nums=[]` for the first fwd pass
* for the second fwd pass, they diverge:
  * bmv1: sg.computed_block_nums=[0, ..., 38]
  * bmv2: sg.computed_block_nums=[]
* takeaway: computed block nums are not being computed correctly in bmv2

likely a bug in `ComputedBlocksTracker`. it doesn't have tests, which is likely why this slipped.