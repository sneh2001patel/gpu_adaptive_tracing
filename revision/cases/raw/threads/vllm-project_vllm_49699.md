# vllm-project/vllm#49699: [Performance]: Compile mode 3 degrades triton w4a16 kernel performance in few request scenarios.
state=closed reason=completed created=2026-07-24T09:22:34Z closed=2026-09-02T03:55:36Z labels=['performance', 'rocm']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/51453']

## body (@hnhyzz)
### Proposal to improve performance

Currently, I turned up the priority  of the exllama to get rid of the throughput regression. But I am afraid other triton kernels may also be interfered.

### Report of performance regression

When serving a Qwen 27B GPTQ-4bit model and setting the compile mode from 0 to 3, the decode throughput degrades from 7.0 to 4.8 . But the exllama kernel increases from 13 to 26.

Following is the command to start the vllm docker. The compile mode can be directly set in the command. To force using the exllama kernel, I commented the triton w4a16 kernel in the vllm/model_executor/kernels/linear/__init__.py.

docker run -it --rm --network=host --device=/dev/kfd --device=/dev/dri --group-add video --ipc=host --shm-size 128g --cap-add=SYS_PTRACE \
-v ./models:/models \
--cpuset-cpus="48-95" \
--cpuset-mems="1" \
-e VLLM_ROCM_USE_SKINNY_GEMM=1 \
-e HIP_VISIBLE_DEVICES=0 \
vllm-gfx908:latest bash -c "vllm serve /models/Qwen-4bit/ --dtype float16 --gpu-memory-utilization 0.94 --tensor-parallel-size 1 --pipeline-parallel-size 1 --data-parallel-size 1 --attention-backend TRITON_ATTN --mm-encoder-attn-backend TORCH_SDPA --max-model-len 32000 --max-num-seqs 4 --enable-prefix-caching --reasoning-parser qwen3 --enable-auto-tool-choice --tool-call-parser qwen3_coder  --served-model-name 'Qwen' --api-key 'xxxxxx' --compilation-config '{\"cudagraph_mode\": \"FULL_AND_PIECEWISE\", \"mode\":3 }' --skip-mm-profiling --limit-mm-per-prompt '{\"image\": 2}'  --max_num_batched_tokens 4096"

### Misc discussion on performance

As I confirmed, it is not a result of CUDA graph, as the degradation also exists when keeping CUDA graph off.
I think it is because the inductor compilation is interfered by the triton w4a16 kernel. As I checked the rocprof traces, when the compile mode is 3, the triton_red_fused__to_copy_add_copy__fused_add_rms_norm_5 wastes a lot more time, but it is missing when compile mode is 0.


### Your current environment (if you think it is necessary)

==============================
        System Info
==============================
OS                           : Ubuntu 24.04.4 LTS (x86_64)
GCC version                  : (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
Clang version                : Could not collect
CMake version                : version 4.4.0
Libc version                 : glibc-2.39

==============================
       PyTorch Info
==============================
PyTorch version              : 2.11.0+rocm7.2
Is debug build               : False
CUDA used to build PyTorch   : N/A
ROCM used to build PyTorch   : 7.2.26015
XPU used to build PyTorch    : N/A

==============================
      Python Environment
==============================
Python version               : 3.12.3 (main, Mar 23 2026, 19:04:32) [GCC 13.3.0] (64-bit runtime)
Python platform              : Linux-6.8.0-124-generic-x86_64-with-glibc2.39
    
==============================
       CUDA / GPU Info
==============================
Is CUDA available            : True
CUDA runtime version         : Could not collect
CUDA_MODULE_LOADING set to   : 
GPU models and configuration : AMD Instinct MI100 (gfx908:sramecc+:xnack-)
Nvidia driver version        : Could not collect
cuDNN version                : Could not collect
HIP runtime version          : 7.2.26015
MIOpen runtime version       : 3.5.1
Is XNNPACK available         : True

==============================
          CPU Info
==============================
Architecture:                            x86_64
CPU op-mode(s):                          32-bit, 64-bit
Address sizes:                           43 bits physical, 48 bits virtual
Byte Order:                              Little Endian
CPU(s):                                  96
On-line CPU(s) list:                     0-95
Vendor ID:                               AuthenticAMD
Model name:                              AMD EPYC 7K62 48-Core Processor
CPU family:                              23
Model:                                   49
Thread(s) per core:                      1
Core(s) per socket:                      48
Socket(s):                               2
Stepping:                                0
Frequency boost:                         enabled
CPU(s) scaling MHz:                      60%
CPU max MHz:                             2600.0000
CPU min MHz:                             1500.0000
BogoMIPS:                                5199.88
Flags:                                   fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 ht syscall nx mmxext fxsr_opt pdpe1gb rdtscp lm constant_tsc rep_good nopl nonstop_tsc cpuid extd_apicid aperfmperf rapl pni pclmulqdq monitor ssse3 fma cx16 sse4_1 sse4_2 movbe popcnt aes xsave avx f16c rdrand lahf_lm cmp_legacy svm extapic cr8_legacy abm sse4a misalignsse 3dnowprefetch osvw ibs skinit wdt tce topoext perfctr_core perfctr_nb bpext perfctr_llc mwaitx cpb cat_l3 cdp_l3 hw_pstate ssbd mba ibrs ibpb stibp vmmcall fsgsbase bmi1 avx2 smep bmi2 cqm rdt_a rdseed adx smap clflushopt clwb sha_ni xsaveopt xsavec xgetbv1 xsaves cqm_llc cqm_occup_llc cqm_mbm_total cqm_mbm_local clzero irperf xsaveerptr rdpru wbnoinvd arat npt lbrv svm_lock nrip_save tsc_scale vmcb_clean flushbyasid decodeassists pausefilter pfthreshold avic v_vmsave_vmload vgif v_spec_ctrl umip rdpid overflow_recov succor smca sev sev_es ibpb_exit_to_user
Virtualization:                          AMD-V
L1d cache:                               3 MiB (96 instances)
L1i cache:                               3 MiB (96 instances)
L2 cache:                                48 MiB (96 instances)
L3 cache:                                384 MiB (24 instances)
NUMA node(s):                            2
NUMA node0 CPU(s):                       0-47
NUMA node1 CPU(s):                       48-95
Vulnerability Gather data sampling:      Not affected
Vulnerability Indirect target selection: Not affected
Vulnerability Itlb multihit:             Not affected
Vulnerability L1tf:                      Not affected
Vulnerability Mds:                       Not affected
Vulnerability Meltdown:                  Not affected
Vulnerability Mmio stale data:           Not affected
Vulnerability Reg file data sampling:    Not affected
Vulnerability Retbleed:                  Mitigation; untrained return thunk; SMT disabled
Vulnerability Spec rstack overflow:      Mitigation; SMT disabled
Vulnerability Spec store bypass:         Mitigation; Speculative Store Bypass disabled via prctl
Vulnerability Spectre v1:                Mitigation; usercopy/swapgs barriers and __user pointer sanitization
Vulnerability Spectre v2:                Mitigation; Retpolines; IBPB conditional; STIBP disabled; RSB filling; PBRSB-eIBRS Not affected; BHI Not affected
Vulnerability Srbds:                     Not affected
Vulnerability Tsa:                       Not affected
Vulnerability Tsx async abort:           Not affected
Vulnerability Vmscape:                   Mitigation; IBPB before exit to userspace

==============================
Versions of relevant libraries
==============================
[pip3] conch-triton-kernels==1.2.1
[pip3] numpy==2.3.5
[pip3] onnx==1.22.0
[pip3] onnx-ir==0.2.1
[pip3] onnxscript==0.7.1
[pip3] onnxslim==0.1.94
[pip3] pyzmq==27.1.0
[pip3] torch==2.11.0+rocm7.2
[pip3] torch_c_dlpack_ext==0.1.5
[pip3] torchaudio==2.11.0+rocm7.2
[pip3] torchvision==0.26.0+rocm7.2
[pip3] transformers==5.14.1
[pip3] triton==3.6.0
[pip3] triton-rocm==3.6.0
[conda] Could not collect

==============================
         vLLM Info
==============================
ROCM Version                 : 7.2.53211-97f5574fe2
vLLM Version                 : 0.1.dev18947+gf9f7a4dc9.d20260722 (git sha: f9f7a4dc9, date: 20260722)
vLLM Build Flags:
  CUDA Archs: Not Set; ROCm: Disabled; XPU: Disabled
GPU Topology:
  ============================ ROCm System Management Interface ============================
================================ Weight between two GPUs =================================
       GPU0         GPU1         
GPU0   0            40           
GPU1   40           0            

================================= Hops between two GPUs ==================================
       GPU0         GPU1         
GPU0   0            2            
GPU1   2            0            

=============================== Link Type between two GPUs ===============================
       GPU0         GPU1         
GPU0   0            PCIE         
GPU1   PCIE         0            

======================================= Numa Nodes =======================================
GPU[0]		: (Topology) Numa Node: 1
GPU[0]		: (Topology) Numa Affinity: 1
GPU[1]		: (Topology) Numa Node: 1
GPU[1]		: (Topology) Numa Affinity: 1
================================== End of ROCm SMI Log ===================================

==============================
     Environment Variables
==============================
VLLM_ROCM_USE_AITER_MOE=0
VLLM_ROCM_USE_AITER_TOPK_SAMPLER=0
VLLM_ROCM_USE_AITER=0
VLLM_ROCM_USE_SKINNY_GEMM=1
VLLM_ROCM_USE_AITER_RMSNORM=0
PYTORCH_ROCM_ARCH=gfx908
VLLM_ROCM_USE_AITER_FP8BMM=0
CUDA_VISIBLE_DEVICES=0
CUDA_VISIBLE_DEVICES=0
PYTORCH_NVML_BASED_CUDA_CHECK=1
TORCHINDUCTOR_COMPILE_THREADS=1
TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor_root


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @github-actions[bot] 2026-07-24T09:22:43Z
CC @hongxiayang @tjtanaa @vllmellm @giuseppegrossi for ROCm-related issue

## comment @hnhyzz 2026-07-25T06:45:33Z
I found it is because of the missing of registrating custom ops. The decode throughpt increases to 15.7 after I registered custom op and fake for the triton w4a16 kernel.

May I create a pull request to correct the bug?