# Owned challenge runner — CPU validation

All **531 CPU tests pass** (twenty new); [full log](validation/cpu_suite.log), [51 focused checks](validation/focused.log), [audit fingerprints](validation/CHECKS.json).

[Saved scaled episodes](fixture_001/RESULT.json) run the actual episode controller through an explicit CPU test transport, with 120 ms horizons. Collector-on/off episodes succeed, and a bad-response-ID episode fails as intended. Every fake owned target closes with no active requests. The on case uses five event probes and retains a withheld consumer window; the off case makes zero event RPCs. All **91 artifact hashes** verify. These are synthetic fixtures with no live GPU validation or diagnostic references.

The [engineering source snapshot](snapshot_001/FREEZE.json) and [archive](snapshot_001/source_step030.tar.gz) bind 171 source/input/protocol/test-log entries and twelve installed vLLM source pins. The launcher rejects changed source/packet hashes before starting a server. This engineering snapshot does not freeze the scientific protocol or establish live behavior. No GPU challenge job has executed.

[Execution contract](../../protocol/CHALLENGE_EXECUTION.md) and [step report](../../progress/030_owned_concurrent_challenge_runner.md) describe deadlines, unavailable evidence, cancellation/drain accounting, actual-worker configuration receipts and the bounded live handoff. Next step 031 deploys the snapshot and audits actual L4 campaign outcomes.
