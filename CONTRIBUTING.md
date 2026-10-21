# Contributing to EarningsNerd

## Prerequisites

- Python **3.11**
- git **2.43** or later (`.claude/hooks/secret_scan_guard.py` holds `attr.tree` for its scan, a setting an older git ignores, so the hook refuses its scans there; outside CI, its suite skips the cases that build a scratch project)
- Node.js **22.23.2** (see `frontend/.nvmrc`; `frontend/tests/unit/nodeVersionLockstep.spec.ts` keeps `.nvmrc`, `engines` and every `.github/workflows/*.yml` / `*.yaml` Node pin in lockstep)
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
pip install -r requirements-dev.txt # lint tools + pytest-xdist (the test commands below need it)
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
pytest tests/              # the fast lane, in parallel (pytest.ini adds `-n auto` and deselects the performance suite)
pytest -m "" tests/        # everything, the performance suite included
pytest tests/unit/         # unit only
pytest tests/smoke/ -v     # critical-path smoke tests
pytest -n 0 tests/unit/test_x.py  # one file, serially (debuggers, quick loops)
ruff check . && bandit -r app -ll  # lint and security scan, as CI runs them
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
`backend-tests` (ruff + bandit + the parallel pytest fast lane, then the performance suite
serially), `migrations-postgres` (the migrations and the concurrency tests on PostgreSQL),
`frontend-tests` (vitest), `e2e-tests` (build + Playwright) and `secret-scan` (gitleaks). All five
must pass before the backend auto-deploys to Cloud Run on `main`. See
[`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).

In a Claude Code session that loads the repository's hooks, `.claude/hooks/secret_scan_guard.py`
runs the same pinned gitleaks over what a `git push` or a GitHub MCP file write would add. It
refuses a call that adds commits on a finding and whenever it cannot scan them, as when its binary
is missing or git is older than 2.43, a push whose directory it cannot name or whose repository
git cannot read, whatever the push adds, and a few calls it cannot read, whether they push or not
(a case in a command substitution whose pattern no `(` opens, a `<<` bash reads in a word such as
`a[1<<2]=x`, and a parameter expansion such as `${x%)}` outside quotes or `"${x:-"a"}"`, among
them); its header lists every case. Install the
binary once per machine and pin, a new cloud container included, with
`python3 .claude/hooks/secret_scan_guard.py --install`.

The same scan runs as git's pre-push hook, `.claude/hooks/git/pre-push`, before each `git push`
leaves a clone, yours and a script's included. Turn it on once per clone, from any worktree, and
again from the main checkout if you move the clone (a move breaks a linked worktree's link), with
`python3 .claude/hooks/secret_scan_guard.py --turn-on`: it sets
`core.hooksPath` to the main checkout's `.claude/hooks/git` by its absolute path (every worktree
reads the clone's one path, a linked worktree's own would go with it, and a relative one would miss a
push run inside `.git`, or with a `GIT_DIR` from a subdirectory), and says the hook is on or why not,
leaving a hooks path naming another directory, or hooks of the clone's own, as they are, and setting
nothing on a git older than 2.43, whose every push that adds commits the hook would refuse. A Claude
Code cloud session that loads the repository's hooks does it for its clone as it starts; Codex and
Astra sessions leave it to the founder (`AGENTS.md` §5, F53). Both hooks take the remote named
`origin` for GitHub: in a clone whose GitHub remote has another name, every push that adds commits
has its whole history scanned without main's pins, and is refused. The hook stops a push on a finding
and whenever it cannot scan (it needs the binary above, git 2.43 or later and `python3`), naming why;
`git push --no-verify` skips it, as do `git send-pack`, `git http-push` and a program pushing through
a git library, and CI's `secret-scan` still reads every branch after the push.

## Workflow

1. Branch off `main`.
2. Keep changes surgical — touch only what the change requires; match surrounding style.
3. Add/extend tests for the behavior you change.
4. Open a PR; ensure CI is green. Backend deploys automatically once merged to `main`.

## Where things live

A full map of services, routers, and models is in [`CLAUDE.md`](./CLAUDE.md); the human-facing
architecture overview is in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

For UI work, start with [DESIGN.md](./DESIGN.md), then use
[frontend/DESIGN_SYSTEM.md](./frontend/DESIGN_SYSTEM.md) for implementation conventions and
verification. [CLAUDE.md's design-document maintenance guidance](./CLAUDE.md#design-documentation)
explains when to refresh the visual snapshot, its sidecar and the implementation guide.
