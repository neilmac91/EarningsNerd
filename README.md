# EarningsNerd

**AI-powered SEC filing analysis.** EarningsNerd turns dense 10-K and 10-Q filings into clear,
evidence-backed summaries — business performance, financials, risks, and management discussion —
so investors can understand a company in minutes instead of hours.

🌐 **Live:** [earningsnerd.io](https://earningsnerd.io) · API: [api.earningsnerd.io](https://api.earningsnerd.io)
🔒 **Status:** pre-launch (waitlist mode)

---

## What it does

- **Search any public company** by name or ticker and pull its filings straight from SEC EDGAR.
- **Generate structured AI summaries** of 10-Ks and 10-Qs, streamed in real time — executive
  snapshot, financials, liquidity, MD&A, risks, guidance, and trends.
- **Evidence-backed output.** Every bullet must cite a filing excerpt or an XBRL anchor; the AI
  output is held to a strict JSON contract with deterministic repair and a fallback path.
- **Side-by-side comparison** of 2–5 filings to surface trends and changes (Pro).
- **Financial visualization** — interactive charts for revenue, earnings, and key metrics, grounded
  in parsed XBRL data.
- **Watchlists, saved summaries, trending & hot filings, and email alerts.**
- **Tiered subscriptions** (Free / Pro) via Stripe.

## Tech stack

**Frontend** — Next.js 14 (App Router) · TypeScript · Tailwind CSS + shadcn/ui · React Query ·
Recharts · PostHog · Sentry. Deployed on **Vercel**.

**Backend** — FastAPI (Python 3.11) · SQLAlchemy 2.0 · PostgreSQL 15 · two-tier cache (in-memory +
optional Redis). SEC data via **`edgartools`** (XBRL extraction, filing parsing). Deployed on
**Google Cloud Run** with Cloud SQL.

**AI** — an OpenAI-*compatible* client pointed at **Google AI Studio**; default model
**`gemini-3.1-pro-preview`**. (The `OPENAI_*` env names are just the compatibility shim — this is
not OpenAI/GPT-4.)

**Platform** — Stripe (payments) · Resend (email) · PostHog (analytics) · Sentry (errors).

> A deeper, human-facing architecture overview is in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).
> The exhaustive engineering reference is in [`CLAUDE.md`](./CLAUDE.md).

## How a summary is built

```
Frontend ─▶ FastAPI ─▶ SEC EDGAR (filing text + XBRL) ─▶ section extraction
        ─▶ Gemini summarization (strict JSON contract, fallback on failure)
        ─▶ quality assessment ─▶ persist ─▶ streamed back over SSE
```

Resilience is built in: a circuit breaker and token-bucket rate limiter in front of SEC EDGAR,
JSON-contract repair for model output, and a deterministic fallback summary when the model fails or
times out.

## Quick start

```bash
# Backend
cd backend && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set SECRET_KEY and OPENAI_API_KEY
uvicorn main:app --reload --port 8000     # http://localhost:8000/docs

# Frontend (new terminal)
cd frontend && npm install
cp .env.local.example .env.local
npm run dev                                # http://localhost:3000
```

Full setup, tests, and workflow: [`CONTRIBUTING.md`](./CONTRIBUTING.md).

## Project layout

```
backend/    FastAPI app (routers, services, models, schemas), SEC pipeline, prompts, tests
frontend/   Next.js app (app/, components/, features/, lib/)
docs/        Architecture, deployment, compliance, troubleshooting
```

Key API surface (full, always-current reference at `/docs`):

| Area | Endpoint |
|------|----------|
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me` |
| Companies & filings | `GET /api/companies/search`, `GET /api/filings/company/{ticker}` |
| Summaries | `POST /api/summaries/filing/{id}/generate-stream`, `GET /api/summaries/filing/{id}` |
| Comparison (Pro) | `POST /api/compare` |
| Subscriptions | `POST /api/subscriptions/create-checkout-session` |

## Deployment

Backend deploys to Google Cloud Run automatically via GitHub Actions on push to `main` (gated on
tests); the frontend deploys to Vercel via its GitHub integration. See
[`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).

## Privacy & compliance

Data export and account-deletion endpoints, cookie consent, and a documented retention policy are
in place. See [`docs/DATA_COMPLIANCE.md`](./docs/DATA_COMPLIANCE.md).

## License

MIT.
