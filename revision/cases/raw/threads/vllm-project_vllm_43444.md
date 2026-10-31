# vllm-project/vllm#43444: [Performance]: Significant performance degradation  v1/reranker under concurrent requests while swiching from v.0.19.1 to v0.20.2 v0.21.1
state=closed reason=completed created=2026-05-22T18:33:21Z closed=2026-07-22T10:56:25Z labels=['performance']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/49019', 'https://github.com/vllm-project/vllm/pull/49153']

## body (@AI1718)
### Proposal to improve performance

_No response_

### Report of performance regression


Model: bge-reranker-v2-m3.
Here 3 runs of some sample code for 3 version of vllm. Same code, just different version of vllm.
Mean Latency(T) - sec using requests 
Mean Latency(A)  - sec using aiohttp

<!--StartFragment--><!DOCTYPE html><p cid="n1919" mdtype="paragraph" class="md-end-block md-p md-focus" style="box-sizing: border-box; line-height: inherit; orphans: 4; margin: 0.8em 0px; white-space: pre-wrap; position: relative; color: rgb(51, 51, 51); font-family: &quot;Open Sans&quot;, &quot;Clear Sans&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, &quot;Segoe UI Emoji&quot;, &quot;SF Pro&quot;, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><span md-inline="plain" class="md-plain md-expand" style="box-sizing: border-box;">(vllm v0.19.1)</span></p><figure class="md-table-fig table-figure" cid="n1920" mdtype="table" style="box-sizing: border-box; margin: 1.2em 0px; overflow-x: auto; max-width: calc(100% + 16px); padding: 0px; cursor: default; color: rgb(51, 51, 51); font-family: &quot;Open Sans&quot;, &quot;Clear Sans&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, &quot;Segoe UI Emoji&quot;, &quot;SF Pro&quot;, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">
Сoncurency | Time (A) | Time(T) | RPS(A) | RPS(T) | Mean Latency(A) | Mean Latency(T) | Max Latency(A) | Max Latency(T) | Min Latency(A) | Min Latency(T)
-- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --
1 | 4.49 | 3.7 | 0.22 | 0.27 | 3.93 | 3.7 | 3.93 | 3.7 | 3.93 | 3.7
5 | 15.45 | 15.33 | 0.32 | 0.33 | 11.77 | 11.63 | 15.1 | 15.32 | 7.67 | 7.74
10 | 29.32 | 28.54 | 0.34 | 0.35 | 20.95 | 20.04 | 28.97 | 28.53 | 11.87 | 10.87
20 | 53.89 | 58.27 | 0.37 | 0.34 | 35.08 | 40.06 | 53.49 | 58.24 | 13.26 | 20.25

</figure><br class="Apple-interchange-newline"><!--EndFragment-->

<!--StartFragment--><!DOCTYPE html><p cid="n1523" mdtype="paragraph" class="md-end-block md-p md-focus" style="box-sizing: border-box; line-height: inherit; orphans: 4; margin: 0.8em 0px; white-space: pre-wrap; position: relative; color: rgb(51, 51, 51); font-family: &quot;Open Sans&quot;, &quot;Clear Sans&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, &quot;Segoe UI Emoji&quot;, &quot;SF Pro&quot;, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><span md-inline="plain" class="md-plain md-expand" style="box-sizing: border-box;"> (vllm v0.20.2)</span></p><figure class="md-table-fig table-figure md-focus" cid="n1590" mdtype="table" style="box-sizing: border-box; margin: 1.2em 0px; overflow-x: auto; max-width: calc(100% + 16px); padding: 0px; cursor: default; color: rgb(51, 51, 51); font-family: &quot;Open Sans&quot;, &quot;Clear Sans&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, &quot;Segoe UI Emoji&quot;, &quot;SF Pro&quot;, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">
Сoncurency | Time (A) | Time(T) | RPS(A) | RPS(T) | Mean Latency(A) | Mean Latency(T) | Max Latency(A) | Max Latency(T) | Min Latency(A) | Min Latency(T)
-- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --
1 | 5.55 | 4.89 | 0.18 | 0.2 | 5.09 | 4.88 | 5.09 | 4.88 | 5.09 | 4.88
5 | 21.44 | 20.81 | 0.23 | 0.24 | 21.11 | 20.79 | 21.12 | 20.8 | 21.09 | 20.77
10 | 42.53 | 42.76 | 0.24 | 0.23 | 42.19 | 42.71 | 42.21 | 42.74 | 42.16 | 42.65
20 | 85.83 | 82.97 | 0.23 | 0.24 | 85.43 | 82.89 | 85.48 | 82.96 | 85.36 | 82.69

</figure><!--EndFragment-->

<!--StartFragment--><!DOCTYPE html><p cid="n1661" mdtype="paragraph" class="md-end-block md-p md-focus" style="box-sizing: border-box; line-height: inherit; orphans: 4; margin: 0.8em 0px; white-space: pre-wrap; position: relative; color: rgb(51, 51, 51); font-family: &quot;Open Sans&quot;, &quot;Clear Sans&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, &quot;Segoe UI Emoji&quot;, &quot;SF Pro&quot;, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><span md-inline="plain" class="md-plain md-expand" style="box-sizing: border-box;"> (vllm v0.21.0)</span></p><figure class="md-table-fig table-figure" cid="n1984" mdtype="table" style="box-sizing: border-box; margin: 1.2em 0px; overflow-x: auto; max-width: calc(100% + 16px); padding: 0px; cursor: default; color: rgb(51, 51, 51); font-family: &quot;Open Sans&quot;, &quot;Clear Sans&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, &quot;Segoe UI Emoji&quot;, &quot;SF Pro&quot;, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">
Сoncurency | Time (A) | Time(T) | RPS(A) | RPS(T) | Mean Latency(A) | Mean Latency(T) | Max Latency(A) | Max Latency(T) | Min Latency(A) | Min Latency(T)
-- | -- | -- | -- | -- | -- | -- | -- | -- | -- | --
1 | 5.58 | 5.06 | 0.18 | 0.2 | 5.09 | 5.05 | 5.09 | 5.05 | 5.09 | 5.05
5 | 21.86 | 21.74 | 0.23 | 0.23 | 21.48 | 21.72 | 21.49 | 21.73 | 21.47 | 21.7
10 | 43.03 | 42.62 | 0.23 | 0.23 | 42.66 | 42.58 | 42.69 | 42.62 | 42.61 | 42.52
20 | 85.62 | 85.81 | 0.23 | 0.23 | 85.22 | 85.71 | 85.29 | 85.78 | 85.12 | 85.6

</figure><!--EndFragment-->

### Misc discussion on performance

_No response_

### Your current environment (if you think it is necessary)

Collecting environment information...
==============================
        System Info
==============================
OS                           : Ubuntu 22.04.5 LTS (x86_64)
GCC version                  : (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0
Clang version                : Could not collect
CMake version                : Could not collect
Libc version                 : glibc-2.35

==============================
       PyTorch Info
==============================
PyTorch version              : 2.11.0+cu130
Is debug build               : False
CUDA used to build PyTorch   : 13.0
ROCM used to build PyTorch   : N/A
XPU used to build PyTorch    : N/A

==============================
      Python Environment
==============================
Python version               : 3.12.13 (main, Mar  4 2026, 09:23:07) [GCC 11.4.0] (64-bit runtime)
Python platform              : Linux-5.15.0-176-generic-x86_64-with-glibc2.35
    
==============================
       CUDA / GPU Info
==============================
Is CUDA available            : True
CUDA runtime version         : 13.0.88
CUDA_MODULE_LOADING set to   : 
GPU models and configuration : GPU 0: NVIDIA L40S
Nvidia driver version        : 570.211.01
cuDNN version                : Could not collect
HIP runtime version          : N/A
MIOpen runtime version       : N/A
Is XNNPACK available         : True

==============================
          CPU Info
==============================
Architecture:                            x86_64
CPU op-mode(s):                          32-bit, 64-bit
Address sizes:                           45 bits physical, 48 bits virtual
Byte Order:                              Little Endian
CPU(s):                                  24
On-line CPU(s) list:                     0-23
Vendor ID:                               AuthenticAMD
Model name:                              AMD EPYC 9654 96-Core Processor
CPU family:                              25
Model:                                   17
Thread(s) per core:                      1
Core(s) per socket:                      1
Socket(s):                               24
Stepping:                                1
BogoMIPS:                                4792.79
Flags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl tsc_reliable nonstop_tsc cpuid extd_apicid tsc_known_freq pni pclmulqdq ssse3 fma cx16 pcid sse4_1 sse4_2 x2apic movbe popcnt aes xsave avx f16c rdrand hypervisor lahf_lm extapic cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw topoext invpcid_single ssbd ibrs ibpb ibrs_enhanced vmmcall fsgsbase bmi1 avx2 smep bmi2 erms invpcid avx512f avx512dq rdseed adx smap avx512ifma clflushopt clwb avx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves avx512_bf16 clzero wbnoinvd arat avx512vbmi umip pku ospke avx512_vbmi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg avx512_vpopcntdq rdpid overflow_recov succor fsrm flush_l1d
Hypervisor vendor:                       VMware
Virtualization type:                     full
L1d cache:                               768 KiB (24 instances)
L1i cache:                               768 KiB (24 instances)
L2 cache:                                24 MiB (24 instances)
L3 cache:                                768 MiB (24 instances)
NUMA node(s):                            1
NUMA node0 CPU(s):                       0-23
Vulnerability Gather data sampling:      Not affected
Vulnerability Indirect target selection: Not affected
Vulnerability Itlb multihit:             Not affected
Vulnerability L1tf:                      Not affected
Vulnerability Mds:                       Not affected
Vulnerability Meltdown:                  Not affected
Vulnerability Mmio stale data:           Not affected
Vulnerability Reg file data sampling:    Not affected
Vulnerability Retbleed:                  Not affected
Vulnerability Spec rstack overflow:      Mitigation; safe RET
Vulnerability Spec store bypass:         Mitigation; Speculative Store Bypass disabled via prctl and seccomp
Vulnerability Spectre v1:                Mitigation; usercopy/swapgs barriers and __user pointer sanitization
Vulnerability Spectre v2:                Mitigation; Enhanced / Automatic IBRS; IBPB conditional; STIBP disabled; PBRSB-eIBRS Not affected; BHI Not affected
Vulnerability Srbds:                     Not affected
Vulnerability Tsa:                       Vulnerable: Clear CPU buffers attempted, no microcode
Vulnerability Tsx async abort:           Not affected
Vulnerability Vmscape:                   Not affected

==============================
Versions of relevant libraries
==============================
[pip3] flashinfer-python==0.6.8.post1
[pip3] numpy==2.2.6
[pip3] nvidia-cublas==13.1.0.3
[pip3] nvidia-cuda-cupti==13.0.85
[pip3] nvidia-cuda-nvrtc==13.0.88
[pip3] nvidia-cuda-runtime==13.0.96
[pip3] nvidia-cudnn-cu13==9.19.0.56
[pip3] nvidia-cudnn-frontend==1.18.0
[pip3] nvidia-cufft==12.0.0.61
[pip3] nvidia-cufile==1.15.1.6
[pip3] nvidia-curand==10.4.0.35
[pip3] nvidia-cusolver==12.0.4.66
[pip3] nvidia-cusparse==12.6.3.3
[pip3] nvidia-cusparselt-cu13==0.8.0
[pip3] nvidia-cutlass-dsl==4.4.2
[pip3] nvidia-cutlass-dsl-libs-base==4.4.2
[pip3] nvidia-ml-py==13.595.45
[pip3] nvidia-nccl-cu13==2.28.9
[pip3] nvidia-nvjitlink==13.0.88
[pip3] nvidia-nvshmem-cu13==3.4.5
[pip3] nvidia-nvtx==13.0.85
[pip3] pyzmq==27.1.0
[pip3] tokenspeed-triton==3.7.10.post20260505
[pip3] torch==2.11.0+cu130
[pip3] torch_c_dlpack_ext==0.1.5
[pip3] torchaudio==2.11.0+cu130
[pip3] torchvision==0.26.0+cu130
[pip3] transformers==5.8.1
[pip3] triton==3.6.0
[conda] Could not collect

==============================
         vLLM Info
==============================
ROCM Version                 : Could not collect
vLLM Version                 : 0.21.0
vLLM Build Flags:
  CUDA Archs: 7.5 8.0 8.6 8.9 9.0 10.0 12.0+PTX; ROCm: Disabled; XPU: Disabled
GPU Topology:
        GPU0    CPU Affinity    NUMA Affinity   GPU NUMA ID
GPU0     X      0-23    0               N/A

Legend:

  X    = Self
  SYS  = Connection traversing PCIe as well as the SMP interconnect between NUMA nodes (e.g., QPI/UPI)
  NODE = Connection traversing PCIe as well as the interconnect between PCIe Host Bridges within a NUMA node
  PHB  = Connection traversing PCIe as well as a PCIe Host Bridge (typically the CPU)
  PXB  = Connection traversing multiple PCIe bridges (without traversing the PCIe Host Bridge)
  PIX  = Connection traversing at most a single PCIe bridge
  NV#  = Connection traversing a bonded set of # NVLinks

==============================
     Environment Variables
==============================
NVIDIA_VISIBLE_DEVICES=all
NVIDIA_REQUIRE_CUDA=cuda>=13.0 brand=unknown,driver>=535,driver<536 brand=grid,driver>=535,driver<536 brand=tesla,driver>=535,driver<536 brand=nvidia,driver>=535,driver<536 brand=quadro,driver>=535,driver<536 brand=quadrortx,driver>=535,driver<536 brand=nvidiartx,driver>=535,driver<536 brand=vapps,driver>=535,driver<536 brand=vpc,driver>=535,driver<536 brand=vcs,driver>=535,driver<536 brand=vws,driver>=535,driver<536 brand=cloudgaming,driver>=535,driver<536 brand=unknown,driver>=550,driver<551 brand=grid,driver>=550,driver<551 brand=tesla,driver>=550,driver<551 brand=nvidia,driver>=550,driver<551 brand=quadro,driver>=550,driver<551 brand=quadrortx,driver>=550,driver<551 brand=nvidiartx,driver>=550,driver<551 brand=vapps,driver>=550,driver<551 brand=vpc,driver>=550,driver<551 brand=vcs,driver>=550,driver<551 brand=vws,driver>=550,driver<551 brand=cloudgaming,driver>=550,driver<551 brand=unknown,driver>=565,driver<566 brand=grid,driver>=565,driver<566 brand=tesla,driver>=565,driver<566 brand=nvidia,driver>=565,driver<566 brand=quadro,driver>=565,driver<566 brand=quadrortx,driver>=565,driver<566 brand=nvidiartx,driver>=565,driver<566 brand=vapps,driver>=565,driver<566 brand=vpc,driver>=565,driver<566 brand=vcs,driver>=565,driver<566 brand=vws,driver>=565,driver<566 brand=cloudgaming,driver>=565,driver<566 brand=unknown,driver>=570,driver<571 brand=grid,driver>=570,driver<571 brand=tesla,driver>=570,driver<571 brand=nvidia,driver>=570,driver<571 brand=quadro,driver>=570,driver<571 brand=quadrortx,driver>=570,driver<571 brand=nvidiartx,driver>=570,driver<571 brand=vapps,driver>=570,driver<571 brand=vpc,driver>=570,driver<571 brand=vcs,driver>=570,driver<571 brand=vws,driver>=570,driver<571 brand=cloudgaming,driver>=570,driver<571 brand=unknown,driver>=575,driver<576 brand=grid,driver>=575,driver<576 brand=tesla,driver>=575,driver<576 brand=nvidia,driver>=575,driver<576 brand=quadro,driver>=575,driver<576 brand=quadrortx,driver>=575,driver<576 brand=nvidiartx,driver>=575,driver<576 brand=vapps,driver>=575,driver<576 brand=vpc,driver>=575,driver<576 brand=vcs,driver>=575,driver<576 brand=vws,driver>=575,driver<576 brand=cloudgaming,driver>=575,driver<576
TORCH_CUDA_ARCH_LIST=7.5 8.0 8.6 8.9 9.0 10.0 12.0+PTX
NVIDIA_DRIVER_CAPABILITIES=compute,utility
VLLM_USAGE_SOURCE=production-docker-image
CUDA_VERSION=13.0.2
VLLM_ENABLE_CUDA_COMPATIBILITY=0
LD_LIBRARY_PATH=/usr/local/nvidia/lib64:/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:/usr/local/cuda/lib64
VLLM_LOGGING_LEVEL=DEBUG
PYTORCH_NVML_BASED_CUDA_CHECK=1
TORCHINDUCTOR_COMPILE_THREADS=1
TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor_root

### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @AI1718 2026-05-25T20:39:43Z
I made test  more clear.
Simple python script:
<code>
async def rerank(session, api_url, query:str, documents:list[str]):
    data = {
        "model": "bge-reranker-v2-m3",
        "queries": query,
        "documents": documents
    }
    dt1 = time.time_ns()
    async with session.post(api_url, json=data, ssl=False, timeout=None,
                            headers={"Connection": "close"}) as response:
        dt2 = time.time_ns()
        elps = (dt2 - dt1) // (1_000_000)
        if response.status == 200:
            res = await response.json()
        else:
            response.raise_for_status()
        return (elps, res)

async def t_rerank(data:dict, concurrency:int):
    connector = aiohttp.TCPConnector(ssl=False, limit=0, limit_per_host=50)

    api_url = "http://172.16.25.97:9004/v1/score"
    query = data["query"]
    docs = data["docs"]
    slide_size = 100
    slides = [docs[i : i + slide_size] for i in range(0, len(docs), slide_size)]
    results = []
    limiter = anyio.CapacityLimiter(concurrency)
    async with aiohttp.ClientSession(connector=connector, timeout=None) as session:
        async def run_rerank(session, api_url, query, batch):
            res = await rerank(session, api_url, query, batch)
            results.append(res[0])
        async with limiter:
            async with anyio.create_task_group() as tg:
                for batch in slides:
                    tg.start_soon(run_rerank, session, api_url, query, batch)
    return round(max(results),2), round(min(results),2), round(sum(results)/len(results),2),len(results)





async def t_rerank_probe(data):
    table = PrettyTable()
    table.field_names =["Concurrency", "Avg msec", "Max msec", "Min msec"]
    table.align = "l"
    table.set_style(TableStyle.MARKDOWN)
    for c in [1,5,10,15,20,30, 50]:
        r_max, r_min, r_avg, calls = await t_rerank(data,c)
        #print(f"{c}\t\{r_avg},\t{r_max}\t{r_min}")
        table.add_row([c,  r_avg, r_max,r_min])
        print(table.get_string())


if __name__ == '__main__':
    with open("./_test_data/rerank.json", "r", encoding="utf-8") as f:
        data_str = f.read()
    data  = json.loads(data_str)
    asyncio.run(t_rerank_probe(data))
    #asyncio.run(t_sql())
    exit(0)
</code>
Rerank 100 docs per request. Total call to /v1/score =22
Resulsts:

v0.19.1

| Concurrency | Avg msec | Max msec | Min msec |
| :-----------| :--------| :--------| :--------|
| 1           | 1339.91  | 2313     | 390      |
| 5           | 1207.36  | 2062     | 348      |
| 10          | 1325.0   | 2153     | 325      |
| 15          | 1210.77  | 2108     | 347      |
| 20          | 1331.0   | 2273     | 335      |
| 30          | 1377.55  | 2083     | 588      |
| 50          | 1270.18  | 2095     | 654      |

Process finished with exit code 0


v0.20.2

| Concurrency | Avg msec | Max msec | Min msec |
| :---------- | :------- | :------- | :------- |
| 1           | 2069.23  | 2279     | 2024     |
| 5           | 2069.0   | 2318     | 2011     |
| 10          | 1997.77  | 2246     | 1951     |
| 15          | 1994.18  | 2257     | 1944     |
| 20          | 2040.23  | 2309     | 1973     |
| 30          | 2031.82  | 2320     | 1968     |
| 50          | 1998.23  | 2550     | 1855     |



v0.21.1

| Concurrency | Avg msec | Max msec | Min msec |
| :---------- | :------- | :------- | :------- |
| 1           | 2031.59  | 2454     | 1930     |
| 5           | 1957.0   | 2299     | 1884     |
| 10          | 1991.91  | 2541     | 1871     |
| 15          | 1960.23  | 2305     | 1883     |
| 20          | 1994.59  | 2456     | 1911     |
| 30          | 1940.68  | 2338     | 1850     |
| 50          | 1978.68  | 2559     | 1846     |


## comment @noooop 2026-05-29T07:33:41Z
In my tests, I observed a 2% peak throughput reduction, which may be caused by the upgrade from 2.10.0+cu128 to 2.11.0+cu130.

https://github.com/noooop/snippet/blob/main/observability/pooling/scoring/benchmark.py

<img width="1183" height="888" alt="Image" src="https://github.com/user-attachments/assets/d8bd1794-2042-4bfb-b8b0-046a72610267" />

If using api_server_count = 8, there is no significant change, so it should not be an issue with the entrypoint.

<img width="1184" height="887" alt="Image" src="https://github.com/user-attachments/assets/91d2f52c-deda-4829-ae72-2f0c7a9f1534" />

## comment @noooop 2026-05-29T08:51:31Z
Could you please try my new Observability PR #43069? It might help us see exactly what is taking too much time.

1.  setup  Grafana Tempo

Refer to https://github.com/grafana/tempo/tree/main/example/docker-compose

https://github.com/noooop/snippet/tree/main/observability/tempo

```
docker compose up
```

2. setup  server

```
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=http://localhost:4317

vllm serve BAAI/bge-reranker-v2-m3 --otlp-traces-endpoint="$OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"
```

3. dummy_client

https://github.com/noooop/snippet/blob/main/observability/pooling/scoring/dummy_client.py

```
python observability/pooling/scoring/dummy_client.py
```


<img width="1919" height="910" alt="Image" src="https://github.com/user-attachments/assets/cb51384e-cb88-474f-ba0c-93d315cda6b3" />

At least on my machine (4090), all the time spent is reasonable.

***

Maybe CPU preprocessing is the bottleneck on your machine. Try increasing api_server_count, which defaults to 1.

## comment @AI1718 2026-05-29T10:48:43Z
Your test differs from mine in that:
1) I send 100 documents in one single request - you send only 1 in single request.
2) I use max_model_len = 8000 (you 512), and larger docs (up to 8000 toks)

Maybe that's the point

## comment @noooop 2026-05-29T11:27:53Z
You can see that a batch size of 32 x 512 to 16k token is enough to saturate the GPU, so sending many documents in a single request doesn’t make much sense. 

Furthermore, since preprocessing within a single request is not parallelized, you should split requests as much as possible to maximize preprocessing parallelism.

## comment @noooop 2026-05-29T12:19:14Z
Maybe we should parallelize preprocessing within the same request. Previously, we thought it might introduce unnecessary complexity.

## comment @AI1718 2026-05-29T21:04:56Z
> You can see that a batch size of 32 x 512 to 16k token is enough to saturate the GPU, so sending many documents in a single request doesn’t make much sense.
> 
> Furthermore, since preprocessing within a single request is not parallelized, you should split requests as much as possible to maximize preprocessing parallelism.

One could certainly delve into the intricacies of optimization, but that is not important in this case. The point is that under the same conditions, degradation appeared after version v0.19.1. The code I provided is easy to verify.