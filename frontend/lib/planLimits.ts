/**
 * Plan facts the copy states: the free-tier caps mirrored from the server's entitlement constants
 * (`backend/app/services/entitlements.py`: FREE_TIER_SUMMARY_LIMIT, FREE_EARNINGS_ALERT_LIMIT), and
 * the flag-following plan lines below.
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
 * Every plan-benefit line that names Multi-Period Analysis, typed once here: the upgrade dialog's
 * sentence, the /pricing Pro card and the landing's two plan cards. The feature ships behind
 * NEXT_PUBLIC_ENABLE_ANALYSIS (its route 404s while the flag is off), so a list takes its line through
 * `analysisLine()`, which reads the flag at call time and returns nothing while it is off.
 * `tests/unit/analysis-route-hidden.spec.tsx` renders the lists both ways and fails on a string or JSX
 * text naming the feature anywhere else, outside the analysis feature itself and a short reasoned list.
 */
const ANALYSIS_LINES = {
  upgradeDialog: 'Multi-Period Analysis',
  pricingPro: 'Unlimited Multi-Period Analysis: 10-year trends, quarterly deltas & AI narrative',
  landingPro: 'Unlimited Multi-Period Analysis',
  landingFree: 'Multi-Period Analysis demo (locked)',
} as const

/** The Multi-Period Analysis line for one plan list while the flag ships it, else none: spread it in. */
export function analysisLine(list: keyof typeof ANALYSIS_LINES): string[] {
  return ENABLE_ANALYSIS ? [ANALYSIS_LINES[list]] : []
}

/**
 * The upgrade dialog's Pro list, one shared sentence. Multi-Period Analysis joins it only while the
 * flag ships it (analysisLine above).
 */
export function proIncludes(): string {
  const items = ['unlimited summaries', 'hourly filing alerts', '8-K alerts', 'exports', ...analysisLine('upgradeDialog')]
  return `Pro includes ${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}.`
}
