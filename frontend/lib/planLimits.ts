/**
 * Free-tier caps mirrored from the server's entitlement constants
 * (`backend/app/services/entitlements.py`: FREE_TIER_SUMMARY_LIMIT, FREE_EARNINGS_ALERT_LIMIT).
 *
 * The server remains the only source of plan truth (CLAUDE.md rule 4): signed-in surfaces read
 * `summaries_limit` from `/api/subscriptions/usage`, and alert caps are enforced by the API's 403.
 * These constants exist only for guest-facing copy and pre-flight UI that renders before any usage
 * response exists. Never hardcode the numbers elsewhere — `tests/unit/planLimitsLockstep.spec.ts`
 * fails when a value diverges from the backend or a bare literal reappears in copy.
 */
import { ENABLE_ANALYSIS } from './featureFlags'

export const FREE_SUMMARY_LIMIT = 5
export const FREE_EARNINGS_ALERT_LIMIT = 3

/**
 * Two more free-tier facts the marketing pricing card states, mirrored from the same
 * `_FREE = Entitlements(...)` block (`copilot_free_taste`, `history_retention_days`). Same
 * lockstep spec keeps them honest.
 */
export const FREE_COPILOT_QUESTIONS = 3
export const FREE_HISTORY_RETENTION_DAYS = 90

/**
 * What Pro adds, as the one hand-typed list the product shows (the upgrade dialog and anything that
 * composes it). Multi-Period Analysis is named only while NEXT_PUBLIC_ENABLE_ANALYSIS ships it, read
 * at call time so the flag decides each render. `tests/unit/analysis-route-hidden.spec.tsx` renders
 * the dialog both ways and fails on a second "Pro includes" list anywhere else in the source.
 */
export function proIncludes(): string {
  const items = ['unlimited summaries', 'hourly filing alerts', '8-K alerts', 'exports']
  if (ENABLE_ANALYSIS) items.push('Multi-Period Analysis')
  return `Pro includes ${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}.`
}
