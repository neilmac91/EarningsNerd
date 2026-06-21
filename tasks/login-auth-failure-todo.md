# Login / Registration failure investigation (2026-06-21)

Symptom (from user screenshots): both **Login** and **Create account** show
"Unable to connect to the server. Please ensure the backend API is running on
https://api.earningsnerd.io".

## Investigation method
Live probes against prod (`https://api.earningsnerd.io`) + code reading. The backend
is **up**: `/health` → 200, `/health/detailed` → DB healthy (6ms), Redis intentionally
disabled in prod, circuit breaker closed. So this is **not** a backend outage.

The frontend only prints "Unable to connect to the server" for a true network-level
failure — axios `Network Error` / no HTTP response (`frontend/lib/api/client.ts:165-166`).
A 4xx/5xx would render a different message. A browser surfaces a **blocked CORS preflight**
as exactly this generic network error. So the user is hitting a CORS preflight failure.

## Root causes found (two independent, both block working auth)

### 1. CORS preflight rejects the Turnstile header  ← the message the user sees
- Auth/contact/waitlist forms attach `cf-turnstile-response` (when Turnstile is enabled):
  `frontend/features/auth/api/auth-api.ts:7-8`, backend reads it in
  `backend/app/services/turnstile.py:29` (`_TOKEN_HEADERS`).
- The backend CORS `allow_headers` (`backend/main.py`) did **not** include that header.
- Reproduced against prod: preflight requesting `cf-turnstile-response` →
  `400 Disallowed CORS headers`; preflight with only `content-type` → 200.
- **Fix (this PR):** added `cf-turnstile-response` + `x-turnstile-token` to
  `allow_headers` in `backend/main.py`. Verified in isolation that the preflight now
  returns 200 and advertises both headers.
- NOTE: only the active cause if `NEXT_PUBLIC_TURNSTILE_SITE_KEY` is set on the Vercel
  frontend. If instead the page is served from a **non-allowlisted origin** (e.g. a
  Vercel preview `*.vercel.app`), the preflight fails with `400 Disallowed CORS origin`
  — same user-visible message; remedy is to add the origin to `CORS_ORIGINS_STR` on
  Cloud Run. (Allowed origins `https://earningsnerd.io` / `https://www.earningsnerd.io`
  preflight cleanly.)

### 2. Server 500 on every endpoint that queries `User` (latent, hits once CORS passes)
- `POST /api/auth/login`, `/api/auth/forgot-password`, `/api/auth/resend-verification`
  all return `500 {"detail":"An unexpected error occurred"}` for a non-existent email.
  The login *logic* is correct (clean 401 path), so the crash is in `db.query(User)`.
- Leading diagnosis: **prod DB schema drift**. The `User` model
  (`backend/app/models/__init__.py`) maps columns added only via manual SQL migrations
  (`email_verified`, `email_verification_token`, `notifications_seen_at`, …).
  `Base.metadata.create_all()` never ALTERs an existing `users` table, so if a migration
  wasn't applied to Cloud SQL, every `SELECT users.*` fails → 500.
  `backend/migrations/20260620_users_notifications_seen_at.sql` is dated the day before
  the report — fits a fresh breakage.
- **Remediation (operational — needs prod DB access, cannot be done from the repo):**
  apply pending migrations to Cloud SQL, e.g.
  `psql "$DATABASE_URL" -f backend/migrations/20260620_users_notifications_seen_at.sql`
  (and audit the other `users`-touching migrations). Confirm against the actual Cloud Run
  error log for the correlation IDs of the 500s before/after.

## Status
- [x] Diagnosed both failures with live evidence
- [x] Fixed CORS `allow_headers` (Turnstile) + verified preflight now 200
- [ ] (operational) Confirm/repair prod `users` schema drift — apply manual migrations
- [ ] (operational) If user is on a non-allowlisted origin, add it to `CORS_ORIGINS_STR`
