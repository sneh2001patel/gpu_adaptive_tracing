# vllm-project/vllm#9238: [Performance]: qwen2vl very slow when preprocess large image
state=closed reason=completed created=2024-10-10T08:30:06Z closed=2024-10-30T16:34:09Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/9818']

## body (@zhjunqin)
### Proposal to improve performance

_No response_

### Report of performance regression

build with latest vllm code and start Qwen2-VL-7B-Instruct

![image](https://github.com/user-attachments/assets/2f8e4aa4-0789-4e82-8920-b4180075f53d)

It takes too long time to handle preprocess lead to heartbeat timeout.

ERROR 10-10 01:14:54 client.py:250] RuntimeError('Engine loop has died')
ERROR 10-10 01:14:54 client.py:250] Traceback (most recent call last):
ERROR 10-10 01:14:54 client.py:250]   File "/usr/local/lib/python3.12/dist-packages/vllm/engine/multiprocessing/client.py", line 150, in run_heartbeat_loop
ERROR 10-10 01:14:54 client.py:250]     await self._check_success(
ERROR 10-10 01:14:54 client.py:250]   File "/usr/local/lib/python3.12/dist-packages/vllm/engine/multiprocessing/client.py", line 314, in _check_success
ERROR 10-10 01:14:54 client.py:250]     raise response
ERROR 10-10 01:14:54 client.py:250] RuntimeError: Engine loop has died

ERROR 10-10 01:25:08 client.py:250] TimeoutError('No heartbeat received from MQLLMEngine')
ERROR 10-10 01:25:08 client.py:250] NoneType: None
DEBUG 10-10 01:25:08 client.py:144] Shutting down MQLLMEngineClient check health loop due to timeout
DEBUG 10-10 01:25:14 client.py:170] Waiting for output from MQLLMEngine.
CRITICAL 10-10 01:25:14 launcher.py:99] MQLLMEngine is already dead, terminating server process

Any suggestion to help improve preprocess preformance?


### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [X] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @zhjunqin 2024-10-10T08:36:21Z
code in transformers 
https://github.com/huggingface/transformers/blob/main/src/transformers/image_transforms.py#L97

```
def rescale(
    image: np.ndarray,
    scale: float,
    data_format: Optional[ChannelDimension] = None,
    dtype: np.dtype = np.float32,
    input_data_format: Optional[Union[str, ChannelDimension]] = None,
) -> np.ndarray:
    """
    Rescales `image` by `scale`.

    Args:
[... 23 lines truncated ...]
    return rescaled_image
```


**rescaled_image = image * scale  # takes long time for large image**


## comment @DarkLight1337 2024-10-10T08:47:45Z
It is recommended to use `qwen_vl_utils` (as shown [here](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct#quickstart)) to preprocess the images before passing them into vLLM.

## comment @zhjunqin 2024-10-10T09:38:19Z
> It is recommended to use `qwen_vl_utils` (as shown [here](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct#quickstart)) to preprocess the images before passing them into vLLM.

I'm not sure how it work.  After preprocess by qwen_vl_utils, image becomes to a tensor, then send to vLLM？

## comment @DarkLight1337 2024-10-10T09:50:59Z
It should resize the images to be suitable to be used by the model. So, if you input an image that is too large, it should be resized.

## comment @zhjunqin 2024-10-10T11:12:31Z
> It should resize the images to be suitable to be used by the model. So, if you input an image that is too large, it should be resized.

Take 1080p (1980 x 1080) as limit picture size, it still takes more than 10s to preprocess.

## comment @DarkLight1337 2024-10-10T17:10:51Z
Since the processing time is contained inside HuggingFace, I guess it's not really our fault... even if our engine didn't timeout, you would still get very poor performance. Perhaps open an issue on HuggingFace side? cc @fyabc 