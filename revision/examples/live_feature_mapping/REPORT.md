# Step-023 mapping checks — CPU only

[Saved L4 mapping audit](saved_l4_audit/AUDIT.json): 12 previously collected raw receipts from step 022 map to queue samples with zero waiting requests. Each saved raw hash and worker/session/generation binding was checked. Histograms remain diagnostic only. This audit creates no feature windows, calibration data or online decisions and launches no GPU activity.

[Calibration preparation](calibration_preparation/PREPARATION.json): 18 planned collection jobs across nine feature/full-trace pairs; zero observed calibration windows. Intended interventions remain evaluator metadata rather than reference truth. Launch, fitting, calibration and study readiness remain false.

CPU tests separately exercise a real local HTTP metrics response, raw persistence/tampering, malformed/missing data, future/foreign/restarted scope, cancellation, late/outside/duplicate receipts, measured client usage/GPU-sample plumbing, bridge provenance and persistent abstention. Synthetic records remain synthetic. No new GPU experiment or calibrated diagnosis is claimed.
