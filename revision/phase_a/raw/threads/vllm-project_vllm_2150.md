# vllm-project/vllm#2150: torch.distributed.all_reduce does not free memory
state=closed reason=completed created=2023-12-17T07:29:08Z closed=2023-12-17T09:44:46Z labels=['bug']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/2151']

## body (@WoosukKwon)
 I've visualized the memory usage:

* llama 7B, TP=1
<img width="3346" alt="Screenshot 2023-12-16 at 11 14 03 PM" src="https://github.com/vllm-project/vllm/assets/46394894/e6ed7069-2190-4823-8f25-8e27bd94fe35">

The activation memory is reused after every layer.

* llama-70B, TP=8
<img width="3247" alt="Screenshot 2023-12-16 at 11 20 10 PM" src="https://github.com/vllm-project/vllm/assets/46394894/b5f492bb-7262-4c06-a040-7796e0f7fc06">

**However, when using TP, the activation memory for all reduce is not reused**

_Originally posted by @WoosukKwon in https://github.com/vllm-project/vllm/pull/2031#discussion_r1429046645_
            