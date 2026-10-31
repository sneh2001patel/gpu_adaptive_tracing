# vllm-project/vllm#8457: [Performance]: Add weaker memory fence for custom allreduce
state=closed reason=completed created=2024-09-13T09:32:34Z closed=2024-09-24T02:01:13Z labels=['performance']
cross-referenced PRs: none

## body (@HydraQYH)
from here: https://github.com/vllm-project/vllm/issues/8404

I try to use weaker memory fence in custom allreduce implement. This is the code: https://github.com/vllm-project/vllm/commit/4cdb581672afcf81da27b3bb4c0698fde4dc3ef9

I will explain the principle of my code for shot, this is a program flow chart:
![FlowChart](https://github.com/user-attachments/assets/12f29563-2a6b-417d-9343-076d3c0111ff)

Step3 in purple block has a acquire pattern, step 5 in purple block has a release pattern.
+ The order 3->4->5 is guaranteed by acquire & release.
+ 1 may be reordered to between 345(acquire), but it must be before 5(release), so it does not affect the subsequent end flag judgment.
+ 6 may be reordered to between 345(release), but it must be after 3(acquire), so it does not affect the judgment of the previous starting flag.
+ There is no fence between 2 and 3, but 2 must be globally visible before 3 can jump out of the loop (implicitly agreed upon 2->3), and then 3(2)->4->5 can be globally visible.
+ There is no fence between 5 and 7, but 5 must be globally visible before 7 can jump out of the loop (implicitly agreed upon 5->7). Based on the constraint of 4->5(7), it can be guaranteed that the pull data has been executed.


### Report of performance regression

Baseline(no memory fence):
![issue_0](https://github.com/user-attachments/assets/c78bde97-0964-4daf-873f-d42aa2945712)
My Code:
![issue_1](https://github.com/user-attachments/assets/4cae6a06-e13b-45ae-9ddb-ba54d6890234)
It seems like there are 1~3us latency on my code, that is for memory fence.

### Misc discussion on performance

I also try to use this plan: https://github.com/vllm-project/vllm/issues/8410#issuecomment-2347904518
That is the performance:
![issue_2](https://github.com/user-attachments/assets/de0771a6-ba48-4c6a-b93b-491828540b01)

I think we have to solve https://github.com/vllm-project/vllm/issues/8410 first, confirm whether the memory order problem really exists, and then look at this implementation.
@youkaichao @hanzhi713 

TensorRT-LLM use acquire for every ld and release for every st. I test it, it will cause about 6us latency.
https://github.com/NVIDIA/TensorRT-LLM/blob/v0.12.0/cpp/tensorrt_llm/kernels/customAllReduceKernels.cu#L162