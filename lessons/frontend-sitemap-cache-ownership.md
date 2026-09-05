# Cache the rendered sitemap once and fetch a fresh upstream body when regenerating

Date: 2026-09-05   Area: frontend

**Context**: The sitemap route and its backend fetch both used hourly Next caches. A route
regeneration could consume a stale fetch response instead of the backend's latest sitemap.

**Rule**: Give the rendered sitemap an explicit hourly static-route cache and bypass Next's
fetch Data Cache. Pin both the route policy and fresh upstream consumption, and verify the
production build still records hourly sitemap revalidation. Keep the outage fallback complete.

**Evidence**: `frontend/app/sitemap.ts`, `frontend/tests/unit/sitemap.spec.ts`, and
`frontend/tests/e2e/sitemap-cache.spec.ts` (PR #693). Removing `force-static` makes the production
build dynamic and fails the ISR manifest assertion; restoring fetch caching fails the
fresh-fetch policy assertion. Next's metadata handler sets its own browser Cache-Control header,
so verify the server cache through the prerender manifest and an observed `x-nextjs-cache: HIT`.
