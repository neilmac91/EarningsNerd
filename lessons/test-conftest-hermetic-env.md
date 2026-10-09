# The backend suite is hermetic: conftest sets mock env (incl. SKIP_REDIS_INIT) before app import

Date: 2026-07-06   Area: test

**Context**: `backend/tests/conftest.py` unconditionally sets test env vars at import
time — `SKIP_REDIS_INIT=true`, a ≥32-char `SECRET_KEY`, mock Stripe keys,
`PWNED_PASSWORD_CHECK_ENABLED=false`, and empty live-provider keys (`SENTRY_DSN`,
`POSTHOG_API_KEY`, `RESEND_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `TURNSTILE_SECRET_KEY`) — so the suite runs offline with
SQLite and no Redis. Two implications that have bitten: env vars set in CI steps are OVERRIDDEN
by conftest (a CI-provided SECRET_KEY is inert), and any test needing different config must
monkeypatch `settings`, not the environment. The offline claim was not true until 2026-10-09:
CODE RED record 16 found 11 tests reaching SEC and Yahoo on every run, CI included, with the
errors swallowed, and the PR that added the gate found 2 more in the performance lane. `tests/support/network_gate.py` (registered by conftest) now blocks every
in-process outbound attempt and fails the test that made it.

**Rule**: Don't pass config to backend tests via CI env vars; patch `settings` in the
test. Don't add network calls to the suite — hermeticity is what makes the gate fast and
the anchors trustworthy; fake the boundary in the test. Settings also reads `backend/.env`,
so a live-provider key that can arrive from there gets an empty pin in conftest, never an
edit to a locked test. The pin list is kept by hand: in that PR's review, a `TURNSTILE_SECRET_KEY`
in a development `.env` failed 18 auth and form tests with no network attempt. SQLite vs Postgres differ on timezone handling (naive vs aware
reads), so datetime-sensitive code needs both-backend reasoning (see the naive-utcnow
allowlist).

**Evidence**: `backend/tests/conftest.py`; `backend/tests/support/network_gate.py` and its
self-test `backend/tests/unit/test_network_gate.py`; CODE RED decision records 16 and 17; PR #546
review (inert CI SECRET_KEY finding);
`backend/tests/unit/test_naive_utcnow_allowlist.py`.
