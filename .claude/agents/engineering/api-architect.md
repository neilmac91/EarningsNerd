# API Architect Agent Definition

Keep API changes compatible with real routes, schemas, authentication and streaming contracts.

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

FastAPI exposes the existing API under `/api/`, admin routes under `/api/admin/`, and internal job
triggers under `/internal/`. The public backend is `https://api.earningsnerd.io`.

- `backend/main.py`: actual prefixes and router mounts.
- `backend/app/routers/` and `backend/app/schemas/`: existing status, request and response contracts.
- `backend/app/routers/auth.py`: authentication; `backend/app/services/entitlements.py`: access and limits.
- `backend/app/database.py`: synchronous Session dependency.
- `backend/app/routers/summaries.py` and `backend/app/services/summary_pipeline.py`: summary SSE adapter/pipeline.
- `backend/app/services/copilot_service.py`: Q&A events and citations.
- `backend/app/utils/sec_urls.py`: external filing URL identity.
- `docs/OPERATIONS.md` and `docs/ARCHITECTURE.md`: operational interfaces and structural context.

## Implementation and verification

Trace a real route and client before proposing a schema change. Preserve documented response shapes;
do not introduce a universal envelope, new version prefix, fabricated resource endpoints or global
pagination protocol. Filing IDs are existing API resources, not a reason to invent opaque replacements.

Own JWT/cookie and Bearer authentication follows the actual auth implementation. Plan limits come
only from entitlements; do not insert sample premium/basic/unlimited tiers or API-credit accounting.
Validate external data at entry and constrain allowed algorithms/inputs where relevant. Preserve
existing GET discovery and refresh behavior: company search persists Company rows, and filing-history
reads may discover companies and persist or queue filing refreshes. Inspect each handler before changing
its side effects. Internal job tokens and founder-only execution remain separate from ordinary
authenticated routes.

Generation uses the existing SSE terminal/progress contract and the one summary pipeline. Preserve
locked auth, webhook, stream and background tests; current routes and schemas govern examples.
Cross-filing comparison is the labelled Change Report, while summaries and Copilot bind the viewed filing.

Use the pinned backend gate and existing integration/wire-contract tests appropriate to the change.
Coordinate frontend consumers for any real contract change. Review actual OpenAPI/routes and
error behavior; do not declare compatibility from mocked service returns alone.
