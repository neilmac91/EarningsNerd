# Beta Monitoring — PostHog funnel + Sentry attribution (roadmap Week 6)

How the closed beta is instrumented, and how to build the dashboards. This is the source-of-truth
for the analytics/observability wiring; the PostHog funnel + Sentry filters themselves are configured
in their respective UIs from the events/tags documented here.

## Distinct-id stitching (the thing that makes the funnel join)

Every server-side funnel event is keyed on **`str(user.id)`**. The frontend identifies on
**`String(user.id)`** (`analytics.identify` → `posthog.identify`, called from `app/login/page.tsx`
and `app/dashboard/page.tsx`). Because both sides use the same canonical id, server and client events
land on **one person** in PostHog with no separate alias step. Anonymous pre-login client events
(`signup_started`, `signup_submitted`) stitch to that person when `identify` runs at login.

> Invariant to preserve: never key a backend funnel event on anything but `str(user.id)`, and never
> identify the frontend on anything but `String(user.id)`.

## The beta activation funnel (PostHog)

Build a funnel in PostHog with these ordered steps:

| # | Step | Event | Source |
|---|------|-------|--------|
| 1 | Invite redeemed | `invite_redeemed` | backend `auth.register` (beta path) |
| 2 | Signup completed | `signup_completed` | backend `auth.register` (all paths) |
| 3 | Activated (first summary) | `generation_succeeded` | backend `summary_pipeline` |
| 4 | Asked Copilot | `copilot_question_asked` | frontend `lib/analytics.ts` |
| 5 | Gave feedback | `feedback_submitted` | backend `feedback` router |

`trial_started` (backend) is a side-signal, not a funnel step — it fires for reverse-trial grants
(`source: "reverse_trial"`, from `/register`) and Stripe-native trials (`source: "stripe"`, from the
subscription webhook). `subscription_activated` (existing) marks the $0-checkout → Pro conversion.

### Why there is no separate `first_summary_generated` event

A `Summary` belongs to a `Filing` (shared across users), not to a user, so "first summary **by this
user**" can't be computed cheaply in the SSE streaming hot path. PostHog funnels already dedupe to the
**first** occurrence of a step per person, so step 3 uses the existing `generation_succeeded` event
(keyed on the same distinct_id the frontend forwards on the stream request). This avoids a redundant
event + a per-request DB query. If a literal per-user "first" count is ever needed, add a
`users.first_summary_at` timestamp column and emit on the nil→set transition — not before.

### Event property reference (new in Week 6)

| Event | Properties | Notes |
|-------|------------|-------|
| `invite_redeemed` | `email_bound` (bool) | whether the invite was bound to a specific email |
| `signup_completed` | `is_beta` (bool), `invited` (bool) | no email/PII |
| `trial_started` | `source` (`reverse_trial`\|`stripe`), `days`/`trial_end` | |

All three are best-effort: wrapped so telemetry can never break or slow registration / webhooks.

## Sentry attribution

- **Release** = deployed git SHA. Backend reads `SENTRY_RELEASE` (CI sets it to `$GITHUB_SHA` on the
  Cloud Run service, see `.github/workflows/ci.yml`). Frontend reads `NEXT_PUBLIC_SENTRY_RELEASE`,
  which `next.config.js` fills from Vercel's `VERCEL_GIT_COMMIT_SHA` at build time. Server + client
  errors group under one release.
- **User context** = `{ id: str(user.id) }`, set on every authenticated request in
  `auth.get_current_user` (backend) and on `analytics.identify` (frontend). Id only — no email/PII, so
  `send_default_pii=False` is respected. Cleared on the frontend at `analytics.reset` (logout).
- **Beta cohort tag** = `beta: true|false`, set alongside the user in `auth.get_current_user`. Filter
  Sentry issues by `beta:true` to triage tester-only regressions first.
- **Environment** = `ENVIRONMENT` (backend) / `VERCEL_ENV` (frontend) — already wired; documented here
  for completeness.

### Verifying it works

1. Trigger a test error (frontend `SentryTestButton`, or any 500) while logged in as a beta user.
2. In Sentry, the issue should show the user id, `beta: true`, and a `release` matching the deployed
   SHA. Filtering `beta:true` should surface it.

## Required env vars (set in prod at go-live — Week 8)

| Var | Where | Value |
|-----|-------|-------|
| `POSTHOG_API_KEY` / `POSTHOG_HOST` | Cloud Run (backend) | project key + host |
| `NEXT_PUBLIC_POSTHOG_KEY` / `NEXT_PUBLIC_POSTHOG_HOST` | Vercel (frontend) | project key + host |
| `SENTRY_DSN` | Cloud Run | backend DSN |
| `SENTRY_RELEASE` | Cloud Run | `$GITHUB_SHA` — **auto-set by CI deploy**; no manual step |
| `NEXT_PUBLIC_SENTRY_DSN` | Vercel | frontend DSN |
| `ENVIRONMENT` | Cloud Run | `production` |

PostHog/Sentry are **no-ops when their keys are unset** (both backend and frontend), so nothing breaks
in environments where they aren't configured.
