/**
 * The analytics clause the consent dialog and /privacy both say (docs/brand/decisions-log.md D-046, F33): what
 * PostHog's usage statistics are for, and that a logged-in reader's are tied to an internal account id
 * (hooks/usePostHogUserIdentification.ts identifies by the account's id, and only once analytics are allowed).
 * One constant, so the two cannot drift (tests/unit/legalTruth.spec.tsx). A plain module, not a client one, so the
 * server-rendered /privacy reads the value itself.
 */
export const ANALYTICS_CONSENT_CLAUSE =
  'Usage statistics through PostHog, so we can see which pages work. When you are logged in they are tied to an internal account id.'
