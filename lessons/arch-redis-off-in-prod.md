# Production runs with Redis OFF — the two-tier cache is L1-only in prod

Date: 2026-07-06   Area: arch

**Context**: `SKIP_REDIS_INIT=true` in production (ADR-0004): the two-tier XBRL/ticker
caches run L1 (in-memory, per-instance, LRU) only; Redis exists for local dev via
docker-compose. Consequences: cache state is per-instance and dies on restart; "L2"
code paths are effectively dev-only; anything that assumes cross-instance cache
coherence is wrong (see the per-process-state lesson).

**Rule**: Don't build features that require a shared cache without revisiting ADR-0004
(Memorystore would be the upgrade path). When debugging cache behavior in prod, reason
about L1 per-instance semantics: max 1000 entries, LRU eviction, 24h TTL, stats via
`GET /metrics` → `cache.xbrl_l1`.

**Evidence**: ADR-0004; `backend/app/services/redis_service.py` +
`edgar/xbrl_service.py` two-tier implementation.
