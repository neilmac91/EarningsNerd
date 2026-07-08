# Operations — health, metrics, caches, circuit breaker, admin & runbook

Production operations reference for the Cloud Run backend: monitoring surfaces, cache and
circuit-breaker management, performance tuning, alerting thresholds, admin endpoints, and
the verification-script catalog. Deploy/rollout mechanics live in docs/DEPLOYMENT.md;
local-dev issues in docs/TROUBLESHOOTING.md.

> Moved out of CLAUDE.md in the July 2026 refactor (Wave 3 / M3).

## Health Check & Monitoring Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /health` | Basic health check for load balancers | `{"status": "healthy"}` |
| `GET /health/detailed` | Detailed check with DB + Redis + circuit breaker | See example below |
| `GET /metrics` | Application metrics for monitoring dashboards | See metrics response below |

### Detailed Health Check Response

```json
{
  "status": "healthy",
  "checks": {
    "database": {
      "healthy": true,
      "latency_ms": 2.45
    },
    "redis": {
      "healthy": true,
      "latency_ms": 1.12
    },
    "sec_edgar_circuit": {
      "state": "closed",
      "healthy": true,
      "stats": {
        "total_requests": 1500,
        "success_rate": 98.5,
        "rejected_requests": 0
      }
    }
  },
  "timestamp": 1706454000.123
}
```

### Metrics Endpoint Response

```json
{
  "timestamp": "2024-01-29T12:34:56Z",
  "app": {"name": "EarningsNerd API", "version": "1.0.0", "environment": "production"},
  "circuit_breaker": {"sec_edgar": {"state": "closed", "stats": {...}}},
  "cache": {
    "redis": {"healthy": true, "hit_rate": 84.75, "hits": 1200, "misses": 215},
    "xbrl_l1": {
      "total_entries": 450,
      "valid_entries": 445,
      "max_size": 1000,
      "utilization_percent": 45.0,
      "hits": 3200,
      "misses": 800,
      "hit_rate": 80.0,
      "evictions": 50
    }
  },
  "thread_pool": {"edgar": {"max_workers": 4, "threads_created": 3}},
  "database": {"pool_size": 10, "checked_in": 8, "checked_out": 2}
}
```

**Status codes:**
- `200` with `status: healthy` - All dependencies operational
- `200` with `status: degraded` - Non-critical dependency (Redis) unavailable
- `503` with `status: unhealthy` - Critical dependency (database) unavailable

## Operational Runbook

### Cache Management

**L1 (In-Memory) Cache:**
- Max 1000 entries with LRU eviction
- 24-hour TTL
- Check stats: `GET /metrics` → `cache.xbrl_l1`
- Clear via admin: `POST /api/admin/xbrl/clear-memory-cache`

**L2 (Redis) Cache:**
- Persistent across restarts
- Shared across instances
- Check stats: `GET /metrics` → `cache.redis`
- Clear pattern: Use Redis CLI `SCAN` + `DEL` for bulk deletion

**Cache Pressure Indicators:**
- `l1_utilization_percent > 90%` - Cache is near capacity, expect more evictions
- `l1_evictions` increasing rapidly - High churn, consider increasing `_cache_max_size`
- `l1_hit_rate < 50%` - Poor cache effectiveness, review access patterns
- Look for `cache_eviction` events in logs for structured eviction details

### Circuit Breaker Management

**States:**
- `closed` - Normal operation, all requests pass through
- `open` - Failing fast, rejecting requests (check SEC EDGAR status)
- `half_open` - Testing recovery, limited requests allowed

**Actions:**
- If stuck in `open`: Check SEC EDGAR status, network connectivity
- Manual reset (if needed): Restart application or use admin endpoint
- Check stats: `GET /metrics` → `circuit_breaker.sec_edgar`

### Performance Tuning

**L1 Cache Size:**
```python
# In xbrl_service.py
_cache_max_size = 1000  # Increase for more memory, fewer evictions
```

**Redis Timeouts:**
```python
# In redis_service.py
CACHE_OPERATION_TIMEOUT = 2.0  # Increase if Redis is slow
```

**Thread Pool Size:**
```python
# In edgar/config.py
EDGAR_THREAD_POOL_SIZE = 4  # Increase for more concurrent SEC API calls
```

### Monitoring Alerts (Suggested Thresholds)

| Metric | Warning | Critical |
|--------|---------|----------|
| `cache.xbrl_l1.utilization_percent` | > 80% | > 95% |
| `cache.redis.healthy` | - | `false` |
| `circuit_breaker.sec_edgar.state` | `half_open` | `open` |
| `database.checked_out` | > 8 | = pool_size |

## Request Timeout Configuration

Per-endpoint timeouts configured in `backend/main.py`:

| Endpoint Pattern | Timeout |
|------------------|---------|
| `/api/summaries/` | 120s |
| `/api/filings/` | 60s |
| `/health` | 5s |
| Default | 30s |

Streaming endpoints (`*stream*`, `*/progress`) are excluded from timeout middleware.

## Admin Features

Admin endpoints require `is_admin=True` on the user account. Available at `/api/admin/`:

| Endpoint | Purpose |
|----------|---------|
| `POST /email/test` | Send a test email via Resend (diagnoses email config; defaults to admin's own address) |
| `DELETE /filing/{id}/summary` | Delete summary for a filing |
| `DELETE /filing/{id}/xbrl` | Clear XBRL cache for a filing |
| `DELETE /filing/{id}/reset` | Full reset (summary, XBRL, content cache, progress) |
| `POST /xbrl/clear-memory-cache` | Clear in-memory XBRL cache |
| `GET /xbrl/cache-stats` | View XBRL cache statistics |
| `GET /filings/audit-xbrl` | Audit filings for stale XBRL data |
| `POST /filings/bulk-reset-stale` | Bulk reset stale filings (supports dry_run) |
| `POST /summaries/reset-all` | Bulk delete summaries by form so they regenerate with current prompts; skips saved (bookmarked) rows unless `include_saved=true` (supports dry_run) |
| `POST /summaries/refresh-stale` | Bulk **in-place** refresh of version-stale summaries (below a `schema_version`, or stale vs the current schema+prompt version) via the one orchestrator with `force_regenerate=True`; preserves `summaries.id` so bookmarks survive, keep-better quality gate prevents downgrades, `dry_run` reports the staleness count |

Outside `/api/admin/`, two token/ops refresh endpoints exist for the discovery caches:
`POST /api/hot_filings/refresh` (gated by `X-Admin-Token` = `HOT_FILINGS_REFRESH_TOKEN`;
returns 501 when the token is unset) and `GET /api/trending_tickers/refresh-prices`.

### Verification Scripts

Located in `backend/scripts/`:
- `deploy_check.py` - Pre-deployment validation (env vars, DB, dependencies)
- `validate_db_performance.py` - PostgreSQL performance benchmarking
- `verify_extraction_standalone.py` - Test XBRL extraction against live SEC data
- `verify_extraction_mock.py` - Tests XBRL extraction with mock data
- `verify_startup_config.py` - Detailed startup configuration verification
- `debug_extraction.py` - Debug regex patterns for extraction
- `fix_null_sec_urls.py` - Repair filings with NULL sec_url values (see docs/TROUBLESHOOTING.md)
- `backfill_facts.py` - Backfill the `financial_fact` table from cached/parsed XBRL
- `filing_scan.py` - Scan for new filings on watched companies (alerts pipeline)
- `pregenerate_examples.py` - Pre-generate example summaries (weekly refresh cron)
  - **Keep the recommended filing warm:** the company-page "Recommended" banner now points at a
    company's *most recent* filing of any type (usually a 10-Q), but the precompute path
    (`POST /internal/jobs/precompute` and this cron) defaults to `forms=["10-K"]`. So the A1 warm
    covers the old recommendation, not the new one — a first click on a newly-recommended 10-Q
    generates on demand. To close the gap, include `"10-Q"` in the `forms` list of the weekly
    pregenerate payload (one-line change to the trigger's request body).
- `verify_insider_extraction.py` - Verify Form 4 insider extraction against live SEC data
