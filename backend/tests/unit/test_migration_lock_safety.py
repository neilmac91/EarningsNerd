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

2. The lint toolchain must be pinned. `pip install ruff` in CI let ruff 0.16's wider default rule set
   turn a clean tree into 2,767 findings with no code change (lessons/ops-pin-ci-toolchain.md). CI
   must install from `backend/requirements-dev.txt` with exact pins, and `ruff.toml` must select its
   rules explicitly.

Deliberately OUTSIDE this gate: plain `CREATE INDEX IF NOT EXISTS` on a pre-existing table. Postgres
opens the relation with a SHARE lock before the existence check, so the ~43 re-applied index statements
still queue behind any open writer; they are bounded only by the psql `lock_timeout`. Extending the gate
(a second frozen legacy list, `CONCURRENTLY` for new files) is tracked with the migration-ledger
decision in `tasks/todo.md`.

Everything here is text-level and runs in the hermetic unit suite (no Postgres needed).
"""
import re
import tomllib
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
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


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"/\*.*?\*/", "", sql, flags=re.S)


def _norm(ident: str) -> str:
    return ident.replace('"', "").lower()


def _unguarded_alter_targets(sql: str) -> list[str]:
    """Tables hit by an ALTER TABLE that will take ACCESS EXCLUSIVE on every re-apply.

    Counts: top-level ALTERs (split on `;`, so several statements on one line are all seen) and
    ALTERs inside a DO body that has no catalog/subquery existence check. Ignores tables the same
    file CREATEs (a brand-new table has no readers to block).
    """
    sql = _strip_comments(sql)
    do_bodies = [m.group(2) for m in _DO_BLOCK.finditer(sql)]
    top = _DO_BLOCK.sub(" ", sql)
    created = {_norm(m) for m in _CREATE.findall(top)}
    altered: set[str] = set()
    for statement in top.split(";"):
        altered.update(_norm(m) for m in _ALTER.findall(statement))
    for body in do_bodies:
        if _ALTER.search(body) and not _GUARD.search(body):
            altered.update(_norm(m) for m in _ALTER.findall(body))
    return sorted(t for t in altered if t not in created)


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
    # Quoted identifiers and two statements on one line are both seen.
    assert _unguarded_alter_targets('ALTER TABLE "public"."users" ADD COLUMN x INT;') == ["public.users"]
    assert _unguarded_alter_targets("CREATE INDEX IF NOT EXISTS i ON t (x); ALTER TABLE t ADD COLUMN y INT;") == ["t"]
    # Comments never count.
    assert _unguarded_alter_targets("-- ALTER TABLE users ADD COLUMN x INT;\nSELECT 1;") == []


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


def test_new_migrations_guard_alter_table_with_a_do_block():
    found: dict[str, list[str]] = {}
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        targets = _unguarded_alter_targets(path.read_text(encoding="utf-8"))
        if targets:
            found[path.name] = targets

    unexpected = {name: tables for name, tables in found.items() if name not in LEGACY_UNGUARDED_ALTERS}
    assert not unexpected, (
        "New migration files must not issue a top-level ALTER TABLE on a pre-existing table — every "
        "file is re-applied on EVERY deploy and `IF NOT EXISTS` still takes ACCESS EXCLUSIVE. Wrap it:\n"
        "  DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM information_schema.columns\n"
        "      WHERE table_name = '<table>' AND column_name = '<col>') THEN\n"
        "    ALTER TABLE <table> ADD COLUMN <col> ...; END IF; END $$;\n"
        f"  offending: {unexpected}"
    )

    stale = LEGACY_UNGUARDED_ALTERS - set(found)
    assert not stale, (
        "These files no longer issue an unguarded ALTER TABLE (or were removed) — delete them from "
        f"LEGACY_UNGUARDED_ALTERS so the allow-list only ever shrinks: {sorted(stale)}"
    )
