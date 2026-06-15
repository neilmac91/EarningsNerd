# Contributing to EarningsNerd

## Prerequisites

- Python **3.11**
- Node.js **20.x** (see `frontend/.nvmrc`)
- Docker + Docker Compose (optional, for local Postgres/Redis)

## Local setup

### 1. Databases (optional but recommended)

```bash
docker-compose up -d postgres redis
```

You can skip this and run against SQLite — the backend defaults to a local SQLite file if
`DATABASE_URL` is unset.

### 2. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # then edit: SECRET_KEY and OPENAI_API_KEY are required
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`

The database schema is created automatically at startup (`Base.metadata.create_all`) — there is no
Alembic step.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local    # defaults target http://localhost:8000
npm run dev
```

- App: `http://localhost:3000`

## Tests, lint, build

**Backend** (from `backend/`):
```bash
pytest tests/              # all tests
pytest tests/unit/         # unit only
pytest tests/smoke/ -v     # critical-path smoke tests
ruff check app             # lint
```

**Frontend** (from `frontend/`):
```bash
npm run test               # Vitest unit tests
npm run test:e2e           # Playwright E2E
npm run lint               # ESLint
npm run build              # production build
```

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs on every push and PR:
`backend-tests` (ruff + bandit + pytest), `frontend-tests` (vitest), and `e2e-tests` (build +
Playwright). All three must pass before the backend auto-deploys to Cloud Run on `main`. See
[`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).

## Workflow

1. Branch off `main`.
2. Keep changes surgical — touch only what the change requires; match surrounding style.
3. Add/extend tests for the behavior you change.
4. Open a PR; ensure CI is green. Backend deploys automatically once merged to `main`.

## Where things live

A full map of services, routers, and models is in [`CLAUDE.md`](./CLAUDE.md); the human-facing
architecture overview is in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).
