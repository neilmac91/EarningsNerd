"""Structural gate for the deploy pipeline's two 2026-09 lessons (CLAUDE.md rule 12: rules become gates).

1. Migrations must fail fast, never hang. On 2026-07-16 the `deploy-backend` job re-applied the
   converged `20260122_add_markdown_cache_columns.sql`; its `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
   still takes ACCESS EXCLUSIVE before the existence check, queued behind one open transaction, and
   with no `lock_timeout` and no job timeout the deploy sat for GitHub's 6 h default and never
   shipped (lessons/ops-migrations-need-lock-timeout.md). This test pins the workflow-level guards
   (job `timeout-minutes`, `lock_timeout` + `statement_timeout` on the psql session) and freezes the
   set of legacy files that still issue a top-level `ALTER TABLE` on a pre-existing table. New
   migration files must wrap such ALTERs in a `DO $$ ... IF NOT EXISTS (...) THEN ... END IF $$`
   block (see `20260705_summary_filing_id_unique.sql`), so re-application on every deploy is a true
   no-op that takes no table lock. The allow-list can only shrink.

   The same trap in a smaller lock: plain `CREATE [UNIQUE] INDEX IF NOT EXISTS` opens the table with
   a SHARE lock before the existence check, so it queues behind any open writer. Of the 40 index
   statements in `backend/migrations/` today, 8 (in 7 files) target a table the file did not create;
   those files form a second frozen, shrink-only list. New files guard with a `pg_indexes` check in
   a DO block, or use `CONCURRENTLY` outside a transaction block.

   Also pinned here (WS-1, audit 2026-09): the retry in `apply_with_retry` keys on the lock-contention
   SQLSTATEs (55P03/57014/40P01) in psql's stderr rather than on any error; the blocker dump shows
   every backend and joins `pg_locks` to `pg_class`; the `cloud-sql-proxy` download is verified
   against one sha256 shared by `ci.yml` and `ops.yml`; and `ops.yml` is dispatch-only, sets the
   same `PGOPTIONS`, and refuses to run while a main push is in flight.

   Since ADR-0007 (WS-2) the apply logic — PGOPTIONS, `apply_with_retry`, `dump_blockers` — lives in
   `backend/scripts/apply_migrations.sh`, which records each applied file in the `migration_ledger`
   table (filename + sha256) and skips it on later deploys. The ledger is NOT `schema_migrations`:
   prod already had a table of that name and the first ledger deploy adopted it via IF NOT EXISTS
   (2026-09-05); the CI job plants a decoy `schema_migrations` so the script can never depend on it. The retry/dump pins above therefore read
   the SCRIPT (comment-stripped); the proxy-pin and job-level pins keep reading `ci.yml`. The deploy
   step and the `migrations-postgres` CI job (postgres:15 service, three passes: seed, skip,
   reset-and-reapply) must both run that one script — no second copy of the psql loop anywhere.
   "Only the script" is an allow-list of the executable ci.yml lines that mention psql
   (CI_PSQL_ALLOWLIST), not a deny-list regex: `psql -f"$f"`, `psql --file=…`, `cat "$f" | psql`,
   `psql < "$f"` and `psql -c "ALTER TABLE …"` all slipped past the regex version under mutation.
   Likewise the pipefail pin reads executable lines with an anchored `set -…o pipefail`, because a
   `# no pipefail here` comment satisfied the raw-text version.

2. The lint toolchain must be pinned. `pip install ruff` in CI let ruff 0.16's wider default rule set
   turn a clean tree into 2,767 findings with no code change (lessons/ops-pin-ci-toolchain.md). CI
   must install from `backend/requirements-dev.txt` with exact pins, and `ruff.toml` must select its
   rules explicitly.

Known limits, by design: a table the same file CREATEs is exempt from both detectors, yet on deploy
N+1 that table exists and its `CREATE INDEX IF NOT EXISTS` statements (32 today) still take SHARE
locks; and that exemption is text-level, so a file that writes `CREATE TABLE IF NOT EXISTS <table
that already exists>` before its ALTER/INDEX bypasses the gate (reviewers, not regexes, catch that).
The migration ledger (WS-2, ADR-0007) removes re-application on deploys altogether; these detectors
still matter because a ledger reset, an edited file (new sha256) and CI's third pass re-run every
file, and because the first application of a new file takes the lock regardless. `ops.yml`'s deploy
pre-flight is likewise a point-in-time, one-directional check (see its header); its psql steps are
outside the "only the script applies SQL" pin below (they run ops SQL, never migration files).

Everything here is text-level and runs in the hermetic unit suite (no Postgres needed).
"""
import re
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
OPS_YML = REPO_ROOT / ".github" / "workflows" / "ops.yml"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"
APPLY_SCRIPT = BACKEND_DIR / "scripts" / "apply_migrations.sh"
MIGRATIONS_JOB = "migrations-postgres"

# The only executable lines in ci.yml allowed to mention psql (trimmed, verbatim). Migration SQL is
# applied by backend/scripts/apply_migrations.sh alone; the workflow may install the client and reset
# the CI ledger between passes, nothing else. Extend deliberately, never with a `-f`/`--file`/stdin form.
CI_PSQL_ALLOWLIST = {
    "- name: Install psql",
    "run: command -v psql >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y -qq postgresql-client)",
    'psql -X -v ON_ERROR_STOP=1 -c "DELETE FROM migration_ledger;"',
    'run: psql -X -v ON_ERROR_STOP=1 -c "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"',
}
LEDGER_TABLE = "migration_ledger"
LEGACY_LEDGER_NAME = "schema_migrations"  # exists in prod with a foreign shape; the script must never touch it
_SET_PIPEFAIL = re.compile(r"^\s*set -[a-z]*o pipefail\b", re.M)
REQUIREMENTS_DEV = BACKEND_DIR / "requirements-dev.txt"
RUFF_TOML = BACKEND_DIR / "ruff.toml"

MIGRATION_NAME = re.compile(r"^\d{8}_[a-z0-9_]+\.sql$")

# Legacy files that issue a top-level ALTER TABLE on a table they did not create. The ledger
# (ADR-0007) runs each of them once, but a ledger reset or an edit re-runs them with only the psql
# lock_timeout for protection. Do NOT add to this set: new files must use the DO-block guard.
# Remove an entry when its file is rewritten.
LEGACY_UNGUARDED_ALTERS = {
    "20260122_add_markdown_cache_columns.sql",
    "20260126_add_is_admin_to_users.sql",
    "20260615_oauth_and_email_verification.sql",
    "20260618_phase2_alerts.sql",
    "20260620_filing_processed_facts_at.sql",
    "20260620_users_notifications_seen_at.sql",
    "20260621_user_usage_qa_count.sql",
    "20260624_add_cohort_to_invite_codes.sql",
    "20260624_add_is_beta_to_users.sql",
    "20260628_fpi_alert_prefs.sql",
    "20260629_user_copilot_free_taste.sql",
    "20260703_create_earnings_events.sql",
    "20260706_company_facts_synced_at.sql",
    "20260707_user_usage_analysis_count.sql",
    "20260708_add_trend_analysis_unverified.sql",
    "20260708_summary_version_stamps.sql",
    "20260711_companies_history_backfilled_at.sql",
}

# Legacy files that issue a top-level, non-CONCURRENT `CREATE [UNIQUE] INDEX` on a table they did
# not create. Postgres opens the relation with a SHARE lock BEFORE evaluating IF NOT EXISTS, so each
# re-apply queues behind any open writer on that table (bounded only by the psql lock_timeout).
# Same rules as above: frozen, shrink-only. New files guard the statement in a DO block with a
# `pg_indexes` check, or use `CREATE INDEX CONCURRENTLY` outside a BEGIN/COMMIT block.
LEGACY_UNGUARDED_INDEXES = {
    "20260122_add_markdown_cache_columns.sql",
    "20260126_add_is_admin_to_users.sql",
    "20260615_oauth_and_email_verification.sql",
    "20260624_add_cohort_to_invite_codes.sql",
    "20260624_add_is_beta_to_users.sql",
    "20260624_add_oauth_account_unique.sql",
    "20260710_filings_company_type_date_index.sql",
}


def _load_ci() -> dict:
    return yaml.safe_load(CI_YML.read_text(encoding="utf-8"))


def _deploy_job(ci: dict) -> dict:
    return ci["jobs"]["deploy-backend"]


def _step(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"step {name!r} not found in job (was it renamed? update this test too)")


_DO_BLOCK = re.compile(r"DO\s+(\$[A-Za-z_]*\$)(.*?)\1", re.S | re.I)
# A DO body only counts as a guard when it checks existence via a subquery or the catalog. A bare
# `ADD COLUMN IF NOT EXISTS` inside a DO block is NOT a guard — it still takes ACCESS EXCLUSIVE.
_GUARD = re.compile(
    r"IF\s+NOT\s+EXISTS\s*\(\s*SELECT|IF\s+EXISTS\s*\(\s*SELECT|information_schema\.|pg_catalog\.|"
    r"\bpg_constraint\b|\bpg_indexes\b|\bpg_class\b|\bpg_attribute\b|\bto_regclass\b",
    re.I,
)
_IDENT = r'((?:"[^"]+"|\w+)(?:\.(?:"[^"]+"|\w+))?)'
_ALTER = re.compile(r"\bALTER\s+TABLE\s+(?:ONLY\s+)?(?:IF\s+EXISTS\s+)?" + _IDENT, re.I)
_CREATE = re.compile(r"\bCREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?" + _IDENT, re.I)
# group(1) = CONCURRENTLY (sanctioned: builds without a SHARE lock on the table), group(2) = index
# name (Postgres allows it to be omitted), group(3) = table.
_CREATE_INDEX = re.compile(
    r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?(?:"
    + _IDENT
    + r"\s+)?ON\s+(?:ONLY\s+)?"
    + _IDENT,
    re.I,
)
_IF_THEN = re.compile(r"\bIF\b.*?\bTHEN\b", re.S | re.I)
_END_IF = re.compile(r"\bEND\s+IF\b", re.I)
_TXN_OPEN = re.compile(r"^\s*(?:BEGIN|START\s+TRANSACTION)\b", re.I)
_TXN_CLOSE = re.compile(r"^\s*(?:COMMIT|ROLLBACK)\b", re.I)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"/\*.*?\*/", "", sql, flags=re.S)


def _norm(ident: str) -> str:
    """Unqualified, unquoted, lowercase — `"public"."Users"` and `users` name the same table."""
    return ident.replace('"', "").lower().rsplit(".", 1)[-1]


def _unguarded_targets(
    sql: str, statement: re.Pattern[str], table_of: Callable[[re.Match[str]], str | None]
) -> list[str]:
    """Tables `statement` will lock on every re-apply.

    Counts every top-level match (a regex over the whole comment-stripped text, so several
    statements on one line are all seen) and every match inside a DO body that is not enclosed by
    an `IF <catalog check> THEN ... END IF` branch. Ignores tables the same file CREATEs (a
    brand-new table has no readers to block) and matches `table_of` maps to None (the sanctioned
    form, e.g. CONCURRENTLY).
    """
    sql = _strip_comments(sql)
    do_bodies = [m.group(2) for m in _DO_BLOCK.finditer(sql)]
    top = _DO_BLOCK.sub(" ", sql)
    created = {_norm(m) for m in _CREATE.findall(top)}
    hit = {table_of(m) for m in statement.finditer(top)}
    for body in do_bodies:
        hit |= _unguarded_in_do_body(body, statement, table_of)
    return sorted(t for t in hit if t and t not in created)


def _unguarded_in_do_body(
    body: str, statement: re.Pattern[str], table_of: Callable[[re.Match[str]], str | None]
) -> set[str | None]:
    """Matches in a DO body that no enclosing `IF <catalog check> THEN` branch protects.

    Walks the body statement by statement (`;`) with a stack of open IF branches, so one catalog
    check whitelists only the statements inside its own branch — never the whole block.
    """
    hit: set[str | None] = set()
    guards: list[bool] = []
    for chunk in body.split(";"):
        opened = _IF_THEN.search(chunk)
        if opened:
            guards.append(bool(_GUARD.search(opened.group(0))))
        if not any(guards):
            hit.update(table_of(m) for m in statement.finditer(chunk))
        if _END_IF.search(chunk) and guards:
            guards.pop()
    return hit


def _concurrent_index_inside_transaction(sql: str) -> list[str]:
    """Tables whose `CREATE INDEX CONCURRENTLY` sits between BEGIN and COMMIT.

    Postgres rejects CONCURRENTLY inside a transaction block (SQLSTATE 25001), so such a file fails
    on EVERY deploy, not just the first.
    """
    top = _DO_BLOCK.sub(" ", _strip_comments(sql))
    in_txn = False
    hit: set[str] = set()
    for chunk in top.split(";"):
        if _TXN_OPEN.match(chunk):
            in_txn = True
        elif _TXN_CLOSE.match(chunk):
            in_txn = False
        elif in_txn:
            hit.update(_norm(m.group(3)) for m in _CREATE_INDEX.finditer(chunk) if m.group(1))
    return sorted(hit)


def _unguarded_alter_targets(sql: str) -> list[str]:
    """Tables an ALTER TABLE takes ACCESS EXCLUSIVE on, on every re-apply."""
    return _unguarded_targets(sql, _ALTER, lambda m: _norm(m.group(1)))


def _unguarded_index_targets(sql: str) -> list[str]:
    """Tables a non-CONCURRENT CREATE [UNIQUE] INDEX opens with a SHARE lock, on every re-apply."""
    return _unguarded_targets(sql, _CREATE_INDEX, lambda m: None if m.group(1) else _norm(m.group(3)))


def test_unguarded_alter_detector_semantics():
    guarded = """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                       WHERE table_name = 'users' AND column_name = 'x') THEN
            ALTER TABLE users ADD COLUMN x INTEGER;
        END IF; END $$;"""
    assert _unguarded_alter_targets(guarded) == []
    # A DO wrapper alone is not a guard (review finding on PR #653).
    assert _unguarded_alter_targets("DO $$ BEGIN ALTER TABLE users ADD COLUMN x INT; END $$;") == ["users"]
    assert _unguarded_alter_targets(
        "DO $$ BEGIN ALTER TABLE users ADD COLUMN IF NOT EXISTS x INT; END $$;"
    ) == ["users"]
    # One catalog check guards only its own branch: a second ALTER outside the IF is still unguarded,
    # and an IF on a plain variable (no catalog check) guards nothing.
    assert _unguarded_alter_targets(
        """DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='x') THEN
            ALTER TABLE users ADD COLUMN x INT;
        END IF;
        ALTER TABLE accounts ADD COLUMN y INT;
        END $$;"""
    ) == ["accounts"]
    assert _unguarded_alter_targets(
        "DO $$ DECLARE go BOOLEAN := TRUE; BEGIN IF go THEN ALTER TABLE users ADD COLUMN x INT; END IF; END $$;"
    ) == ["users"]
    # Same-file CREATE + ALTER: a brand-new table has no readers to block.
    assert _unguarded_alter_targets("CREATE TABLE IF NOT EXISTS t (id INT); ALTER TABLE t ADD COLUMN y INT;") == []
    # ...and the match is on the unqualified lowercase name, so a schema-qualified or quoted
    # spelling of the same table still counts as created in-file.
    assert _unguarded_alter_targets('CREATE TABLE t (id INT); ALTER TABLE "public"."T" ADD COLUMN y INT;') == []
    # Quoted identifiers and two statements on one line are both seen.
    assert _unguarded_alter_targets('ALTER TABLE "public"."users" ADD COLUMN x INT;') == ["users"]
    assert _unguarded_alter_targets("BEGIN; ALTER TABLE users ADD COLUMN x INT; COMMIT;") == ["users"]
    assert _unguarded_alter_targets("CREATE INDEX IF NOT EXISTS i ON t (x); ALTER TABLE t ADD COLUMN y INT;") == ["t"]
    # Comments never count.
    assert _unguarded_alter_targets("-- ALTER TABLE users ADD COLUMN x INT;\nSELECT 1;") == []


def test_unguarded_index_detector_semantics():
    # Plain CREATE INDEX on a pre-existing table opens the relation (SHARE lock) before IF NOT EXISTS.
    assert _unguarded_index_targets("CREATE INDEX IF NOT EXISTS i ON users (x);") == ["users"]
    assert _unguarded_index_targets('CREATE UNIQUE INDEX i ON "public"."Users" (x);') == ["users"]
    # CONCURRENTLY never blocks readers/writers on the table — it is the sanctioned top-level form.
    assert _unguarded_index_targets("CREATE INDEX CONCURRENTLY IF NOT EXISTS i ON users (x);") == []
    # A table created in the same file has no readers to block.
    assert _unguarded_index_targets("CREATE TABLE IF NOT EXISTS t (id INT); CREATE INDEX i ON t (id);") == []
    # A DO body is a guard only when it checks the catalog first; a bare wrapper is not.
    assert _unguarded_index_targets(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'i') THEN "
        "CREATE INDEX i ON users (x); END IF; END $$;"
    ) == []
    assert _unguarded_index_targets("DO $$ BEGIN CREATE INDEX IF NOT EXISTS i ON users (x); END $$;") == ["users"]
    # Unnamed indexes (Postgres picks the name) are caught too.
    assert _unguarded_index_targets("CREATE INDEX ON users (x);") == ["users"]
    assert _unguarded_index_targets("CREATE UNIQUE INDEX CONCURRENTLY ON users (x);") == []
    # A guarded branch does not cover a sibling statement outside it.
    assert _unguarded_index_targets(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'i') THEN "
        "CREATE INDEX i ON users (x); END IF; CREATE INDEX j ON accounts (y); END $$;"
    ) == ["accounts"]
    assert _unguarded_index_targets("-- CREATE INDEX i ON users (x);\nSELECT 1;") == []


def test_concurrent_index_in_transaction_detector_semantics():
    assert _concurrent_index_inside_transaction(
        "BEGIN;\nCREATE INDEX CONCURRENTLY IF NOT EXISTS i ON users (x);\nCOMMIT;"
    ) == ["users"]
    assert _concurrent_index_inside_transaction(
        "BEGIN;\nALTER TABLE t ADD COLUMN x INT;\nCOMMIT;\nCREATE INDEX CONCURRENTLY i ON t (x);"
    ) == []
    assert _concurrent_index_inside_transaction("START TRANSACTION; CREATE INDEX CONCURRENTLY ON t (x); ROLLBACK;") == ["t"]
    # A plain index inside the block is a lock question (previous detector), not a syntax error.
    assert _concurrent_index_inside_transaction("BEGIN; CREATE INDEX i ON t (x); COMMIT;") == []
    # `BEGIN` inside a DO body opens a PL/pgSQL block, not a transaction.
    assert _concurrent_index_inside_transaction(
        "DO $$ BEGIN PERFORM 1; END $$; CREATE INDEX CONCURRENTLY i ON t (x);"
    ) == []


def test_deploy_job_has_a_bounded_timeout():
    job = _deploy_job(_load_ci())
    minutes = job.get("timeout-minutes")
    assert isinstance(minutes, int) and 0 < minutes <= 60, (
        "deploy-backend needs `timeout-minutes` (<= 60). Without it a migration waiting on a lock "
        "holds the deploy for GitHub's 6 h default and the release never ships (2026-07-16)."
    )


def _executable(text: str) -> str:
    """Drop `#` comment lines so no assertion below can be satisfied by prose (YAML or shell)."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def _script() -> str:
    """The migration script's executable lines — its header documents every knob by name."""
    return _executable(APPLY_SCRIPT.read_text(encoding="utf-8"))


def test_migration_step_runs_only_the_shared_ledger_script():
    ci = _load_ci()
    step = _step(_deploy_job(ci), "Apply database migrations")
    assert "bash backend/scripts/apply_migrations.sh" in _executable(step["run"]), (
        "The deploy step must apply migrations by running backend/scripts/apply_migrations.sh — the "
        "one script the migrations-postgres CI job also runs (ADR-0007). Do not inline a psql loop."
    )
    # The script is the ONLY place migration SQL is executed. Deny-list regexes (`psql -f`, `psql …
    # migrations/`) were mutation-tested and let `-f"$f"`, `--file=`, `cat "$f" | psql`, `psql < "$f"`
    # and `psql -c "ALTER TABLE …"` through — so this is an allow-list: every EXECUTABLE ci.yml line
    # that mentions psql must be one of these two, verbatim (trimmed). Anything else fails, naming it.
    psql_lines = {
        line.strip() for line in _executable(CI_YML.read_text(encoding="utf-8")).splitlines() if "psql" in line
    }
    assert psql_lines == CI_PSQL_ALLOWLIST, (
        "ci.yml may invoke psql only to install it and to reset the CI ledger before pass 3; migration SQL "
        "runs through backend/scripts/apply_migrations.sh alone (ADR-0007).\n"
        f"  unexpected: {sorted(psql_lines - CI_PSQL_ALLOWLIST)}\n  missing: {sorted(CI_PSQL_ALLOWLIST - psql_lines)}"
    )


def test_apply_script_sets_lock_and_statement_timeouts_and_keeps_a_ledger():
    script = _script()
    for knob in ("lock_timeout=", "statement_timeout="):
        assert knob in script, (
            f"apply_migrations.sh must set `{knob}` on the psql session (via PGOPTIONS). "
            "`ALTER TABLE ... IF NOT EXISTS` takes ACCESS EXCLUSIVE before it checks; without a "
            "lock_timeout one open transaction parks the whole deploy."
        )
    assert "ON_ERROR_STOP=1" in script, "every psql call must fail the script on the first SQL error"
    assert f"CREATE TABLE IF NOT EXISTS {LEDGER_TABLE}" in script, "the script owns the ledger DDL (not create_all)"
    assert LEGACY_LEDGER_NAME not in script, (
        f"apply_migrations.sh must never reference `{LEGACY_LEDGER_NAME}`: prod has a legacy table of that name "
        "with a different shape, and CREATE TABLE IF NOT EXISTS silently adopted it on 2026-09-05 "
        f"(deploy failed on the missing sha256 column). The ledger is `{LEDGER_TABLE}`."
    )
    assert "ON CONFLICT (filename) DO UPDATE" in script, "an edited file (new sha256) must re-apply once and re-record"
    assert re.search(r"sha256sum|shasum -a 256", script), "ledger entries are keyed on the file's sha256"
    assert "skipped" in script and "applied=" in script, "the CI job asserts on the `applied=N skipped=M` summary line"
    bash = shutil.which("bash")
    assert bash, "bash is required to syntax-check the migration script"
    subprocess.run([bash, "-n", str(APPLY_SCRIPT)], check=True)  # fixed argv, no user input


def test_ci_gates_the_deploy_on_a_real_postgres_triple_apply():
    ci = _load_ci()
    job = ci["jobs"].get(MIGRATIONS_JOB)
    assert job, f"ci.yml needs a `{MIGRATIONS_JOB}` job: the unit suite runs on SQLite and never executes the SQL files"
    minutes = job.get("timeout-minutes")
    assert isinstance(minutes, int) and 0 < minutes <= 30, (
        f"{MIGRATIONS_JOB} needs `timeout-minutes` (<= 30): three passes against a fresh service container "
        "take ~5 min; a hung psql must not hold the PR gate for GitHub's 6 h default."
    )
    assert str(job["services"]["postgres"]["image"]).startswith("postgres:15"), "prod is Cloud SQL PostgreSQL 15"
    runs = [str(step.get("run", "")) for step in job["steps"]]
    passes = [run for run in runs if "backend/scripts/apply_migrations.sh" in run]
    assert len(passes) >= 3, (
        "The job must run apply_migrations.sh at least three times: seed the ledger, prove the skip "
        f"(applied=0), then reset the ledger and prove every file still re-runs (found {len(passes)})."
    )
    # `script | tee` under GitHub's default `bash -e {0}` (no pipefail) reports tee's exit status, so a
    # failing script would only be caught by the follow-up grep. Every pass must opt into pipefail
    # itself, or the job must declare `shell: bash` (which GitHub runs with `-eo pipefail`).
    # Matched on executable lines with an anchored `set -…o pipefail`: a comment saying "pipefail"
    # (mutation-tested) must not satisfy it.
    job_shell = (job.get("defaults") or {}).get("run", {}).get("shell")
    for run in passes:
        assert _SET_PIPEFAIL.search(_executable(run)) or job_shell == "bash", (
            "each pass step must `set -euo pipefail` (or the job must set defaults.run.shell: bash) so "
            "the script's failure fails the step even though its output is piped through tee"
        )
    # Full-set applies (seed, reset) and the skip pass each assert the exact summary line.
    all_applied = 'grep -qx "apply_migrations: applied=$N skipped=0"'
    none_applied = 'grep -qx "apply_migrations: applied=0 skipped=$N"'
    assert all_applied in passes[0] and all_applied in passes[2], "passes 1 and 3 must assert applied=$N skipped=0"
    assert none_applied in passes[1], "pass 2 must assert applied=0 skipped=$N"
    assert any(f"DELETE FROM {LEDGER_TABLE}" in run for run in runs), "the third pass must reset the ledger first"
    # The decoy must exist BEFORE the first pass so every pass proves the script ignores the legacy name.
    step_names = [str(step.get("name", "")) for step in job["steps"]]
    decoy = next((i for i, n in enumerate(step_names) if "decoy schema_migrations" in n), None)
    first_pass = next(i for i, run in enumerate(runs) if "backend/scripts/apply_migrations.sh" in run)
    assert decoy is not None and decoy < first_pass, (
        "migrations-postgres must plant a decoy `schema_migrations` table before pass 1 (prod has a legacy "
        "table of that name; the ledger must never adopt it)"
    )
    # A soft-failing gate is no gate.
    assert job.get("continue-on-error") is not True, "migrations-postgres must be blocking"
    assert all(step.get("continue-on-error") is not True for step in job["steps"]), "no step may soft-fail"
    assert MIGRATIONS_JOB in _deploy_job(ci)["needs"], (
        "deploy-backend must `needs:` the migrations-postgres job so a file that fails on real Postgres "
        "blocks the release instead of failing in the deploy step."
    )


def test_migration_retry_is_limited_to_lock_contention_sqlstates():
    # These lines moved from the ci.yml step into backend/scripts/apply_migrations.sh (ADR-0007);
    # the pins are unchanged and read the script's executable lines.
    run = _script()
    # psql prints SQLSTATE codes only under VERBOSITY=verbose; the retry must key on the codes in the
    # captured stderr, not on human-readable message text, and only for the contention class.
    assert re.search(r"psql\s.*-v VERBOSITY=verbose\s.*2>\"\$ERRLOG\"", run), (
        "psql must run with `-v VERBOSITY=verbose` and capture stderr to $ERRLOG"
    )
    assert "grep -qE '\\b(55P03|57014|40P01)\\b' \"$ERRLOG\"" in run, (
        "the retry decision must be exactly a SQLSTATE grep on the captured stderr (55P03 lock "
        "timeout, 57014 statement timeout, 40P01 deadlock) — update this pin deliberately"
    )
    # The blocker dump must show every backend (other roles' rows have NULL xact_start without
    # pg_read_all_stats) and name the locked relation via pg_locks ⨝ pg_class.
    assert "xact_start IS NOT NULL" not in run
    assert re.search(r"psql .*FROM pg_stat_activity", run), "dump must query pg_stat_activity"
    assert re.search(r"psql .*FROM pg_locks l JOIN pg_class c", run), "dump must join pg_locks to pg_class"


def _workflow_env_pin(workflow: dict, job: dict) -> tuple[str, str]:
    env = {**workflow.get("env", {}), **job.get("env", {})}
    return env.get("CLOUD_SQL_PROXY_VERSION", ""), env.get("CLOUD_SQL_PROXY_SHA256", "")


def test_cloud_sql_proxy_is_pinned_by_checksum_in_both_workflows():
    ci = _load_ci()
    ops = yaml.safe_load(OPS_YML.read_text(encoding="utf-8"))
    pins = []
    for workflow, job, step_name in (
        (ci, _deploy_job(ci), "Apply database migrations"),
        (ops, ops["jobs"]["ops"], "Start Cloud SQL proxy and export connection env"),
    ):
        version, sha = _workflow_env_pin(workflow, job)
        assert re.fullmatch(r"v\d+\.\d+\.\d+", version), f"CLOUD_SQL_PROXY_VERSION must be pinned (got {version!r})"
        assert re.fullmatch(r"[0-9a-f]{64}", sha), f"CLOUD_SQL_PROXY_SHA256 must be a sha256 hex digest (got {sha!r})"
        run = _executable(_step(job, step_name)["run"])
        assert '/${CLOUD_SQL_PROXY_VERSION}/cloud-sql-proxy.linux.amd64"' in run, (
            f"{step_name!r} must download the pinned CLOUD_SQL_PROXY_VERSION"
        )
        assert 'echo "${CLOUD_SQL_PROXY_SHA256}  cloud-sql-proxy" | sha256sum -c -' in run, (
            f"{step_name!r} must verify the download with `sha256sum -c` before chmod/exec"
        )
        pins.append((version, sha))
    assert len(set(pins)) == 1, f"ci.yml and ops.yml must pin the same cloud-sql-proxy build: {pins}"


_OPS_PREFLIGHT_EXEMPT = "describe-service describe-jobs logs-probe rollback-traffic"


def test_ops_workflow_is_dispatch_only_and_sets_lock_timeout():
    ops = yaml.safe_load(OPS_YML.read_text(encoding="utf-8"))
    job = ops["jobs"]["ops"]
    triggers = ops.get("on") or ops.get(True)  # PyYAML reads a bare `on:` key as boolean True
    assert set(triggers) == {"workflow_dispatch"}, (
        f"ops.yml must fire only from workflow_dispatch; its push trigger pointed at a branch that no "
        f"longer exists on origin (audit 2026-09). Found: {sorted(triggers)}"
    )
    # PGOPTIONS is scoped per step: the read-only detection snapshots full-scan financial_fact and
    # get a larger statement budget; the write path matches the deploy migration step exactly.
    proxy_run = _executable(_step(job, "Start Cloud SQL proxy and export connection env")["run"])
    assert "PGOPTIONS" not in proxy_run, "do not export PGOPTIONS globally — scope it per Cloud SQL step"
    for step_name, statement_timeout in (
        ("Run committed detection SQL (read-only snapshots)", "600s"),
        ("Run ticker repair script", "120s"),
    ):
        opts = (_step(job, step_name).get("env") or {}).get("PGOPTIONS", "")
        assert "-c lock_timeout=10s" in opts and f"-c statement_timeout={statement_timeout}" in opts, (
            f"{step_name!r} must set env PGOPTIONS with lock_timeout=10s and statement_timeout={statement_timeout} "
            f"(found {opts!r})"
        )
    # A prose "do not dispatch while a deploy is in flight" rotted into an incident risk; the job
    # must check for an in-flight main push itself (rule 12), with the exemption list pinned.
    step = _step(job, "Refuse to run while a main push (deploy) is in flight")
    assert step["if"] == f"${{{{ !contains('{_OPS_PREFLIGHT_EXEMPT}', steps.request.outputs.operation) }}}}"
    run = _executable(step["run"])
    assert re.search(r"gh run list .*--workflow ci\.yml --branch main --event push", run), (
        "pre-flight must list CI runs for pushes to main"
    )
    assert re.search(r'--status "\$1"', run) and "in_progress" in run and "queued" in run
    assert "exit 1" in run, "pre-flight must fail the run (exit 1) when a main push is in flight, not just warn"
    assert ops["permissions"].get("actions") == "read"


def test_lint_toolchain_is_installed_from_pinned_dev_requirements():
    # Only executable lines count — YAML comments may (and do) mention the anti-pattern by name.
    text = _executable(CI_YML.read_text(encoding="utf-8"))
    assert not re.search(r"pip install\s+(?:[^\n]*\s)?(?:ruff|bandit)\b", text), (
        "ci.yml must not `pip install ruff`/`bandit` unpinned — install from backend/requirements-dev.txt."
    )
    assert "backend/requirements-dev.txt" in text
    pins = {
        line.split("==")[0].strip(): line.split("==")[1].strip()
        for line in REQUIREMENTS_DEV.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for tool in ("ruff", "bandit"):
        assert tool in pins and re.fullmatch(r"\d+\.\d+\.\d+", pins[tool]), (
            f"requirements-dev.txt must pin {tool} to an exact version (found {pins.get(tool)!r})."
        )


def test_ruff_rule_set_is_selected_explicitly():
    lint = tomllib.loads(RUFF_TOML.read_text(encoding="utf-8")).get("lint", {})
    assert lint.get("select"), (
        "ruff.toml [lint] must set `select` explicitly. Inheriting ruff's defaults let a tool upgrade "
        "(0.16 widened them) turn a clean tree red with no code change."
    )


def test_migration_filenames_follow_the_convention():
    bad = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if not MIGRATION_NAME.match(p.name))
    assert not bad, f"Migration files must be named YYYYMMDD_snake_case.sql (sorted apply order): {bad}"


def _scan_migrations(detector: Callable[[str], list[str]]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        targets = detector(path.read_text(encoding="utf-8"))
        if targets:
            found[path.name] = targets
    return found


def _assert_frozen_allowlist(found: dict[str, list[str]], legacy: set[str], list_name: str, fix: str) -> None:
    unexpected = {name: tables for name, tables in found.items() if name not in legacy}
    assert not unexpected, f"{fix}\n  offending: {unexpected}"
    stale = legacy - set(found)
    assert not stale, (
        f"These files no longer trip the detector (or were removed) — delete them from {list_name} so "
        f"the allow-list only ever shrinks: {sorted(stale)}"
    )


def test_new_migrations_guard_alter_table_with_a_do_block():
    _assert_frozen_allowlist(
        _scan_migrations(_unguarded_alter_targets),
        LEGACY_UNGUARDED_ALTERS,
        "LEGACY_UNGUARDED_ALTERS",
        "New migration files must not issue a top-level ALTER TABLE on a pre-existing table — a ledger "
        "reset or an edit re-runs the file and `IF NOT EXISTS` still takes ACCESS EXCLUSIVE. Wrap it:\n"
        "  DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns\n"
        "      WHERE table_name = '<table>' AND column_name = '<col>') THEN\n"
        "    ALTER TABLE <table> ADD COLUMN <col> ...; END IF; END $$;",
    )


def test_new_migrations_guard_create_index_with_a_do_block():
    _assert_frozen_allowlist(
        _scan_migrations(_unguarded_index_targets),
        LEGACY_UNGUARDED_INDEXES,
        "LEGACY_UNGUARDED_INDEXES",
        "New migration files must not CREATE INDEX on a pre-existing table at top level — a ledger reset "
        "or an edit re-runs the file and Postgres takes a SHARE lock on the table before it evaluates "
        "`IF NOT EXISTS`. Wrap it:\n"
        "  DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '<name>') THEN\n"
        "    CREATE INDEX <name> ON <table> (...); END IF; END $$;\n"
        "or, for a large table, `CREATE INDEX CONCURRENTLY IF NOT EXISTS` OUTSIDE any BEGIN/COMMIT block.",
    )


def test_concurrent_index_is_never_inside_a_transaction_block():
    found = _scan_migrations(_concurrent_index_inside_transaction)
    assert not found, (
        "`CREATE INDEX CONCURRENTLY` cannot run inside a transaction block (Postgres SQLSTATE 25001) — "
        "the file would fail on EVERY deploy. Move the statement after `COMMIT;` (or drop the "
        f"BEGIN/COMMIT wrapper for that file). offending: {found}"
    )
