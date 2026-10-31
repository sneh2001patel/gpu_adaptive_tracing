# Quiet-evidence isolation and historical provenance — step 034

Completed 2026-10-28 on CPU. No SSH, GPU workload, new capture, classification, reference or calibration. The last remote cleanup/rental observation remains step 033; this step does not recheck rental state.

## Working-source correction

`OwnedLiveActivity.quiet` now persists a separate evidence list for each resolved output directory. Jobs may reuse labels such as `before` and `after` in different directories without inheriting earlier jobs' rows. Multiple quiet phases and deliberate worker resets within one episode/output retain their original nonce, generation, PID, barrier and raw-file records. The output must contain the owned session. Existing evidence from a different activity, unsafe labels and previously used raw filenames are rejected before the RPC or overwrite.

The dictionary remains in memory for the activity lifetime; isolation concerns the saved episode files, rather than discarding intentional same-episode history. The runtime is still serialized by its existing callers. This change does not add a resume/retry mechanism, change request budgets or alter the frozen v2 protocol.

## Tests and regression proof

All **565 CPU tests pass**, including **sixteen new tests**; the focused activity/provenance group passes 33. Six new activity tests exercise distinct job bindings with deliberately reused raw basenames, unchanged earlier outputs, same-episode reset generations, partial failure followed by another job, existing-log refusal, filename reuse, output aliases and invalid labels/destinations. Existing cleanup-failure coverage also passes.

Ten new provenance tests check explicit original-job lookup, preserved input bytes, raw hash tampering, foreign bindings/clocks, conflicting copies, duplicate original tokens, unsafe cross-job paths, orphan historical rows, busy gauges and fresh separate CLI output.

The new multi-job test was additionally run against the exact archived step-032 activity implementation: it fails as expected because the second job contains **eight rows instead of four**. That [expected old-code failure](validation/frozen_regression_reproduction.log) is separate from the passing [current suite](validation/cpu_suite.log). The first reproduction harness patched the current module's HTTP dependency but not the archived module's separate globals; its CPU loopback connection error is retained in [the initial harness log](validation/initial_reproduction_harness_error.log). Forwarding that dependency through the test mock fixes the reproduction harness without modifying archived code or contacting a GPU.

## Immutable live-data index and re-audit

The [separate provenance index](../../hardware/l4_20261028/challenges_v2_quiet_provenance_034/INDEX.json) verifies all **6,142 campaign artifact hashes**, then resolves **544 observed rows** to **64 unique original barriers**. Exactly **480 rows are historical copies**. Each original occurs in its own job and is validated against its original session nonce, generation, PID, clock and UUID. Repeated rows must be identical. Both surrounding metric files resolve to the original job, match their hashes, and show available zero queue/running gauges with valid acquisition/barrier ordering and no outstanding owned client work.

| Family of observed files | Observed rows | Own rows | Historical rows |
|---|---:|---:|---:|
| Four ladder jobs | 40 | 16 | 24 |
| Four pressure/removal jobs | 104 | 16 | 88 |
| Four lull/recurrence jobs | 168 | 16 | 152 |
| Four evidence-gap controls | 232 | 16 | 216 |
| Total | 544 | 64 | 480 |

Each occurrence records its observed file/row position and original job. Each unique barrier records its original file/row position, complete binding, canonical row hash and both original raw paths/hashes. This is an offline provenance aid; it does not make the historical per-job files self-contained or repair their stored paths.

The step-033 independent audit is rerun with its report write intercepted and compared byte-for-byte to the existing report. The comparison passes; the original report and campaign remain untouched. The two archived snapshots verify **171/184 entries**, both descriptors/backups retain their original hashes, and all **362 v1 failed-run artifacts** verify with the outcome still failed. [Preservation record](validation/PRESERVATION.json); [audit log](validation/live_campaign_reaudit.log).

Current working source correctly fails validation against the old v2 freeze at `revision/feasibility/activity.py`. No new engineering archive or hardware-validation claim is created. [Working source manifest](validation/SOURCE_MANIFEST.json) identifies this CPU-tested source version; any later live execution must use a newly prepared engineering snapshot.

To index another unchanged campaign, use a fresh destination outside its result directory:

```bash
python3 -m revision.scripts.audit_quiet_provenance \
  --campaign revision/hardware/l4_20261028/challenges_v2_001 \
  --output /tmp/new_quiet_provenance_index
```

## Next — step 035, CPU-only

Audit the saved scheduler wait bounds and feature cohort semantics: quantify bracket widths, boundary ambiguities, unfinished/censored requests, receipt readiness and available sample counts by window. Keep measured host scheduler bounds separate from GPU execution phases and diagnostic truth. Expose unset scientific precision/mismatch/reference criteria and prepare independent assessment instructions. These development observations cannot retrospectively supply held-out confirmation thresholds, labels or calibration. Future hardware confirmation of the source correction remains pending; the next offline audit does not require the GPU.
