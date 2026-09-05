#!/usr/bin/env bash
# apply_migrations.sh — apply backend/migrations/*.sql to a PostgreSQL database through the
# `schema_migrations` ledger (ADR-0007). This is the ONLY place migration SQL is applied: the
# `deploy-backend` job (prod, via cloud-sql-proxy) and the `migrations-postgres` CI job (postgres:15
# service, three passes) both run this file, so the two can never drift.
#
# What it does, per file in byte-order (LC_ALL=C) filename order:
#   1. sha256 the file. If (filename, sha256) is already in `schema_migrations`, skip it — a converged
#      migration is never re-executed, so its ALTER/CREATE INDEX never re-acquires a table lock.
#   2. Otherwise run it with `psql -v ON_ERROR_STOP=1` under `lock_timeout=10s` /
#      `statement_timeout=120s`, retrying only the lock-contention SQLSTATEs (55P03 lock timeout,
#      57014 statement timeout, 40P01 deadlock — read from psql stderr under VERBOSITY=verbose) up to
#      5 times, then dumping pg_stat_activity + pg_locks so the blocker is visible in the CI log
#      (lessons/ops-migrations-need-lock-timeout.md).
#   3. Record it: INSERT ... ON CONFLICT (filename) DO UPDATE SET sha256, applied_at. An EDITED file
#      therefore re-applies exactly once (new hash) — that is the escape hatch, not a workflow;
#      CLAUDE.md rule 3 still says never edit an applied migration. Apply and record are two
#      statements, so a crash between them re-applies the file next run: files stay idempotent.
#
# The ledger table is created here with CREATE TABLE IF NOT EXISTS — never by create_all and never in
# the serving container (lessons/ops-no-ddl-in-startup-path.md). The first run against a database
# that predates the ledger applies every file once (they are idempotent) and records them; nothing
# is pre-inserted by hand.
#
# Usage:      bash backend/scripts/apply_migrations.sh [MIGRATIONS_DIR]
# Connection: standard libpq env — PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE. The caller starts
#             cloud-sql-proxy (deploy) or points at the CI service container.
# Output:     one line per file ("== applying X ==" / "-- skipping X (recorded) --") and a final
#             "apply_migrations: applied=N skipped=M" summary that the CI job asserts on.
# Exit:       non-zero on the first non-retryable psql error, when a file is still blocked after 5
#             attempts, when the ledger cannot be read/written, or when MIGRATIONS_DIR has no *.sql.
# Force a re-run of one file (e.g. after a hand-fix in prod):
#             DELETE FROM schema_migrations WHERE filename = '<file>.sql';  then re-run the deploy.
#
# tests/unit/test_migration_lock_safety.py pins the executable lines below (timeouts, VERBOSITY,
# SQLSTATE grep, dump queries, ledger DDL/upsert). Change them deliberately, with the test.

set -euo pipefail
export LC_ALL=C   # byte-order glob sort == Python sorted() in tests/unit/test_migration_lock_safety.py

MIGRATIONS_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../migrations" && pwd)}"

# Fail fast instead of queueing behind an open transaction; bound any single statement.
export PGOPTIONS="-c lock_timeout=10s -c statement_timeout=120s"

ERRLOG="$(mktemp)"
RECORDED="$(mktemp)"
trap 'rm -f "$ERRLOG" "$RECORDED"' EXIT

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1   # macOS
  fi
}

dump_blockers() {
  # pg_stat_activity nulls state/xact_start/wait_event for OTHER roles' backends unless this role has
  # pg_read_all_stats, so never filter on them (a human Cloud SQL Studio session would vanish).
  # pg_locks is visible to every role and names the relation.
  echo "Sessions in this database (NULL columns = another role's backend):"
  psql -X -c "SELECT pid, usename, application_name, backend_type, state, wait_event_type, now() - xact_start AS xact_age FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid() ORDER BY xact_start NULLS LAST;" || true
  echo "Relation locks held or awaited in this database:"
  psql -X -c "SELECT l.pid, l.mode, l.granted, c.relname FROM pg_locks l JOIN pg_class c ON c.oid = l.relation WHERE l.locktype = 'relation' AND l.database = (SELECT oid FROM pg_database WHERE datname = current_database()) AND c.relnamespace = 'public'::regnamespace AND l.pid <> pg_backend_pid() ORDER BY c.relname, l.pid;" || true
}

apply_with_retry() {
  local f="$1" attempt rc
  for attempt in 1 2 3 4 5; do
    rc=0
    # VERBOSITY=verbose makes psql print the SQLSTATE (e.g. `ERROR:  55P03: ...`) so the retry
    # decision keys on the code, not on message wording. -X skips ~/.psqlrc.
    psql -X -v ON_ERROR_STOP=1 -v VERBOSITY=verbose -f "$f" 2>"$ERRLOG" || rc=$?
    cat "$ERRLOG" >&2
    if [ "$rc" -eq 0 ]; then
      return 0
    fi
    # Retry only the contention class: lock_timeout 55P03, statement_timeout 57014, deadlock 40P01.
    # A syntax or permission error is final on the first attempt.
    if ! grep -qE '\b(55P03|57014|40P01)\b' "$ERRLOG"; then
      echo "::error::$(basename "$f") failed with a non-retryable error (see above)."
      return 1
    fi
    echo "::warning::$(basename "$f") hit a lock/statement timeout (attempt $attempt/5); retrying in 15s"
    sleep 15
  done
  echo "::error::$(basename "$f") still blocked after 5 attempts. Terminate the blocker below, then re-run the job."
  dump_blockers
  return 1
}

record_applied() {
  # psql interpolates :'var' as a properly quoted literal — no shell-built SQL. Interpolation only
  # happens for stdin/-f input (never for -c strings), hence the heredoc.
  psql -X -q -v ON_ERROR_STOP=1 -v fn="$1" -v sha="$2" <<'SQL'
INSERT INTO schema_migrations (filename, sha256) VALUES (:'fn', :'sha')
ON CONFLICT (filename) DO UPDATE SET sha256 = EXCLUDED.sha256, applied_at = now();
SQL
}

shopt -s nullglob
files=("$MIGRATIONS_DIR"/*.sql)
if [ "${#files[@]}" -eq 0 ]; then
  echo "::error::no *.sql files found in $MIGRATIONS_DIR"
  exit 1
fi

# The ledger. A brand-new table on first run; a catalog no-op (no table lock) on every later run.
psql -X -q -v ON_ERROR_STOP=1 -c "CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, sha256 TEXT NOT NULL, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"
psql -X -q -v ON_ERROR_STOP=1 -At -c "SELECT filename || ' ' || sha256 FROM schema_migrations;" > "$RECORDED"

applied=0
skipped=0
for f in "${files[@]}"; do
  name="$(basename "$f")"
  sha="$(sha256_of "$f")"
  if grep -qxF "$name $sha" "$RECORDED"; then
    echo "-- skipping $name (recorded) --"
    skipped=$((skipped + 1))
    continue
  fi
  echo "== applying $name =="
  apply_with_retry "$f"
  record_applied "$name" "$sha"
  applied=$((applied + 1))
done

echo "apply_migrations: applied=$applied skipped=$skipped"
