# vllm-project/vllm#7592: [Performance]: vllm 0.5.4 with enable_chunked_prefill =True, throughput is slightly lower than 0.5.3~0.5.0.
state=closed reason=completed created=2024-08-16T16:06:39Z closed=2024-09-02T21:20:13Z labels=['bug']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/7874']

## body (@noooop)
### Your current environment

<details>
<summary>environment</summary>

# Hardware & Nvidia driver & OS
GPU models and configuration: GPU 0: NVIDIA GeForce RTX 4090       

Nvidia driver version: 550.107.02 

OS: Ubuntu 22.04.4 LTS (x86_64) 

# conda env create -f environment_linux.yml
```
name: vllm_xxx
channels:
  - conda-forge
  - pytorch
  - nvidia
  - defaults
dependencies:
  - python=3.11
  - anaconda
  - pip
  - pip:
[... 1 lines truncated ...]
pip install vllm==v0.5.4 / v0.5.3.post1 / v0.5.2 / v0.5.1
```

</details>


### 🐛 Describe the bug

Throughput and latency vary with max_num_seqs。

vllm 0.5.4 with enable_chunked_prefill =True, throughput is slightly lower than 0.5.3~0.5.1. very strange.

![chunked_prefill](https://github.com/user-attachments/assets/0250456a-60b8-45e9-82ad-316204f6e778)

| max_num_seqs | requests/s | disable 0.5.4 | requests/s | disable 0.5.3 | requests/s | disable 0.5.2 | requests/s | disable 0.5.1 | requests/s | enable 0.5.4 | requests/s | enable 0.5.3 | requests/s | enable 0.5.2 | requests/s | enable 0.5.1 |
|--------------|------------|---------------|------------|---------------|------------|---------------|------------|---------------|------------|--------------|------------|--------------|------------|--------------|------------|--------------|
| 1024         | 2.5115     | 36.1          | 2.4747     | 36.69         | 2.4878     | 36.82         | 2.4972     | 36.33         | 3.1797     | 39.72        | 3.1341     | 40.15        | 3.1696     | 39.67        | 3.1745     | 39.61        |
| 768          | 3.2838     | 42.6          | 3.2242     | 43.48         | 3.2608     | 42.93         | 3.2648     | 42.88         | 4.1047     | 43.4         | 3.9708     | 44.42        | 4.0413     | 43.6         | 4.0439     | 43.57        |
| 512          | 4.1063     | 51.93         | 4.0102     | 53.22         | 4.0966     | 52.07         | 4.0998     | 51.97         | 4.6486     | 46.79        | 4.6377     | 46.25        | 4.7419     | 45.15        | 4.747      | 45.13        |
| 384          | 4.1705     | 54.83         | 4.0749     | 56.35         | 4.1538     | 55.07         | 4.1587     | 55            | 4.798      | 49.66        | 4.8605     | 45.93        | 4.9834     | 44.72        | 5.0019     | 44.61        |
| 256          | 4.3613     | 59.37         | 4.2659     | 60.94         | 4.3586     | 59.44         | 4.3632     | 59.36         | 4.9096     | 48.27        | 5.4424     | 42.23        | 5.5876     | 41.1         | 5.5949     | 41.04        |
| 128          | 4.7441     | 42.75         | 4.6511     | 43.76         | 4.7564     | 42.62         | 4.7583     | 42.58         | 4.2047     | 32.77        | 4.0718     | 29.7         | 4.1528     | 29.11        | 4.1544     | 29.1         |
| 64           | 3.7161     | 29.56         | 3.6446     | 30.2          | 3.6972     | 29.71         | 3.7044     | 29.66         | 2.435      | 26.88        | 2.3879     | 25.74        | 2.4141     | 25.45        | 2.4175     | 25.41        |
| 32           | 2.6923     | 20.76         | 2.6465     | 21.16         | 2.6702     | 20.94         | 2.6735     | 20.92         | 1.6103     | 19.83        | 1.5846     | 19.55        | 1.593      | 19.44        | 1.5942     | 19.43        |

```
import os
import random
import numpy as np
import time


def benchmark(args):
    random.seed(args.seed)

    os.environ["VLLM_LOGGING_LEVEL"] = "ERROR"
    os.environ["VLLM_NO_USAGE_STATS"] = "True"
[... 131 lines truncated ...]
        run(args)
```




## comment @noooop 2024-08-18T08:32:16Z
update

I managed to compile vllm 0.5.4 with torch == 2.3.1 xformers == 0.0.27 vllm-flash-attn == 2.5.9.post1 (from vllm 0.5.3 requirements )， the bug is still there.

![chunked_prefill2](https://github.com/user-attachments/assets/fbfca114-ae8b-4e13-ae3c-3afe9d3730d7)


The bug only affects chunked_prefill, everything works fine when chunked_prefill is turned off.


## comment @noooop 2024-08-18T10:16:24Z
update

I managed to merge vllm 0.5.3 python part and vllm 0.5.4 c part，the bug gone.  labeled as vllm 0.5.3+.

![chunked_prefill3](https://github.com/user-attachments/assets/c02f1f5c-a0bf-4f0e-b502-b9cb040316f2)

so, bug in vllm 0.5.4 python part, and not in attention folder.




## comment @noooop 2024-08-18T10:50:45Z
Caused by [core,scheduler] simplify and improve scheduler #6867

https://github.com/vllm-project/vllm/pull/6867

Revert the commit, the bug gone. 

## comment @njhill 2024-08-18T15:02:46Z
@youkaichao ^^

## comment @youkaichao 2024-08-19T05:51:12Z
first, this is not a bug. it's better to appear with a "performance" tag.

second, there are various workloads you can test, and it is difficult to have any code change that benefits all workloads.

that pr is very important for optimizing the case in large offline batch inference setting. If you can achieve the same effect while keeping chunked prefill performance the untouched, we'd welcome that contribution.

## comment @noooop 2024-08-19T06:37:40Z
That PR caused chunked prefill peak throughput to drop by 15%. 
I thought it would be interesting to figure out why.