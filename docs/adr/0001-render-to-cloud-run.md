# ADR 0001 — Migrate hosting from Render to Google Cloud Run

- **Status:** Accepted (June 2026)
- **Deciders:** EarningsNerd maintainers
- **Supersedes:** the Render-based deployment described in `docs/history/render/`

## Context

The backend originally ran on [Render.com](https://render.com) as a managed web service,
with `render.yaml` as the infrastructure manifest. That setup accumulated friction that is
preserved in the historical record under `docs/history/render/`:

- Repeated Python-version and start-command drift (`RENDER_PYTHON_311_FIX.md`,
  `RENDER_START_COMMAND_FIX.md`, `RENDER_START_COMMAND_NOT_APPLYING.md`).
- SQLAlchemy / Postgres connection issues specific to the platform
  (`RENDER_SQLALCHEMY_FIX.md`).
- The `render.yaml` manifest had also gone stale — it referenced an Alembic setup that
  does not exist (schema is created at startup via `Base.metadata.create_all()`) and a
  removed `update_contact_schema.py`.

At the same time the data layer was moving toward Google Cloud SQL (PostgreSQL 15), and
the team wanted first-class, reproducible, container-based deploys with keyless CI auth
and a managed Postgres connector — rather than a second cloud relationship to maintain.

## Decision

Host the backend on **Google Cloud Run** (project `earnings-nerd`, region `us-west1`,
service `earningsnerd-backend`):

- The service is **containerized** via `backend/Dockerfile`; the image installs the pinned
  `requirements.txt` (see [ADR-0004 context] and the pip-tools lockfile).
- **Continuous deployment** runs from the `deploy-backend` job in
  `.github/workflows/ci.yml` on push to `main`, gated on all test jobs and only when
  `backend/` changed. Auth to GCP is **keyless** via Workload Identity Federation
  (repo variables `GCP_WIF_PROVIDER` + `GCP_DEPLOYER_SA`) — no long-lived service-account
  keys in the repo.
- The database is **Cloud SQL for PostgreSQL 15** (`earningsnerd-db`), reached through the
  Cloud SQL connector socket (`?host=/cloudsql/<connection-name>` in `DATABASE_URL`).
- Secrets live in **Google Secret Manager**, mounted as env vars on the Cloud Run
  service/job.
- The weekly example-refresh cron is a Cloud Run **job** (`earningsnerd-pregenerate`) on a
  Cloud Scheduler trigger (Mondays 06:00 UTC), updated by the same deploy job.
- Custom domain `api.earningsnerd.io` via Cloud Run domain mapping (Cloudflare CNAME →
  `ghs.googlehosted.com`, DNS-only).

The frontend remains on **Vercel** (`NEXT_PUBLIC_API_BASE_URL=https://api.earningsnerd.io`).

## Consequences

**Positive**
- One cloud for compute + managed Postgres; the Cloud SQL connector removes the bespoke
  connection-string fragility seen on Render.
- Reproducible builds from a pinned lockfile + a single `Dockerfile`.
- Gated, keyless CD: deploys can only happen on green tests, with no static cloud
  credentials stored in the repo.
- Scale-to-zero economics suit a pre-launch product.

**Negative / costs**
- Cold starts are possible at scale-to-zero; acceptable for current traffic.
- More GCP-specific knowledge required (WIF, Cloud SQL connector, Secret Manager) — see
  `docs/DEPLOYMENT.md` and `tasks/gcp-deploy-runbook.md`.

**Cleanup**
- `render.yaml` was removed; the Render docs are archived under `docs/history/render/` for
  provenance only and are **not** current guidance.
