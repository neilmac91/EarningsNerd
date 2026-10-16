/**
 * Plan facts the copy states: the free-tier caps mirrored from the server's entitlement constants
 * (`backend/app/services/entitlements.py`: FREE_TIER_SUMMARY_LIMIT, FREE_EARNINGS_ALERT_LIMIT), and
 * the plan lines a feature flag decides, with their one reader, below.
 *
 * The server remains the only source of plan truth (CLAUDE.md rule 4): signed-in surfaces read
 * `summaries_limit` from `/api/subscriptions/usage`, and alert caps are enforced by the API's 403.
 * These constants exist only for guest-facing copy and pre-flight UI that renders before any usage
 * response exists. Never hardcode the numbers elsewhere — `tests/unit/planLimitsLockstep.spec.ts`
 * fails when a value diverges from the backend or a bare literal reappears in copy.
 */
import { ENABLE_ANALYSIS, ENABLE_FPI_FILINGS } from './featureFlags'

export const FREE_SUMMARY_LIMIT = 5
export const FREE_EARNINGS_ALERT_LIMIT = 3

/**
 * The Pro trial's length, for copy only. The trial exists only while the backend's PRO_TRIAL_DAYS is
 * set (it defaults to 0 in backend/app/config.py) and the UI flag ENABLE_PRO_TRIAL is on, flipped
 * together; every sentence that states the length reads this constant under that flag
 * (`tests/unit/planLimitsLockstep.spec.ts`).
 */
export const TRIAL_DAYS = 7

/**
 * Two more free-tier facts the marketing pricing card states, mirrored from the same
 * `_FREE = Entitlements(...)` block (`copilot_free_taste`, `history_retention_days`). Same
 * lockstep spec keeps them honest.
 */
export const FREE_COPILOT_QUESTIONS = 3
export const FREE_HISTORY_RETENTION_DAYS = 90

/** A flag a plan line follows: `analysis` is NEXT_PUBLIC_ENABLE_ANALYSIS, `fpi` NEXT_PUBLIC_ENABLE_FPI_FILINGS. */
export type PlanFlag = 'analysis' | 'fpi'

/**
 * One plan line, in #1311's shape (D-040): a line with no flag always lists; a line keyed to a flag lists
 * `text` while that flag ships the feature it names and `off` while it does not, or nothing if it has no
 * `off`. The lines a flag decides are typed once, below; the plan lists read every line through shipped().
 */
export interface PlanLine {
  readonly text: string
  readonly flag?: PlanFlag
  readonly off?: string
}

// Read at call time, and only the flag a line names, so a page lists what the flags it ships with turn on.
const FLAG_ON: Record<PlanFlag, () => boolean> = {
  analysis: () => ENABLE_ANALYSIS,
  fpi: () => ENABLE_FPI_FILINGS,
}

/** The one reader of plan lines: each line's text while its flag is on, its `off` (or nothing) while not. */
export function shipped(lines: readonly PlanLine[]): string[] {
  return lines.flatMap((line) => (!line.flag || FLAG_ON[line.flag]() ? [line.text] : line.off ? [line.off] : []))
}

/**
 * Every plan line the analysis flag decides, typed once: the lines that name Multi-Period Analysis (the
 * upgrade dialog's sentence, the /pricing Pro card, the landing's two plan cards and the /pricing Product
 * JSON-LD) and the Pro exports line, whose Excel workbook is the analysis export. The feature ships behind
 * NEXT_PUBLIC_ENABLE_ANALYSIS (its route 404s while the flag is off), so each list takes these entries and
 * reads them through shipped(). tests/unit/analysis-route-hidden.spec.tsx renders every list both ways and
 * fails on a string or JSX text naming the feature outside this declaration, the route's own files and a
 * short reasoned list.
 */
export const ANALYSIS_LINES = {
  upgradeDialog: { text: 'Multi-Period Analysis', flag: 'analysis' },
  pricingPro: { text: 'Unlimited Multi-Period Analysis: 10-year trends, quarterly deltas & AI narrative', flag: 'analysis' },
  landingPro: { text: 'Unlimited Multi-Period Analysis', flag: 'analysis' },
  landingFree: { text: 'Multi-Period Analysis demo (locked)', flag: 'analysis' },
  productJsonLd: { text: 'multi-period analysis', flag: 'analysis' },
  exports: { text: 'PDF, CSV and Excel exports', flag: 'analysis', off: 'PDF and CSV exports' },
} as const satisfies Record<string, PlanLine>

/**
 * The filing forms the Free plan names: 20-F only while NEXT_PUBLIC_ENABLE_FPI_FILINGS mirrors the API's
 * ENABLE_FPI_FILINGS (tasks/todo.md F39), so the cards never name a form the API keeps off.
 */
export const FILING_FORMS_LINE: PlanLine = {
  text: '10-K, 10-Q and 20-F filings from SEC EDGAR',
  flag: 'fpi',
  off: '10-K and 10-Q filings from SEC EDGAR',
}

const PRO_INCLUDES: readonly PlanLine[] = [
  { text: 'unlimited summaries' },
  { text: 'hourly filing alerts' },
  { text: '8-K alerts' },
  { text: 'exports' },
  ANALYSIS_LINES.upgradeDialog,
]

/**
 * The upgrade dialog's Pro list, one shared sentence. Multi-Period Analysis joins it only while the flag
 * ships it (shipped() above).
 */
export function proIncludes(): string {
  const items = shipped(PRO_INCLUDES)
  return `Pro includes ${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}.`
}
