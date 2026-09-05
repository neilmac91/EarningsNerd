# Cache the rendered sitemap once and fetch a fresh upstream body when regenerating

Date: 2026-09-05   Area: frontend

**Context**: The sitemap route and its backend fetch both used hourly Next caches. A route
regeneration could consume a stale fetch response instead of the backend's latest sitemap.

**Rule**: Give the rendered sitemap an explicit hourly static-route cache and bypass Next's
fetch Data Cache. Pin both the route policy and fresh upstream consumption, and verify the
production build still records hourly sitemap revalidation. Keep the outage fallback complete.

**Evidence**: `frontend/app/sitemap.ts`; fresh-response regression, cache-policy gate and
production build evidence must be present before this draft leaves review.
