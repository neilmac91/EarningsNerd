# Preserve SEC pacing and distinguish selected breaker coverage from limiter-only paths

Date: 2026-07-06   Area: sec

**Context**: S4 found the resilience machinery existed but was bypassed on the primary
data path: 15 edgartools call sites had timeouts but no breaker, and raw httpx sec.gov
calls skipped the rate limiter. Wiring it on taught two calibration rules: (1) the
breaker's trip set is network-shaped (`EdgarNetworkError`, timeouts, rate-limit errors) so
business errors (404s, parse failures) never open it; (2) heavy LOCAL parse operations
(big-filing section/statement parsing legitimately runs 20–40s) must NOT feed the shared
breaker — five slow filings in a row would open the circuit and fail-fast every SEC call
while SEC is healthy. Also: full retry/backoff ladders (Retry-After up to 120s) belong to
background jobs; user-facing cold paths get a bounded single attempt + stale-cache
fallback.

**Rule**: New SEC fetches use `run_with_circuit_breaker` (edgartools) or
`sec_rate_limiter.execute*` (raw HTTP) — never bare httpx to sec.gov. CPU-bound parse
steps stay on plain `run_in_executor_with_timeout` with a comment saying why they are
breaker-exempt. Choose `execute()` (single token wait) on user-facing paths and
`execute_with_backoff` only where minutes of latency is acceptable.

**Existing paths**: `SECFullTextSearchClient` in `backend/app/integrations/sec_api.py`
and `_fetch_companyfacts_async` in `backend/app/services/facts_service.py` (also used by its
sync bridge) use direct httpx through shared limiter/backoff without the breaker. The in-layer
`edgar/xbrl_service.py` companyfacts fallback uses `execute()` without the breaker. Ticker and
filing-document fetches in `edgar/compat.py` carry both limiter and breaker. Primary XBRL/local
parsing retains plain timeouts so CPU cost does not become a false SEC-health failure.
These existing paths do not authorize new unpaced SEC requests.

**Gate scope**: `test_sec_gov_importers_allowlist.py` bounds `sec.gov` literal locations and
keeps pure URL-builder/Settings exemptions free of HTTP imports. It does not trace dynamic URL
helpers or prove every request's limiter/breaker routing. The legacy manual diagnostic
`backend/scripts/verify_extraction_standalone.py` performs raw SEC requests outside this app-only
gate and without the shared limiter/breaker; it is not evidence of application coverage or
authorization to run it. Do not copy that diagnostic transport into application paths.

**Evidence**: PR #551 (S4) + its review; `backend/app/services/edgar/async_executor.py`,
`circuit_breaker.py` (trip_exceptions), `compat.py` (bounded user-facing fetch).
