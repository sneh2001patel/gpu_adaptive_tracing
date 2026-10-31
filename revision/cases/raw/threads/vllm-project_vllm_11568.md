# vllm-project/vllm#11568: [Performance]: The performance of bge-rerank model on vllm and huggingface is inconsistent
state=closed reason=completed created=2024-12-27T11:04:23Z closed=2025-01-15T16:31:03Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/12050']

## body (@yumingmin88)
### Proposal to improve performance

_No response_

### Report of performance regression

_No response_

### Misc discussion on performance

The script loaded using vllm is:
```
from vllm import LLM
model_path = "/data/reranker/bge-reranker-large"
# Create an LLM.
# You should pass task="score" for cross-encoder models
model = LLM(
    model=model_path,
    task="score",
    enforce_eager=True,
    dtype="float32"
)
```
huggingface scripts mainly use default parameters for，float32
```
 CrossEncoder(
            model, max_length=512, device=device
        )
```
After running 200 sets of data, in which 100 paragraphs were rearranged, 19 sets were found to be in inconsistent order after rearrangement
I also looked up some information online and there is the following information：
https://zhuanlan.zhihu.com/p/658780653

I do not know whether the parameter of my vllm is wrong, or what causes it?


### Your current environment (if you think it is necessary)

Current environment
linux: ubuntu 18  
NVIDIA-SMI 525.105.17   Driver Version: 525.105.17   CUDA Version: 12.0  Tesla T4 
vllm==0.6.6

### Before submitting a new issue...

- [X] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @DarkLight1337 2024-12-27T12:52:43Z
Can you provide a minimum reproducible example where the outputs are inconsistent?

## comment @cafeii 2024-12-28T07:23:07Z
hello @DarkLight1337 , it seems that different prompt inputs can result the different embedding results.
e.g.:
```
llm = LLM(
    model='/data1/model/llama-7b-base/',
    task='embed',
    enforce_eager=True
)
```
```
output1 = llm.embed(['hello world', 'hello world'])
output2 = llm.embed(['hello world'])
```
And the results of the two embeddings are like:
```
output1[0].outputs.embedding: 
[0.0108795166015625,
 -0.01033782958984375,
 0.0052490234375,
 -0.033599853515625,
 0.0019931793212890625,
 -0.005802154541015625,
 -0.0067291259765625,
 -0.00399017333984375,
...]
output2[0].outputs.embedding:
[... 9 lines truncated ...]
...]
```
The difference between emb1 and emb2 is typically small.
```
diff = np.array(emb1) - np.array(emb2)
np.mean(np.abs(diff)), np.std(diff)
(1.1552008800208569e-05, 1.6885600893505396e-05)
```
Do you know the possible reason that may lead to this difference? I think this may be the same reason of the inconsistence mentioned by @yumingmin88 

## comment @noooop 2024-12-28T09:10:57Z
I also found that reranker results will lead to different results because different tokens are batched 

When verifying whether the model is consistent with hf, it is necessary to compare the results after softmax to ensure that the difference is within 0.01

[test_bge-reranker-v2-m3](https://github.com/noooop/vllm/blob/653794e37db5af6a8951d927f2a231a67531bea0/tests/wde/reranker/models/test_bge-reranker-v2-m3.py#L103)


Of course, I think the model should handle this kind of dynamic batch. 
If you don’t use dynamic batch inference, it will be too slow.

@yumingmin88 

Try using softmax on the rerank model output and it to see if the order can be maintained.

## comment @DarkLight1337 2024-12-28T09:15:19Z
> hello @DarkLight1337 , it seems that different prompt inputs can result the different embedding results
> Do you know the possible reason that may lead to this difference? I think this may be the same reason of the inconsistence mentioned by @yumingmin88

Please see https://github.com/vllm-project/vllm/issues/11526#issuecomment-2562972224


## comment @yumingmin88 2024-12-28T10:31:32Z
> Can you provide a minimum reproducible example where the outputs are inconsistent?

Hello, do you think such an example is OK? I was learning RAG, so I ran 200 sets of examples like this from the knowledge base, 19 sets with different candidates length and number of shards, and 181 sets with the same index and only a slight difference in score
Thank you for your reply
`
query, candidates = 'J2智能扫地机器人能吸得干净猫毛吗？',['请勿使用清洁勾刀、刷子等物品直接清理滤网)\n\n安装回干净滤网并盖上上盖板，完成滤网清洁和替换。\n(注意\n滤网水洗后需24小时自然晾干后才能使用，建议两块滤网交替使用)\n\n边刷\n定期清理边刷，可以保证机器人扫地清洁的清洁效率，避免机器人工作时边刷转动可能发出的异响。\n保养周期  \n建议两周清理一次毛发，三到六个月更换一次\n保养步骤  \n清理毛发缠绕\n\n清理扫地模块上的其他脏污。 (扫地模块可直接用水冲洗，水洗后晾千才可以继续使用)\n如需更换新的边刷，双手扯住刷毛往上提拉\n\n滚刷\n保养周期  \n建议两周清理一次，六个月更换一次\n保养步骤  \n取下滚刷壳\n\n取下滚刷\n\n取下两端堵头，清理两端毛发\n\n勾刀或剪刀清理中间缠绕\n\n装回滚刷和壳体\n\n万向轮\n', ' Q:边刷炸毛严重\nA:机器人在地毯等材质上面清洁，可能导致出现容易炸毛的情况。边刷炸毛对扫地功能、清洁效果影响不大，可定期更换边刷使用\n', ' Q:边刷炸毛严重\nA:机器人在地毯等材质上面清洁，可能导致出现容易炸毛的情况。边刷炸毛对扫地功能、清洁效果影响不大，可定期更换边刷使用。\n']

from sentence_transformers import CrossEncoder
model_path = "/data/reranker/bge-reranker-large"
model = CrossEncoder(model_path, max_length=512)

pairs = [[query, candidate] for candidate in candidates]
scores = model.predict(pairs)

ranked_candidates = [(idx, score) for idx, score in enumerate(scores)]
ranked_candidates.sort(key=lambda x: x[1], reverse=True)
print("Ranked Candidates:")
for idx, score in ranked_candidates:
    print(f"index:{idx} socre:{score}")

from vllm import LLM
model_path = "/data/reranker/bge-reranker-large"
model = LLM(
    model=model_path,
    task="score",
    enforce_eager=True,
    dtype="float32"
)
outputs = model.score(query, candidates, truncate_prompt_tokens=512)
outputs_list = sorted([(idx, output.outputs.score) for idx, output in enumerate(outputs)], key= lambda x: -x[1])
for idx, score in outputs_list:
    print(f"index:{idx} socre:{score}")



`

## comment @yumingmin88 2024-12-28T10:34:53Z
> I also found that reranker results will lead to different results because different tokens are batched
> 
> When verifying whether the model is consistent with hf, it is necessary to compare the results after softmax to ensure that the difference is within 0.01
> 
> [test_bge-reranker-v2-m3](https://github.com/noooop/vllm/blob/653794e37db5af6a8951d927f2a231a67531bea0/tests/wde/reranker/models/test_bge-reranker-v2-m3.py#L103)
> 
> Of course, I think the model should handle this kind of dynamic batch. If you don’t use dynamic batch inference, it will be too slow.
> 
> @yumingmin88
> 
> Try using softmax on the rerank model output and it to see if the order can be maintained.

Thank you very much for your reply. I will try it like this

## comment @yumingmin88 2024-12-28T10:38:11Z
> 你好@DarkLight1337，似乎不同的提示输入可能会导致不同的嵌入结果。 例如：
> 
> ```
> llm = LLM(
>     model='/data1/model/llama-7b-base/',
>     task='embed',
>     enforce_eager=True
> )
> ```
> 
> ```
> output1 = llm.embed(['hello world', 'hello world'])
> output2 = llm.embed(['hello world'])
> ```
> 
> 两次嵌入的结果如下：
> 
> ```
> output1[0].outputs.embedding: 
> [0.0108795166015625,
>  -0.01033782958984375,
>  0.0052490234375,
>  -0.033599853515625,
>  0.0019931793212890625,
>  -0.005802154541015625,
>  -0.0067291259765625,
>  -0.00399017333984375,
> ...]
> output2[0].outputs.embedding:
[... 9 lines truncated ...]
> ...]
> ```
> 
> emb1 和 emb2 之间的差异通常很小。
> 
> ```
> diff = np.array(emb1) - np.array(emb2)
> np.mean(np.abs(diff)), np.std(diff)
> (1.1552008800208569e-05, 1.6885600893505396e-05)
> ```
> 
> 你知道导致这种差异的可能原因是什么吗？我认为这可能是@yumingmin88



> 你好@DarkLight1337，似乎不同的提示输入可能会导致不同的嵌入结果。 例如：
> 
> ```
> llm = LLM(
>     model='/data1/model/llama-7b-base/',
>     task='embed',
>     enforce_eager=True
> )
> ```
> 
> ```
> output1 = llm.embed(['hello world', 'hello world'])
> output2 = llm.embed(['hello world'])
> ```
> 
> 两次嵌入的结果如下：
> 
> ```
> output1[0].outputs.embedding: 
> [0.0108795166015625,
>  -0.01033782958984375,
>  0.0052490234375,
>  -0.033599853515625,
>  0.0019931793212890625,
>  -0.005802154541015625,
>  -0.0067291259765625,
>  -0.00399017333984375,
> ...]
> output2[0].outputs.embedding:
[... 9 lines truncated ...]
> ...]
> ```
> 
> emb1 和 emb2 之间的差异通常很小。
> 
> ```
> diff = np.array(emb1) - np.array(emb2)
> np.mean(np.abs(diff)), np.std(diff)
> (1.1552008800208569e-05, 1.6885600893505396e-05)
> ```
> 
> 你知道导致这种差异的可能原因是什么吗？我认为这可能是@yumingmin88

I don't know what the underlying principle is. Is the cumulative accuracy different due to the different calculation methods of KQV?

## comment @noooop 2024-12-28T11:39:22Z
@yumingmin88 

我们一件事一件事的说：

1. 首先这种随机性来自于使用fp16或者bf16，它的精度真的很低。

科学计算需要用双精度浮点，最差也用单精度浮点，现在使用的是半精度浮点。

这还不够，现在开始使用fp8。

通常 fp8做推理已经认为是无损的，deepseek v3 甚至使用 fp8 训练模型。

所以完全相同的结果是不可能的，只要在一个大数据集上统计意义上精度差不多就行了。

2. 具体随机结果是怎么来的

计算attention时，将多个序列放在一个批次执行时，用 mask 来将不同序列的attention区分开。

但是乘法的精度比较低，所以不是一个序列的中间向量的值也会互相影响

具体的看 [Is Flash Attention Stable?](https://arxiv.org/abs/2405.02803)

3. 对于解码模型 使用 [check_logprobs_close](https://github.com/vllm-project/vllm/blob/59d6bb4c863e511e58799efac847065c28c52c8b/tests/models/utils.py#L74) 对比结果是否正确

4. 对于  embedding 模型，对比 Cosine Similarity， 当然绝对值也算吧，1.1552008800208569e-05 已经足够精确了

5. 对于 rerank 模型，我也发现如果不使用 softmax ，误差偶尔会超过 0.01，有时确实不可接受，你试试 加 softmax 效果会好吗




## comment @DarkLight1337 2024-12-28T11:49:11Z
Here are the scores I got using your script

```
[Sentence Transformers]
index:0 socre:0.43743935227394104
index:2 socre:0.16435925662517548
index:1 socre:0.14919064939022064
[vLLM]
index:0 socre:0.4374387860298157
index:2 socre:0.16435886919498444
index:1 socre:0.14919109642505646
```

The results look close enough to me.

## comment @yumingmin88 2024-12-30T02:58:08Z
> @yumingmin88
> 
> 我们一件事一件事的说：
> 
> 1. 首先这种随机性来自于使用fp16或者bf16，它的精度真的很低。
> 
> 科学计算需要用双精度浮点，最差也用单精度浮点，现在使用的是半精度浮点。
> 
> 这还不够，现在开始使用fp8。
> 
> 通常 fp8做推理已经认为是无损的，deepseek v3 甚至使用 fp8 训练模型。
> 
> 所以完全相同的结果是不可能的，只要在一个大数据集上统计意义上精度差不多就行了。
> 
> 2. 具体随机结果是怎么来的
> 
> 计算attention时，将多个序列放在一个批次执行时，用 mask 来将不同序列的attention区分开。
> 
> 但是乘法的精度比较低，所以不是一个序列的中间向量的值也会互相影响
> 
> 具体的看 [Is Flash Attention Stable?](https://arxiv.org/abs/2405.02803)
> 
> 3. 对于解码模型 使用 [check_logprobs_close](https://github.com/vllm-project/vllm/blob/59d6bb4c863e511e58799efac847065c28c52c8b/tests/models/utils.py#L74) 对比结果是否正确
> 4. 对于  embedding 模型，对比 Cosine Similarity， 当然绝对值也算吧，1.1552008800208569e-05 已经足够精确了
> 5. 对于 rerank 模型，我也发现如果不使用 softmax ，误差偶尔会超过 0.01，有时确实不可接受，你试试 加 softmax 效果会好吗

谢谢您的回复，我正在一条条理解，些许精度差异我也认为是正常，也有提前搜过网上别人的解释。
尝试rerank时是发现有个别数据会出现原来在Sentence Transformers排序位置处于top1，在vllm处在top17
我正在尝试按照5看看效果

## comment @yumingmin88 2024-12-30T03:03:08Z
> Here are the scores I got using your script
> 
> ```
> [Sentence Transformers]
> index:0 socre:0.43743935227394104
> index:2 socre:0.16435925662517548
> index:1 socre:0.14919064939022064
> [vLLM]
> index:0 socre:0.4374387860298157
> index:2 socre:0.16435886919498444
> index:1 socre:0.14919109642505646
> ```
> 
> The results look close enough to me.

Ok, thank you, the index is inconsistent when I run it, I can accept the slight difference in the score, maybe I need to carefully find the problem，The sentence_transformers version is 3.3.1
[Sentence Transformers]
index:1 socre:0.8325262665748596
index:0 socre:0.771981418132782
index:2 socre:0.6860415935516357
[vLLM]
index:0 socre:0.7844522595405579
index:1 socre:0.7098560929298401
index:2 socre:0.7048576474189758

## comment @noooop 2024-12-30T05:21:39Z
@yumingmin88 

如果你想尽可能减少vllm 和 hf 的差距，可以尝试;
1. 所有依赖版本库保持一致
2. 使用 fp32
3. 使用 max_num_seqs = 1

当然这样不能保证结果完全一样，不同的硬件，驱动版本，cuda版本，依赖库版本都可能对结果造成影响

我觉得误差百分之一到千分之一都是可以接受的

## comment @yumingmin88 2024-12-30T09:21:33Z
> Here are the scores I got using your script
> 
> ```
> [Sentence Transformers]
> index:0 socre:0.43743935227394104
> index:2 socre:0.16435925662517548
> index:1 socre:0.14919064939022064
> [vLLM]
> index:0 socre:0.4374387860298157
> index:2 socre:0.16435886919498444
> index:1 socre:0.14919109642505646
> ```
> 
> The results look close enough to me.

I am even more confused as to why my results are more different from yours on Sentence Transformers, both index and score.
Is it because the T4 graphics card I use is slightly weak? Or is the rerank model used different? I use the rearrangement of model source: https://huggingface.co/BAAI/bge-reranker-large/tree/main

## comment @DarkLight1337 2024-12-30T09:23:18Z
I used `bge-reranker-v2-m3` model for this test as I was unsure which model you used. Let me try again using `bge-reranker-large`.

## comment @yumingmin88 2024-12-30T09:27:55Z
> I used `bge-reranker-v2-m3` model for this test as I was unsure which model you used. Let me try again using `bge-reranker-large`.

Sorry, it was my mistake not to specify the specific model

## comment @DarkLight1337 2024-12-30T09:31:35Z
I got this result:

```
[Sentence Transformers]
Ranked Candidates:
index:1 socre:0.8325262069702148
index:0 socre:0.7719812989234924
index:2 socre:0.6860411763191223
[vLLM]
index:0 socre:0.7844531536102295
index:1 socre:0.7098551988601685
index:2 socre:0.704855740070343
```

So indeed there seems to be a problem. cc @maxdebayser 

## comment @yumingmin88 2024-12-30T09:37:14Z
> I got this result:
> 
> ```
> [Sentence Transformers]
> Ranked Candidates:
> index:1 socre:0.8325262069702148
> index:0 socre:0.7719812989234924
> index:2 socre:0.6860411763191223
> [vLLM]
> index:0 socre:0.7844531536102295
> index:1 socre:0.7098551988601685
> index:2 socre:0.704855740070343
> ```
> 
> So indeed there seems to be a problem. cc @maxdebayser

Great, now we have the same results. I've been going through the code and learning about vLLM to try to understand why this difference was made

## comment @yumingmin88 2024-12-30T09:54:58Z
> @yumingmin88
> 
> 如果你想尽可能减少vllm 和 hf 的差距，可以尝试;
> 
> 1. 所有依赖版本库保持一致
> 2. 使用 fp32
> 3. 使用 max_num_seqs = 1
> 
> 当然这样不能保证结果完全一样，不同的硬件，驱动版本，cuda版本，依赖库版本都可能对结果造成影响
> 
> 我觉得误差百分之一到千分之一都是可以接受的

恩恩 已经按照您说的做了 统一的conda环境，都使用的fp32 目前看似乎bge-rerank-large在vLLM结果与hf确实很不同，也许是网络结构的差异？bge-rerank还不支持吧

## comment @noooop 2024-12-30T10:02:57Z
https://github.com/vllm-project/vllm/pull/10400

@DarkLight1337 

maybe we may need more long pairs for testing

## comment @maxdebayser 2025-01-06T19:50:23Z
Thanks for reporting this. I was out of office in the past couple of weeks. I'll take a look a this.

## comment @yumingmin88 2025-01-07T02:43:29Z
> Thanks for reporting this. I was out of office in the past couple of weeks. I'll take a look a this.

Ok, thank you very much for the code

## comment @joerunde 2025-01-10T20:17:01Z
@maxdebayser @yumingmin88 I'm running the script as well and getting the same results, and I'm pretty confident that the sentence_transformers example is the one that's wrong here, not vLLM.

I get this warning on my machine when loading the cross encoder model:
```
No sentence-transformers model found with name BAAI/bge-reranker-large. Creating a new one with mean pooling.
Some weights of XLMRobertaModel were not initialized from the model checkpoint at BAAI/bge-reranker-large and are newly initialized: ['roberta.pooler.dense.bias', 'roberta.pooler.dense.weight']
You should probably TRAIN this model on a down-stream task to be able to use it for predictions and inference.
```

In the script, the candidates at index 1 and 2 are nearly identical, while the one at index 0 is very different. The vLLM results reflect this: the scores for 1 and 2 are very close together:
```
index:1 socre:0.7098551988601685
index:2 socre:0.704855740070343
```
The scores from the sentence_transformers model make no sense at all:
```
index:1 socre:0.8325262069702148
index:2 socre:0.6860411763191223
```


I did step through the code as a sanity check, and saw that the vllm tokenizer is adding a token id `6` at the end of each input, while the `CrossEncoder`'s use of the tokenizer does not have this extra token. Manually removing this token in a debugger and replaying the vllm model gives only very slightly different results though:
```
index:0 score:0.7844536304473877
index:1 score:0.7098554968833923
index:2 score:0.7048584818840027
```
So I don't think that's an issue

## comment @yumingmin88 2025-01-13T07:29:07Z
> @maxdebayser @yumingmin88 I'm running the script as well and getting the same results, and I'm pretty confident that the sentence_transformers example is the one that's wrong here, not vLLM.
> 
> I get this warning on my machine when loading the cross encoder model:
> 
> ```
> No sentence-transformers model found with name BAAI/bge-reranker-large. Creating a new one with mean pooling.
> Some weights of XLMRobertaModel were not initialized from the model checkpoint at BAAI/bge-reranker-large and are newly initialized: ['roberta.pooler.dense.bias', 'roberta.pooler.dense.weight']
> You should probably TRAIN this model on a down-stream task to be able to use it for predictions and inference.
> ```
> 
> In the script, the candidates at index 1 and 2 are nearly identical, while the one at index 0 is very different. The vLLM results reflect this: the scores for 1 and 2 are very close together:
> 
> ```
> index:1 socre:0.7098551988601685
> index:2 socre:0.704855740070343
> ```
> 
> The scores from the sentence_transformers model make no sense at all:
> 
> ```
> index:1 socre:0.8325262069702148
> index:2 socre:0.6860411763191223
> ```
> 
> I did step through the code as a sanity check, and saw that the vllm tokenizer is adding a token id `6` at the end of each input, while the `CrossEncoder`'s use of the tokenizer does not have this extra token. Manually removing this token in a debugger and replaying the vllm model gives only very slightly different results though:
> 
> ```
> index:0 score:0.7844536304473877
> index:1 score:0.7098554968833923
> index:2 score:0.7048584818840027
> ```
> 
> So I don't think that's an issue

Hello, thank you for your careful check. This example is three fragments selected from 100 fragments, so I failed to find that two of the examples are almost the same. I used another library, FlagEmbedding, to do the rearrangement and get the same ordering as vLLM.
@DarkLight1337 @noooop @maxdebayser I'm sorry, the title says vLLM and hf are different, I subconsciously thought hf is correct. hf is wrong in this example so far. I haven't found anyone reporting it in sentence_transformers.
If the above example is confusing, I will provide the following example that is also quite different: index 7 is different in hf from vLLM
`query, candidates = "五华县", ['五华县，旧名长乐县，民国初改现名，隶属广东省梅州市，地处广东省东北部，韩江上游，是粤东丘陵地带的一部分。东南界丰顺、揭西、陆河，西南接东源、紫金，西北邻龙川，东北连兴宁。总面积3237.8平方公里。 [1]辖16个镇，县政府驻水寨镇 [8]。\n五华是以传承中华文化的汉族客家民系为主体的群落聚居地， [208]是南粤文化的发源地之一，是中国酿酒文明的发源地之一，是中国内地现代足球的发源地 [2]。享有“文化之乡、华侨之乡、足球之乡、工匠之乡”的美誉。文化古迹有狮雄山遗址、狮雄山塔、长乐台、长乐学宫等文保单位；民间传统文化艺术有五华提线木偶戏、五华采茶戏、五华竹马舞、五华石雕等非遗项目。 [3]\n五华是国家级农产品主产区、原中央苏区县、财政省直管县 [4]。享有国家“原中央苏区振兴发展政策”和省“促进粤东西北地区振兴发展政策”、“广州全面对口帮扶政策”等发展扶持政策。\n2021年末，五华县户籍人口1523442人，常住人口921912人。 [207]2023年，五华县地区生产总值为184.55亿元，同比增长4.5%。 [225]', '肇庆市是粤港澳大湾区唯一与大西南接壤的重要节点城市， [112]有新能源汽车及汽车零部件、电子信息、生物医药、金属加工四大主导产业，建筑材料、家具制造、食品饮料、精细化工四大特色产业。 [113-114]2023年，肇庆市地区生产总值为2792.51亿元， [27]三次产业结构比重为17.9:41.3:40.8。 [85]\n肇庆是岭南文化、西江文化 [205]和广府文化的发祥地，是中原文化与岭南文化、中国传统文明与西方文明交汇最早的地区之一， [47]国家历史文化名城、全国文明城市 [160]、广府宜居山水城市，历史上五次成为岭南或大西南政治、经济和文化中心。 [158-159]', '肇庆市（Zhaoqing）， [157]古称端州， [60]广东省辖地级市， [88]位于广东省中西部，东和东南分别与佛山、江门市接壤，西南与云浮市相连，西及西北分别与广西壮族自治区的梧州、贺州市交界，北和东北与清远市相邻。 [59]全市辖3区4县1市， [1]总面积1.49万平方千米， [59]2023年，常住人口413.17万人。 [29]市内主要流行粤方言和客家方言。 [108]\n肇庆属南亚热带季风湿润型气候，境内有西江干流和北江干流，属珠江水系，地势西北高、东南低，雨水充沛，阳光充足，气候温和。 [31] [33]14万年前，境内已有人类生活，文字记载历史2230多年。春秋战国为百越地，秦始皇三十三年（前214年）所设四会县是广东省4个最早建制县之一。明朝嘉靖四十三年（1564年）至清朝乾隆十一年（1746年），肇庆是两广总督府驻地。 [59]1949年5月，广东省重新划分政区，第十一区行政机关驻高要县肇庆镇。1970年10月，肇庆专区改为肇庆地区。1988年1月，撤销肇庆地区，设立肇庆地级市。 [88]', '[15] 王刚刚。 图片验证码的识别与研究[D]。南京邮电大学,2018。[16] Margaretha Ohyver,Jurike V。 Moniaga,Iwa Sungkawa,Bonifasius Edwin Subagyo,Ian Argus Chandra。 The Comparison Firebase Realtime Database and MySQL Database Performance using Wilcoxon Signed-Rank Test[J]。 Procedia Computer Science,2019,157。[17] 王青青,秦贝,郝园媛。车辆信息化管理系统设计[J]。', '浙江 浙江省，简称“浙”，是中华人民共和国省级行政区，省会杭州市，地处中国东南沿海，长江三角洲南翼 [1]；东临东海，北与上海市、江苏省接壤，南接福建省，西与安徽省、江西省相连。浙江省最大的河流钱塘江，因江流曲折，称之江，又称浙江，省以江名。“七山一水两分田”是浙江地形的概貌，浙江省是中国岛屿最多的省份，海岸线总长居全国首位 [121]，属亚热带季风性湿润气候。浙江省陆域面积10.55万平方公里，海域面积26万平方公里 [175]。2023年末，浙江省常住人口为6627万人 [69] [174]。明初，置浙江行中书省，简称浙江省，省名自此出现，后改为浙江承宣布政使司，省界区域基本定型。清康熙初年改为浙江省，沿袭迄今 [173]。浙江省是中国古代文明和中华优秀传统文化发祥地之一， [184]有良渚文化、河姆渡文化、马家浜文化等新石器时代文化 [66]和吴越文化、江南文化 [92]、宋韵文化等地域文化 [79]。浙江省是国务院批复确定的长江经济带发展、长三角一体化发展战略的交汇区，是中国式现代化的先行者 [3]。2021年5月，中共中央、国务院支持浙江高质量发展建设共同富裕示范区 [20]。浙江省人均地区生产总值达到中上等发达国家和地区水平，城镇居民人均可支配收入、农村居民人均可支配收入连续多年居省（区）第1位 [120]，是唯一一个所有设区市居民收入都超过全国平均水平的省份 [77]。2023年，浙江省实现生产总值82553亿元，按不变价格计算，比上年增长6.0% [172]。2024年上半年，浙江全省地区生产总值40920亿元，首次突破4万亿元，同比增长5.6%。 [193]', '北京市 北京市（Beijing），简称“京”，古称燕京、北平，是中华人民共和国首都、直辖市、国家中心城市、超大城市， [185]国务院批复确定的中国政治中心、文化中心、国际交往中心、科技创新中心， [1]中国历史文化名城和古都之一，世界一线城市。 [3] [142] [188]截至2023年10月，北京市下辖16个区，总面积16410.54平方千米。 [82] [193] [195]2023年末，北京市常住人口2185.8万人。 [214-215]北京市地处中国北部、华北平原北部，东与天津市毗连，其余均与河北省相邻，中心位于东经116°20′、北纬39°56′，北京市地势西北高、东南低。西部、北部和东北部三面环山，东南部是一片缓缓向渤海倾斜的平原。境内流经的主要河流有：永定河、潮白河、北运河、拒马河等，北京市的气候为暖温带半湿润半干旱季风气候，夏季高温多雨，冬季寒冷干燥，春、秋短促。北京市是中国共产党中央委员会、中华人民共和国中央人民政府和中华人民共和国全国人民代表大会常务委员会所在地。 [142]北京市成功举办夏奥会与冬奥会，成为全世界第一个“双奥之城”。 [127]北京市是中华民族的发祥地之一， [194]世界著名古都和现代化国际城市， [2]荟萃了自元、明、清以来的中华优秀传统文化成果，拥有众多名胜古迹和人文景观，是全球拥有世界文化遗产数量最多的城市。 [194]2023年，北京市全年实现地区生产总值43760.7亿元，按不变价格计算，比上年增长5.2%。第一产业实现增加值105.5亿元，下降4.6%；第二产业实现增加值6525.6亿元，增长0.4%；第三产业实现增加值37129.6亿元，增长6.1%。 [208]', '白切贵妃鸡 特点：著名的粤式菜肴。以贵妃鸡为原料，肉质鲜美，制作方法特别，蘸酱食用即可。 [27]', '发电厂 并入电网运行的火力（燃煤、燃油、燃气及生物质）、水力、核、风力、太阳能、地热能、海洋能等发电厂（场、站）。 [5]发电厂（power plant）又称发电站，是将自然界蕴藏的各种一次能源转换为电能（二次能源）的工厂。19世纪末，随着电力需求的增长，人们开始提出建立电力生产中心的设想。电机制造技术的发展，电能应用范围的扩大，生产对电的需要的迅速增长，发电厂随之应运而生。发电厂有多种发电途径：靠火力发电的称火电厂，靠水力发电的称水电厂，还有些靠太阳能（光伏）和风力与潮汐发电的电厂等。而以核燃料为能源的核电厂已在世界许多国家发挥越来越大的作用。分类水力发电厂利用水流的动能和势能来生产电能的工厂，简称水电厂。水流量的大小和水头的高低，决定了水流能量的大小。从能量转换的观点分析，其过程为：水能→机械能→电能。实现这一能量转换的生产方式，一般是在河流的上游筑坝，提高水位以造成较高的水头；建造相应的水工设施，以有效地获取集中的水流。水经引水机沟引入水电厂的水轮机，驱动水轮机转动，水能便被转换为水轮机的旋转机械能。与水轮机直接相连的发电机将机械能转换成电能，并由发电厂电气系统升压送入电网。建造强大的水力发电厂时，要考虑改善通航和土地灌溉以及生态平衡。水电厂按电厂结构及水能开发方式分类有引水式、堤坝式、混合式水电厂；按电厂性能及水流调节程度分类有径流式、水库式水电厂；按电厂厂房布置位置分类有坝后式、坝内式水电厂；按主机布置方式分类有地面式、地下式水电站。水力发电厂建设费用高，发电量受水文和气象条件限制，但是电能成本低，具有水利综合效益。水轮机从启动到带满负荷只需几分钟，能够适应电力系统负荷变动，因此水力发电厂可担任系统调频、调峰及负荷备用。小水电从容量角度来说处于所有水电站的末端，它一般是指容量5万千瓦以下的水电站。世界小水电在整个水电的比重大体在5%-6%。中国可开发小水电资源如以原统计数7000万kW计，占世界一半左右。而且，中国的小水电资源分布广泛，特别是广大农村地区和偏远山区，适合因地制宜开发利用，既可以发展地方经济解决当地人民用电困难的问题，又可以给投资人带来可观的效益回报，有很大的发展前景，它将成为中国21世纪前20年的发展热点。世界上，许多发展中国家都制订了一系列鼓励民企投资小水电的政策。由于小水电站投资小、风险低、效益稳、运营成本比较低。在中国各种优惠政策的鼓励下，全国掀起了一股投资建设小水电站的热潮，由于全国缺电严重，民企投资小水电如雨后春笋，悄然兴起。国家鼓励合理开发和利用小水电资源的总方针是确定的，2003年开始，特大水电投资项目也开始向民资开放。根据国务院和水利部的“十一五”计划和2015年发展规划，将对民资投资小水电以及小水电发展给予更多优惠政策。中国小水电可开发量占全国水电资源可开发量的23%，居世界第一位。火力发电厂利用可燃物作为燃料生产电能的工厂，简称火电厂。从能量转换的观点分析，其基本过程是：化学能→热能→机械能→电能。世界上多数国家的火电厂以燃煤为主。煤粉和空气在电厂锅炉炉膛空间内悬浮并进行强烈的混合和氧化燃烧，燃料的化学能转化为热能。热能以辐射和热对流的方式传递给锅炉内的高压水介质，分阶段完成水的预热、汽化和过热过程，使水成为高压高温的过热水蒸气。水蒸气经管道有控制地送入汽轮机，由汽轮机实现蒸气热能向旋转机械能的转换。高速旋转的汽轮机转子通过联轴器拖动发电机发出电能，电能由发电厂电气系统升压送入电网。 [3]垃圾发电厂垃圾发电作为火力发电的一种，截至2007年底，中国垃圾焚烧发电厂总数已达75座，其中建成50座，在建25座垃圾焚烧发电厂的收益稳定、运营成本低廉并享有一定的税收优惠政策，能给投资者带来稳定的收益，但是垃圾发电带来的环境问题不容忽视。核能发电厂利用核能来生产电能工厂，又称核电厂（核电站）。原子核的各个核子（中子与质子）之间具有强大的结合力。重核分裂和轻核聚合时，都会放出巨大的能量，称为核能。技术已比较成熟，形成规模投入运营的，只是重核裂变释放出的核能生产电能的原子能发电厂从能量转换的观点分析，是由重核裂变核能→热能→机械能→电能的转换过程。太阳能发电厂太阳能发电厂是一种用可再生能源——太阳能来发电的工厂，它利用把太阳能转换为电能的光电技术来工作的。德国利用太阳能来发电可供55万个家庭用电所需，是利用太阳能发电的世界冠军。风能发电厂截止到2003年底，全国风能资源丰富的14个省（自治区）已建成风电场40座，累计运行风力发电机组1042台，总容量达567.02MW（以完成整机吊装作为统计依据）。地热发电厂地热能是指贮存在地球内部的可再生热能，一般集中分布在构造板块边缘一带，起源于地球的熔融岩浆和放射性物质的衰变。全球地热能的储量与资源潜量十分巨大，每年从地球内部传到地面的热能相当于100PW·h,但是地热能的分布相对比较分散，因此开发难度很大。由于地热能是储存在地下的，因此不会受到任何天气状况的影响，并且地热资源同时具有其它可再生能源的所有特点，随时可以采用，不带有害物质，关键在于是否有更先进的技术进行开发。地热能在全球很多地区的应用相当广泛，开发技术也在日益完善。对于地热能的利用，包括将低温地热资源用于浴池和空间供热以及用于温室、热力泵和某些热处理过程的供热，同时还可以利用干燥的过热蒸汽和高温水进行发电，利用中等温度水通过双流体循环发电设备发电等，这些地热能的开发应用技术已经逐步成熟，而且对从干燥的岩石中和从地热增压资源及岩浆资源中提取地热能的有效方法进行研究可以进一步提高地热能的应用潜力，但是地热能的勘探和提取技术还有待改进。太空发电厂太空发电厂可能是迄今为止人类有望实现的最大规模轨道建筑，如果建造完成，那么太空发电厂面积将达到6平方公里，部署在3.6万公里的轨道高度上。如此之大的人造建筑甚至可用肉眼察觉到，研究人员称从地面看轨道电站好像一颗恒星高高挂的天空中。把太阳能发电厂转移到太空中的优势很明显，即不会因为昼夜的问题导致能量输出受到影响，而且天气问题也不必去考虑，没有云层会遮挡住电站对阳光的采集。更重要的是，太空发电厂也不占用土地资源。当然，建造轨道发电站还需要克服几个重大问题，比如如何把能量传递到地球上，方法是用微波或者激光。日本科学家的方案是通过微波远程传递把能量接入地面。但是轨道电站的重量将达到1万吨。美国宇航局在研的超级火箭一次仅能将120吨的载荷送入轨道。同时太阳能电池板的安装也是个问题，定期也需要更换，这里都涉及到庞大的资金供应。当前在电力系统中起主导作用的仍是火力、水力、核能发电厂。 [4]']`

## comment @yumingmin88 2025-01-13T10:00:17Z
> @maxdebayser @yumingmin88 I'm running the script as well and getting the same results, and I'm pretty confident that the sentence_transformers example is the one that's wrong here, not vLLM.
> 
> I get this warning on my machine when loading the cross encoder model:
> 
> ```
> No sentence-transformers model found with name BAAI/bge-reranker-large. Creating a new one with mean pooling.
> Some weights of XLMRobertaModel were not initialized from the model checkpoint at BAAI/bge-reranker-large and are newly initialized: ['roberta.pooler.dense.bias', 'roberta.pooler.dense.weight']
> You should probably TRAIN this model on a down-stream task to be able to use it for predictions and inference.
> ```
> 
> In the script, the candidates at index 1 and 2 are nearly identical, while the one at index 0 is very different. The vLLM results reflect this: the scores for 1 and 2 are very close together:
> 
> ```
> index:1 socre:0.7098551988601685
> index:2 socre:0.704855740070343
> ```
> 
> The scores from the sentence_transformers model make no sense at all:
> 
> ```
> index:1 socre:0.8325262069702148
> index:2 socre:0.6860411763191223
> ```
> 
> I did step through the code as a sanity check, and saw that the vllm tokenizer is adding a token id `6` at the end of each input, while the `CrossEncoder`'s use of the tokenizer does not have this extra token. Manually removing this token in a debugger and replaying the vllm model gives only very slightly different results though:
> 
> ```
> index:0 score:0.7844536304473877
> index:1 score:0.7098554968833923
> index:2 score:0.7048584818840027
> ```
> 
> So I don't think that's an issue



> @maxdebayser @yumingmin88 I'm running the script as well and getting the same results, and I'm pretty confident that the sentence_transformers example is the one that's wrong here, not vLLM.
> 
> I get this warning on my machine when loading the cross encoder model:
> 
> ```
> No sentence-transformers model found with name BAAI/bge-reranker-large. Creating a new one with mean pooling.
> Some weights of XLMRobertaModel were not initialized from the model checkpoint at BAAI/bge-reranker-large and are newly initialized: ['roberta.pooler.dense.bias', 'roberta.pooler.dense.weight']
> You should probably TRAIN this model on a down-stream task to be able to use it for predictions and inference.
> ```
> 
> In the script, the candidates at index 1 and 2 are nearly identical, while the one at index 0 is very different. The vLLM results reflect this: the scores for 1 and 2 are very close together:
> 
> ```
> index:1 socre:0.7098551988601685
> index:2 socre:0.704855740070343
> ```
> 
> The scores from the sentence_transformers model make no sense at all:
> 
> ```
> index:1 socre:0.8325262069702148
> index:2 socre:0.6860411763191223
> ```
> 
> I did step through the code as a sanity check, and saw that the vllm tokenizer is adding a token id `6` at the end of each input, while the `CrossEncoder`'s use of the tokenizer does not have this extra token. Manually removing this token in a debugger and replaying the vllm model gives only very slightly different results though:
> 
> ```
> index:0 score:0.7844536304473877
> index:1 score:0.7098554968833923
> index:2 score:0.7048584818840027
> ```
> 
> So I don't think that's an issue

CrossEncoder automatically strips whitespace from inputs.

## comment @joerunde 2025-01-14T00:02:43Z
Thanks @yumingmin88, running these new examples with `FlagReranker` and vllm I get:

```
Ranked Candidates [FlagReranker]:
index:0 score:0.9980823211009958
index:2 score:0.016639577163301045
index:4 score:0.010001778836014575
index:7 score:0.007793925085878985
index:1 score:0.005180309876550857
index:5 score:0.003582984521665067
index:6 score:0.0012977806174509904
index:3 score:0.00010514122792962543
```

```
Ranked Candidates [vLLM]:
index:0 score:0.9980822801589966
index:2 score:0.01663956046104431
index:4 score:0.010001764632761478
index:1 score:0.005180324427783489
index:5 score:0.0035829755943268538
index:6 score:0.0012977831065654755
index:7 score:0.0012506351340562105
index:3 score:0.00010514142923057079
```

I see the difference with index 7, haven't looked into why that is yet. One thing I notice is that the FlagEmbedding library currently only supports transformers 4.44.2, while vllm requires a newer transformers version


## comment @joerunde 2025-01-14T00:21:09Z
🤔 
If I manually truncate `candidates[7]` to less than 512 tokens, then both vllm and the FlagReranker give the same result, so it looks like difference is caused by how the inputs are truncated. I can keep looking tomorrow

## comment @yumingmin88 2025-01-14T02:53:29Z
> 🤔 If I manually truncate `candidates[7]` to less than 512 tokens, then both vllm and the FlagReranker give the same result, so it looks like difference is caused by how the inputs are truncated. I can keep looking tomorrow

Thanks a lot, so far we've found out why these tools might make a difference (for these two examples only).

1. CrossEncoder automatically strips whitespace from inputs.(from sentence_transformers community. Accurate)
2. Truncate the input

Different hardware, driver versions, cuda versions, and dependency library versions may have affected the results. I wonder if you can only get accurate output of your model by using pytorch's native interface?

## comment @joerunde 2025-01-14T18:15:07Z
@yumingmin88 after looking into it more, vLLM always defaults to `left` truncation since for text generation tasks you usually want to keep the end of the prompt, not the beginning of it. For embedding and scoring though, it's common to do `right` truncation to keep the beginning of the prompt. After changing the truncation side, the vLLM results match FlagReranker.

I'll put up a PR in a minute

## comment @ehuaa 2025-03-24T11:53:03Z
Hi guys, when i use v0.7.3 to create embeddings, it turns out weird in the behavior between batching and send requests one by one.
My model is "intfloat/e5-mistral-7b-instruct", my test data is a list with 100 string.
When i set the max-num-seqs=1， i can pass the test in https://github.com/vllm-project/vllm/commits/main/tests/models/embedding/language/test_embedding.py .

But when i use batch inference, the result is inconsistent with huggingface or sentence-transformers, only the first 20 of embeddings can stay consistent with hf, others are inconsistent with cosine_similarity of 0.98 or lower, do you have any ideas to solve this batch inference problem? Thanks @maxdebayser @noooop @joerunde @yumingmin88 