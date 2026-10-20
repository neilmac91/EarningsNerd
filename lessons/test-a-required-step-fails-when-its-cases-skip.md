# A required test step fails when its cases skip

Date: 2026-10-20   Area: test

**Context**: Each PostgreSQL gate runs as its own required step in CI's migrations-postgres job.
The step sets the gate's database variable, and the gate's cases skip when it is unset, which is
how the fast lane runs them. A gate whose engine fixture stopped reading the variable would skip
its PostgreSQL cases at setup, and its step would pass: pytest exits 0 when collected tests skip,
whether the gate's SQLite cases still ran or nothing did. E127's review found it (E132).
`test_migration_lock_safety.py` only checked that each home read its variable somewhere. A
module-level skip was already caught: a step that runs one module and collects no test exits 5.

**Rule**: A required step that runs gated cases must fail when they skip. Skip a gate's case only
when its variable is unset. For the PostgreSQL gates, `backend/tests/support/postgres_gates.py`
fails the run when a gate's variable is set and any of its cases, or its module, skips. A new
gate goes into the plugin's `POSTGRES_GATES` and the step test's `_POSTGRES_STEPS` in the PR that
adds its step; the step test fails until both match the workflow.

**Evidence**:
- `backend/tests/support/postgres_gates.py`
- `backend/tests/unit/test_postgres_gates_fail_when_their_cases_skip.py`: a fixture's skip and a
  module's skip fail, serially and under pytest-xdist; an unset variable, or a home that is no
  gate, still skips.
- `backend/tests/unit/test_migration_lock_safety.py::test_every_postgres_step_fails_when_its_cases_skip`
