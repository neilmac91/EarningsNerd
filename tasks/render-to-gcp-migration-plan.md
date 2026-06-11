# Migration Plan — Render → Google Cloud (Backend)

Status: **PLAN ONLY** (awaiting review before generating artifacts).
Owner decisions captured: start DB **fresh** (no data migration), **skip Redis** at first,
**plan only** for now, cost-vs-warm call delegated → **scale-to-zero to launch**.

North star: `api.earningsnerd.io` serves a healthy FastAPI backend on Google Cloud at the
lowest sensible idle cost, with good streaming (SSE) performance and a one-flag path to
always-warm when traffic justifies it.

---

## 1. Target architecture (recommended)

| Concern | Today (Render) | Target (Google Cloud) |
|---|---|---|
| API compute | Render web `plan: standard`, 2 uvicorn workers | **Cloud Run** service, 1 worker/instance, autoscaling, scale-to-zero |
| Database | Render Postgres (host dead) | **Cloud SQL for PostgreSQL 15** |
| Cache | Redis 7 (L1 mem + L2 Redis) | **None initially** (L1 in-memory only); add **Memorystore** later if needed |
| Cron | Render cron `pregenerate_examples` weekly | **Cloud Scheduler → Cloud Run Job** |
| Migrations | `alembic upgrade head` in start cmd | Same container CMD initially; optionally promote to a Cloud Run **Job** later |
| Secrets | Render env (`sync:false`) | **Secret Manager** mounted as env vars |
| Custom domain/TLS | Render-managed cert | Cloud Run domain mapping (or HTTPS LB) + Cloudflare DNS-only CNAME |

Why Cloud Run: runs the existing container as-is, native SSE/streaming, request timeout up to
60 min (your `STREAM_TIMEOUT=600s` fits), scale-to-zero for cost, trivial flip to min-instances=1
for warmth. App Engine Flex / GKE / Cloud Functions are all worse fits (see chat assessment).

---

## 2. What's already done (no work needed)

- `backend/Dockerfile` exists and is **Cloud Run-tuned**: `python:3.11-slim`, system libs for
  psycopg2/weasyprint/lxml, `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5`, `PORT=8080`, single worker.
- `backend/.dockerignore` exists.
- Redis is **optional in code**: `get_redis_pool()` returns `None` on failure
  (`redis_service.py:229`) and cache helpers fall back gracefully → safe to launch without Redis.

---

## 3. Pre-work / code changes to land BEFORE cutover

- [ ] **Disable Redis cleanly.** Set `SKIP_REDIS_INIT=true` (skips the 3s startup probe in
      `main.py:126-138`) and leave `REDIS_URL` unset. Verify no runtime path hard-requires Redis
      (cache helpers already 2s-timeout + degrade). Add a smoke check that a summary generates
      with Redis absent.
- [ ] **Connection-pool vs Cloud SQL max_connections.** Cloud SQL `db-f1-micro` allows only
      ~25 connections. With `DB_POOL_SIZE=5 + overflow=5 = 10` per instance, cap
      `--max-instances` (e.g. 2 on micro) OR size the DB up so `max-instances × 10 < db max_conns`.
      Document the chosen ceiling. (This is the #1 production gotcha for serverless + Postgres.)
- [ ] **Decide migrations location.** Keep `alembic upgrade head` in the container CMD for launch
      (idempotent; small cold-start cost), with a follow-up to move it to a dedicated Cloud Run
      Job to avoid concurrent-startup migration races at higher scale.
- [ ] **CORS / host unchanged.** `CORS_ORIGINS_STR` stays `https://earningsnerd.io,https://www.earningsnerd.io`;
      frontend `NEXT_PUBLIC_API_BASE_URL` stays `https://api.earningsnerd.io`. No frontend redeploy
      needed if we keep the same hostname.

---

## 4. Step-by-step migration

### Phase 0 — GCP prerequisites
- [ ] Confirm/create GCP project + **billing account** linked.
- [ ] Install/auth `gcloud`; set default project + region (recommend **`us-west1`/Oregon** to match
      current Render region and stay close to users).
- [ ] Enable APIs: `run`, `sqladmin`, `secretmanager`, `cloudscheduler`, `artifactregistry`,
      `cloudbuild`.

### Phase 1 — Build & store the image
- [ ] Create an **Artifact Registry** Docker repo.
- [ ] Build the existing `backend/Dockerfile` (Cloud Build or local) and push the image.

### Phase 2 — Cloud SQL (Postgres 15, fresh)
- [ ] Create instance. **Sizing recommendation:** start `db-g1-small` (~$25/mo, dedicated-ish,
      balanced cost/perf) — or `db-f1-micro` (~$9/mo) for absolute minimum, accepting the ~25-conn
      ceiling and shared-core latency. Cloud SQL has **no scale-to-zero**; it's the dominant fixed cost.
- [ ] Create database + app user; store the password in Secret Manager.
- [ ] Choose connectivity: **Cloud SQL connector** (`--add-cloudsql-instances`, builds the
      `?host=/cloudsql/...` socket path) — no VPC connector needed. Set `DATABASE_URL` accordingly.
- [ ] Leave schema creation to `alembic upgrade head` on first deploy (fresh DB).

### Phase 3 — Secrets
- [ ] Put every `sync:false` value into Secret Manager: `DATABASE_URL`, `OPENAI_API_KEY`,
      `SECRET_KEY`, `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`,
      `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `FINNHUB_API_KEY`. (Omit `REDIS_URL`.)
- [ ] Plain env (non-secret), mirror `render.yaml`: `OPENAI_BASE_URL`, `EARNINGS_WHISPERS_API_BASE`,
      `FINNHUB_API_BASE`, `SEC_EDGAR_BASE_URL`, `ENVIRONMENT=production`, `CORS_ORIGINS_STR`,
      `SKIP_REDIS_INIT=true`, plus the Dockerfile's `DB_POOL_*` (already baked in).

### Phase 4 — Deploy the API to Cloud Run
- [ ] `gcloud run deploy earningsnerd-backend` with:
  - region `us-west1`, `--cpu=1 --memory=512Mi` (bump to 1Gi if weasyprint/PDF export OOMs),
  - `--min-instances=0` (scale-to-zero) `--max-instances=<conn-safe cap>`,
  - `--concurrency=40` (tune for SSE — long streams hold a slot for their lifetime),
  - `--timeout=600` (matches `STREAM_TIMEOUT`),
  - `--add-cloudsql-instances=<instance>`, secrets + env from Phase 3,
  - `--no-cpu-throttling` only if streaming stalls during idle CPU (else default for cost).
- [ ] Hit the `*.run.app` URL: `/health` → 200, `/health/detailed` → DB healthy, Redis "degraded"
      (expected), circuit breaker closed.

### Phase 5 — Cron (pregenerate examples)
- [ ] Create a **Cloud Run Job** running `python scripts/pregenerate_examples.py` (same image,
      same secrets + Cloud SQL connection).
- [ ] **Cloud Scheduler** trigger: `0 6 * * 1` (Mon 06:00 UTC), invoking the Job. (First 3
      Scheduler jobs are free.)

### Phase 6 — Custom domain + DNS cutover
- [ ] Add a Cloud Run **domain mapping** for `api.earningsnerd.io` (or front with an HTTPS Load
      Balancer if you later want Cloud Armor/CDN).
- [ ] In Cloudflare, repoint the `api` record to the Google target (keep **DNS-only / grey cloud**,
      as today). Wait for Google-managed cert to provision.
- [ ] Verify `https://api.earningsnerd.io/health` → 200 from the Cloud Run origin.

### Phase 7 — Verify end-to-end (don't mark done until proven)
- [ ] Frontend (Vercel, unchanged) loads and talks to the new backend (CORS ok).
- [ ] **Full SSE summary generation** completes end-to-end (the streaming path is the riskiest).
- [ ] Stripe webhook reachable at the new origin; Resend email send works.
- [ ] Cold-start latency observed and acceptable (~1–3s first request after idle).
- [ ] `/metrics` shows sane request/cache/db numbers.

### Phase 8 — Decommission Render
- [ ] Leave Render running until GCP is verified in prod for a few days.
- [ ] Then suspend/delete the Render web + cron services and the dead Postgres.
- [ ] Update `render.yaml` (archive or remove) and this repo's deploy docs / `CLAUDE.md`
      Deployment section.

---

## 5. Cost estimate (rough, monthly, USD)

| Item | Lean (recommended launch) | Comfortable (later) |
|---|---|---|
| Cloud Run | scale-to-zero ≈ **$0–10** | min-1 warm ≈ $15–60 |
| Cloud SQL | db-f1-micro ≈ **$9** | db-g1-small + storage ≈ $25–35 |
| Memorystore Redis | **$0** (skipped) | ~$35 (1GB Basic) |
| Cloud Scheduler | **$0** (free tier) | $0 |
| Artifact Registry / egress | ~$1–3 | a few $ |
| **Total** | **≈ $10–25/mo** | ≈ $75–130/mo |

For comparison: ~$40–60/mo on Render today with no scale-to-zero. Lean GCP is **cheaper and
elastic**; the main fixed floor is Cloud SQL (no scale-to-zero).

---

## 6. Performance notes / risks

- **SSE + concurrency:** each open stream consumes a Cloud Run concurrency slot for up to 10 min.
  Tune `--concurrency` and `--max-instances` so streams don't starve normal requests. Primary tuning knob.
- **Cold starts:** scale-to-zero adds ~1–3s on the first request after idle (image pull + app +
  DB validate in `main.py:78-94`, which has a 5s timeout — comfortably fits). Flip to
  `--min-instances=1` to eliminate, at always-warm cost.
- **DB connections:** see Phase 3 pre-work — cap instances against Cloud SQL `max_connections`.
- **AI latency upside:** running on GCP sits next to Gemini/AI Studio endpoints → lower
  summarization latency; optional future move to Vertex AI without leaving the network.

---

## 7. Rollback

DNS is the cutover switch. If anything fails post-cutover, repoint the Cloudflare `api` record
back to `earningsnerd.onrender.com` (Render kept alive through Phase 8). Because the DB started
fresh, there's no data divergence to reconcile during the overlap window.

---

## 8. Open items to confirm before I generate artifacts

1. GCP **project ID + billing** ready? Preferred **region** (default: `us-west1`/Oregon)?
2. Cloud SQL size: **db-f1-micro** (cheapest) vs **db-g1-small** (balanced) — recommend g1-small.
3. Delivery format when we proceed: **gcloud runbook** vs **Terraform**.
4. Keep `alembic` in the container CMD for launch, or set up the migration **Job** now?
