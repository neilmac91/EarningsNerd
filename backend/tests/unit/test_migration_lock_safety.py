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

2. The lint toolchain must be pinned. `pip install ruff` in CI let ruff 0.16's wider default rule set
   turn a clean tree into 2,767 findings with no code change (lessons/ops-pin-ci-toolchain.md). CI
   must install from `backend/requirements-dev.txt` with exact pins, and `ruff.toml` must select its
   rules explicitly.

Known limit, by design: a table the same file CREATEs is exempt from both detectors, yet on deploy
N+1 that table exists and its `CREATE INDEX IF NOT EXISTS` statements (32 today) still take SHARE
locks. The migration ledger (WS-2, ADR-0007) removes re-application altogether and is the fix for
that class; this gate stops the set of re-run lock acquisitions from growing until then.

Everything here is text-level and runs in the hermetic unit suite (no Postgres needed).
"""
import re
import tomllib
from collections.abc import Callable
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
OPS_YML = REPO_ROOT / ".github" / "workflows" / "ops.yml"
MIGRATIONS_DIR = BACKEND_DIR / "migrations"
REQUIREMENTS_DEV = BACKEND_DIR / "requirements-dev.txt"
RUFF_TOML = BACKEND_DIR / "ruff.toml"

MIGRATION_NAME = re.compile(r"^\d{8}_[a-z0-9_]+\.sql$")

# Legacy files that issue a top-level ALTER TABLE on a table they did not create. They stay
# re-applied every deploy (rule 3) and are protected only by the psql lock_timeout. Do NOT add to
# this set: new files must use the DO-block guard. Remove an entry when its file is rewritten.
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
# name, group(3) = table.
_CREATE_INDEX = re.compile(
    r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+(CONCURRENTLY\s+)?(?:IF\s+NOT\s+EXISTS\s+)?"
    + _IDENT
    + r"\s+ON\s+(?:ONLY\s+)?"
    + _IDENT,
    re.I,
)


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
    statements on one line are all seen) and matches inside a DO body that has no catalog/subquery
    existence check. Ignores tables the same file CREATEs (a brand-new table has no readers to
    block) and matches `table_of` maps to None (the sanctioned form, e.g. CONCURRENTLY).
    """
    sql = _strip_comments(sql)
    do_bodies = [m.group(2) for m in _DO_BLOCK.finditer(sql)]
    top = _DO_BLOCK.sub(" ", sql)
    created = {_norm(m) for m in _CREATE.findall(top)}
    hit = {table_of(m) for m in statement.finditer(top)}
    for body in do_bodies:
        if statement.search(body) and not _GUARD.search(body):
            hit.update(table_of(m) for m in statement.finditer(body))
    return sorted(t for t in hit if t and t not in created)


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
    assert _unguarded_index_targets("-- CREATE INDEX i ON users (x);\nSELECT 1;") == []


def test_deploy_job_has_a_bounded_timeout():
    job = _deploy_job(_load_ci())
    minutes = job.get("timeout-minutes")
    assert isinstance(minutes, int) and 0 < minutes <= 60, (
        "deploy-backend needs `timeout-minutes` (<= 60). Without it a migration waiting on a lock "
        "holds the deploy for GitHub's 6 h default and the release never ships (2026-07-16)."
    )


def test_migration_step_sets_lock_and_statement_timeouts():
    step = _step(_deploy_job(_load_ci()), "Apply database migrations")
    run = step["run"]
    for knob in ("lock_timeout=", "statement_timeout="):
        assert knob in run, (
            f"The migration step must set `{knob}` on the psql session (via PGOPTIONS). "
            "`ALTER TABLE ... IF NOT EXISTS` takes ACCESS EXCLUSIVE before it checks; without a "
            "lock_timeout one open transaction parks the whole deploy."
        )
    assert "psql" in run and "backend/migrations/*.sql" in run


def test_migration_retry_is_limited_to_lock_contention_sqlstates():
    run = _step(_deploy_job(_load_ci()), "Apply database migrations")["run"]
    # psql prints SQLSTATE codes only under VERBOSITY=verbose; the retry must key on the codes, not
    # on human-readable message text, and must be limited to the contention class.
    assert "VERBOSITY=verbose" in run, "psql must run with -v VERBOSITY=verbose so SQLSTATEs reach stderr"
    for code in ("55P03", "57014"):
        assert code in run, f"retry must match SQLSTATE {code} in captured psql stderr"
    assert re.search(r"grep\s+-[A-Za-z]*E[A-Za-z]*\s+'[^']*55P03[^']*'", run), (
        "the retry decision must be a grep on the captured stderr for the SQLSTATE codes"
    )
    # The blocker dump must show every backend (other roles' rows have NULL xact_start without
    # pg_read_all_stats) and name the locked relation via pg_locks.
    assert "xact_start IS NOT NULL" not in run
    assert "pg_stat_activity" in run and "pg_locks" in run and "pg_class" in run


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
        run = _step(job, step_name)["run"]
        assert "sha256sum -c" in run, f"{step_name!r} must verify the download with `sha256sum -c`"
        assert "CLOUD_SQL_PROXY_VERSION" in run and "CLOUD_SQL_PROXY_SHA256" in run
        pins.append((version, sha))
    assert len(set(pins)) == 1, f"ci.yml and ops.yml must pin the same cloud-sql-proxy build: {pins}"


def test_ops_workflow_is_dispatch_only_and_sets_lock_timeout():
    ops = yaml.safe_load(OPS_YML.read_text(encoding="utf-8"))
    triggers = ops.get("on") or ops.get(True)  # PyYAML reads a bare `on:` key as boolean True
    assert set(triggers) == {"workflow_dispatch"}, (
        f"ops.yml must fire only from workflow_dispatch; its push trigger pointed at a branch that no "
        f"longer exists on origin (audit 2026-09). Found: {sorted(triggers)}"
    )
    run = _step(ops["jobs"]["ops"], "Start Cloud SQL proxy and export connection env")["run"]
    for knob in ("lock_timeout=", "statement_timeout="):
        assert knob in run, f"ops.yml Cloud SQL sessions must set `{knob}` (PGOPTIONS), same as the deploy step"
    assert "PGOPTIONS" in run
    # A prose "do not dispatch while a deploy is in flight" rotted into an incident risk; the job
    # must check for an in-flight main push itself (rule 12).
    step = _step(ops["jobs"]["ops"], "Refuse to run while a main push (deploy) is in flight")
    assert "workflow" in step["run"] and "ci.yml" in step["run"] and "in_progress" in step["run"]
    assert ops["permissions"].get("actions") == "read"


def test_lint_toolchain_is_installed_from_pinned_dev_requirements():
    # Only executable lines count — YAML comments may (and do) mention the anti-pattern by name.
    text = "\n".join(
        line for line in CI_YML.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#")
    )
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
        "New migration files must not issue a top-level ALTER TABLE on a pre-existing table — every "
        "file is re-applied on EVERY deploy and `IF NOT EXISTS` still takes ACCESS EXCLUSIVE. Wrap it:\n"
        "  DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns\n"
        "      WHERE table_name = '<table>' AND column_name = '<col>') THEN\n"
        "    ALTER TABLE <table> ADD COLUMN <col> ...; END IF; END $$;",
    )


def test_new_migrations_guard_create_index_with_a_do_block():
    _assert_frozen_allowlist(
        _scan_migrations(_unguarded_index_targets),
        LEGACY_UNGUARDED_INDEXES,
        "LEGACY_UNGUARDED_INDEXES",
        "New migration files must not CREATE INDEX on a pre-existing table at top level — the file is "
        "re-applied on EVERY deploy and Postgres takes a SHARE lock on the table before it evaluates "
        "`IF NOT EXISTS`. Wrap it:\n"
        "  DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = '<name>') THEN\n"
        "    CREATE INDEX <name> ON <table> (...); END IF; END $$;\n"
        "or, for a large table, `CREATE INDEX CONCURRENTLY IF NOT EXISTS` OUTSIDE any BEGIN/COMMIT block.",
    )
