# Open every session in a PostgreSQL gate with production's settings

Date: 2026-10-20   Area: test

**Context**: `Session(engine)` autoflushes; production's `SessionLocal` does not. An autoflushing
session flushes a pending write at its next query, where production waits for the commit, so it
can serialize two requests that production does not.
- **E127.** Its gate ran a password reset that way. The reset flushed its users UPDATE before its
  bulk revoke and waited there for a racing refresh. That hid a mutant that moved the lock out of
  the revocation.
- **E132.** The usage-counter, login-failure and alert-delivery gates ran their code the same way.
  Their app mutants failed alike under both kinds of session: their writes are Core statements
  that run at once, or ORM inserts flushed explicitly or right before a commit. The review's
  mutant shows what was at stake. With the usage counter's users-row lock replaced by an ORM write
  on that row, 4 cases fail under production's settings, and all 30 pass under autoflushing
  sessions.

**Rule**: Open every session in a PostgreSQL gate home through a `sessionmaker` that spreads
`SessionLocal.kw` and replaces only its bind, with the engine or connection the case was handed (a
parameter of the function that builds it): `_session(bind)` in each home, or
`sessionmaker(**{**SessionLocal.kw, "bind": engine})`, with `class_=` for a test's Session
subclass.
- Never `Session(engine)`, and never a factory with settings of its own.
- Never production's `SessionLocal()` itself, nor a bind the case was not handed, such as
  `database.engine` or `SessionLocal.kw["bind"]`: each is the app's database, which under the test
  conftest is the suite's SQLite file, so a case that opens it runs nothing on PostgreSQL (Codex on
  #1454).
- Seeds and assertions follow the rule too. The production code they run, such as `create_batch`,
  `create_refresh_token` and `payment_report`, then runs as production runs it.

**Evidence**:
- `_session` in each of the five homes under `backend/tests/integration/` (`*_transactions.py`).
- `backend/tests/unit/test_migration_lock_safety.py`:
  - `test_concurrency_has_a_required_postgres_ci_execution_path` fails a session a gate home opens
    other than with production's settings on the engine its case was handed (`_unapproved_sessions`);
  - `test_session_settings_detector_semantics` holds the detector to planted forms.
  - Aliases are followed: an import alias, any assignment form, and a class derived from `Session`
    (Codex on #1454).
- `backend/tests/support/postgres_gates.py`, in the steps, checks every ORM session a PostgreSQL
  case (one that takes `postgres_engine`) opens, as it begins a transaction in any thread: one that
  autoflushes, or that runs on an engine other than the case's own `postgres_engine`, fails the
  case. Another engine is the app's (the suite's SQLite file) or a second PostgreSQL engine, such
  as one built from the gate's URL, which runs outside the case's disposable schema (Codex on
  #1454). That covers what reading the source cannot: a helper handed another engine, a name
  reached through a call or `getattr`, a module the home imports, a setting changed before the
  session's transaction begins.
  `backend/tests/unit/test_postgres_gates_open_production_sessions.py` runs it in child sessions,
  and the step test pins each home's `postgres_engine` fixture, which the check keys on.
- Review-checked: a SQLite case's session built where the source rule cannot follow it, and a
  Core connection (no ORM session) on another database in a PostgreSQL case.
