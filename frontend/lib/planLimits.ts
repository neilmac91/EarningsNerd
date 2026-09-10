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
export const FREE_SUMMARY_LIMIT = 5
export const FREE_EARNINGS_ALERT_LIMIT = 3

/**
 * Two more free-tier facts the marketing pricing card states, mirrored from the same
 * `_FREE = Entitlements(...)` block (`copilot_free_taste`, `history_retention_days`). Same
 * lockstep spec keeps them honest.
 */
export const FREE_COPILOT_QUESTIONS = 3
export const FREE_HISTORY_RETENTION_DAYS = 90
