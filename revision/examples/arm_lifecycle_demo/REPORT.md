# CPU experiment-arm lifecycle validation

All values below are CPU-fixture mechanics; no GPU, diagnostic accuracy, profiler overhead or hardware baseline is established.

| Arm | Target capture mode | Fresh cheap sampler | Captures | Server quiet/reset passed | Owned group absent |
|---|---|---|---:|---|---|
| full_horizon_reference | continuous | True | 1 | True | True |
| hybrid_stop | bounded | True | 3 | True | True |
| repeated_fixed_burst | bounded | True | 3 | True | True |
| stability_stop | bounded | True | 3 | True | True |
| counter_recovery_stop | bounded | True | 3 | True | True |
| cheap_only | disabled | True | 0 | True | True |
| no_profiler | disabled | False | 0 | True | True |
| fixed_burst | bounded | True | 1 | True | True |

All eight arms reuse offered-file SHA-256 `e762785e3913108cacdeae4a058538ce4508317a473d9129b7caa5535a2009ea` and the same comparison contract.

Four injected failures are retained: missing server metric, persistent busy status, stale reset acknowledgement and startup failure. Each fails its gate and still closes its owned process group.

Source/report fingerprints, raw playback and status observations, generation/nonce checks, reset acknowledgements and timing scopes are retained. Capture-control spans include RPC/report latency; active GPU time and persisted total lifecycle remain unknown. Policy diagnoses deliberately abstain.

Next: durable blinded reference locking/scoring and additional interval instrumentation; validate the corresponding real GPU session/queue/reset semantics before confirmation.
