# ADR 0004 — Run Redis off in production (L1 in-memory cache only)

- **Status:** Accepted
- **Deciders:** EarningsNerd maintainers

## Context

EarningsNerd uses a **two-tier cache** for expensive SEC/XBRL data:

- **L1** — an in-memory LRU cache (max ~1000 entries, 24h TTL, `asyncio.Lock`-protected)
  inside the process.
- **L2** — Redis, for persistence across restarts and sharing across instances.

The cache layer is written to **degrade gracefully**: on any Redis/network failure it falls
back to (possibly stale) L1, and all cache operations have a 2s timeout so a slow or absent
Redis can never hang a request.

For a pre-launch product on Cloud Run, standing up and paying for a managed Redis
(Memorystore) — plus wiring VPC connectivity from the Cloud Run service — is real cost and
operational surface for a workload that currently runs at low concurrency, often on a single
scaled instance.

## Decision

**Disable Redis in production** and run the cache **L1-only**:

- Production sets `SKIP_REDIS_INIT=true` on the Cloud Run service. The two-tier cache
  therefore operates with L1 (in-memory) only.
- Redis remains a **local-development** dependency via `docker-compose` (and is used by the
  L2 paths and their tests there).
- `SKIP_REDIS_INIT` is also forced `true` in the test suite (`conftest.py`) so tests never
  require a live Redis.

## Consequences

**Positive**
- No Memorystore cost, no VPC connector, less production surface to operate and secure.
- The graceful-degradation design means "no Redis" is an already-tested, first-class mode,
  not a hack.
- Test stability: no external cache dependency in CI.

**Negative / costs**
- **No cross-instance cache sharing and no cache persistence across restarts/deploys** in
  production. Each instance warms its own L1; a deploy or scale event starts cold.
- Cache hit rates are bounded by per-instance L1 size and lifetime. At higher concurrency
  this becomes a reason to revisit the decision.

## When to revisit

Add Memorystore (flip `SKIP_REDIS_INIT=false` and wire connectivity) if any of:
- the service routinely runs **multiple instances** and cold L1 caches cause redundant SEC
  fetches / rate-limit pressure, or
- L1 eviction churn is high (`cache.xbrl_l1.utilization_percent` consistently > 80–95% in
  `/metrics`), or
- deploy-time cold caches measurably hurt first-request latency for users.
