# The SEC 10 req/s limit is per-IP / per-process, not global — N instances multiply it

**Area:** edgar-data · **Date:** 2026-07-06

The `sec_rate_limiter` (token bucket, 10 req/s) is an in-memory, per-process limiter. With `--max-instances=N` on Cloud Run plus the separate cron jobs, the aggregate SEC request rate is up to N× the per-process cap. An IP ban from SEC takes the product down.

**Rule:** treat the SEC cap as per-process and bound the fleet — pin `--max-instances` (in `ci.yml`, not just the runbook) so the aggregate can't silently drift past 10 req/s. All sec.gov traffic goes through the edgar service layer (limiter + breaker); never raw httpx to sec.gov outside it.
