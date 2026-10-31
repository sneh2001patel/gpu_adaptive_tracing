# vllm-project/vllm#5274: [Bug]: high gpu_memory_utilization with 'OOM' and low gpu_memory_utilization with 'No available memory for the cache blocks'
state=closed reason=not_planned created=2024-06-05T10:26:43Z closed=2024-11-29T02:05:56Z labels=['bug', 'stale']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/5355']

## body (@mars-ch)
### Your current environment

v100 32G * 8


### 🐛 Describe the bug

I tried to run a 32B model with lora adapters and test different GPU_MEMORY_UTILIZATION.

When `gpu_memory_utilization = 0.9` , it came with OOM.
When `gpu_memory_utilization = 0.8` , it came with 'No available memory for the cache blocks. Try increasing `gpu_memory_utilization` when initializing the engine.'

Does it mean that I need to find a suitable value for `gpu_memory_utilization`  or is there any other things going wrong?

## comment @mgoin 2024-06-05T14:21:51Z
@mars-ch what if you try using a smaller `max_model_len`? Could you share your script? It is important to know how many lora adapters and what tensor parallelism you are using.

## comment @riverind 2024-06-12T13:12:54Z
> ### Your current environment
> v100 32G * 8
> 
> ### 🐛 Describe the bug
> I tried to run a 32B model with lora adapters and test different GPU_MEMORY_UTILIZATION.
> 
> When `gpu_memory_utilization = 0.9` , it came with OOM. When `gpu_memory_utilization = 0.8` , it came with 'No available memory for the cache blocks. Try increasing `gpu_memory_utilization` when initializing the engine.'
> 
> Does it mean that I need to find a suitable value for `gpu_memory_utilization` or is there any other things going wrong?

please decrease max_model_len or increase gpu_memory_utilization or increase tensor-parallel-size gpus

## comment @mars-ch 2024-06-13T02:38:35Z
> @mars-ch what if you try using a smaller `max_model_len`? Could you share your script? It is important to know how many lora adapters and what tensor parallelism you are using.


I used the LLM class like this:

sampling_params = SamplingParams(temperature=0.7, top_p=0.8, repetition_penalty=1.05, max_tokens=512)

llm = LLM(model="output_merged",dtype="half",gpu_memory_utilization=0.95, tensor_parallel_size=8, enforce_eager=True)


Thanks.

## comment @mars-ch 2024-06-13T10:08:38Z
What's more, the error shows that there are 2 processes:

torch.cuda.OutOfMemoryError: CUDA out of memory. Tried to allocate 234.00 MiB. GPU ^A has a total capacity of 31.75 GiB of which 98.75 MiB is free. Process 2852145 has 8.72 GiB memory in use. Process 2878797 has 22.92 GiB memory in use. Of the allocated memory 20.56 GiB is allocated by PyTorch, and 480.11 MiB is reserved by PyTorch but unallocated. 



## comment @DarkLight1337 2024-06-23T01:23:30Z
There is currently a bug in the model profiling logic which causes the memory profiler to underestimate the amount of memory to be used by the model. To circumvent this, you can reduce the value of `gpu_memory_utilization`.

## comment @github-actions[bot] 2024-10-26T01:59:40Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2024-11-29T02:05:56Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!