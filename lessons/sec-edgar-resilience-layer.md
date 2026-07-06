# All SEC/EDGAR access goes through the edgar layer: limiter + circuit breaker + timeout — and keep local-parse timeouts out of the breaker

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

**Evidence**: PR #551 (S4) + its review; `backend/app/services/edgar/async_executor.py`,
`circuit_breaker.py` (trip_exceptions), `compat.py` (bounded user-facing fetch).
