# Step-027 scheduler events — CPU fixtures and prospective preparation

[Fixture summary](fixture_001/SUMMARY.json): five explicitly synthetic cases. Complete batch history yields two bounded delays; boundary uncertainty yields no eligible value and retains ambiguous IDs; a two-event budget drops four later records and invalidates history; pending/aborted-before-schedule requests do not become zero wait; foreign scope is rejected. All live-validation flags are false.

[Prospective specification](prospective_001/SPECIFICATION.json) pins actual corpus/source-manifest hashes, engineering-only limits and bounded rate/removal/lull/unresolved controls. It is not executable and enables no reference export, fitting or study freeze. Eight-request source commissioning must precede challenging cases. Scientific equivalence/precision/repetition limits remain unset.

All 484 CPU tests pass, including 17 new checks. The actual subclass wrappers are tested against fake source modules, not a running GPU scheduler. Same-host temporary-file probe tests validate bracket/identity and timeout cleanup. Installed-package source files were copied read-only from the authorized host; no package or serving defaults were modified and no GPU workload was launched.

Existing measured wait/phase fields and the classifier remain unchanged/unavailable. Actual GPU plugin startup, engine/client ID mapping, effective cache flags, snapshot coverage and observer perturbation remain unvalidated. See [the operating contract](../../protocol/SERVER_EVENT_INSTRUMENTATION.md).
