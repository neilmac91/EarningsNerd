# In-memory state is per-process — count every Cloud Run instance and job before trusting it

Date: 2026-07-06   Area: arch

**Context**: Rate limiters, the XBRL L1 cache, in-flight dedup maps
(`summary_pipeline._inflight_generations`, `facts_service._inflight_syncs`), and freshness
stamps are module-level Python state. Production is Cloud Run: the API service
(max-instances pinned, see docs/DEPLOYMENT.md) PLUS several independent job processes —
each carries its OWN copy. The dangerous case is the SEC rate limiter: SEC's fair-access
cap is ~10 req/s PER IP and an IP ban takes the product down, but the token bucket is
per-process, so aggregate SEC traffic = (instances + concurrently-running jobs) × the
per-process budget.

**Rule**: Before relying on any module-level counter/lock/cache for correctness or an
external quota, enumerate who else runs the same code (service instances × Cloud Run
jobs). All sec.gov traffic must go through the edgar service layer (shared
`sec_rate_limiter` + circuit breaker) — never raw httpx to sec.gov outside it — and new
SEC-calling jobs must be counted against the aggregate budget. Per-process dedup is a
best-effort optimization; correctness must come from DB constraints (e.g.
`Summary.filing_id` UNIQUE handles the cross-instance double-insert race).

**Evidence**: `backend/app/services/sec_rate_limiter.py` (per-process token bucket);
S4 hardening (PR #551) routing raw calls through the limiter; the
`uq_summaries_filing_id` constraint closing the cross-process race (PR #549).
