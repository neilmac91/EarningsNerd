# CLAUDE.md — EarningsNerd

AI-powered SEC filing analysis: 10-K/10-Q → grounded, filing-only summaries for investors
(EDGAR + XBRL + LLM). Solo-founder project — optimize for maintainability, small diffs, and
verified behavior.

**Stack:** FastAPI + sync SQLAlchemy 2.0 + PostgreSQL 15 on Cloud Run | Next.js 16 (App Router) +
TypeScript + Tailwind + React Query on Vercel | AI via OpenAI-compatible client (default
`deepseek-flash` via `https://api.deepseek.com/v1`; env-configurable via `OPENAI_BASE_URL` +
`AI_DEFAULT_MODEL`) | Stripe, Resend, PostHog + Vercel Analytics, Sentry. Redis is dev-only;
prod runs the L1 in-memory cache (ADR-0004).

## Read by task — nothing else is mandatory

- Every session: this file, then the `lessons/README.md` sections for your task area (skip
  "Enforced by a machine gate"; CI fails those on its own).
- Continuing a plan or release: `tasks/todo.md`, the short open-items file. Handovers and the
  ledger under `tasks/archive/` are history; open them only when an open item points there.
- Boundaries or data flow: `docs/ARCHITECTURE.md`. Settled decisions: `docs/adr/` — supersede
  with a new ADR, don't re-litigate.
- Prompt, model, eval or AI-flag change: `backend/evals/RUNBOOK.md` — "Regression gate (B1)" and
  "Judging a pull request's eval artifact" are MANDATORY, "Gotchas" before any paid run, plus the
  section for the surface you touch (Copilot citation-fidelity audit, Multi-Period Analysis
  gate, FPI adoption gate).
- UI work: rule 11 applies (read `DESIGN.md` and `frontend/DESIGN_SYSTEM.md`). The rules live in
  `DESIGN_SYSTEM.md` §1–§6 and §12 and in `DESIGN.md` from "Overview" on; `DESIGN.md`'s frontmatter
  is the token snapshot that `frontend/tailwind.config.js` already defines, and `DESIGN_SYSTEM.md`
  §7–§11 cover marketing, theme mechanics, exemptions, charts and motion — read those for such a
  change. Link both files in UI subagent briefs.
- Operating model (what pauses for the founder, verification proportionality, review tiers,
  model per agent stage, deploy discipline, handover format): `AGENTS.md` §3–§7. Reference: `docs/CONFIGURATION.md`, `docs/OPERATIONS.md`,
  `docs/TROUBLESHOOTING.md`, `docs/DEPLOYMENT.md`.

## Design documentation

`DESIGN.md` and `frontend/DESIGN_SYSTEM.md` are documentation; the token sources and components
take precedence ([precedence](AGENTS.md#2-precedence-when-documents-conflict)). When a change
affects documented tokens, typography, reusable component states or visual conventions, load the
`design-docs-maintenance` skill and refresh the docs and sidecar together in that PR.

## Commands

Backend (from `/backend`):
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000   # Dev server
pip install -r requirements-dev.txt                    # Pinned lint toolchain (same as CI)
ruff check . && bandit -r app -ll && python -m pytest  # FULL local gate — run before every push
python -m pytest -m ""                                 # Also the performance suite (real sleeps)
python3 scripts/deploy_check.py                        # Pre-deploy validation
```

Frontend (from `/frontend`):
```bash
npm run dev                   # Dev server (http://localhost:3000)
npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run && npm run build  # FULL gate
npm run test:e2e              # Playwright (CI runs these against `next start` with NO backend)
```

Infra: `docker-compose up -d postgres redis` (local only — prod has no Redis).

## Non-negotiable rules

1. **One summary orchestrator.** `app/services/summary_pipeline.py::stream_filing_summary` is the
   only generation pipeline; the SSE endpoint and the background/cron path
   (`generate_summary_background`) both consume it. Never add a second generation path.
2. **Filing-only summaries.** User-visible summary content derives ONLY from the filing the user
   chose (its own text + its own XBRL, which carries prior-period comparatives). Never inject
   other filings' content into the prompt or output. Cross-filing insight belongs to the labeled
   surface: the Change Report (`GET /api/summaries/filing/{id}/what-changed`). The old `/api/compare`
   route was retired (smoke test `test_compare_router_is_gone` locks it at 404).
3. **Migrations: no Alembic.** Fresh-DB schema via `create_all` at startup +
   `ensure_additive_columns` self-heals additive columns. Any change to an existing table = a new
   idempotent SQL file in `backend/migrations/`. The deploy applies each file ONCE per
   (filename, sha256) through the `migration_ledger` table (`backend/scripts/apply_migrations.sh`,
   ADR-0007) and skips it afterwards — but files must still be safe to re-run (ledger reset, edited
   file, crash between apply and record; CI proves it with a triple pass on `postgres:15`). Never
   edit an applied migration — an edit re-applies it once; that is the escape hatch, not a workflow.
   Idempotent is not lock-free: `ALTER TABLE … IF NOT EXISTS` still takes ACCESS EXCLUSIVE, so new
   files wrap ALTERs on existing tables in a `DO $$ … IF NOT EXISTS … $$` guard (gate:
   `tests/unit/test_migration_lock_safety.py`; `lessons/ops-migrations-need-lock-timeout.md`).
4. **Entitlements:** `app/services/entitlements.py` is the ONLY source of plan truth. Never
   hardcode plan limits or Pro checks elsewhere.
5. **SEC calls:** use the existing SEC service/transport paths and shared rate limiter.
   `app/services/edgar/` provides breaker-wrapped fetches and deliberately breaker-exempt local
   parsing. Existing raw-HTTP paths outside it — `SECFullTextSearchClient` in
   `app/integrations/sec_api.py` and companyfacts fetching in `app/services/facts_service.py` —
   use the shared limiter/backoff without the breaker. The in-layer XBRL companyfacts fallback
   also uses the limiter without the breaker, with a single token wait. Preserve these existing
   transport owners: do not add raw-HTTP SEC bypasses outside them, even if paced. Do not assume
   every existing call uses the breaker. SEC's cap is 10 req/s per IP;
   limiter state is per-process (API service + Cloud Run jobs each carry their own bucket).
   `tests/unit/test_sec_gov_importers_allowlist.py` bounds `sec.gov` URL literals and keeps the
   URL-builder/Settings exemptions free of HTTP imports; it does not prove dynamic call routing.
   See `lessons/sec-edgar-resilience-layer.md` for existing-path and diagnostic limitations.
6. **Contract tests are locked.** The SSE stream contract, background-generation
   characterization, auth flow, and Stripe webhook tests may be edited ONLY to delete references
   to symbols deleted in the same PR, or under a pre-approved, PR-body-documented contract change.
   Anything else: stop and surface it first.
7. **datetime:** timezone-aware UTC via `app/utils/datetimes.py` (`utcnow()`, `iso_z()`); never
   `datetime.utcnow()`. The ONLY sanctioned naive sites are the 6 token-expiry call sites enforced
   by `backend/tests/unit/test_naive_utcnow_allowlist.py` (naive by design — SQLite/Postgres parity).
   Serialized timestamps use `iso_z()`; never hand-append `"Z"`.
8. **Config:** all env access through `app/config.py` Settings; never `os.getenv` in app code.
   Sole sanctioned exception: pre-Settings infra-bootstrap constants in `database.py`,
   `redis_service.py`, and `edgar/config.py` (pool sizes, EDGAR identity) plus `Settings.__init__`
   itself — enforced by `tests/unit/test_os_getenv_allowlist.py`.
9. **Boundaries:** validate external data where it enters (SEC responses, Stripe webhooks, AI
   output); do NOT re-validate internally-produced data downstream.
10. **Data integrity:** `Filing.sec_url`/`document_url` are NOT NULL (event-listener enforced;
    the listener raises rather than fabricating a URL when the Company isn't loaded). URL format:
    `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/` with CIK leading zeros stripped
    and accession dashes removed — build it ONLY with `app/utils/sec_urls.py` (see
    `lessons/sec-filing-url-format.md`; tests in `tests/unit/test_filing_url_listeners.py`).
11. **Design system:** read `DESIGN.md` and `frontend/DESIGN_SYSTEM.md` before UI work and apply
    the [design-document maintenance guidance](#design-documentation) when the documented system changes.
    Any theme/token change is app-wide (public + authed). Done-gate = the legacy-color grep in
    `frontend/DESIGN_SYSTEM.md` returns nothing AND both themes verified on preview.
    Dialogs only via `ui/Modal`; z from the ladder; eyebrows = `tracking-eyebrow`; chip/delta text = the
    700-level tokens; page bg = `background`, cards = `panel`, on every route. Gates: the design rules in
    `frontend/eslint.config.mjs` (raw hex/palette, `z-[N]`, off-ramp tracking, sub-scale type, `alert`)
    `tests/unit/dialogAllowlist.spec.ts` and `tests/unit/bottomChromeLadder.spec.ts` (no fixed bottom chrome
    outranks the workspace layers; the consent bar's inset); the 700-level and surface clauses are review-checked.
12. **Rules become gates.** When a review or plan produces a "never do X again" rule, land the
    machine enforcement in the same PR (ESLint rule, allowlist spec, AST test, CI grep). Prose-only
    rules rot — see `lessons/arch-structural-gates-over-prose-rules.md`.

## Where things live

- **Backend:** `app/routers/` = HTTP only; `app/services/` = business logic; `services/ai/` = AI
  internals behind the `openai_service.py` façade; `services/edgar/` = SEC service layer (rule 5);
  `app/integrations/` = third-party APIs (finnhub/fmp/stocktwits were torn down in #657;
  `test_dead_integrations_allowlist.py` keeps them gone). Map: `docs/ARCHITECTURE.md`.
- **Frontend:** `features/<domain>/` = domain code; `components/` = `ui/` + app chrome ONLY
  (`componentsAllowlist.spec.ts`); query keys from `lib/queryKeys.ts` (ESLint-enforced); all HTTP
  through `lib/api/client.ts` (raw `fetch` only for SSE readers and Next ISR/server fetches);
  blob downloads via `lib/downloadBlob.ts`.
- **Tests:** `backend/tests/{unit,integration,smoke,performance}` (conftest sets a hermetic mock
  env incl. `SKIP_REDIS_INIT=true` — patch `settings`, not env vars) and `frontend/tests/{unit,e2e}`.
  NO other test roots — a test outside these does not run in CI (gate:
  `frontend/tests/unit/testHomesAllowlist.spec.ts`; its one exemption is the hash-sealed judging
  fixture pinned by a `code-sha256.json` in its package; offline proof run by the operator, not CI).
- **Scripts:** one-offs in `backend/scripts/` with a docstring header; nothing executable at repo
  root. **Open items** → `tasks/todo.md`; finished work and the ledger → `tasks/archive/`;
  **lessons** → `lessons/` (one file per rule, never a monolith); **prompts** → `backend/prompts/*.md`.
  Founder deliberations (pricing, fundraising, strategy, council transcripts) never enter this
  public repository (`AGENTS.md` §7).

## API conventions & code style

- Routes are `/api/`-prefixed (admin `/api/admin/`, cron triggers `/internal/`); JWT via
  `Authorization: Bearer`; long-running generation streams over SSE; Pydantic-validated JSON.
- Python: type hints required, async for I/O, no raw SQL (SQLAlchemy ORM only).
  TypeScript: strict mode, interfaces for API responses.

## Deploy

CI (`.github/workflows/ci.yml`): ruff + bandit + pytest; eslint + tsc + vitest; Playwright with NO
backend; `eval-baseline` compares AI output against `backend/evals/baseline_scores.json` (advisory:
`continue-on-error`, not a required check).
`deploy-backend` runs on push to main when `backend/` changed outside `backend/tests/` (migrations
through the `migration_ledger`, Cloud Run `earningsnerd-backend` in `earnings-nerd`/us-west1, job
images); a failed deploy is not retried, so check its conclusion after every such merge. Vercel
deploys the frontend on push to main (`docs/DEPLOYMENT.md`). Manual bootstrap:
`tasks/gcp-deploy-runbook.md`.

## Workflow

- **Review by risk tier** (`AGENTS.md` §5): records-only PRs get one Sonnet lens; routine code one
  Opus lens; high-risk paths (summary pipeline, Copilot, prompts, evals, entitlements and billing,
  auth, migrations and schema, SEC fetching, config, CI and deploy files, settings and workflows)
  keep the full adversarial review. Every agent stage names its model there; never put a subagent
  on the session's premium model by default. Unsure of the tier: review as high.
- **Plan** briefly when work has real dependencies or architectural choices; resolve routine
  implementation choices directly and re-plan when evidence changes the approach; record open
  items in `tasks/todo.md`, one line each. Ask only when a decision needs founder input; otherwise
  carry authorized work through implementation, verification (`AGENTS.md` §4) and fixes,
  preserve explicit approval and release boundaries, and report any blocker precisely.
- **Delegate** bounded independent work when parallelism or context isolation helps, naming the
  model (`AGENTS.md` §5). The briefs under `.claude/agents/` are reading material, not subagents.
- **After ANY user correction**, add or update a file in `lessons/` (format in its README).
- **Bugs:** fix the root cause — no temporary patches. **Better approach:** say so first (2-4
  tradeoff bullets), then proceed unless the alternative avoids serious risk; for non-trivial
  changes ask "is there a more elegant way?" without over-engineering. **Docs vs code:** code
  is truth — fix the doc in the same PR. Skills: `.claude/skills/README.md`; `karpathy-guidelines`
  is the baseline (Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution).
