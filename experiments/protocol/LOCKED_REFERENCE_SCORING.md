# Locked references and offline scoring — step 017

Implemented on CPU with synthetic references and hand-authored candidate predictions. No GPU use, fitted diagnosis, human adjudication or empirical stopping result is added.

## Reference-only locking

`experiments.evaluation.reference_store.ReferenceStore.lock` accepts adjudicated reference records, artifact root, a versioned rubric and a same-domain evaluator clock. It accepts no predictions. It verifies artifact bytes, rubric membership, run/provenance/clock identity, nonoverlapping reference intervals and adjudication time. Incoming records must be unlocked; the lock operation assigns their shared lock time.

Artifacts, rubric and stamped records are copied into `blobs/<sha256>`; the manifest in `locks/<sha256>` is committed last. Files are flushed/fsynced, made read-only and published through an exclusive atomic hard link; namespace directories are fsynced. Existing objects must verify before reuse. Corrections create a new digest and preserve old locks. Raw evidence is streamed in bounded memory, with a 2 GiB per-file limit; metadata JSON is limited to 32 MiB. Unsupported sizes fail explicitly.

Retain the manifest digest outside the store (the CLI writes a new exclusive `LOCK_ANCHOR.json`). Loading requires this explicit anchor and rechecks manifest, rubric, records and every artifact. Original files can later disappear or change without changing the snapshot. There is no automatic latest-reference selection. A retained anchor detects changed bytes; read-only permissions do not prevent an administrator from modifying files or replacing both data and the retained anchor.

Assessor/blinding declarations and corroborating channels are retained, not independently proven by storage. The code cannot establish causal truth, human blinding or clock authority. Locking before loading predictions in this tool does not prove an assessor has never seen predictions elsewhere. The demo declares itself unblinded with synthetic assessor limitations.

## Offline join and denominators

`experiments.evaluation.scoring.evaluate_files` validates the lock before opening prediction inputs. A join requires matching run, provenance and clock domain, with join time at or after locking. The API expects an actual same-domain clock; cross-process host/domain binding still requires validation. The CLI deliberately accepts synthetic provenance and explicit synthetic clocks only.

Inputs include a strict initial-stop record per logged activated episode and a hashed controller snapshot wrapped as `{run_id, controller}`. Episode IDs must agree with unique activation events; missing, duplicate or extra initial stops fail. Thus failure, unknown, budget exhaustion and horizon-censored rows cannot be silently dropped. This denominator is conditional on the supplied controller snapshot; it is not a complete incident census or evidence of detection recall.

Each initial-stop row retains policy, episode/evidence identity, acquisition/availability/decision times, terminal reason/status, label, explicit asserted causes and classifier/mapping versions. These evaluator assertions do not enter classifier inputs. No automatic conversion from a workload name or generic `mixed` label to a supported cause set is performed. A long-prompt label alone does not establish prefill-dominated service. Step 018 adds [offline export from finalized controllers](INTERVAL_METRICS_AND_EXPORT.md), with no cause mapping. Calibrated cause mapping and live collection binding remain pending.

Match the evidence acquisition interval to one fully containing locked reference interval. Decision timestamps do not select a more favorable label. Transitions, uncovered gaps, unresolved references and assertions outside an incomplete reference's known cause set remain reference-unavailable. An explicit contradiction can establish an unsupported assertion even when the overall reference is incomplete.

| Outcome | Meaning |
|---|---|
| `supported_complete` | Explicit asserted causes match a complete supported cause set |
| `supported_partial` | Assertions cover a supported subset without unsupported assertions; completeness is not established |
| `unsupported_concrete` | At least one assertion contradicts the reference, or lies outside a declared complete set |
| `unresolved` | No supported cause assertion, including unknown, generic unmapped mixed, or failed diagnosis |
| `reference_unavailable` | Available reference cannot adjudicate this acquisition/assertion |

Unknown is never credited as a correct healthy diagnosis. Stable unsupported, stable incomplete and stable unadjudicable counts are separate. All-episode and reference-adjudicable agreement denominators are both retained; zero denominators produce null fractions. Budget/failure/censoring reason/status counts remain separate from diagnosis outcomes. Input, lock and scorer hashes accompany the output.

## Run the CPU example

```bash
python3 -m experiments.scripts.demo_reference_scoring --output /tmp/new_reference_scoring_demo
python3 -m experiments.scripts.reference_eval lock --help
python3 -m experiments.scripts.reference_eval score --help
python3 -m unittest experiments.tests.test_locked_reference_scoring -v
```

The demo requires a new directory and writes references/lock before creating prediction inputs. The separate CLI `lock` command accepts `--store`, `--references`, `--artifact-root`, `--rubric`, `--anchor-output`, `--synthetic-clock-ns` and `--clock-domain`. `score` takes `--store`, the retained `--lock-sha256`, `--predictions`, `--controller-snapshot`, a new `--output`, and the same synthetic clock domain with a later join time.

The [saved example](../examples/reference_scoring_demo/REPORT.md) has 12 hand-authored initial stops: 1 complete, 1 partial, 2 unsupported, 3 unresolved and 5 reference-unavailable. This validates scorer counterexamples, not deployed classifier performance. The deployed adapter continues to abstain. No stopping safety, detection recall, operator benefit, profiler cost or empirical novelty is established.

Step 018 implements interval adapters and evaluation export contracts on CPU; scorer v2 explicitly accepts absent acquisition for failed/censored decisions. The saved step-017 v1 scores and source hashes remain historical. Step 019 binds collection/persistence/export to CPU arm runs. Step 020 prepares gated live-feasibility checks and read-only discovery. Next: step 021 needs actual L4 capability discovery. Actual metric semantics, phase attribution, independent reference quality, calibrated diagnoses and GPU feasibility remain required before freezing the study.
