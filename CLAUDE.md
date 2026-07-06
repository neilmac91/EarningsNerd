# CLAUDE.md — EarningsNerd

AI-powered SEC filing analysis (10-K/10-Q → grounded, evidence-backed summaries for investors).
Solo-founder project: optimize for maintainability, small diffs, and verified behavior.

**Stack:** FastAPI + sync SQLAlchemy 2.0 + PostgreSQL 15 (Cloud Run) · Next.js 16 + React 18 +
Tailwind + React Query v5 (Vercel) · AI via an OpenAI-compatible API (**DeepSeek V4 default** —
`OPENAI_BASE_URL` + `AI_DEFAULT_MODEL` are env-configurable; see ADR-0006) · Stripe · Resend ·
PostHog · Sentry.

This file is the **index**. Reference detail lives in the docs it points to — keep it that way; do
not grow this back into a monolith.

## Read before working
- **`lessons/README.md`** — hard-won operating rules, one greppable file each. Scan the index, open
  what your task touches. After ANY correction (from the user or a mistake you catch), add a new
  lesson file (format in that README).
- **`docs/adr/`** — settled, hard-to-reverse decisions (Cloud Run, DeepSeek, edgartools,
  Redis-off-in-prod, React 18). Don't re-litigate; supersede with a new ADR.
- **`docs/ARCHITECTURE.md`** — system map. **`frontend/DESIGN_SYSTEM.md`** — MANDATORY before any
  UI work (the design tokens + the legacy-color done-gate grep live there).
- **`backend/evals/RUNBOOK.md`** — before changing AI prompts, models, or AI flags.

## Commands
Backend (from `/backend`):
- Dev: `uvicorn main:app --reload --host 0.0.0.0 --port 8000`
- **FULL local gate (run all three before every push):** `ruff check . && bandit -r app -ll && python -m pytest`
- Fast lane: `python -m pytest` (pytest.ini deselects performance/slow); full: `python -m pytest -m ""`

Frontend (from `/frontend`):
- Dev: `npm run dev` · **Gate:** `npm run lint && npx tsc -p tsconfig.ci.json && npm run test -- --run && npm run build`

Infra: `docker-compose up -d postgres redis` (Redis is **DEV-ONLY**; prod runs the L1 in-memory
cache only — ADR-0004).

## Non-negotiable rules
1. **Summary generation has ONE orchestrator** — `services/summary_pipeline.stream_filing_summary`.
   The SSE endpoint streams it; `generate_summary_background` (cron/precompute) drains it headless.
   Never add a second generation path.
2. **Migrations:** no Alembic. Fresh schema = `create_all()` at startup; ANY change to an existing
   table = a new **idempotent** SQL file in `backend/migrations/` (CI re-applies ALL of them every
   deploy — must be safe to re-run). Never edit an applied migration, and never run schema-altering
   DDL in the serving container's startup path.
3. **Entitlements:** `app/services/entitlements.py` is the ONLY source of plan truth. Never hardcode
   plan limits or Pro checks elsewhere.
4. **SEC calls:** all sec.gov traffic goes through the edgar service layer (rate limiter + circuit
   breaker). Never raw httpx to sec.gov outside it. The 10 req/s cap is **per-process** — an IP ban
   takes the product down.
5. **Boundaries:** validate external data where it enters (SEC, Stripe, AI responses); do NOT
   re-validate internally-produced data downstream.
6. **Contract tests** (SSE stream contract, `test_auth_flow`, Stripe webhooks) must not be edited in
   the same PR as the code they guard — except to drop a reference to a symbol deleted in that PR.
   Any other change = stop and surface it as an explicit, signed-off contract change.
7. **datetime:** timezone-aware UTC via the shared `app/utils/datetimes.utcnow()`; never the stdlib
   naive `datetime.utcnow()`. The ONLY sanctioned naive sites are the three deliberately-naive
   OAuthState/RefreshToken token-expiry columns — enforced by `test_naive_utcnow_allowlist`.
8. **Config:** all env access through `app/config.py` Settings; never `os.getenv` in app code (the
   infra-bootstrap constants in `database.py`/`redis_service.py`/`edgar/config.py` are the only
   allow-listed exceptions).
9. **Data integrity:** `Filing.sec_url`/`document_url` are NOT NULL (event-listener enforced); URL
   format in `lessons/`.
10. **Design system:** any theme/token change is app-wide (public + authed). Done-gate = the
    legacy-color grep in `DESIGN_SYSTEM.md` returns nothing AND both themes verified on the preview.

## Where things live
- `backend/app/routers/` = HTTP only; `backend/app/services/` = business logic. Query keys →
  `frontend/lib/queryKeys.ts` (eslint-enforced; no string-literal keys).
- `frontend/features/<domain>/` = domain code (`api/` + `components/`). `frontend/components/` = the
  UI library (`ui/`) + app chrome (Header/Footer/boundaries/logos) ONLY — enforced by a vitest
  allowlist spec.
- **Tests:** `backend/tests/{unit,integration,smoke,performance}` (markers in `pytest.ini`) and
  `frontend/tests/{unit,e2e}`. NO other test root runs in CI. The test DB is a **persistent** SQLite
  file — `rm backend/earningsnerd.db` after a schema change/rebase if you hit `no such column`.
- One-off scripts: `backend/scripts/` with a docstring header. Nothing executable at repo root.
- Plans → `tasks/todo.md`; finished plans → `tasks/archive/`; lessons → `lessons/` (one per file,
  never back into a monolith).

## Deploy
CI (`.github/workflows/ci.yml`): backend gate = ruff + bandit + pytest; frontend gate = eslint + tsc
+ vitest; e2e = Playwright (runs with **no backend** — prod telemetry is the only real end-to-end
signal). `deploy-backend` runs on push to `main` when `backend/` changed: applies
`backend/migrations/*.sql` to Cloud SQL, deploys the `earningsnerd-backend` Cloud Run service, then
updates the 6 Cloud Run jobs (pregenerate, filing-scan, filing-digest, backfill-facts,
earnings-calendar-refresh, earnings-day-alerts). Keyless auth via Workload Identity Federation.
Manual fallback: `tasks/gcp-deploy-runbook.md`.

## Workflow
- Plan mode for any non-trivial task (3+ steps / architectural). Verify before done — run the gates;
  for UI, eyeball both themes on the preview. Green CI is necessary, not sufficient.
- After ANY user correction: add/update a file in `lessons/`.
- When docs contradict code, the code is truth — fix the doc in the same PR and note it.
- Ride flag/behavior changes on a soak + observation window (CI e2e has no backend; only prod
  PostHog/Sentry validates end-to-end).
