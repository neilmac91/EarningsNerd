# Redis is OFF in production — the two-tier cache runs L1 (in-memory) only

**Area:** backend · **Date:** 2026-07-06

Prod runs with `SKIP_REDIS_INIT=true` (ADR-0004). The two-tier cache degrades to L1 (in-memory, per-instance, LRU) only; Redis exists solely for local dev via docker-compose. Rate limiting and in-flight dedup are in-memory too.

**Rule:** never assume Redis (or any cross-instance shared state) in prod. Anything that must be shared across Cloud Run instances needs the DB, not the cache. Cache helpers must degrade gracefully when Redis is absent — that IS the prod path, not an edge case.
