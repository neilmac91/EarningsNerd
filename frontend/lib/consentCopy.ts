/**
 * The analytics clause the consent dialog and /privacy both say (docs/brand/decisions-log.md D-046, F33): what
 * PostHog's usage statistics are for, and that a logged-in reader's are tied to an internal account id
 * (hooks/usePostHogUserIdentification.ts identifies by the account's id, and only once analytics are allowed).
 * One constant, so the two cannot drift (tests/unit/legalTruth.spec.tsx). A plain module, not a client one, so the
 * server-rendered /privacy reads the value itself.
 */
export const ANALYTICS_CONSENT_CLAUSE =
  'Usage statistics through PostHog, so we can see which pages work. When you are logged in they are tied to an internal account id.'

/**
 * The account events the API records whatever the reader chose in the consent dialog (D-051): sign-ups and
 * invites (routers/auth.py), Stripe's subscription, trial and payment events (services/subscription_webhook_service.py,
 * services/billing_revenue_service.py), feedback (routers/feedback.py), and Ask this Filing answers, Multi-Period
 * Analysis runs and alert-email clicks (routers/summaries.py, routers/analysis.py, routers/webhooks.py), each keyed on
 * the account id. In generic words that name no provider, as the founder asked; the second sentence keeps the
 * browser's consent wording from reading as covering these events. /security and /privacy both say it, and
 * tests/unit/legalTruth.spec.tsx holds each example to those capture_event callers.
 */
export const ACCOUNT_EVENTS_DISCLOSURE =
  'The service also records how accounts use it, such as sign-ups, plan changes, payments, feedback and feature use, against your internal account id, to run and improve it. This does not depend on your analytics choice.'
