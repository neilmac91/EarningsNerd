# Dashboard UX & Network Remediation

Branch: `claude/confident-cannon-ylfw88`

## Root Cause (verified against live prod)
`GET /api/watchlist` and `GET /api/saved-summaries` (plus `POST /api/saved-summaries`,
`POST /api/compare`) are called WITHOUT a trailing slash, but their FastAPI routes are
defined as `@router.get("/")` / `@router.post("/")`. FastAPI 307-redirects to the canonical
trailing-slash URL — but uvicorn behind Cloud Run's TLS proxy ignores `X-Forwarded-Proto`
(`forwarded-allow-ips` defaults to 127.0.0.1), so the redirect `Location` is generated as
`http://` instead of `https://`. A browser on an HTTPS page refuses the cross-origin
redirect to http (mixed-content) → axios reports a bare `Network Error` (status 0) →
client.ts maps it to "Unable to connect to the server." Subscriptions endpoints work
because they hit exact sub-paths and never redirect — which is why only those two cards fail.

## Per-issue verdict
- #3 saved summaries / #4 watchlist: caused directly by the http:// 307.
- #5 retry: NOT broken — correctly wired to refetch(); just re-hits a broken endpoint.
- #1 star: onClick wired, but getWatchlist fails so state never loads; no error feedback.
- #2 manage subscription: reaches backend, but portalMutation has no onError (silent on 400).

## Plan
### A. Eliminate the redirect (fixes #3, #4, #5; unblocks #1)
- [ ] frontend: `getWatchlist` -> `/api/watchlist/`
- [ ] frontend: `getSavedSummaries` -> `/api/saved-summaries/`
- [ ] frontend: `saveSummary` (POST) -> `/api/saved-summaries/`
- [ ] frontend: `compareFilings` (POST) -> `/api/compare/`
- [ ] backend: uvicorn `--proxy-headers --forwarded-allow-ips="*"` in Dockerfile (true root cause)

### B. Premium UX — toasts (sonner)
- [ ] add sonner dep (done: ^1.7.4)
- [ ] mount `<Toaster />` in providers.tsx (theme-aware)

### C. Optimistic UI — Star icon (#1)
- [ ] watchlistMutation: onMutate (cancel+snapshot+optimistic toggle), onError (rollback+toast),
      onSuccess (analytics+toast), onSettled (invalidate)
- [ ] pass explicit `shouldAdd` from click handler (avoid cache read-after-write inversion)

### D. Robust error handling (#2 + all mutations)
- [ ] dashboard portalMutation: onError toast (surfaces "No subscription found" etc.)
- [ ] dashboard removeWatchlistMutation / deleteSummaryMutation: onError toast

## Verification
- [ ] `npm run typecheck` + `npm run lint` clean
- [ ] `npm run test` (vitest) green
- [ ] live trace: fixed URLs return 401 (auth) not 307

## Review
Implemented all four pillars (approved: both layers + sonner).

Verification:
- typecheck: PASS · lint: PASS (--max-warnings 0) · vitest: 50/50 PASS
- Live trace (pre-redeploy) confirms the frontend fix alone resolves the symptoms:
  - `GET /api/watchlist/`        -> 401 + ACAO (was: 307 -> http:// -> blocked)
  - `GET /api/saved-summaries/`  -> 401 + ACAO
  - `POST /api/compare/`         -> 401 (no redirect)
- Backend `--forwarded-allow-ips="*"` takes effect on next Cloud Run deploy; from then on any
  slashless request also redirects over https instead of http (whole bug class closed).

Outcome by issue:
- #3 / #4: fixed (trailing-slash canonical URLs bypass the redirect).
- #5: now functional (retry's refetch() reaches a working endpoint).
- #1: star loads correct state + optimistic instant toggle + rollback/toast on failure.
- #2: Manage Subscription now surfaces backend errors via toast instead of a dead click.
</content>
