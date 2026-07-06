# CLAUDE.md — EarningsNerd

AI-powered SEC filing analysis: 10-K/10-Q → grounded, filing-only summaries for investors
(EDGAR + XBRL + LLM). Solo-founder project — optimize for maintainability, small diffs, and
verified behavior.

**Stack:** FastAPI + sync SQLAlchemy 2.0 + PostgreSQL 15 on Cloud Run | Next.js 16 (App Router) +
TypeScript + Tailwind + React Query on Vercel | AI via OpenAI-compatible client (default
`deepseek-v4-pro` via `https://api.deepseek.com/v1`; env-configurable via `OPENAI_BASE_URL` +
`AI_DEFAULT_MODEL`) | Stripe, Resend, PostHog, Sentry. Redis is dev-only; prod runs the L1
in-memory cache (ADR-0004).

## Read before working

- `lessons/README.md` — hard-won operating rules, one file each. Scan the index; open what applies.
- `docs/adr/` — settled decisions (Cloud Run, edgartools, Redis-off-in-prod, React 18,
  DeepSeek supersedes Gemini). Don't re-litigate; supersede with a new ADR.
- `docs/ARCHITECTURE.md` — system map (services, routers, data model, patterns).
- `frontend/DESIGN_SYSTEM.md` — MANDATORY before any UI work; link it in subagent briefs.
- `backend/evals/RUNBOOK.md` — MANDATORY before changing prompts, models, or AI flags.
- Reference detail lives in `docs/CONFIGURATION.md` (env vars), `docs/OPERATIONS.md`
  (health/metrics/runbook/admin), `docs/TROUBLESHOOTING.md`, `docs/DEPLOYMENT.md`.

## Commands

Backend (from `/backend`):
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000   # Dev server
ruff check . && bandit -r app -ll && python -m pytest  # FULL local gate — run before every push
python -m pytest              # Fast lane: pytest.ini deselects performance (real sleeps)
python -m pytest -m ""        # Everything, including the performance suite
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
   surfaces: Change Report and `/api/compare`.
3. **Migrations: no Alembic.** Fresh-DB schema via `create_all` at startup +
   `ensure_additive_columns` self-heals additive columns. Any change to an existing table = a new
   idempotent SQL file in `backend/migrations/` — CI re-applies ALL files on every deploy, so every
   file must stay safe to re-run forever. Never edit an applied migration.
4. **Entitlements:** `app/services/entitlements.py` is the ONLY source of plan truth. Never
   hardcode plan limits or Pro checks elsewhere.
5. **SEC calls:** all sec.gov traffic goes through the edgar service layer
   (`app/services/edgar/` — rate limiter + circuit breaker). Never raw httpx to sec.gov outside
   it. SEC's cap is 10 req/s per IP; limiter state is per-process, so every new call path outside
   the layer raises ban risk (API service + Cloud Run jobs each carry their own bucket).
6. **Contract tests are locked.** The SSE stream contract, background-generation
   characterization, auth flow, and Stripe webhook tests may be edited ONLY to delete references
   to symbols deleted in the same PR, or under a pre-approved, PR-body-documented contract change.
   Anything else: stop and surface it first.
7. **datetime:** timezone-aware UTC via `app/utils/datetimes.py` (`utcnow()`, `iso_z()`); never
   `datetime.utcnow()`. The ONLY sanctioned naive sites are the 6 token-expiry columns enforced by
   `backend/tests/unit/test_naive_utcnow_allowlist.py` (naive by design — SQLite/Postgres parity).
   Serialized timestamps use `iso_z()`; never hand-append `"Z"`.
8. **Config:** all env access through `app/config.py` Settings; never `os.getenv` in app code.
9. **Boundaries:** validate external data where it enters (SEC responses, Stripe webhooks, AI
   output); do NOT re-validate internally-produced data downstream.
10. **Data integrity:** `Filing.sec_url`/`document_url` are NOT NULL (event-listener enforced).
    URL format: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/` with CIK leading
    zeros stripped and accession dashes removed (see `lessons/sec-filing-url-format.md`).
11. **Design system:** any theme/token change is app-wide (public + authed). Done-gate = the
    legacy-color grep in `DESIGN_SYSTEM.md` returns nothing AND both themes verified on preview.
12. **Rules become gates.** When a review or plan produces a "never do X again" rule, land the
    machine enforcement in the same PR (ESLint rule, allowlist spec, AST test, CI grep). Prose-only
    rules rot — see `lessons/arch-structural-gates-over-prose-rules.md`.

## Where things live

- **Backend:** `app/routers/` = HTTP only; `app/services/` = business logic. `services/ai/` holds
  the AI internals (extraction, json_repair, section_recovery, markdown_render, xbrl_narrative,
  copilot_chat, …) behind the `openai_service.py` façade. `services/edgar/` owns all SEC traffic.
  `app/integrations/` = third-party APIs (finnhub, fmp, stocktwits, alpha_vantage, sec_api).
- **Frontend:** `features/<domain>/` = domain code (api/ + components/ + hooks/).
  `components/` = `ui/` + app chrome ONLY (enforced by `componentsAllowlist.spec.ts`). Query keys
  come from `lib/queryKeys.ts` (ESLint-enforced — no inline key arrays). All HTTP goes through the
  shared axios client (`lib/api/client.ts`); raw `fetch` is sanctioned only for SSE readers and
  Next ISR/server fetches. Blob downloads via `lib/downloadBlob.ts`.
- **Tests:** `backend/tests/{unit,integration,smoke,performance}` (config + markers in
  `backend/pytest.ini`; conftest auto-sets hermetic mock env incl. `SKIP_REDIS_INIT=true` — patch
  `settings`, not env vars) and `frontend/tests/{unit,e2e}`. NO other test roots — a test outside
  these does not run in CI.
- **Scripts:** one-offs in `backend/scripts/` with a docstring header; nothing executable at repo
  root. **Plans** → `tasks/todo.md`; finished plans → `tasks/archive/`; **lessons** → `lessons/`
  (one file per rule; never back into a monolith). **Prompts** → `backend/prompts/*.md`.

## API conventions & code style

- Routes are `/api/`-prefixed (admin at `/api/admin/`, cron triggers at `/internal/`); JWT via
  `Authorization: Bearer`; long-running generation streams over SSE; Pydantic-validated JSON.
- Python: type hints required, async for I/O, no raw SQL (SQLAlchemy ORM only).
  TypeScript: strict mode, interfaces for API responses.

## Deploy

CI (`.github/workflows/ci.yml`): backend gate = ruff + bandit + pytest; frontend gate = eslint +
tsc + vitest; e2e = Playwright (no backend running — specs must tolerate a dead API); the
`eval-baseline` job gates AI regressions against `backend/evals/baseline_scores.json`.
`deploy-backend` runs on push to main when `backend/` changed: applies `backend/migrations/*.sql`
idempotently to Cloud SQL, deploys the Cloud Run service (`earningsnerd-backend`, project
`earnings-nerd`, us-west1, keyless WIF auth), and refreshes the weekly pregenerate cron
(Mondays 06:00 UTC). Frontend deploys via Vercel (`NEXT_PUBLIC_API_BASE_URL=https://api.earningsnerd.io`).
Manual bootstrap: `tasks/gcp-deploy-runbook.md`. Full detail: `docs/DEPLOYMENT.md`.

## Workflow

- **Plan first:** plan mode for any non-trivial task (3+ steps or architectural decisions); write
  the plan to `tasks/todo.md` with checkable items and check in before implementing. If something
  goes sideways, STOP and re-plan — don't keep pushing.
- **Subagents:** offload research/exploration to subagents (`.claude/agents/`), one task each, to
  keep the main context clean.
- **Verify before done:** never mark complete without demonstrating correctness — run the gates,
  diff behavior vs main, check logs. Ask: "Would a staff engineer approve this?"
- **Self-improvement loop:** after ANY user correction, add or update a file in `lessons/`
  (format in `lessons/README.md`). Review relevant lessons at session start.
- **Elegance (balanced):** for non-trivial changes ask "is there a more elegant way?"; skip for
  simple fixes — don't over-engineer.
- **Autonomous bug fixing:** given a bug report, just fix it — find root causes, no temporary
  patches, no hand-holding.
- **Suggest better approaches:** if you see a clearly better way, say so before implementing
  (2-4 tradeoff bullets); proceed with the request unless the alternative avoids serious risk.
- **Docs vs code:** when they contradict, the code is truth — fix the doc in the same PR.
- These reinforce the `karpathy-guidelines` skill (`.claude/skills/meta/karpathy-guidelines/`):
  Think Before Coding, Simplicity First, Surgical Changes, Goal-Driven Execution.

## Skills

`.claude/skills/` (docs in its README): karpathy-guidelines, llm-council ("council this" /
"pressure-test this"), stripe-best-practices, cloudflare-agents-sdk, react-best-practices,
web-design-guidelines, vercel-deploy, voltagent. Invoke manually via `/<skill-name>`.
