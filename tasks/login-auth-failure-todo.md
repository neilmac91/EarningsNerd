# Login / Registration failure investigation (2026-06-21)

Symptom (from user screenshots): both **Login** and **Create account** show
"Unable to connect to the server. Please ensure the backend API is running on
https://api.earningsnerd.io".

User-confirmed context: testing on **`earningsnerd.io`** (an allow-listed origin),
and **`NEXT_PUBLIC_TURNSTILE_SITE_KEY` is NOT set** on Vercel (Turnstile disabled).

## Investigation method
Live probes against prod + code reading. Backend is **up**: `/health` 200,
`/health/detailed` DB healthy (~6ms), circuit breaker closed. Not an outage. The
frontend prints "Unable to connect" only for a true network failure with no readable
HTTP response (`frontend/lib/api/client.ts:165-166`) — which is also how a browser
reports a cross-origin response that lacks `Access-Control-Allow-Origin`.

## CONFIRMED ROOT CAUSE (for this user)

1. **`POST /api/auth/login` returns 500.** Reproduced from the allow-listed origin.
   `/forgot-password` and `/resend-verification` 500 too — every endpoint that runs
   `db.query(User)`. The login *logic* is correct (clean 401 path), so the crash is
   the User query itself. Leading diagnosis: **prod DB schema drift** — the `User`
   model (`backend/app/models/__init__.py`) maps columns added only via the manual
   SQL files in `backend/migrations/` (`email_verified`, `email_verification_token`,
   `notifications_seen_at`, …), and `Base.metadata.create_all()` never ALTERs an
   existing `users` table. `20260620_users_notifications_seen_at.sql` is dated the day
   before the report — fits a fresh breakage.

2. **The 500 response carries no CORS headers, so it masquerades as a network error.**
   Confirmed: the 500 has no `access-control-allow-origin` (the 422 does). Cause: the
   `@app.exception_handler(Exception)` at `backend/main.py` is invoked by Starlette's
   ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware, so its response skips CORS
   header injection. A browser then blocks the cross-origin 500 and axios sees a generic
   "Network Error" → the UI prints "Unable to connect to the server" instead of the real
   server error. This is why the symptom looked like connectivity loss on a healthy API.

## Fixes

### Repo (this PR)
- [x] `_error_response_cors_headers()` helper added in `backend/main.py`; applied to the
      global `Exception` handler **and** the `CircuitOpenError` handler so hand-built error
      responses are readable cross-origin. Verified in isolation: a cross-origin 500 now
      carries `Access-Control-Allow-Origin` (was absent). This makes server errors surface
      honestly (correct message + ability to retry) instead of as "Unable to connect".
- [x] CORS `allow_headers` now includes `cf-turnstile-response` / `x-turnstile-token`.
      Latent bug (NOT this user's cause, since Turnstile is off) — but the moment Turnstile
      is enabled, every auth/contact/waitlist preflight would 400 with "Disallowed CORS
      headers" → same "Unable to connect". Fixed pre-emptively; preflight verified 200.

> NOTE: The repo fixes change the *message* (honest server error instead of "Unable to
> connect") but do NOT by themselves make login succeed — the 500 must be eliminated.

### Operational (NOT possible from the repo — needs prod DB access)
- [ ] **Apply pending migration(s) to Cloud SQL** to repair the `users` schema, e.g.
      `psql "$DATABASE_URL" -f backend/migrations/20260620_users_notifications_seen_at.sql`
      (audit the other `users`-touching migrations too). This is the fix that makes login
      and registration actually work.
- [ ] Confirm against the Cloud Run error log (the 500s carry `x-cloud-trace-context` /
      correlation IDs) that the exception is the expected "column does not exist".
