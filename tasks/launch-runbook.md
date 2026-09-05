# Launch Runbook — Gate Flip & Phase 4 Measurement

*The [homepage redesign archive](archive/homepage-redesign-v2.md) records Phases 0–3 shipped
in historical PR #241. Updated 2026-09-05: code deployment does not verify the operator,
cache, analytics or launch conditions below. Confirm current state before changing it;
remaining accepted policies and founder boundaries are in the [handover](handover-wave2-2026-09.md).*

## A. Pre-flip (do in order)

1. **PR #241 is historical and merged.** Confirm current production deployments against the
   [verified engineering ledger](wave2-ledger-2026-09.md)
   (Vercel frontend + Cloud Run backend — `gcloud run services describe
   earningsnerd-backend --region=us-west1`).
2. **Verify the existing example-refresh job** — `earningsnerd-pregenerate`
   image and FPI/10-Q environment updates were observed in deployment. Confirm its effective
   secrets and weekly Scheduler trigger before execution (see `tasks/gcp-deploy-runbook.md` Phase 9);
   do not create a duplicate job or infer the trigger is healthy from a service deploy.
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
   - Confirm effective `NEXT_PUBLIC_ENABLE_QUALITY_BADGE=true` (already declared in repository config) — aligns the homepage's
     "honest about quality" claim with product behavior (S4 badge +
     regenerate, stops client-side notice-stripping).
   - Confirm `NEXT_PUBLIC_POSTHOG_KEY` is set — all frontend funnel events
     silently no-op without it.
5. **Backend env vars on Cloud Run**: guest generation no longer exists
   (generation requires an account since #619 — the old
   `ENABLE_GUEST_DAILY_QUOTA` flag was deleted; deploys now clear it via
   `--remove-env-vars`). Confirm `POSTHOG_API_KEY` is set (as a secret
   or env var) — server-side generation events no-op without it.
   **7-day Pro trial (ships dark):** the trial defaults OFF
   (`PRO_TRIAL_DAYS=0`). Enable it only after the PR #619 Stripe test-mode
   checklist passes (trial checkout collects a card, cancel-in-trial is
   free, day-8 charge converts, billing-portal cancellation is enabled in
   the Stripe Dashboard): set `PRO_TRIAL_DAYS=7` on the Cloud Run service
   AND `NEXT_PUBLIC_ENABLE_PRO_TRIAL=true` on Vercel in the same change —
   the UI trial copy and the checkout behavior must flip together.
6. **Smoke-test the preview/production** while still gated (sign in first —
   generation requires an account since #619): `/company/AAPL`
   → recommended filing → summary generates; the example CTA on `/waitlist`
   lands on the cached example instantly; events appear in PostHog
   (Activity view: `generation_started` … `summary_viewed`).

## B. The flip

7. **Confirm founder WAITLIST intent and effective Vercel state.** Repository config already
   declares `WAITLIST_MODE=false`; a console override may differ. Make a coordinated change
   only for the accepted launch state, then verify `/` and middleware behavior.
   Rollback uses `WAITLIST_MODE=true` with redeployment.

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
  `USE_STRUCTURED_OUTPUT` on vs off in an environment with provider
  keys; flip the default only if it wins on schema-validity + numeric
  accuracy + coverage.
- **SB6 real counters**: build the cached COUNT endpoint and show live
  numbers on the social-proof strip only once they impress on their own.
