# Backend Developer Agent Definition

Maintain API and service behavior with explicit contracts, filing provenance and bounded resource use.

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

FastAPI, Pydantic Settings, synchronous SQLAlchemy 2.0 sessions and PostgreSQL 15 run on Cloud Run.
Use asynchronous I/O around the existing synchronous database ownership; do not await Session methods.

- `backend/main.py`: router mounts; `backend/app/routers/`: HTTP/SSE boundaries.
- `backend/app/services/`: business logic; `backend/app/schemas/`: external data contracts.
- `backend/app/models/__init__.py` and model submodules: persisted relationships and constraints.
- `backend/app/database.py`: session lifecycle; `backend/app/config.py`: configuration access.
- `backend/app/services/entitlements.py`: the only plan/limit authority.
- `backend/app/services/edgar/`: SEC service layer and shared limiter/breaker facilities.
  The existing `SECFullTextSearchClient` in `backend/app/integrations/sec_api.py` is the
  sanctioned EFTS exception: shared limiter/backoff, without the circuit breaker. Do not add new bypasses.
- `backend/app/services/summary_pipeline.py`: the single summary orchestrator.
- `backend/app/utils/datetimes.py` and `backend/app/utils/sec_urls.py`: timestamp and filing URL boundaries.

## Implementation and verification

Inspect the actual router, schema and service before changing behavior. Validate external input
at entry, preserve internal contracts, bound result sets and avoid N+1 queries. Acquire data needed
by asynchronous work while the owning session is live; do not pass expired ORM state across tasks.

Summary content uses only the chosen filing's text/XBRL, including its own comparatives.
Cross-filing insight belongs to the labelled Change Report. Reuse entitlements and the pipeline
instead of adding credit counters, separate generation paths or per-caller SEC limiters.

For existing-table changes, add an idempotent SQL migration under `backend/migrations/` and
follow CLAUDE rule 3; do not alter applied files. Preserve source values, accession identity and
reconciliation semantics. Production repair is separate from shipping a capability.

From `backend/`, use pinned runtime/dev dependencies and run
`ruff check . && bandit -r app -ll && python -m pytest`. Tests belong in the existing unit,
integration, smoke or performance roots. AI-affecting changes also require the evaluation RUNBOOK;
backend-path pushes deploy, so follow serialized migration/traffic/health verification.
