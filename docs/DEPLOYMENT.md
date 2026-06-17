# Deployment

EarningsNerd runs on two platforms:

| Tier | Platform | How it deploys |
|------|----------|----------------|
| **Backend** (FastAPI) | Google Cloud Run — service `earningsnerd-backend`, project `earnings-nerd`, region `us-west1` | **Automated** via GitHub Actions on push to `main` (gated on tests) |
| **Frontend** (Next.js) | Vercel | **Automated** via Vercel's GitHub integration on push to `main` |
| **Database** | Cloud SQL for PostgreSQL 15 (`earningsnerd-db`) | Reached over the Cloud SQL connector socket |
| **Cache** | None in production (`SKIP_REDIS_INIT=true`) — L1 in-memory only | Redis is local-dev only (docker-compose) |
| **Secrets** | Google Secret Manager, mounted as env vars on the Cloud Run service | — |
| **Custom domain** | `api.earningsnerd.io` → Cloud Run domain mapping (Cloudflare CNAME → `ghs.googlehosted.com`, DNS-only) | — |

> Schema is created at startup by `Base.metadata.create_all()` in `main.py`'s lifespan — there is **no Alembic**. One-off SQL migrations live in `backend/migrations/` and are applied manually.

---

## Backend — continuous deployment (the normal path)

The `deploy-backend` job in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) deploys automatically when:

- the push is to `main`, **and**
- `backend/` changed, **and**
- all test jobs (`backend-tests`, `frontend-tests`, `e2e-tests`) passed.

It builds `backend/Dockerfile`, pushes to Artifact Registry
(`us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend`), runs `gcloud run deploy`,
refreshes the weekly example-pregeneration job, and health-checks
`https://api.earningsnerd.io/health`. Auth is keyless via Workload Identity Federation
(repo variables `GCP_WIF_PROVIDER` + `GCP_DEPLOYER_SA`).

**Nothing manual is required for routine releases** — merge to `main` and the pipeline ships it.

## Frontend — continuous deployment

Vercel's GitHub integration builds and deploys the `frontend/` app on every push to `main`
(and creates preview deployments for PRs). CI does **not** deploy the frontend.

> **Single source of Vercel config.** The project's **Root Directory** is set to `frontend`, so
> Vercel reads `frontend/vercel.json` (region `iad1`) — that is the only Vercel config file
> (the inert repo-root `/vercel.json` was removed). Build/dev/install commands are relative to
> `frontend/`, so there is **no** `cd frontend` prefix.
>
> **Sentry DSN lives in the Vercel dashboard, not the repo.** Set `NEXT_PUBLIC_SENTRY_DSN` **and**
> `SENTRY_DSN` as project environment variables (Production **and** Preview). `instrumentation.ts`
> reads `SENTRY_DSN || NEXT_PUBLIC_SENTRY_DSN`; `instrumentation-client.ts` reads
> `NEXT_PUBLIC_SENTRY_DSN`. If both are unset, Sentry silently does not initialize.
>
> **Rotating the DSN:** `SENTRY_DSN` is read at runtime, so changing it in the dashboard takes effect
> on the next request. `NEXT_PUBLIC_SENTRY_DSN`, however, is baked into the client bundle by Next.js
> **at build time** — rotating it requires a **new deployment (rebuild)** to reach the browser.

---

## Backend — one-time bootstrap (new environment)

Run in Google Cloud Shell. Each phase has a success check; if a step errors, stop and fix it
before continuing.

### 1. Enable APIs
```bash
gcloud config set project earnings-nerd
gcloud services enable \
  run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com \
  cloudscheduler.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
```

### 2. Build the image
```bash
gcloud artifacts repositories create earningsnerd \
  --repository-format=docker --location=us-west1
gcloud builds submit \
  --tag us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest
```

### 3. Cloud SQL (Postgres 15)
```bash
gcloud sql instances create earningsnerd-db \
  --database-version=POSTGRES_15 --tier=db-g1-small \
  --region=us-west1 --storage-size=10GB --storage-auto-increase   # ~5-10 min
gcloud sql databases create earningsnerd --instance=earningsnerd-db
DB_PASS=$(openssl rand -hex 24)
gcloud sql users create appuser --instance=earningsnerd-db --password="$DB_PASS"
CONN=$(gcloud sql instances describe earningsnerd-db --format='value(connectionName)')
echo "Connection name: $CONN"   # earnings-nerd:us-west1:earningsnerd-db
```

### 4. Secrets (Secret Manager)
```bash
printf 'postgresql://appuser:%s@/earningsnerd?host=/cloudsql/%s' "$DB_PASS" "$CONN" \
  | gcloud secrets create DATABASE_URL --data-file=-

# Repeat for each secret, pasting the real value:
printf '%s' 'PASTE_VALUE' | gcloud secrets create OPENAI_API_KEY        --data-file=-
printf '%s' 'PASTE_VALUE' | gcloud secrets create SECRET_KEY            --data-file=-
printf '%s' 'PASTE_VALUE' | gcloud secrets create STRIPE_SECRET_KEY     --data-file=-
printf '%s' 'PASTE_VALUE' | gcloud secrets create STRIPE_PUBLISHABLE_KEY --data-file=-
printf '%s' 'PASTE_VALUE' | gcloud secrets create STRIPE_WEBHOOK_SECRET --data-file=-
printf '%s' 'PASTE_VALUE' | gcloud secrets create RESEND_API_KEY        --data-file=-
printf '%s' 'PASTE_VALUE' | gcloud secrets create RESEND_FROM_EMAIL     --data-file=-
printf '%s' 'PASTE_VALUE' | gcloud secrets create FINNHUB_API_KEY       --data-file=-
```

### 5. Grant the runtime service account access
```bash
PROJECT_NUMBER=$(gcloud projects describe earnings-nerd --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding earnings-nerd \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding earnings-nerd \
  --member="serviceAccount:${SA}" --role="roles/cloudsql.client"
```

### 6. Deploy
```bash
gcloud run deploy earningsnerd-backend \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --region=us-west1 --allow-unauthenticated \
  --add-cloudsql-instances=earnings-nerd:us-west1:earningsnerd-db \
  --cpu=1 --memory=1Gi --min-instances=0 --max-instances=2 --concurrency=40 --timeout=600 \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest,STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_PUBLISHABLE_KEY=STRIPE_PUBLISHABLE_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest,RESEND_API_KEY=RESEND_API_KEY:latest,RESEND_FROM_EMAIL=RESEND_FROM_EMAIL:latest,FINNHUB_API_KEY=FINNHUB_API_KEY:latest \
  --set-env-vars="^@^ENVIRONMENT=production@SKIP_REDIS_INIT=true@OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/@SEC_EDGAR_BASE_URL=https://data.sec.gov@FINNHUB_API_BASE=https://finnhub.io/api/v1@EARNINGS_WHISPERS_API_BASE=https://www.earningswhispers.com/api@CORS_ORIGINS_STR=https://earningsnerd.io,https://www.earningsnerd.io@COOKIE_DOMAIN=.earningsnerd.io"
```

### 7. Verify
```bash
SVC=$(gcloud run services describe earningsnerd-backend --region=us-west1 --format='value(status.url)')
curl -s $SVC/health           # {"status":"healthy"}
curl -s $SVC/health/detailed  # database healthy:true; redis degraded (EXPECTED, off); circuit closed
```

### 8. Domain mapping
```bash
gcloud beta run domain-mappings create \
  --service=earningsnerd-backend --domain=api.earningsnerd.io --region=us-west1
```
Point the Cloudflare `api` CNAME at the printed target (`ghs.googlehosted.com`), keep it
**DNS-only (grey cloud)**, wait for the managed TLS cert, then `curl https://api.earningsnerd.io/health`.

### 9. (Optional) Weekly example-refresh cron
A Cloud Run Job `earningsnerd-pregenerate` + Cloud Scheduler (`0 6 * * 1`, Mondays 06:00 UTC) runs
`scripts/pregenerate_examples.py`. The CD pipeline keeps this job's image in sync; see the
`deploy-backend` job for the exact commands.

### 10. New-filing alert scan (Phase 2)
A Cloud Run Job `earningsnerd-filing-scan` runs `scripts/filing_scan.py` to detect new SEC filings
for watched companies and send alerts (real-time for Pro, daily digest for Free). The CD pipeline
keeps the job image in sync **once the job exists** (the step skips gracefully otherwise). Create it
once, with two Cloud Scheduler triggers — hourly scan + once-daily digest:

```bash
# One-time job creation (needs DB + Resend secrets, same connector as the service)
gcloud run jobs create earningsnerd-filing-scan --region=us-west1 \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --command=python --args=scripts/filing_scan.py \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,RESEND_API_KEY=RESEND_API_KEY:latest \
  --set-cloudsql-instances=<CONNECTION_NAME>

# Hourly real-time scan
gcloud scheduler jobs create http filing-scan-hourly --location=us-west1 --schedule="0 * * * *" \
  --uri="https://<run-jobs-execute-endpoint>/earningsnerd-filing-scan:run" --http-method=POST \
  --oauth-service-account-email=<SCHEDULER_SA>

# Daily digest (08:00 UTC) — override the job args to --digest
gcloud scheduler jobs create http filing-digest-daily --location=us-west1 --schedule="0 8 * * *" \
  --uri="https://<run-jobs-execute-endpoint>/earningsnerd-filing-scan:run" --http-method=POST \
  --oauth-service-account-email=<SCHEDULER_SA>
```

**Alternative (no extra job):** the backend also exposes token-gated triggers
`POST /internal/jobs/filing-scan` and `POST /internal/jobs/filing-digest` (header
`X-Internal-Token: $INTERNAL_JOB_TOKEN`). Point Cloud Scheduler at those instead. Set
`INTERNAL_JOB_TOKEN` in Secret Manager to enable them (unset ⇒ the endpoints return 503).

> **Migrations for Phase 2:** the alert tables auto-create, but the new **columns** on `watchlist`
> and `companies` do not (`create_all` never alters existing tables). Apply
> `backend/migrations/20260618_phase2_alerts.sql` against the prod DB **before/with** the deploy that
> ships the Phase 2 models, or ORM reads of `Company`/`Watchlist` will fail. Same applies to any
> future column migration.

---

## Troubleshooting

- **Health probe timeout on deploy:** check logs with
  `gcloud run services logs read earningsnerd-backend --region=us-west1`.
- **`could not connect to server` / socket errors:** confirm `--add-cloudsql-instances` matches the
  instance connection name and the service account has `roles/cloudsql.client`.
- **Raising capacity:** bump `--max-instances` (and size up Cloud SQL); keep
  `max-instances × concurrency` comfortably under the DB's `max_connections`.
- **Eliminate cold starts:** `gcloud run services update earningsnerd-backend --region=us-west1 --min-instances=1`.

> Migrated off Render.com (June 2026). Superseded Render/Vercel/Firebase deployment notes are
> archived under [`docs/history/`](./history/) for provenance.
