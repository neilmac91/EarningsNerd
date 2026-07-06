# Tests live in exactly one home per stack — a test outside it does not run in CI

Date: 2026-07-06   Area: test

**Context**: Wave 0 found THREE test roots (backend/tests, an orphaned repo-root /tests/
never collected by CI, and dual frontend dirs with mixed suffixes). The orphaned root
silently held the only coverage of security headers and the Stripe price allowlist —
"tests exist" meant nothing because CI never ran them.

**Rule**: Backend tests: `backend/tests/{unit,integration,smoke,performance}` — config
is `backend/pytest.ini` ONLY (testpaths, markers, fast-lane
`addopts = -m "not performance and not slow"`; CI runs performance explicitly with
`-o addopts=`). Frontend: `frontend/tests/unit/**/*.spec.*` + `frontend/tests/e2e` —
one home, one suffix. Never create a test file outside these paths; if you find one,
it is dead until moved.

**Evidence**: Wave 0a (PR #546) — pytest.ini creation, orphan-suite triage; F3 test-dir
merge (PR #559); `frontend/vitest.config.mts` include line.
