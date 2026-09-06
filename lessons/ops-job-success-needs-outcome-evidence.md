# A returned job function is not proof that its work succeeded

Date: 2026-09-05   Area: ops / data integrity

**Context**: Filing scans, calendar refreshes and pregeneration caught provider or per-item
errors and returned normally. Recording a successful heartbeat only from normal return would
have refreshed last-success even when work failed. Notable also caught errors after its first
pagination page; Alpha Vantage degraded HTTP and throttling responses to empty data.

**Rule**: Preserve partial work but expose numeric failure counters at the catch site. A job
wrapper persists the outcome in an independent transaction and fails the execution when work
failed. Dry runs and maintenance overrides have separate outcomes/identities and cannot refresh
a scheduled job's last-success. Missing runs stay visible. Provider adapters can preserve existing
best-effort callers while offering explicit error propagation to the monitored ingestion path.

**Evidence**: `backend/app/services/job_run_service.py`, job script adapters,
`backend/tests/unit/test_job_reporting.py`. The gate injects returned failures in all seven
scheduled modes, later-page failure, provider error payloads and a business rollback; mutation
proofs remove each signal and confirm the tests fail. Report tests pin the last successful
completion separately from the latest attempt and from dry runs.

**Filing-job dry-run correction (2026-09-06):** A no-op email sender still lets the filing
engine write notification logs and advance watermarks. Marking only its heartbeat dry_run does
not make business work read-only. Until a safe preview exists, `scripts/filing_scan.py --dry-run`
(scan and digest) must reject before application imports or any DB, tracker or service call.
The existing `test_job_reporting.py` gate runs both actual CLI modes with import and boundary
spies, plus normal-mode controls. Rejection is not a working preview or historical repair.
