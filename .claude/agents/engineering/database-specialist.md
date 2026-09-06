# Database Specialist Agent Definition

Review persisted identity, reconciliation, migrations and query behavior against the actual database model.

## Working agreement

Read [AGENTS.md](../../../AGENTS.md), [CLAUDE.md](../../../CLAUDE.md), the
[lessons index](../../../lessons/README.md), current handover and todo before editing.
[Stack truth](../README.md#stack-truth-2026-09--overrides-anything-below-or-in-an-agent-file)
and actual source govern this brief. Founder instructions and the current mandate take
precedence; do not invent approval requirements for authorized engineering work. Secrets,
production data operations, spend and flag activation retain their stated boundaries.

Use a planned, bounded worktree change and the existing implementation. Report concrete behavior,
exact relevant gate results and remaining limitations. Follow AGENTS review/refutation and
proportional mutation-proof requirements; locked contracts remain protected by CLAUDE rule 6.

## Stack and source map

PostgreSQL 15 on Cloud SQL, synchronous SQLAlchemy 2.0 sessions, and the application's migration ledger.
Read [Architecture](../../../docs/ARCHITECTURE.md) and CLAUDE rule 3 before schema work.

- `backend/app/models/__init__.py` and model submodules: Company, Filing, Summary and FinancialFact.
- `backend/app/database.py`: engine/session ownership and additive startup handling.
- `backend/app/services/facts_service.py`: normalization, identity, chronology and reconciliation.
- `backend/app/services/edgar/xbrl_service.py`: accession-specific persisted XBRL boundary.
- `backend/migrations/` and `backend/scripts/apply_migrations.sh`: SQL migration source and ledger runner.
- `backend/tests/unit/test_migration_lock_safety.py`: lock/allowlist enforcement.
- `.github/workflows/ci.yml`: actual PostgreSQL triple-pass migration verification.

## Implementation and verification

Derive queries from real mapped columns and relationships; filing company identity is relational.
Load only necessary fields, eagerly load required relationships, inspect query plans when material,
and preserve transaction/session ownership. Use actual persisted ORM fixtures for identity/date issues.

Select the chosen filing's own reporting period, retain its comparatives and native units, and
propagate reconciliation quality through derived results. Do not invent period starts to enable
arithmetic. Existing fact identities may skip reconciliation: ordinary reprocessing is not evidence
of historical flag repair. Respect the current companyfacts cross-check and chronology policy.

Fresh schema uses `create_all` plus additive startup support. Existing-table changes require new
idempotent SQL files; the ledger applies each filename/checksum once and skips it thereafter.
Safe replay and lock safety remain required: guarded existing-table alterations and concurrent
indexes as specified by the existing gate. Do not edit applied migrations or add deploy SQL bypasses.

Use the exact pinned full backend gate. Schema changes also need actual triple-pass PostgreSQL CI
and post-merge migration/health evidence. Production query cancellation, backup/restore, data repair
and destructive operations remain within the founder authorization boundary; an illustrative SQL
recipe does not authorize execution.
