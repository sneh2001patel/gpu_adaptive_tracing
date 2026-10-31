# vllm-project/vllm#25671: [Performance] `model_config.compute_hash` is computed every time and introduce overhead in each new multi-modal req
state=closed reason=completed created=2025-09-25T13:05:30Z closed=2025-09-25T21:06:51Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/25682', 'https://github.com/vllm-project/vllm/pull/25702']

## body (@imkero)
call stack: `InputPreprocessor::_process_multimodal` -> `MultiModalRegistry::create_processor` -> `MultiModalRegistry::_get_model_cls` -> `get_model_architecture` -> `model_config.compute_hash`

https://github.com/vllm-project/vllm/blob/c60e6137f0bf2034853919b3a9d705d7e06b93cf/vllm/model_executor/model_loader/utils.py#L216-L224

## comment @DarkLight1337 2025-09-25T14:42:02Z
How much overhead does this introduce compared to getting the model architecture each time?

## comment @DarkLight1337 2025-09-25T14:50:23Z
I suppose a straightforward way to solve this would be to cache the hash of the model config, and update it whenever the config is mutated.

## comment @DarkLight1337 2025-09-25T15:21:06Z
I've opened https://github.com/vllm-project/vllm/pull/25682, can you try it out?

## comment @ProExpertProg 2025-09-25T17:46:30Z
Why is this computed multiple times? Can we not just save the model class or at least model arch?

## comment @DarkLight1337 2025-09-25T17:48:22Z
The model class is saved in `get_model_architecture` by associating it with the model config, but we use the hash of the config to determine whether it is already in the cache or not. That's why `compute_hash` is called each time.

## comment @DarkLight1337 2025-09-25T17:54:30Z
Basically, `compute_hash` is the way we save the model class. How do you suggest otherwise?

## comment @ProExpertProg 2025-09-25T18:03:01Z
In `InputPreprocessor::_process_multimodal`
```
    if not hasattr(self, 'mm_processor'):
        self.mm_processor = self.mm_registry.create_processor(
            self.model_config,
            tokenizer=tokenizer,
            cache=self.mm_processor_cache,
        )
    
    # now we just use self.mm_processor instead of mm_processor? 
```

I'm not sure that works but that''s roughly the idea. Basically I think ModelConfig shouldn't be caching its hash instead the user should cache stuff because the user is also more aware of changes 


## comment @ProExpertProg 2025-09-25T18:06:01Z
To clarify, the only reason I care about this is we're overhauling how hashing is done for compilation: #23134

## comment @DarkLight1337 2025-09-25T18:08:07Z
I see. I also just realized that we have gotten rid of `lora_request` so we don't have to worry about `tokenizer` changing per-request anymore. I'll apply your suggestion then, thanks!

## comment @DarkLight1337 2025-09-25T18:10:58Z
Actually, I realized that this can't be done until the Renderer refactor (#22880), because we also call `self.mm_registry.create_processor` inside `BaseMultiModalItemTracker` which is initialized per request. I'll edit `get_model_architecture` to use a smaller set of fields instead of using `compute_hash` instead then.

## comment @ywang96 2025-09-25T18:21:39Z
> Actually, I realized that this can't be done until the Renderer refactor ([#22880](https://github.com/vllm-project/vllm/issues/22880)), because we also call `self.mm_registry.create_processor` inside `BaseMultiModalItemTracker` which is initialized per request. I'll edit `get_model_architecture` to use a smaller set of fields instead of using `compute_hash` instead then.

@DarkLight1337 But at least the processor inside `InputPreprocessor::_process_multimodal` can be done, correct? 

## comment @DarkLight1337 2025-09-25T18:22:54Z
Yes, I mean that we can't solve the problem only by changing the call inside `InputPreprocessor`. So we still need to modify `get_model_architecture` regardless.

## comment @DarkLight1337 2025-09-25T18:25:26Z
> But at least the processor inside InputPreprocessor::_process_multimodal can be done, correct?

Let's do that in a separate PR. I also find that `InputProcessor` has some redundant methods like `_tokenize_prompt_async` and `_get_mm_tokenizer_async`, which are left over from #24078

## comment @DarkLight1337 2025-09-25T18:34:50Z
Opened #25702

## comment @imkero 2025-09-26T08:37:14Z
> I've opened [#25682](https://github.com/vllm-project/vllm/pull/25682), can you try it out?

I tried the latest `main` and the result is fine. Thanks @DarkLight1337 

---

(Fire 3 reqs at the same time decoding 1 token for each req)

**before**
```
         41313 function calls (35492 primitive calls) in 0.043 seconds

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
[...]
        3    0.000    0.000    0.010    0.003 /usr/local/app/miniforge3/envs/vllm/lib/python3.12/site-packages/vllm/multimodal/registry.py:254(create_processor)
        3    0.000    0.000    0.009    0.003 /usr/local/app/miniforge3/envs/vllm/lib/python3.12/site-packages/vllm/multimodal/registry.py:227(_get_model_cls)
        3    0.000    0.000    0.009    0.003 /usr/local/app/miniforge3/envs/vllm/lib/python3.12/site-packages/vllm/model_executor/model_loader/utils.py:216(get_model_architecture)
        3    0.000    0.000    0.009    0.003 /usr/local/app/miniforge3/envs/vllm/lib/python3.12/site-packages/vllm/config/model.py:289(compute_hash)
```

**after**
```
         9813 function calls (9419 primitive calls) in 0.033 seconds
```