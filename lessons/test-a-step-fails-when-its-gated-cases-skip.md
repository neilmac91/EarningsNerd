# A step that runs gated cases fails when they skip

Date: 2026-10-20   Area: test

**Context**: Each PostgreSQL gate runs as its own required step in CI's migrations-postgres job.
The step sets the gate's database variable, and the gate's cases skip when it is unset, which is
how the fast lane runs them. pytest exits 0 when the tests it collected skip. So a gate whose
engine fixture stopped reading the variable, or whose module carried a skip mark (`pytestmark`),
would pass its step with its PostgreSQL cases unrun, whether its SQLite cases still ran or nothing
did. E127's review found it (E132); `test_migration_lock_safety.py` only checked that each home
read its variable somewhere. Only a skip raised while the module imports
(`pytest.skip(..., allow_module_level=True)`, a module-level `importorskip`) failed already: the
step collected no test and exited 5.

**Rule**: A step that runs gated cases fails when they do not run. Skip a gated case only when its
variable is unset.
- **The PostgreSQL gates.** `backend/tests/support/postgres_gates.py` fails the run when a gate's
  variable is set and any of its cases skips or is an expected failure (xfail). That covers a skip
  at setup, in a test's body or by a mark, and a module that skips as it imports.
- **A new PostgreSQL gate.** Add it to the plugin's `POSTGRES_GATES` and the step test's
  `_POSTGRES_STEPS` in the PR that adds its step. The step test fails until both match the
  workflow: each step named "Verify … concurrency on PostgreSQL", and each env that sets a
  `*_TEST_DATABASE_URL`, needs a row.
- **Other steps that run gated cases** are review-checked. The daily prod smoke's
  `SMOKE_BASE_URL` for `frontend/tests/e2e/prod-smoke.spec.ts` is one.

**Evidence**:
- `backend/tests/support/postgres_gates.py`.
- `backend/tests/unit/test_postgres_gates_fail_when_their_cases_skip.py`, serially and under
  pytest-xdist:
  - a fixture's skip, a module's skip, a skip mark, a skip in a body and an xfail fail the run;
  - with the variable unset, or in a home that is no gate, the skips pass;
  - each run in one process keeps its own count.
- `backend/tests/unit/test_migration_lock_safety.py::test_every_postgres_step_fails_when_its_cases_skip`
  pins the plugin to the workflow and to the conftest. The steps clear `pytest.ini`'s addopts, so
  only the conftest loads it there.
