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

> Schema is created at startup by `Base.metadata.create_all()` in `main.py`'s lifespan — there is **no Alembic**. Idempotent SQL migrations live in `backend/migrations/` and are re-applied by the CI deploy job on **every** deploy (plus `ensure_additive_columns` self-heals additive columns at startup), so every file must stay safe to re-run forever.

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
  --cpu=1 --memory=1Gi --cpu-boost --min-instances=0 --max-instances=2 --concurrency=40 --timeout=600 \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest,STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_PUBLISHABLE_KEY=STRIPE_PUBLISHABLE_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest,RESEND_API_KEY=RESEND_API_KEY:latest,RESEND_FROM_EMAIL=RESEND_FROM_EMAIL:latest,FINNHUB_API_KEY=FINNHUB_API_KEY:latest \
  --set-env-vars="^@^ENVIRONMENT=production@SKIP_REDIS_INIT=true@OPENAI_BASE_URL=https://api.deepseek.com/v1@SEC_EDGAR_BASE_URL=https://data.sec.gov@FINNHUB_API_BASE=https://finnhub.io/api/v1@CORS_ORIGINS_STR=https://earningsnerd.io,https://www.earningsnerd.io@COOKIE_DOMAIN=.earningsnerd.io"
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
Two Cloud Run Jobs run `scripts/filing_scan.py` to detect new SEC filings for watched companies and
send alerts (real-time for Pro, daily digest for Free): `earningsnerd-filing-scan` (real-time pass)
and `earningsnerd-filing-digest` (the `--digest` pass). They are **separate jobs** on purpose — a
plain Cloud Run Jobs `:run` POST cannot override `--args`, so baking `--digest` into its own job is
the simplest robust way to schedule the digest. The CD pipeline keeps both job images in sync **once
they exist** (each step skips gracefully otherwise). Create them once, with one Cloud Scheduler
trigger each (hourly scan + once-daily digest):

```bash
# Same connector + scheduler SA the rest of this runbook uses.
CONN=earnings-nerd:us-west1:earningsnerd-db
SA="$(gcloud projects describe earnings-nerd --format='value(projectNumber)')-compute@developer.gserviceaccount.com"

# NOTE: app/config.py requires SECRET_KEY and OPENAI_API_KEY at import — the job crashes on startup
# without them, even though the scan itself makes no AI calls. RESEND_API_KEY is needed to send mail.
SECRETS=DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,RESEND_API_KEY=RESEND_API_KEY:latest,RESEND_FROM_EMAIL=RESEND_FROM_EMAIL:latest
ENVV="^@^ENVIRONMENT=production@SKIP_REDIS_INIT=true@SEC_EDGAR_BASE_URL=https://data.sec.gov"

# Real-time scan job
gcloud run jobs create earningsnerd-filing-scan --region=us-west1 \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --cpu=1 --memory=1Gi --task-timeout=1800 \
  --set-cloudsql-instances="$CONN" --set-secrets="$SECRETS" --set-env-vars="$ENVV" \
  --command=python --args=scripts/filing_scan.py

# Daily digest job (same script, --digest baked in)
gcloud run jobs create earningsnerd-filing-digest --region=us-west1 \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --cpu=1 --memory=1Gi --task-timeout=1800 \
  --set-cloudsql-instances="$CONN" --set-secrets="$SECRETS" --set-env-vars="$ENVV" \
  --command=python --args=scripts/filing_scan.py,--digest

# Facts backfill job — normalize filings' XBRL into financial_fact (peers F3 + fundamentals F5).
# --only-new makes the scheduled run incremental (just newly-arrived filings); drop it for a full
# idempotent re-pass. RESEND_* aren't needed here but reusing $SECRETS is harmless.
gcloud run jobs create earningsnerd-backfill-facts --region=us-west1 \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --cpu=1 --memory=1Gi --task-timeout=3600 \
  --set-cloudsql-instances="$CONN" --set-secrets="$SECRETS" --set-env-vars="$ENVV" \
  --command=python --args=scripts/backfill_facts.py,--only-new

# roles/run.invoker is sufficient: it includes both run.routes.invoke (services)
# and run.jobs.run (jobs). roles/run.developer would also work but is overly
# permissive (adds create/update/delete on services and jobs).
gcloud projects add-iam-policy-binding earnings-nerd \
  --member="serviceAccount:${SA}" --role="roles/run.invoker"

# Hourly real-time scan
gcloud scheduler jobs create http filing-scan-hourly --location=us-west1 --schedule="0 * * * *" \
  --uri="https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-filing-scan:run" \
  --http-method=POST --oauth-service-account-email="${SA}"

# Daily digest at 08:00 UTC
gcloud scheduler jobs create http filing-digest-daily --location=us-west1 --schedule="0 8 * * *" \
  --uri="https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-filing-digest:run" \
  --http-method=POST --oauth-service-account-email="${SA}"

# Facts backfill weekly (Mondays 07:00 UTC — after the scan has ingested the week's filings)
gcloud scheduler jobs create http backfill-facts-weekly --location=us-west1 --schedule="0 7 * * 1" \
  --uri="https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-backfill-facts:run" \
  --http-method=POST --oauth-service-account-email="${SA}"
```

Smoke-test each before trusting the schedule:
```bash
gcloud run jobs execute earningsnerd-filing-scan    --region=us-west1
gcloud run jobs execute earningsnerd-filing-digest  --region=us-west1
gcloud run jobs execute earningsnerd-backfill-facts --region=us-west1
```

**Alternative (no extra job):** the backend also exposes token-gated triggers
`POST /internal/jobs/filing-scan`, `POST /internal/jobs/filing-digest`, and
`POST /internal/jobs/backfill-facts` (header `X-Internal-Token: $INTERNAL_JOB_TOKEN`). Point Cloud
Scheduler at those instead. Set `INTERNAL_JOB_TOKEN` in Secret Manager to enable them (unset ⇒ the
endpoints return 503). Note the backfill can be long-running; the dedicated Cloud Run job above is
preferred over the in-process endpoint for a large first pass.

### 11. Earnings calendar refresh + alerts

Two Cloud Run Jobs run `scripts/earnings_calendar_job.py` to ingest the earnings calendar (Alpha
Vantage bulk estimates + EDGAR 8-K Item 2.02 sweep + reconciliation) and send the earnings-day alert
digest: `earningsnerd-earnings-calendar-refresh` (default pass) and `earningsnerd-earnings-day-alerts`
(the `--alerts` pass). **These must run as dedicated jobs, not via the `/internal/jobs/*` HTTP
triggers below** — a FastAPI `BackgroundTasks` callback only keeps running as long as the serving
Cloud Run *instance* stays alive after the response is sent, and the instance can be reclaimed
(scale-to-zero) before the callback finishes; a live outage confirmed this (the endpoint returned
`202` instantly but the table never populated — only cold-start log lines appeared, no completion
log). The CD pipeline keeps both job images in sync **once they exist** (skips gracefully otherwise).
Create them once, with one Cloud Scheduler trigger each:

```bash
# Same connector + secrets + scheduler SA as the filing-scan section above.
CONN=earnings-nerd:us-west1:earningsnerd-db
SA="$(gcloud projects describe earnings-nerd --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
SECRETS=DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,RESEND_API_KEY=RESEND_API_KEY:latest,RESEND_FROM_EMAIL=RESEND_FROM_EMAIL:latest,ALPHA_VANTAGE_API_KEY=ALPHA_VANTAGE_API_KEY:latest
ENVV="^@^ENVIRONMENT=production@SKIP_REDIS_INIT=true"

# Daily refresh job
gcloud run jobs create earningsnerd-earnings-calendar-refresh --region=us-west1 \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --cpu=1 --memory=1Gi --task-timeout=1800 \
  --set-cloudsql-instances="$CONN" --set-secrets="$SECRETS" --set-env-vars="$ENVV" \
  --command=python --args=scripts/earnings_calendar_job.py

# Daily alerts job (same script, --alerts baked in)
gcloud run jobs create earningsnerd-earnings-day-alerts --region=us-west1 \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --cpu=1 --memory=1Gi --task-timeout=1800 \
  --set-cloudsql-instances="$CONN" --set-secrets="$SECRETS" --set-env-vars="$ENVV" \
  --command=python --args=scripts/earnings_calendar_job.py,--alerts

gcloud projects add-iam-policy-binding earnings-nerd \
  --member="serviceAccount:${SA}" --role="roles/run.invoker"

# 05:30 America/New_York — before the US pre-market earnings window. Cloud Scheduler's
# --time-zone handles the EST/EDT switch; no DST math needed.
gcloud scheduler jobs create http earnings-calendar-refresh-daily --location=us-west1 \
  --schedule="30 5 * * *" --time-zone="America/New_York" \
  --uri="https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-earnings-calendar-refresh:run" \
  --http-method=POST --oauth-service-account-email="${SA}"

# 06:00 America/New_York — 30 min after the refresh, so today's reporters are already in
# the table before the digest reads them.
gcloud scheduler jobs create http earnings-day-alerts-daily --location=us-west1 \
  --schedule="0 6 * * *" --time-zone="America/New_York" \
  --uri="https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-earnings-day-alerts:run" \
  --http-method=POST --oauth-service-account-email="${SA}"
```

Smoke-test each before trusting the schedule:
```bash
gcloud run jobs execute earningsnerd-earnings-calendar-refresh --region=us-west1
gcloud run jobs execute earningsnerd-earnings-day-alerts       --region=us-west1
```

**One-shot maintenance runs (repair / re-sweep):** `gcloud run jobs execute --args=…` overrides the
arguments for THAT execution only — the job definition keeps `--command=python`, and the next
scheduled run is unaffected. Since the DB is only reachable from Cloud Run, this is also the way to
run any `backend/scripts/*` maintenance script against prod. Used for the 2026-07 false-"reported"
cleanup (unguarded 8-K 2.02 flips — BIIB shown as reported on its pre-announcement day):

```bash
# 1. Re-classify the poisoned window (dry-run first; add ,--execute to apply)
gcloud run jobs execute earningsnerd-earnings-calendar-refresh --region=us-west1 \
  --args="scripts/repair_false_reported_earnings.py,--from,2026-06-28,--to,2026-07-04" --wait
# 2. Guarded re-sweep of the same window to re-flip the genuine releases the old code dropped
gcloud run jobs execute earningsnerd-earnings-calendar-refresh --region=us-west1 \
  --args="scripts/earnings_calendar_job.py,--sweep-from,2026-06-28,--sweep-to,2026-07-04" --wait
```

**Index universe restriction (S&P 500 / Nasdaq 100).** The calendar filter is gated by
`CALENDAR_INDEX_FILTER_ENABLED` (ships off) and reads the committed
`backend/app/data/index_membership.json` (~515 tickers, S&P 500 ∪ Nasdaq 100). It fails **open** —
a missing/short list serves the calendar unfiltered rather than empty, so it can only ever hide
long-tail names, never blank the page. First rollout:

```bash
# 1. Purge the long-tail rows already in the table (dry-run first; add ,--execute to apply). The
#    purge REFUSES to run if the committed list is short — it can never delete the whole calendar.
gcloud run jobs execute earningsnerd-earnings-calendar-refresh --region=us-west1 \
  --args="scripts/purge_non_index_earnings.py" --wait           # dry run: prints what it would delete
gcloud run jobs execute earningsnerd-earnings-calendar-refresh --region=us-west1 \
  --args="scripts/purge_non_index_earnings.py,--execute" --wait
# 2. Turn the filter on (serve + ingest). Instantly reversible: set it back to false and the next
#    daily refresh re-populates non-members (AV returns the full calendar).
gcloud run services update earningsnerd-backend --region=us-west1 \
  --update-env-vars=CALENDAR_INDEX_FILTER_ENABLED=true
# 3. Probe: peak days now show only large caps; spot-check BRK.B / GOOGL present.
#    curl "https://api.earningsnerd.io/api/calendar?from=2026-07-27&to=2026-07-31"
```

**Quarterly: refresh the membership list** (the indexes rebalance ~quarterly). Regenerate, review the
diff in a PR, merge — the served universe only ever changes via a reviewed commit, never a live fetch:

```bash
cd backend && FMP_API_KEY=… python scripts/refresh_index_membership.py   # or --source wikipedia (keyless)
#   Prints the added/removed tickers and rewrites app/data/index_membership.json; commit it via PR.
#   Aborts without writing if the fetch yields < 450 tickers (never truncates the committed list).
```

The `/internal/jobs/earnings-calendar-refresh` and `/internal/jobs/earnings-day-alerts` HTTP triggers
still exist and are useful for an ad-hoc manual kick (e.g. re-seeding after a schema change) — just
don't put the recurring schedule on them.

> **Migrations for Phase 2:** the alert tables auto-create, but the new **columns** on `watchlist`
> and `companies` do not (`create_all` never alters existing tables). Apply
> `backend/migrations/20260618_phase2_alerts.sql` against the prod DB **before/with** the deploy that
> ships the Phase 2 models, or ORM reads of `Company`/`Watchlist` will fail. Same applies to any
> future column migration.
>
> The **in-app notification bell** (the `/api/users/me/notifications` endpoints + Header bell) adds a
> `users.notifications_seen_at` column for unread tracking — apply
> `backend/migrations/20260620_users_notifications_seen_at.sql` the same way. The bell reads the same
> `notification_log` rows the scan writes, so it needs no extra cron; it lights up once the scan
> jobs above are running.

### 12. Notable filings scan (homepage discovery)

One Cloud Run Job runs `scripts/notable_filings_job.py` to sweep EDGAR full-text search for
market-wide notable filings into the `notable_filings` table (the homepage "Notable filings"
section; replaces the retired own-DB Trending Filings — see
`tasks/homepage-sections-review-findings.md`). **Same rule as §11: a dedicated job, not the
`/internal/jobs/notable-filings-scan` HTTP trigger** — `BackgroundTasks` callbacks die with
scale-to-zero; the endpoint is for one-off manual kicks only. EDGAR is keyless, so the job needs
only the DB secrets. The CD pipeline keeps the job image in sync once it exists (skips gracefully
otherwise). Create it once, with one Cloud Scheduler trigger:

```bash
CONN=earnings-nerd:us-west1:earningsnerd-db
SA="$(gcloud projects describe earnings-nerd --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
SECRETS=DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest
ENVV="^@^ENVIRONMENT=production@SKIP_REDIS_INIT=true"

gcloud run jobs create earningsnerd-notable-filings --region=us-west1 \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --cpu=1 --memory=1Gi --task-timeout=900 \
  --set-cloudsql-instances="$CONN" --set-secrets="$SECRETS" --set-env-vars="$ENVV" \
  --command=python --args=scripts/notable_filings_job.py

# 08:30 + 18:30 America/New_York — after the BMO (~06:00-08:30 ET) and AMC (~16:05-17:30 ET)
# filing waves; EFTS indexes within minutes. No collision with the §10/§11 job slots.
gcloud scheduler jobs create http notable-filings-scan --location=us-west1 \
  --schedule="30 8,18 * * *" --time-zone="America/New_York" \
  --uri="https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-notable-filings:run" \
  --http-method=POST --oauth-service-account-email="${SA}"
```

First rollout (the section ships dark):
```bash
# 1. Smoke-test, then seed a full week so the section isn't empty on day one:
gcloud run jobs execute earningsnerd-notable-filings --region=us-west1 --wait
gcloud run jobs execute earningsnerd-notable-filings --region=us-west1 \
  --args="scripts/notable_filings_job.py,--days,7" --wait
# 2. Flip serving on (the scan runs regardless; the flag gates the API only):
gcloud run services update earningsnerd-backend --region=us-west1 \
  --update-env-vars=NOTABLE_FILINGS_ENABLED=true
# 3. Probe, then check the homepage (ISR revalidates within ~15 min):
#    curl "https://api.earningsnerd.io/api/notable_filings?limit=8"
```

---

## Troubleshooting

- **Health probe timeout on deploy:** check logs with
  `gcloud run services logs read earningsnerd-backend --region=us-west1`.
- **`could not connect to server` / socket errors:** confirm `--add-cloudsql-instances` matches the
  instance connection name and the service account has `roles/cloudsql.client`.
- **Raising capacity:** bump `--max-instances` (and size up Cloud SQL); keep
  `max-instances × concurrency` comfortably under the DB's `max_connections`.
- **Cold starts:** the deploy sets `--cpu-boost` (startup CPU boost) to shorten them while keeping
  scale-to-zero (negligible cost). To *eliminate* them entirely (always-warm cost):
  `gcloud run services update earningsnerd-backend --region=us-west1 --min-instances=1`.

> Migrated off Render.com (June 2026). Superseded Render/Vercel/Firebase deployment notes are
> archived under [`docs/history/`](./history/) for provenance.
