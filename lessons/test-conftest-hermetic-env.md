# The backend suite is hermetic: conftest sets mock env (incl. SKIP_REDIS_INIT) before app import

Date: 2026-07-06   Area: test

**Context**: `backend/tests/conftest.py` unconditionally sets test env vars at import time —
`SKIP_REDIS_INIT=true`, a ≥32-char `SECRET_KEY`, mock Stripe keys,
`PWNED_PASSWORD_CHECK_ENABLED=false`, and empty live-provider keys (`SENTRY_DSN`,
`POSTHOG_API_KEY`, `RESEND_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `TURNSTILE_SECRET_KEY`) — so
the suite runs offline with SQLite and no Redis. Two implications that have bitten: env vars
set in CI steps are OVERRIDDEN by conftest (a CI-provided SECRET_KEY is inert), and any test
needing different config must monkeypatch `settings`, not the environment. The offline claim
was not true until 2026-10-09: CODE RED record 16 found 11 tests reaching SEC and Yahoo on
every run, CI included, with the errors swallowed, and the PR that added the gate found 2
more in the performance lane. `tests/support/network_gate.py` (registered by conftest) now
blocks every in-process outbound attempt and fails the test that made it.

**Rule**: Don't pass config to backend tests via CI env vars; patch `settings` in the test.
Don't add network calls to the suite — hermeticity is what makes the gate fast and the
anchors trustworthy; fake the boundary in the test. Settings also reads `backend/.env`, so a
live-provider key that can arrive from there gets an empty pin in conftest, never an edit to
a locked test. The pin list is kept by hand: in that PR's review, a `TURNSTILE_SECRET_KEY`
in a development `.env` failed 18 auth and form tests with no network attempt. SQLite vs
Postgres differ on timezone handling (naive vs aware reads), so datetime-sensitive code
needs both-backend reasoning (see the naive-utcnow allowlist).

**Evidence**: `backend/tests/conftest.py`; `backend/tests/support/network_gate.py` and its
self-test `backend/tests/unit/test_network_gate.py`; CODE RED decision records 16 and 17; PR #546
review (inert CI SECRET_KEY finding);
`backend/tests/unit/test_naive_utcnow_allowlist.py`.

**Local sandbox correction (2026-10-12, #1259).** When constructing an allowlisted environment
for a backend gate with a read-only home directory, provide separate writable temporary paths
for `EDGAR_LOCAL_DATA_DIR` and `EDGAR_CACHE_DIR`. EdgarTools' anchor cache uses the latter; the
data-directory setting does not cover it. Omitting the cache path caused eight Ford source
tests to fail because TOC extraction swallowed the cache-directory `OSError` and selected an
incomplete pattern fallback. A fresh-process probe captured that error, and the unchanged
eight-test owner failed with the cache path absent and passed with only that path supplied.
Keep the failed receipt and correct the local environment; do not replace the fixture or relax
its source-coverage assertions. This is runner setup guidance, not a change to application
configuration or the suite's network guard.

**Update (2026-10-15, E25).** Conftest now sets both directories itself, per process, inside the
temp directory that holds the test database, unless they are already set; a read-only home needs
neither. An environment that sets them must still set both. `tests/unit/test_suite_isolation.py`
runs a fresh pytest with an empty `HOME` and checks that EdgarTools writes only inside that
process's temp directory, that the directory is gone when the process ends, and that values set
beforehand are kept. The two evaluation harnesses (`evals/acceptance_executor.py::child_environment`
and `evals/copilot_bootstrap.py::configure_environment`) set only `EDGAR_LOCAL_DATA_DIR`, so their
anchor cache still goes to the home directory: E25 in `tasks/todo.md`.
