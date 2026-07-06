# The backend suite is hermetic: conftest sets mock env (incl. SKIP_REDIS_INIT) before app import

Date: 2026-07-06   Area: test

**Context**: `backend/tests/conftest.py` unconditionally sets test env vars at import
time — `SKIP_REDIS_INIT=true`, a ≥32-char `SECRET_KEY`, mock Stripe keys,
`PWNED_PASSWORD_CHECK_ENABLED=false` — so the suite runs offline with SQLite and no
Redis. Two implications that have bitten: env vars set in CI steps are OVERRIDDEN by
conftest (a CI-provided SECRET_KEY is inert), and any test needing different config must
monkeypatch `settings`, not the environment.

**Rule**: Don't pass config to backend tests via CI env vars; patch `settings` in the
test. Don't add network calls to the suite — hermeticity is what makes the gate fast and
the anchors trustworthy. SQLite vs Postgres differ on timezone handling (naive vs aware
reads), so datetime-sensitive code needs both-backend reasoning (see the naive-utcnow
allowlist).

**Evidence**: `backend/tests/conftest.py`; PR #546 review (inert CI SECRET_KEY finding);
`backend/tests/unit/test_naive_utcnow_allowlist.py`.
