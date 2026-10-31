# Offline scheduler-bound audit — step 035

Completed 2026-10-28 on CPU. No SSH, GPU workload, new capture, online control execution, labels or calibration. [Assessment plan](../../protocol/SCHEDULER_BOUND_ASSESSMENT.md), [full audit](../../hardware/l4_20261028/scheduler_bounds_035/AUDIT.json), [summary](../../hardware/l4_20261028/scheduler_bounds_035/SUMMARY.json), [scientific criteria draft](../../hardware/l4_20261028/scheduler_bounds_035/CRITERIA_DRAFT.json).

## Implementation

`revision.evaluation.scheduler_bound_audit` verifies the complete source manifest against a separately retained digest, checks the raw source snapshot bytes as well as parent receipts, validates source binding/history prefixes and exact final client-ID/clock joins, and reconstructs interval cohorts independently of the existing bounds function. It checks all 96 recorded consumer gates against their original six-window grid, 750 ms engineering grace and owner-lateness handling.

The audit reports raw evidence ready by each deadline separately from consumer-accepted evidence. Withheld raw bounds and final-history state remain offline-only. Missing/late evidence, empty cohorts, unscheduled/aborted lifecycles, crossing brackets and unsupported GPU phases stay explicit. A CLI writes only a fresh separate output directory and requires the retained campaign-manifest digest.

## Findings

All **6,142 original artifact hashes** verify. The ten source-enabled jobs contribute **ninety probes and 958 complete case-request lifecycles**; warmups are excluded from precision statistics. Across sixty source-enabled windows there are **54 accepted bound windows/798 observations** and **six withheld windows/160 offline-only observations**. The 36 source-disabled windows remain unresolved. No new diagnosis is emitted.

| Observation | Result | Meaning |
|---|---:|---|
| Wait-bound width, median / sample p95 / max | 0.2362 / 0.3252 / 0.7692 ms | Bracket uncertainty; scientific target remains unset |
| Source probe round trip, max | 314.876 ms | Receipt latency, not serving observer overhead |
| Window end to ready receipt, max | 316.594 ms | All sixty raw histories arrive within the existing grace |
| Minimum receipt margin before deadline | 433.406 ms | Engineering readiness only |
| Scheduling vs client-admission cohort mismatch | 40/60 windows | Not an admission-cohort wait metric |
| Scheduling vs client-completion cohort mismatch | 52/60 windows | Not a completion-cohort histogram substitute |
| Raw cohorts below twenty / empty | 32/60 / 8/60 | `bounds_available` does not establish percentile precision |
| Scheduling-bracket boundary ambiguities | 0 observed | Future cases still preserve this category |
| Unscheduled occurrences at probe / window end | 147 / 148 | Observation times are not interchangeable |
| Definitely unfinished source occurrences at window ends | 622 | Retrospective intermediate state; final case lifecycles all complete |

The one pending-count disagreement is request `cmpl-v2-unresolved_source_gap_control-r3-0059-0` at the first withheld control's thirty-second boundary. It is unscheduled at that boundary and scheduled by the later probe. The audit preserves both scopes and does not repair the original consumer result. Counts summed over windows are occurrences, not unique failed/censored requests.

Fourteen scientific limits and all assessor entries remain null. The candidate construct is a host scheduling-decision proxy with interval uncertainty. Existing `request_wait_p95_ms` mapping and exclusive GPU phase attribution remain unsupported. The draft requires independent feature/reference separation, scientific precision/coverage/repetition criteria and adjudication before calibration.

## Validation and preservation

Synthetic tests cover interval clipping, half-open boundaries, empty percentiles, unscheduled/aborted states, cohort mismatch, late/withheld receipts, owner deadlines, retrospective pending reconstruction, foreign bindings, fixed-gate tampering, pinned-manifest changes and unsafe paths. These fixtures are CPU development tests, not hardware baselines or diagnostic truth. Test counts and preservation fingerprints are recorded in [validation/CHECKS.json](validation/CHECKS.json).

All **579 CPU tests pass**, including **fourteen new audit tests**; the focused audit/event group passes 31. The first suite exposed an older export fixture's short observation window (350 ms horizon/15 ms grace), with a separate isolated failure retained. That fixture now uses a one-second horizon, 100 ms window/grace, 300 ms drain/sample timeout and all original assertions. The next suite exposed a second older reset fixture whose 200 ms fake work could finish before the check. Its fake work now lasts one second, with the original 30 ms quiet deadline, all reset/generation assertions and an added explicit busy-state assertion. Both failed full logs, isolated/corrected checks and the final passing suite remain saved. No live GPU guard or runtime stopping/collection policy is changed by these CPU fixture adjustments.

The original step-033 campaign, prior audits, provenance index and archived source/backups remain unchanged. An initial derived audit is retained at `scheduler_bounds_035_initial`; the final separate output adds request-ID-level pending comparisons and the criteria draft. Neither output changes source evidence. No new engineering archive is created, and hardware confirmation of the step-034 runtime fix remains pending.

To repeat into a fresh destination:

```bash
python3 -m revision.scripts.audit_scheduler_bounds \
  --campaign revision/hardware/l4_20261028/challenges_v2_001 \
  --expected-manifest-sha256 d7243e5159c79fc0e704dcf693453a44af0393e25cda924cedb6d40f37f121db \
  --output /tmp/new_scheduler_bound_audit
```

Next step 036 implements the criterion-completion and independent-assessment worksheet contract on CPU. Scientific choices and actual assessor input remain pending; no references or calibration are automatically created.
