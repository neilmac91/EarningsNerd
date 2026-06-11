# Launch Runbook — Gate Flip & Phase 4 Measurement

*Companion to `tasks/homepage-redesign-v2.md` (Phases 0–3 shipped in PR #241).
Every code prerequisite is done; the steps below are operator actions.*

## A. Pre-flip (do in order)

1. **Merge PR #241** and confirm the production deploys are green
   (Vercel frontend + Cloud Run backend — `gcloud run services describe
   earningsnerd-backend --region=us-west1`).
2. **Create the example-refresh job on Cloud Run** — `earningsnerd-pregenerate`
   job + weekly Cloud Scheduler trigger, with secrets attached via
   `--set-secrets` (see `tasks/gcp-deploy-runbook.md` Phase 9).
3. **Pre-generate the example summaries** (don't wait for the weekly cron):
   `gcloud run jobs execute earningsnerd-pregenerate --region=us-west1 --wait`,
   then copy the **AAPL filing id** from the execution logs
   (Cloud Console → Cloud Run → Jobs → latest execution → Logs, or
   `gcloud logging read 'resource.type=cloud_run_job AND
   resource.labels.job_name=earningsnerd-pregenerate' --limit=50
   --format='value(textPayload)'` — look for `AAPL: filing_id=...`).
   NOTE: the Cloud SQL database started fresh — filing ids from the old
   Render database are invalid.
4. **Set the frontend env vars on Vercel** (Production):
   - `NEXT_PUBLIC_EXAMPLE_FILING_ID=<filing id from step 3>` — without it,
     every "see a live example" CTA silently degrades to `/company/AAPL`.
   - `NEXT_PUBLIC_ENABLE_QUALITY_BADGE=true` — aligns the homepage's
     "honest about quality" claim with product behavior (S4 badge +
     regenerate, stops client-side notice-stripping).
   - Confirm `NEXT_PUBLIC_POSTHOG_KEY` is set — all frontend funnel events
     silently no-op without it.
5. **Set the backend env vars on Cloud Run**:
   `gcloud run services update earningsnerd-backend --region=us-west1
   --update-env-vars=ENABLE_GUEST_DAILY_QUOTA=true` (3/day per IP; never
   blocks the first summary). Confirm `POSTHOG_API_KEY` is set (as a secret
   or env var) — server-side generation events no-op without it.
6. **Smoke-test the preview/production** while still gated: `/company/AAPL`
   → recommended filing → summary generates; the example CTA on `/waitlist`
   lands on the cached example instantly; events appear in PostHog
   (Activity view: `generation_started` … `summary_viewed`).

## B. The flip

7. **Set `WAITLIST_MODE=false` on Vercel** (Production) and redeploy.
   `/` now serves the homepage statically; middleware no longer 307s.
   Rollback is the same env var set back to unset/`true`.

## C. Immediately post-flip

8. **PostHog — define the activation funnel** (Insights → Funnel):
   1. `$pageview` where path = `/`
   2. ANY OF: `company_searched`, `quick_access_click`, `example_cta_clicked`
   3. `filing_viewed`
   4. `generation_started`
   5. `summary_viewed`  ← **activation = step 5 / step 1**, breakdown by
      `entry_point`.
9. **PostHog — guardrail insights** (one dashboard):
   - Generation success rate: `generation_succeeded` vs `generation_failed`
     + `generation_timed_out` (target from spec: watch failures from day 1).
   - `duration_ms` p50/p90 on `generation_succeeded` (time-to-summary).
   - `quality_verdict` split (full vs partial) on `generation_succeeded`.
   - `example_cta_clicked` CTR by `placement` (hero / hero_visual /
     hero_mobile_card / cta_banner / waitlist).
10. **Google Search Console**: verify `www.earningsnerd.io`, submit
    `https://www.earningsnerd.io/sitemap.xml`, and request indexing of `/`.
11. **Core Web Vitals**: watch Vercel Analytics (field data) against the
    spec targets — LCP < 2.5s, CLS < 0.1, INP < 200ms.

## D. Weeks 1–2 (baseline — no experiments yet)

12. Record the baseline: activation rate, search engagement rate, example
    CTR, time-to-first-summary p50/p90, generation success rate, signup
    rate among activated users.
13. Only after the baseline: A/B headline/hero variants via PostHog feature
    flags, with targets set relative to baseline (per spec §5 Phase 4 —
    Lighthouse alone is explicitly not a success metric).

## Deferred / optional

- **S1 adoption gate**: run the S3 eval harness (`backend/evals/`) with
  `AI_USE_STRUCTURED_OUTPUT` on vs off in an environment with provider
  keys; flip the default only if it wins on schema-validity + numeric
  accuracy + coverage.
- **SB6 real counters**: build the cached COUNT endpoint and show live
  numbers on the social-proof strip only once they impress on their own.
