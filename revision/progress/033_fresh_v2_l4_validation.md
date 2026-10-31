# Step 033 — fresh frozen v2 L4 validation

Completed 2026-10-28. [Full report](../hardware/l4_20261028/CHALLENGES_V2_REPORT.md), [audited summary](../hardware/l4_20261028/CHALLENGES_V2_SUMMARY.json), [independent validation](../hardware/l4_20261028/CHALLENGES_V2_VALIDATION.json), [phase observations](../hardware/l4_20261028/CHALLENGES_V2_DELIVERY.json).

## Completed checklist

- [x] Read the instance guide and verify an idle authorized L4, a fresh workspace, free loopback port and the exact frozen local files.
- [x] Deploy the unchanged v2 archive/descriptor and verify 184 entries, twelve installed source pins and eleven full model-file hashes before inference.
- [x] Run the single supervised sixteen-job campaign with no automatic restart, retries, changed rates, relaxed guards or runtime edits.
- [x] Preserve all raw requests/responses, metrics, source receipts, consumer decisions and actual cache-configuration acknowledgements.
- [x] Independently recompute work accounting, selection, consumer deadlines and all eight paired reviews.
- [x] Retain and document the cumulative quiet-log persistence defect; audit original session provenance without changing archived bytes.
- [x] Verify all owned parent/worker groups absent, empty compute list and 0 MiB GPU memory after the service exits.
- [x] Copy the full result/service backup off-host and verify remote/local SHA-256; update the plan and progress.

## Outcome

All **16/16 jobs pass** their frozen engineering checks. **1,536/1,536 scheduled offers** and sixteen warmups succeed: 1,552 attempts against the 1,932 maximum, with zero skips, errors or censors. The first complete off-role ladder selects **3 requests/s**. All roles verify actual prefix caching disabled; sixteen fresh workers are distinct. There are 1,920 queue receipts, ninety real event probes and 2,904 final-history events with zero drops/faults.

The 96 consumer windows include 54 with bounds available, 36 unresolved because collection is off and six unresolved because evidence is deliberately withheld. Complete raw histories remain present in the withheld jobs. All eight pair reviews recompute; 22/48 windows meet the twenty-request minimum, none exceeds the 1.25 symmetric p95 ratio review flag, and the maximum is 1.0528. Six pairs compare collection off/on; two compare consumer complete/withheld with collection enabled on both sides. Equivalence and diagnostic accuracy are not established.

The independent audit verifies 6,142 result hashes, 184 frozen entries, 1,520 runtime source entries, all installed/model pins and 64 unique quiet barriers. All original outputs stay unchanged. Backup SHA-256 is `90fff5eb8864fddf66d23c345a1bec08841469f10a9ae8a291e8bbc7d751aa54`. Independent cleanup at 17:07:48 UTC confirms all sixteen parent/worker groups absent and 0 MiB. The rental remains running.

## Limitation discovered

The unchanged activity object accumulates quiet rows across jobs. Later `quiet_evidence.json` files contain 480 repeated historical rows in total, with filenames relative to their original job. Each job still has four valid barriers of its own. The whole-campaign audit resolves historical rows by original nonce/generation/PID and verifies their original files and identical repeated bytes. A later job copied alone is not self-contained for those rows. The execution and whole-campaign provenance checks pass with this explicit limitation; per-job persistence isolation needs correction before future campaigns. No frozen source or result is patched during this step.

This remains development evidence from one GPU/model/stack and two reversed blocks. Positive queue receipts exist during pressure/recurrence and persist briefly into lull/removal; phase names are not healthy labels. Host scheduler bounds do not measure exclusive GPU phases. No new capture, classifier, reference, calibration or main-study result is created. Earlier 549 passing CPU tests are carried forward for the unchanged runtime; the new deployment/audit helpers receive syntax and actual-artifact checks.

## Next step — 034, CPU-only

1. Keep this campaign, both frozen snapshots and the v1 failure immutable. Create a separate provenance index resolving each quiet row to its original job, binding and raw files.
2. Isolate quiet-evidence persistence by owned episode in working source, preserving same-episode multi-phase evidence and any intentional reset history.
3. Add a multi-job CPU regression using distinct nonce/generation/PID bindings and deliberately reused relative filenames. Require every per-job row/hash to resolve within its own output, with no foreign rows; retain failure/cleanup coverage.
4. Run focused and full CPU checks, re-audit the untouched step-033 data, document the new source version and update progress. Do not silently refreeze or rerun this successful development campaign.
5. Then assess source-bound precision/cohort semantics and specify scientific acceptance/reference criteria separately before calibration or main-study work.

No GPU is needed for step 034. Any later live validation of changed source must use a new engineering snapshot.
