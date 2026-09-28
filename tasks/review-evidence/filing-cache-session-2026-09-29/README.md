# Completed filing-list sessions: local evidence

Eight simultaneous cached filing-list requests can exhaust the four-slot synchronous pool before FastAPI's thread-pool dependency finalizers return the first four connections. The async event loop then waits on that same pool. The fix materializes response DTOs and closes each completed cached/live/fallback read synchronously. It preserves the cache, background refresh, pool limits, upstream transports and response contract.

Runtime and test bytes were verified at `de0dcdc706ad4f19616c34dab9d4ec3cc12f4e0a`, based on verified main `4db8f46a`. See [machine-readable local proof](local-proof.json), the [regression](../../../backend/tests/unit/test_cached_filings_pool_lifetime.py) and the [bounded lesson](../../../lessons/ops-release-cached-filing-reads-before-yield.md).

## Evidence and refutations

The first attempt to disprove the finding used the complete `main.app` middleware and genuine `get_db` dependency instead of the initial composed-router app. Eight requests still stalled for about 40 seconds; all four leases stayed checked out while successive ten-second pool waits blocked dependency cleanup.

The second used a real local Uvicorn HTTP server over a private Unix socket, with server and client event loops separated. There was no request-start barrier. All eight requests missed the unchanged 15-second client deadline. The source was workflow commit `ed2527f0`, whose backend tree is identical to base `4db8f46a`. After the fix, the same HTTP mode completed eight of eight with status 200 in 32.512–42.448 milliseconds locally; observed checked-out high water was one and longest lease was 4.746 milliseconds. These timings are local observations, not Cloud Run latency targets.

A separate full-app mixed exercise completed all 44 HTTP requests. It combined coverage leaders/followers, company misses, controlled SEC/quote waits and competing cached reads. Actual normalization persisted 54 facts from the repository's synthetic fixture. Warm coverage reused its stamp without another facts fetch; failed upstream responses left the missing stamp unchanged. The pool high water reached four. Controlled SEC and quote waits held zero checked-out connections at the measured barrier. No external socket attempt was observed; all private PostgreSQL clusters and HTTP servers were stopped.

The durable regression uses a real four-slot SQLite QueuePool with a short pool timeout and the full app/genuine dependency, without mocked sessions or a request-start barrier. The longer standalone PostgreSQL exercise adds actual database and HTTP-server evidence.

## Required gates

On the committed runtime bytes:

```text
ruff check .: All checks passed!
bandit -r app -ll: No issues identified. [no medium/high severity findings]
python -m pytest -rs:
3808 passed, 39 skipped, 2 deselected, 40 warnings in 162.66s (0:02:42)
```

The 39 skipped tests require their separate opt-in PostgreSQL transaction databases. The two deselected performance tests are excluded by the repository's normal pytest configuration. Neither is counted as executed here. Existing tests, including locked contracts, are byte-identical to base; only one new regression was added.

Exactly one committed-state mutation removed the guarded fix by restoring the pre-fix route. The burst returned four 200s then four 500s and failed. The exact committed route bytes were restored:

```text
FAILED tests/unit/test_cached_filings_pool_lifetime.py::test_cached_filings_burst_exceeding_pool_finishes_without_upstream
1 failed, 17 warnings in 10.55s
1 passed, 17 warnings in 5.79s
```

## Review and limits

Correctness review traced all cached/live/error/fallback branches: DTOs are complete before close, and subsequent cache/backfill choices use already captured scalar identities. The coordinating independent reviewer found no blocker. Rules-and-brief review found no change to generation, entitlements, migrations, SEC ownership, configuration, or locked contracts. Tests-and-gates review binds the mutation and full gate above to the unchanged source hashes. Exact-head hosted review/checks and serial release remain pending.

This closes a demonstrated filing-list session-lifetime defect. It does not establish a safe beta cohort size, production throughput, fleet reserve, effective worker count, rollout overlap, shared SEC egress/rate admission, live provider capacity or real user usefulness. Sibling route behavior is a separate follow-up investigation. No production load, paid calls, flags, customer messages or invitations occurred in this local measurement.

Private detailed receipts remain under `outputs/overnight-2026-09-28/capacity/` in the coordinating workspace; hashes are retained here without local connection paths or private database artifacts. The runner was extended between original refutation modes; historical runner byte snapshots were not retained. Backend source commits and clean backend trees were checked per run.
