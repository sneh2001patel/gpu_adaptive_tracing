# L4 capability discovery — 2026-10-28

Completed live on the supplied L4; no main matrix, calibration or new profiler capture was run. The pinned model had to be restored because the previous shared-memory cache disappeared after the instance restart. Exact model-file SHA-256 values, including weights, are recorded in [model_files.json](discovery_001/model_files.json); the weights themselves are not copied to this repository.

| Check | Result |
|---|---|
| GPU | NVIDIA L4, `GPU-baa93118-dfa3-1258-be9e-b6051b77c1cb` |
| Stack | vLLM 0.10.2, Torch 2.8.0, Nsight 2026.3.1 |
| Model | Qwen2.5-7B-Instruct revision `a09a35458c702b33eeacc393d103063234e8bc28` |
| Worker | One CUDA worker, PID 1196, matching selected-device compute inventory |
| Inventory / metrics gates | Passed |
| Quiet/reset gate | Unavailable; no owned activity adapter supplied |
| Capture gate | Skipped; zero new captures |
| Two bounded completion probes | Both succeeded; 12 reported prompt tokens and 16 output tokens each |
| Queue / prefill / decode histogram counts | 0 → 1 → 2 across before/after endpoint snapshots |
| Final process cleanup | Parent 978 and worker 1196 absent; owned group absent, no escalation |
| GPU memory after cleanup | 0 MiB; no remaining compute application |
| Study / diagnosis readiness | False |

[Discovery gates](discovery_001/discovery/RESULT.json), [raw receipt hashes](discovery_001/probe_metric_receipts.json), [request completions](discovery_001/probe_requests.json), [metric inspection](discovery_001/probe_capabilities.json), [cleanup checks](post_cleanup_checks.json), [summary](SUMMARY.json).

The live count sequence is consistent with the source-reviewed finished-request cohort. These samples were taken after completed sequential requests; they do not establish the emission instant under backlog, a request-admission cohort, clock mapping, exclusive GPU phase attribution or sufficient diagnostic evidence. No latency comparison is inferred from two requests. The classifier remains uncalibrated and abstaining.

The server ran as an isolated one-shot supervisor service, with a foreground owner and its own serving process group on local port 8011. Existing pilot directories and management services were preserved. The read-only discovery component did not mutate the server; its outer wrapper submitted the two declared bounded request probes and closed its own process group afterward. The rental instance itself remains running.

All 34 recorded artifact hash entries verify locally against the copied bytes. Source fingerprints match [the exact deployed archive](deployment/source_step021_initial.tar.gz). The current local launcher additionally handles transient host process-group visibility denial during cleanup; this guard was added/tested after deployment. The deployed discovery inspector and serving code are unchanged. Hardware results retain their original source fingerprint rather than being relabeled with the later code.

All 380 CPU tests pass, including five new wrapper ownership/persistence checks. The initial local test failure on transient group visibility is retained; the corrected guard treats denied visibility as unknown, retries within bounds and never reports unknown as absence. Production sampler semantics and historical experiment outputs are unchanged.

Next: implement/validate the owned worker barrier and fresh-process reset adapter, resolve actual cohort/clock feature contracts, then run one bounded Nsight capture/readiness/serving-continuation pilot before calibration or the revised study matrix.
