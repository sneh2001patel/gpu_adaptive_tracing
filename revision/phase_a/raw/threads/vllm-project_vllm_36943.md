# vllm-project/vllm#36943: [Bug/Regression]: CPU spikes to 100% on Multi-node (PP=2, TP=8) | Regression starting from v0.12.0
state=closed reason=not_planned created=2026-03-13T00:07:39Z closed=2026-07-15T02:19:02Z labels=['performance', 'stale']
cross-referenced PRs: ['https://github.com/vllm-project/vllm/pull/37743']

## body (@randomkrml)
### Proposal to improve performance

We are observing a severe regression in CPU management when running vLLM in a multi-node setup on OpenShift. While the deployment is perfectly stable on v0.11.0, any version from v0.12.0 up to v0.17.0 triggers complete CPU saturation.

Even under light inference load, the CPU utilization on both nodes spikes to 100%, leading to a rapid decline in throughput and eventual node unresponsiveness. This behavior is consistent across various models using a TP=8, PP=2 topology on 2xH100 nodes via LeaderWorkerSet (LWS).

The fact that the exact same configuration and infrastructure work seamlessly on v0.11.0 strongly suggests a regression introduced in v0.12.0, possibly related to how the distributed backend or the scheduler interacts with OpenShift's resource constraints.

Questions:
Were there specific changes in the Ray/Distributed backend or scheduling logic in v0.12.0 that could cause this busy-wait loop or thread contention?
Are there recommended environment variables or flags to tune Ray/vLLM resource management in hardened environments like OpenShift?

### Report of performance regression

_No response_

### Misc discussion on performance

Infrastructure: OpenShift Container Platform (LWS).
Topology: 2 Nodes, 8xH100 per node.
Config: tensor_parallel_size=8, pipeline_parallel_size=2.
Versions affected: v0.12.0 through v0.17.0.

### Your current environment (if you think it is necessary)

```text
The output of `python collect_env.py`
```


### Before submitting a new issue...

- [x] Make sure you already searched for relevant issues, and asked the chatbot living at the bottom right corner of the [documentation page](https://docs.vllm.ai/en/latest/), which can answer lots of frequently asked questions.

## comment @FocusMode-coder 2026-03-13T00:12:09Z

🚨 NEXA CLIENT DETECTED

CLIENT: randomkrml

BUG:
[Bug/Regression]: CPU spikes to 100% on Multi-node (PP=2, TP=8) | Regression starting from v0.12.0

PRICE: LOW

PAYMENT LINK:
https://buy.stripe.com/3cI9ASa2Pc9AbtofVy0gw06

If you'd like the full working fix, use the link above.

-Luciano


## comment @haosdent 2026-03-13T02:49:55Z
May try the latest version @randomkrml 

## comment @randomkrml 2026-03-15T20:40:51Z
@haosdent I've already tested v0.17.1 and the issue persists.

As noted, this regression started in v0.12.0 (v0.11.0 works fine).

## comment @haosdent 2026-03-16T01:46:31Z
@randomkrml How about the nightly build

## comment @Salamastik 2026-03-16T13:29:27Z
@haosdent I am currently testing the latest Nightly version and will update soon. In the meantime, here is the top output from v0.17.1 when the CPU spikes.

As you can see, the system load is dominated by sy (70%), and the Ray workers are consuming over 2200% CPU each, while the engine stays at ~85%:

Plaintext

%Cpu(s): 0.5 us, 70.0 sy, 13.0 ni, 12.0 id ...
...
  PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
 1245 vllm      35  15  1144.2g   5.8g   1.2g R  2242.0  0.3   ... ray::RayWorkerW
 1288 vllm      35  15  1144.2g   5.8g   1.1g R  2210.5  0.3   ... ray::RayWorkerW
  850 vllm      20  15   257.8g   1.4g   591k R   84.8  0.1   ... vLLM:EngineCor
This massive overhead in System CPU suggests a kernel-level contention or a busy-wait loop in the distributed backend that was introduced after v0.11.0.

## comment @github-actions[bot] 2026-06-15T02:18:06Z
This issue has been automatically marked as stale because it has not had any activity within 90 days. It will be automatically closed if no further activity occurs within 30 days. Leave a comment if you feel this issue should remain open. Thank you!

## comment @github-actions[bot] 2026-07-15T02:19:02Z
This issue has been automatically closed due to inactivity. Please feel free to reopen if you feel it is still relevant. Thank you!