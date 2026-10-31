# vllm-project/vllm#9565: [Performance]: vllm Eagle performance is worse than expected
state=closed reason=not_planned created=2024-10-21T22:16:51Z closed=2025-09-01T02:49:02Z labels=['performance', 'stale']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/11672', 'https://github.com/vllm-project/vllm/pull/14464']

## body (@LiuXiaoxuanPKU)
### Proposal to improve performance

The spec dec performance of Eagleis worse than expected as shown below:

Model: [meta-llama/Meta-Llama-3.1-70B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct)
Draft model:[ yuhuili/EAGLE-LLaMA3-Instruct-70B](https://huggingface.co/yuhuili/EAGLE-LLaMA3-Instruct-70B)
Hardware: 4xH100
Target model TP=4
Dataset: [ShareGPT](https://huggingface.co/datasets/anon8231489123/ShareGPT_Vicuna_unfiltered)
vllm version: v0.6.1.post2

<img width="391" alt="Screenshot 2024-10-21 at 3 08 39 PM" src="https://github.com/user-attachments/assets/9c6027b1-a8ab-40fd-beb0-82b11dbc8350">

Even at low QPS, the performance is far from 2x speedup reported in the original eagle paper (light blue line is the original, the solid lines are with SD). We need to understand the performance gap here. Possible reasons include but not limited to 

1. Miss tree verification kernel: For each position, we are choosing token from the top1 candidate instead of topk candidates. The reason is that we have not integrated tree verification kernel.
2. System overhead: unnecessary GPU/CPU communication somewhere.
3. We are testing on ShareGPT dataset while the heads are not finetuned on the same dataset. 

Profiling is required to understand the issue. Open this issue to track the progress.




### Report of performance regression

_No response_

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [X] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @fengyang95 2024-10-22T12:58:27Z
@LiuXiaoxuanPKU Hi, what is the acceptance rate based on your tests?  I trained a draft model of DeepSeek-v2, and the acceptance rate from testing is less than 20%. Maybe you should use meta-llama/Meta-Llama-3-70B-Instruct to match with the draft model.

## comment @wooyeonlee0 2024-10-28T08:18:40Z
@LiuXiaoxuanPKU Thanks for sharing the interesting result :)
But, this issue looks focused on system-side optimizations.
In the PR that has introduced Eagle, there's a discussion about the low acceptance rate when using large k.
https://github.com/vllm-project/vllm/pull/6830/files#r1710769971
Does this acceptance rate issue still exist? How was the acceptance rate in your experiment @LiuXiaoxuanPKU ?

## comment @Lin-Qingyang-Alec 2024-10-31T02:40:38Z
The eagle model looks inconsistent with the implementation version of the paper.
The version implemented in this paper lacks two rms_norm operations.

## comment @bettybaii 2024-11-01T07:14:41Z
@LiuXiaoxuanPKU Thanks for sharing this interesting result; I’m very interested in it as well.

However, can [yuhuili/EAGLE-LLaMA3-Instruct-70B](https://huggingface.co/yuhuili/EAGLE-LLaMA3-Instruct-70B) be directly used as a draft model? In my experiments, I found it necessary to convert the trained EAGLE checkpoint to a vLLM-compatible version, similar to the process described here: [eagle.py](https://github.com/vllm-project/vllm/blob/93a76dd21dcec8977f1ffd0e21faa88fb515b9e4/vllm/model_executor/models/eagle.py#L126C1-L133C1). 
However, after conversion, the draft model’s parameter size increased significantly (from 1.55GB to 3.4048GB), which consumed a substantial amount of GPU memory and considerably extended the draft model’s computation time (with the average_time_per_proposal_tok_ms reaching nearly 4 ms).

Additionally, when using [meta-llama/Meta-Llama-3-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct) as the target model and the converted [yuhuili/EAGLE-LLaMA3-Instruct-8B](https://huggingface.co/yuhuili/EAGLE-LLaMA3-Instruct-8B) as the draft model, I observed that with num_speculative_tokens set to 3, the acceptance rate was only around 29.6%.

## comment @LiuXiaoxuanPKU 2024-11-01T20:42:58Z
Some preliminary acceptance rate on ShareGPT with llama3-70B  with the help @OliviaMimiChen:
**Number of speculative tokens = 1**
Speculative metrics: Draft acceptance rate: 0.489, System efficiency: 0.744, Number of speculative tokens: 1, Number of accepted tokens: 579528, Number of draft tokens: 1185420, Number of emitted tokens: 1764948.
**Number of speculative tokens = 2**
Speculative metrics: Draft acceptance rate: 0.341, System efficiency: 0.530, Number of speculative tokens: 2, Number of accepted tokens: 736026, Number of draft tokens: 2157850, Number of emitted tokens: 1714732.
**Number of speculative tokens = 3**
Speculative metrics: Draft acceptance rate: 0.282, System efficiency: 0.405, Number of speculative tokens: 3, Number of accepted tokens: 883021, Number of draft tokens: 3135405, Number of emitted tokens: 1693914.

I think the numbers are wired because:
1. the acceptance rate changes based on the number of spec token, which is not expected. Acceptance rate should not be affected by the propose length.
2. acceptance rate is much smaller than system efficiency. This is also wired as normally, acceptance rate should be higher.
3. In general, the acceptance rate is not good, but this might be attributed to top1 proposer (without tree verification).

We are in the process of 
(1) debugging acceptance rate
(2) nsys profiling to understand the overhead of each part

We will keep you guys posted, any discussion/comments are appeciated!

## comment @gopalsarda 2024-11-02T05:13:54Z
> the acceptance rate changes based on the number of spec token, which is not expected. Acceptance rate should not be affected by the propose length

Maybe I am missing something but isn't this expected? Generally, a draft model's ability to predict tokens at later time steps becomes worse. So if a draft model is predicting 2 spec tokens, and it gets just the first token right, the acceptance rate will be 0.5 where as if a draft model is predicting 3 spec tokens, and it gets just the first token right, the acceptance rate will be 0.33

> acceptance rate is much smaller than system efficiency. This is also wired as normally, acceptance rate should be higher.

I believe this is mostly because bonus token is included in the calculation of system efficiency where as it is not included in acceptance rate.



## comment @LiuXiaoxuanPKU 2024-11-12T23:43:01Z
> > the acceptance rate changes based on the number of spec token, which is not expected. Acceptance rate should not be affected by the propose length
> 
> Maybe I am missing something but isn't this expected? Generally, a draft model's ability to predict tokens at later time steps becomes worse. So if a draft model is predicting 2 spec tokens, and it gets just the first token right, the acceptance rate will be 0.5 where as if a draft model is predicting 3 spec tokens, and it gets just the first token right, the acceptance rate will be 0.33
> 
> > acceptance rate is much smaller than system efficiency. This is also wired as normally, acceptance rate should be higher.
> 
> I believe this is mostly because bonus token is included in the calculation of system efficiency where as it is not included in acceptance rate.

It might be a bit confusing. In vllm, the token acceptance rate also includes tokens after 'wrong prediction'. For example, if 1 means the token is accepted, 0 means the token is not accepted, and after proposing 4 tokens, we have an acceptance vector of [1, 0, 1, 0], the token acceptance rate is 2 / 4 = 0.5, the system efficiency is (1+1) / (4+1) = 0.4. For system efficiency, 1+1 means the accepted token + the bonus token, 4 + 1 is the maximum number of tokens that can be generated in this forward pass.
Ideally, the acceptance rate should be an independent of the proposed length because it models draft model's capability to mimic the target model. On the other hand, system efficiency is affected by the proposed length. Let me know if there are more questions, thanks!



## comment @bettybaii 2024-11-13T02:56:43Z




> > > the acceptance rate changes based on the number of spec token, which is not expected. Acceptance rate should not be affected by the propose length
> > 
> > 
> > Maybe I am missing something but isn't this expected? Generally, a draft model's ability to predict tokens at later time steps becomes worse. So if a draft model is predicting 2 spec tokens, and it gets just the first token right, the acceptance rate will be 0.5 where as if a draft model is predicting 3 spec tokens, and it gets just the first token right, the acceptance rate will be 0.33
> > > acceptance rate is much smaller than system efficiency. This is also wired as normally, acceptance rate should be higher.
> > 
> > 
> > I believe this is mostly because bonus token is included in the calculation of system efficiency where as it is not included in acceptance rate.
> 
> It might be a bit confusing. In vllm, the token acceptance rate also includes tokens after 'wrong prediction'. For example, if 1 means the token is accepted, 0 means the token is not accepted, and after proposing 4 tokens, we have an acceptance vector of [1, 0, 1, 0], the token acceptance rate is 2 / 4 = 0.5, the system efficiency is (1+1) / (4+1) = 0.4. For system efficiency, 1+1 means the accepted token + the bonus token, 4 + 1 is the maximum number of tokens that can be generated in this forward pass. Ideally, the acceptance rate should be an independent of the proposed length because it models draft model's capability to mimic the target model. On the other hand, system efficiency is affected by the proposed length. Let me know if there are more questions, thanks!

I appreciate your insights, [@LiuXiaoxuanPKU](https://github.com/LiuXiaoxuanPKU). However, in Eagle and most speculative decoding methods, the proposal process still follows an autoregressive pattern, where the prediction of each subsequent token depends on the information from the previously predicted token. From my understanding, if an earlier token is predicted incorrectly (deviating from the target model), it is highly likely that subsequent tokens will also be predicted incorrectly. With this in mind, it appears problematic to calculate the acceptance rate for each token position independently, regardless of the proposal length.

Additionally, I am very interested in understanding the time overhead associated with Eagle’s proposal stage. Would you be able to share any relevant test data? In my own testing, this overhead has been substantial, and as I understand it, this cost cannot be hidden and significantly impacts the efficiency of speculative decoding.

## comment @awsvmaringa 2024-11-14T21:22:32Z
I observed 20% lower acceptance length numbers compared to the official EAGLE code using LLaMA3-Instruct 8B as base model and abhigoyal/EAGLE-LLaMA3-Instruct-8B-vllm as draft model. I noticed that the vLLM EAGLE model code has 2 key differences compared to the official EAGLE model code:

1. Official EAGLE model uses [LlamaDecoderLayer](https://github.com/SafeAILab/EAGLE/blob/18f45c61b4e08242f0030d23858e193da8e52575/eagle/model/cnets.py#L398) without input layernorm, possibly because the input (from base model) is already normalized. The vLLM code on the other hand uses [LlamaDecoderLayer](https://github.com/vllm-project/vllm/blob/7c65527918cd16286961a2a779e15743ca41ab0e/vllm/model_executor/models/llama.py#L239) with input layernorm.
2. Official EAGLE [model](https://github.com/SafeAILab/EAGLE/blob/18f45c61b4e08242f0030d23858e193da8e52575/eagle/model/cnets.py#L646) does not use layernorm on it’s outputs (before LMHead). The vLLM code uses [layernorm](https://github.com/vllm-project/vllm/blob/7c65527918cd16286961a2a779e15743ca41ab0e/vllm/model_executor/models/llama.py#L350) on it’s outputs.

After fixing these two issues, the acceptance length of vLLM is now very close to the official EAGLE code.

## comment @avnukala 2024-12-11T19:55:55Z
> After fixing these two issues, the acceptance length of vLLM is now very close to the official EAGLE code.

Are these fixes implemented in a commit? Or did you do these locally. 

## comment @xiongqisong 2024-12-13T09:45:02Z
> @LiuXiaoxuanPKU Thanks for sharing this interesting result; I’m very interested in it as well.
> 
> However, can [yuhuili/EAGLE-LLaMA3-Instruct-70B](https://huggingface.co/yuhuili/EAGLE-LLaMA3-Instruct-70B) be directly used as a draft model? In my experiments, I found it necessary to convert the trained EAGLE checkpoint to a vLLM-compatible version, similar to the process described here: [eagle.py](https://github.com/vllm-project/vllm/blob/93a76dd21dcec8977f1ffd0e21faa88fb515b9e4/vllm/model_executor/models/eagle.py#L126C1-L133C1). However, after conversion, the draft model’s parameter size increased significantly (from 1.55GB to 3.4048GB), which consumed a substantial amount of GPU memory and considerably extended the draft model’s computation time (with the average_time_per_proposal_tok_ms reaching nearly 4 ms).
> 
> Additionally, when using [meta-llama/Meta-Llama-3-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct) as the target model and the converted [yuhuili/EAGLE-LLaMA3-Instruct-8B](https://huggingface.co/yuhuili/EAGLE-LLaMA3-Instruct-8B) as the draft model, I observed that with num_speculative_tokens set to 3, the acceptance rate was only around 29.6%.

Can you teach me how to use EAGLE on vLLM, there is no documention that can clearly tell zhe usage of EAGLE, i already convert the draft model to vLLM format, but vLLM still can't load the weights of draft model, too hard to use!

## comment @sroy745 2024-12-14T15:17:37Z
Hi @xiongqisong can you add some more details on 1) how you converted weights 2) how you are trying to start the vllm server with the converted checkpoint 3) what is the error you are getting?

## comment @llsj14 2024-12-16T01:23:48Z
>Hi @xiongqisong can you add some more details on 1) how you converted weights 2) how you are trying to start the vllm server with the converted checkpoint 3) what is the error you are getting?

I am facing the same issue when running the EAGLE model.
@xiongqisong already raised this issue: https://github.com/vllm-project/vllm/issues/11126.
I have shared my commands, error messages, and attempts as well. Any help would be greatly appreciated!

## comment @xiongqisong 2024-12-16T02:43:56Z
> Hi @xiongqisong can you add some more details on 1) how you converted weights 2) how you are trying to start the vllm server with the converted checkpoint 3) what is the error you are getting?

Thanks for @llsj14 shared the detailed commands/error messages...I think we can discuss the usage of EAGLE on vLLM in #11126 together @LiuXiaoxuanPKU @sroy745 I will share the clue of my situation, thanks for help aging~

## comment @spitzblattr 2024-12-27T10:29:45Z
> * Official EAGLE model uses [LlamaDecoderLayer](https://github.com/SafeAILab/EAGLE/blob/18f45c61b4e08242f0030d23858e193da8e52575/eagle/model/cnets.py#L398) without input layernorm, possibly because the input (from base model) is already normalized. The vLLM code on the other hand uses [LlamaDecoderLayer](https://github.com/vllm-project/vllm/blob/7c65527918cd16286961a2a779e15743ca41ab0e/vllm/model_executor/models/llama.py#L239) with input layernorm.
> * Official EAGLE [model](https://github.com/SafeAILab/EAGLE/blob/18f45c61b4e08242f0030d23858e193da8e52575/eagle/model/cnets.py#L646) does not use layernorm on it’s outputs (before LMHead). The vLLM code uses [layernorm](https://github.com/vllm-project/vllm/blob/7c65527918cd16286961a2a779e15743ca41ab0e/vllm/model_executor/models/llama.py#L350) on it’s outputs.

Hi @awsvmaringa, could you please give some advice on how to modify the source code? I did the 2 changes you mentioned and added last residual to the hidden states, the draft accept rate increases a bit, but still too low, and still far from that of the official EAGLE code. Thank you ;_;

model: meta-llama3-8b, draft tokens = 5, greedy decoding, sharegpt dataset
【original vllm eagle】
Draft acceptance rate: 0.287, System efficiency: 0.303
【remove input layernorm】
Draft acceptance rate: 0.379, System efficiency: 0.343
【remove input layernorm & output layernorm】
Draft acceptance rate: 0.410, System efficiency: 0.355

Edit：According to the article, this table is also tested without tree attention
<img width="298" alt="截屏2025-01-02 17 47 38" src="https://github.com/user-attachments/assets/fd001950-7280-4d8a-9045-d1d629f9790f" />


## comment @llsj14 2025-01-01T16:38:31Z
I tried the following three approaches based on comments from this issue and https://github.com/vllm-project/vllm/issues/11126#issuecomment-2552720713, as well as by reviewing the implementation of the EAGLE framework. Thank you all for your feedback in helping tackle this issue.

1. **disable norm**: Removed input layer normalization and output normalization.
2. **correct input embedding**: I thought this [part](https://github.com/vllm-project/vllm/blob/a115ac46b5be22289dec975c2c06653b22cd6315/vllm/model_executor/models/eagle.py#L101) was incorrect because it causes the first input embeddings to be set to zero while the sequence length or positions are still being counted. I modified it to start with the correct embeddings, as described in the EAGLE paper.
3. **add residual**: Added a residual path at the end of the Llama model. This was omitted because output normalization was disabled in the first step.

Below are the experimental results from the above trials.

- model: `Llama-2-7b-chat-hf / EAGLE-llama2-chat-7B` with `K=1`
- dataset: MT-Bench
- input/output length: 128/128
- the number of requests: 500
- sampling params:
  - multinomial: top_k=-1, top_p=1.0, temp=1.0
  - greedy: top_k=1, top_p=1.0, temp=1.0


| Approach | Accept Rate (Multinomial) | Accept Rate (Greedy) |
| -------- | ------------------------ | -------------------- |
| as-is | 0.131 | 0.308 |
| 1 (disable norm) | 0.391 | 0.529 |
| 1+2 (disable norm + correct input embedding) | 0.375 | 0.517 |
| 1+3 (disable norm + add residual) | 0.565 | 0.619 |


The result from the second step did not improve the acceptance rate (in fact, it slightly worsened the acceptance rate by 1-2%). As a result, I only included the first and third steps in [PR](https://github.com/vllm-project/vllm/pull/11672). I added more experiment  results with other datasets, model combinations, and different values for num_speculative_tokens (K) into the PR.

## comment @UltramanKuz 2025-02-24T08:24:42Z
> I observed 20% lower acceptance length numbers compared to the official EAGLE code using LLaMA3-Instruct 8B as base model and abhigoyal/EAGLE-LLaMA3-Instruct-8B-vllm as draft model. I noticed that the vLLM EAGLE model code has 2 key differences compared to the official EAGLE model code:
> 
> 1. Official EAGLE model uses [LlamaDecoderLayer](https://github.com/SafeAILab/EAGLE/blob/18f45c61b4e08242f0030d23858e193da8e52575/eagle/model/cnets.py#L398) without input layernorm, possibly because the input (from base model) is already normalized. The vLLM code on the other hand uses [LlamaDecoderLayer](https://github.com/vllm-project/vllm/blob/7c65527918cd16286961a2a779e15743ca41ab0e/vllm/model_executor/models/llama.py#L239) with input layernorm.
> 2. Official EAGLE [model](https://github.com/SafeAILab/EAGLE/blob/18f45c61b4e08242f0030d23858e193da8e52575/eagle/model/cnets.py#L646) does not use layernorm on it’s outputs (before LMHead). The vLLM code uses [layernorm](https://github.com/vllm-project/vllm/blob/7c65527918cd16286961a2a779e15743ca41ab0e/vllm/model_executor/models/llama.py#L350) on it’s outputs.
> 
> After fixing these two issues, the acceptance length of vLLM is now very close to the official EAGLE code.

Can you show your modifications？

## comment @UltramanKuz 2025-02-24T09:12:54Z
> I tried the following three approaches based on comments from this issue and [#11126 (comment)](https://github.com/vllm-project/vllm/issues/11126#issuecomment-2552720713), as well as by reviewing the implementation of the EAGLE framework. Thank you all for your feedback in helping tackle this issue.
> 
> 1. **disable norm**: Removed input layer normalization and output normalization.
> 2. **correct input embedding**: I thought this [part](https://github.com/vllm-project/vllm/blob/a115ac46b5be22289dec975c2c06653b22cd6315/vllm/model_executor/models/eagle.py#L101) was incorrect because it causes the first input embeddings to be set to zero while the sequence length or positions are still being counted. I modified it to start with the correct embeddings, as described in the EAGLE paper.
> 3. **add residual**: Added a residual path at the end of the Llama model. This was omitted because output normalization was disabled in the first step.
> 
> Below are the experimental results from the above trials.
> 
> * model: `Llama-2-7b-chat-hf / EAGLE-llama2-chat-7B` with `K=1`
> * dataset: MT-Bench
> * input/output length: 128/128
> * the number of requests: 500
> * sampling params:
>   
>   * multinomial: top_k=-1, top_p=1.0, temp=1.0
>   * greedy: top_k=1, top_p=1.0, temp=1.0
> 
> Approach	Accept Rate (Multinomial)	Accept Rate (Greedy)
> as-is	0.131	0.308
> 1 (disable norm)	0.391	0.529
> 1+2 (disable norm + correct input embedding)	0.375	0.517
> 1+3 (disable norm + add residual)	0.565	0.619
> The result from the second step did not improve the acceptance rate (in fact, it slightly worsened the acceptance rate by 1-2%). As a result, I only included the first and third steps in [PR](https://github.com/vllm-project/vllm/pull/11672). I added more experiment results with other datasets, model combinations, and different values for num_speculative_tokens (K) into the PR.

Thank you for your sharing. May I ask how the step1 and step3 are implemented? I am not familiar with the structure of vllm. 

## comment @llsj14 2025-02-24T13:52:54Z
Hi, @UltramanKuz 
Modifications are applied by this PR. https://github.com/vllm-project/vllm/pull/11672

## comment @UltramanKuz 2025-02-25T02:18:06Z
> Hi, [@UltramanKuz](https://github.com/UltramanKuz) Modifications are applied by this PR. [#11672](https://github.com/vllm-project/vllm/pull/11672)

I really appreciate your assistance!

## comment @longer-is-better 2025-04-25T07:01:45Z
> Some preliminary acceptance rate on ShareGPT with llama3-70B with the help [@OliviaMimiChen](https://github.com/OliviaMimiChen): **Number of speculative tokens = 1** Speculative metrics: Draft acceptance rate: 0.489, System efficiency: 0.744, Number of speculative tokens: 1, Number of accepted tokens: 579528, Number of draft tokens: 1185420, Number of emitted tokens: 1764948. **Number of speculative tokens = 2** Speculative metrics: Draft acceptance rate: 0.341, System efficiency: 0.530, Number of speculative tokens: 2, Number of accepted tokens: 736026, Number of draft tokens: 2157850, Number of emitted tokens: 1714732. **Number of speculative tokens = 3** Speculative metrics: Draft acceptance rate: 0.282, System efficiency: 0.405, Number of speculative tokens: 3, Number of accepted tokens: 883021, Number of draft tokens: 3135405, Number of emitted tokens: 1693914.
> 
> I think the numbers are wired because:
> 
> 1. the acceptance rate changes based on the number of spec token, which is not expected. Acceptance rate should not be affected by the propose length.
> 2. acceptance rate is much smaller than system efficiency. This is also wired as normally, acceptance rate should be higher.
> 3. In general, the acceptance rate is not good, but this might be attributed to top1 proposer (without tree verification).
> 
> We are in the process of (1) debugging acceptance rate (2) nsys profiling to understand the overhead of each part
> 
> We will keep you guys posted, any discussion/comments are appeciated!

could you provide the configuration that can reproduce this acceptance rate? Target model, draft model, vllm version, and the specific shell command for reproduction? 
i got very low acceptance rate with vllm 0.7.3 : https://discuss.vllm.ai/t/spec-decode-with-eagle-get-very-low-draft-acceptance-rate/528

## comment @llsj14 2025-05-03T12:56:52Z
hello, @longer-is-better 
https://github.com/vllm-project/vllm/pull/14464
Would you check this commit is applied in your code?

## comment @github-actions[bot] 2025-08-02T02:24:16Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2025-09-01T02:49:02Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!