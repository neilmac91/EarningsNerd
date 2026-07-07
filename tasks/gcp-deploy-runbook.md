# Cloud Run Deploy Runbook — EarningsNerd Backend

Project: `earnings-nerd` · Region: `us-west1` · DB: `db-g1-small` · Redis: off · Migrations: in-container.
Run everything in **Google Cloud Shell** (https://console.cloud.google.com → `>_`).

Success criteria per phase are noted. If a step errors, stop and report it — don't push past it.

---

## Phase 1 — Project setup & APIs
```bash
gcloud config set project earnings-nerd
gcloud services enable \
  run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com \
  cloudscheduler.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
```
✅ Success: "Operation finished successfully" / returns to prompt with no error.

## Phase 2 — Get the code & build the image
```bash
gh auth login          # GitHub.com → HTTPS → "Login with a web browser", paste the code
gh repo clone neilmac91/EarningsNerd
cd EarningsNerd/backend

gcloud artifacts repositories create earningsnerd \
  --repository-format=docker --location=us-west1 \
  --description="EarningsNerd backend images"

gcloud builds submit \
  --tag us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest
```
✅ Success: build ends with `SUCCESS` and an image digest.

## Phase 3 — Cloud SQL (Postgres 15, fresh)
```bash
gcloud sql instances create earningsnerd-db \
  --database-version=POSTGRES_15 --tier=db-g1-small \
  --region=us-west1 --storage-size=10GB --storage-auto-increase
# ^ takes ~5-10 min

gcloud sql databases create earningsnerd --instance=earningsnerd-db

# Generate a URL-safe password and create the app user
DB_PASS=$(openssl rand -hex 24)
gcloud sql users create appuser --instance=earningsnerd-db --password="$DB_PASS"

# Capture the instance connection name
CONN=$(gcloud sql instances describe earningsnerd-db --format='value(connectionName)')
echo "Connection name: $CONN"
```
✅ Success: `$CONN` prints `earnings-nerd:us-west1:earningsnerd-db`.

## Phase 4 — Secrets (Secret Manager)
First the generated DB URL (uses the Cloud SQL socket — keep this in the SAME shell session as Phase 3):
```bash
printf 'postgresql://appuser:%s@/earningsnerd?host=/cloudsql/%s' "$DB_PASS" "$CONN" \
  | gcloud secrets create DATABASE_URL --data-file=-
```
Now your Render secrets — **replace each `PASTE_...` with the real value** from Render → earningsnerd-backend → Environment:
```bash
printf '%s' 'PASTE_OPENAI_API_KEY'        | gcloud secrets create OPENAI_API_KEY        --data-file=-
printf '%s' 'PASTE_SECRET_KEY'            | gcloud secrets create SECRET_KEY            --data-file=-
printf '%s' 'PASTE_STRIPE_SECRET_KEY'     | gcloud secrets create STRIPE_SECRET_KEY     --data-file=-
printf '%s' 'PASTE_STRIPE_PUBLISHABLE'    | gcloud secrets create STRIPE_PUBLISHABLE_KEY --data-file=-
printf '%s' 'PASTE_STRIPE_WEBHOOK_SECRET' | gcloud secrets create STRIPE_WEBHOOK_SECRET --data-file=-
printf '%s' 'PASTE_RESEND_API_KEY'        | gcloud secrets create RESEND_API_KEY        --data-file=-
printf '%s' 'PASTE_RESEND_FROM_EMAIL'     | gcloud secrets create RESEND_FROM_EMAIL     --data-file=-
printf '%s' 'PASTE_FINNHUB_API_KEY'       | gcloud secrets create FINNHUB_API_KEY       --data-file=-
```
✅ Success: each prints `Created secret [NAME]`.

## Phase 5 — Grant the runtime service account access
```bash
PROJECT_NUMBER=$(gcloud projects describe earnings-nerd --format='value(projectNumber)')
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding earnings-nerd \
  --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding earnings-nerd \
  --member="serviceAccount:${SA}" --role="roles/cloudsql.client"
```
✅ Success: each prints an updated IAM policy.

## Phase 6 — Deploy to Cloud Run
```bash
gcloud run deploy earningsnerd-backend \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --region=us-west1 --allow-unauthenticated \
  --add-cloudsql-instances=earnings-nerd:us-west1:earningsnerd-db \
  --cpu=1 --memory=1Gi --cpu-boost \
  --min-instances=1 --max-instances=2 --concurrency=40 --timeout=600 \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest,STRIPE_SECRET_KEY=STRIPE_SECRET_KEY:latest,STRIPE_PUBLISHABLE_KEY=STRIPE_PUBLISHABLE_KEY:latest,STRIPE_WEBHOOK_SECRET=STRIPE_WEBHOOK_SECRET:latest,RESEND_API_KEY=RESEND_API_KEY:latest,RESEND_FROM_EMAIL=RESEND_FROM_EMAIL:latest,FINNHUB_API_KEY=FINNHUB_API_KEY:latest \
  --set-env-vars="^@^ENVIRONMENT=production@SKIP_REDIS_INIT=true@OPENAI_BASE_URL=https://api.deepseek.com/v1@AI_DEFAULT_MODEL=deepseek-v4-pro@SEC_EDGAR_BASE_URL=https://data.sec.gov@FINNHUB_API_BASE=https://finnhub.io/api/v1@EARNINGS_WHISPERS_API_BASE=https://www.earningswhispers.com/api@CORS_ORIGINS_STR=https://earningsnerd.io,https://www.earningsnerd.io"
```
✅ Success: prints `Service [earningsnerd-backend] revision ... has been deployed` and a `Service URL`.

## Phase 7 — Verify
```bash
SVC=$(gcloud run services describe earningsnerd-backend --region=us-west1 --format='value(status.url)')
curl -s $SVC/health ; echo
curl -s $SVC/health/detailed ; echo
```
✅ Success: `/health` → `{"status":"healthy"}`. `/health/detailed` → database `healthy:true`,
redis shows degraded/unhealthy (EXPECTED — Redis is off), circuit breaker `closed`.

## Phase 8 — Point api.earningsnerd.io at Cloud Run
```bash
gcloud beta run domain-mappings create \
  --service=earningsnerd-backend --domain=api.earningsnerd.io --region=us-west1
```
- If it asks you to **verify domain ownership**, follow the link, add the TXT record it gives you
  in Cloudflare, then re-run. (You already have Google verification on this domain, so it may skip this.)
- It prints a DNS target (usually `ghs.googlehosted.com`). In **Cloudflare**, edit the `api`
  record → CNAME → that target → keep **DNS-only (grey cloud)** → save.
- Wait for the managed TLS cert (a few min to ~an hour), then:
```bash
curl -s https://api.earningsnerd.io/health ; echo
```
✅ Success: returns `{"status":"healthy"}` from the new origin.

## Phase 9 (optional, last) — Weekly example-refresh cron
```bash
gcloud run jobs create earningsnerd-pregenerate \
  --image=us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:latest \
  --region=us-west1 \
  --set-cloudsql-instances=earnings-nerd:us-west1:earningsnerd-db \
  --cpu=1 --memory=1Gi --task-timeout=3600 \
  --set-secrets=DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest \
  --set-env-vars="^@^ENVIRONMENT=production@SKIP_REDIS_INIT=true@OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/@SEC_EDGAR_BASE_URL=https://data.sec.gov" \
  --command=python --args=scripts/pregenerate_examples.py

gcloud projects add-iam-policy-binding earnings-nerd \
  --member="serviceAccount:${SA}" --role="roles/run.invoker"

gcloud scheduler jobs create http earningsnerd-pregenerate-weekly \
  --location=us-west1 --schedule="0 6 * * 1" \
  --uri="https://us-west1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/earnings-nerd/jobs/earningsnerd-pregenerate:run" \
  --http-method=POST --oauth-service-account-email="${SA}"
```
✅ Success: job + scheduler created. Test now: `gcloud run jobs execute earningsnerd-pregenerate --region=us-west1`.

---

## After it's verified in prod for a few days — decommission Render
- Suspend/delete the Render `earningsnerd-backend` web service, the `earningsnerd-pregenerate-examples`
  cron, and the dead Postgres.
- Archive/remove `render.yaml`; update the Deployment section of `CLAUDE.md`.

## Troubleshooting
- **Deploy fails on startup / health probe timeout:** the container runs `alembic upgrade head`
  before uvicorn. On a fresh DB this is fast; if it ever times out, we move migrations to their own
  Cloud Run Job. Check logs: `gcloud run services logs read earningsnerd-backend --region=us-west1`.
- **`could not connect to server` / socket errors:** confirm `--add-cloudsql-instances` matches
  `$CONN` and the SA has `roles/cloudsql.client`.
- **Raising capacity later:** bump `--max-instances` (and size up Cloud SQL) — keep
  `max-instances × 10` under the DB's `max_connections`.
- **Cold starts:** the service runs `--min-instances=1` (one always-warm instance) plus `--cpu-boost`,
  re-asserted by CI on every deploy — so there are no cold starts and per-process caches survive. To
  save cost by allowing scale-to-zero instead: set `--min-instances=0` in the ci.yml deploy step.
