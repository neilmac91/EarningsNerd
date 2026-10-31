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
import { fmtCount } from './format'

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
 * One more free-tier fact the marketing pricing card states, mirrored from the same
 * `_FREE = Entitlements(...)` block (`copilot_free_taste`). Same lockstep spec keeps it honest.
 * The block's `history_retention_days` has no mirror: nothing enforces it (entitlements.py calls it
 * forward-looking), so no copy claims a summary history or its length while that holds (D-046;
 * tests/unit/summaryPlanClaims.spec.ts).
 */
export const FREE_COPILOT_QUESTIONS = 3

/**
 * Pro's summary and analysis fair-use ceilings, mirrored from backend/app/services/entitlements.py's plan constants of
 * the same names (D-050; the Copilot's ceiling is a setting its usage response states). The lockstep spec holds both,
 * and fails if backend/app/config.py binds either name to a setting (a field in any case, or an alias), so no deploy
 * can move a ceiling the page states. Pro's summaries and Multi-Period Analysis are unlimited as a plan, and these
 * bound the generations one account runs in a calendar month (UTC), regenerations included, so the copy counts
 * generations, never new summaries or analyses. Every summary run the usage gate admits takes a unit when its
 * provider request is issued, a Pro regeneration among them; a provider failure, the pipeline's timeout or a partial
 * verdict under the quality gate gives the unit back, and a run the reader leaves after the request is issued keeps
 * it; a stored summary served or a run joined in flight never takes one. An analysis run takes a unit when its fresh
 * narrative completes, a reader's forced refresh among them; a cached re-serve never takes one, nor does a
 * regeneration the system starts after new facts or a prompt change once its result is stored
 * (tests/unit/summaryPlanClaims.spec.ts holds the copy to both). Both are stated once, in proFairUseLine() below,
 * which the /pricing FAQ and the filing page's monthly-limit card place (E58, D-046), while the plan cards, the
 * dashboard strip, BillingPanel, the upgrade dialog and the signup gate keep "Unlimited" (D-040). At each ceiling the
 * reader is told the same unit: the filing page's card at the summary ceiling
 * (features/summaries/lib/streamErrorCopy.ts) and the analysis route's 429 (backend/app/routers/analysis.py), which
 * also states the number.
 */
export const PRO_SUMMARY_MONTHLY_CAP = 300
export const ANALYSIS_MONTHLY_CAP = 1000

/**
 * Multi-Period Analysis period caps, mirrored from `backend/app/config.py` (ANALYSIS_MAX_ANNUAL_PERIODS,
 * ANALYSIS_MAX_QUARTERLY_PERIODS defaults). The picker reads the live values from the coverage
 * response (`limits`); these exist for copy that renders before it (the /analysis metadata and lead,
 * the landing, and the /pricing Pro card's line in ANALYSIS_LINES below, which reads the annual cap as
 * this module evaluates, so the caps are declared first). The same lockstep spec holds them to the
 * backend and bans the numbers typed in copy.
 */
export const ANALYSIS_MAX_ANNUAL_PERIODS = 10
export const ANALYSIS_MAX_QUARTERLY_PERIODS = 12

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
 * upgrade dialog's sentence, the /pricing Pro card, the landing's plan table and the /pricing Product
 * JSON-LD), Pro's fair-use sentence, which states the analysis ceiling beside the summary one
 * (proFairUseLine() reads it), and the Pro exports line, whose Excel workbook is the analysis export. The
 * landing's table gives the feature a row of its own (D-045): `landingRow` is the row's label, and
 * `landingFree` and `landingPro` are its two cells, which the label already names. The feature ships behind
 * NEXT_PUBLIC_ENABLE_ANALYSIS
 * (its route 404s while the flag is off), so each list takes these entries and reads them through
 * shipped(). tests/unit/analysis-route-hidden.spec.tsx renders every list both ways and fails on a string
 * or JSX text naming the feature outside this declaration, the route's own files and a short reasoned list.
 */
export const ANALYSIS_LINES = {
  upgradeDialog: { text: 'Multi-Period Analysis', flag: 'analysis' },
  pricingPro: { text: `Unlimited Multi-Period Analysis: ${ANALYSIS_MAX_ANNUAL_PERIODS}-year trends, quarterly deltas & AI narrative`, flag: 'analysis' },
  landingRow: { text: 'Multi-Period Analysis', flag: 'analysis' },
  landingPro: { text: 'Unlimited', flag: 'analysis' },
  landingFree: { text: 'Demo (locked)', flag: 'analysis' },
  productJsonLd: { text: 'multi-period analysis', flag: 'analysis' },
  fairUse: {
    text: `Pro's unlimited summaries and Multi-Period Analysis have fair-use ceilings: an account can run up to ${PRO_SUMMARY_MONTHLY_CAP} summary and ${fmtCount(ANALYSIS_MONTHLY_CAP)} analysis generations a month, regenerations included.`,
    flag: 'analysis',
    off: `Pro's unlimited summaries have a fair-use ceiling: an account can run up to ${PRO_SUMMARY_MONTHLY_CAP} summary generations a month, regenerations included.`,
  },
  exports: { text: 'PDF, CSV and Excel exports', flag: 'analysis', off: 'PDF and CSV exports' },
} as const satisfies Record<string, PlanLine>

/**
 * Pro's fair-use sentence (E58, D-050), the one place copy states Pro's summary and analysis ceilings before a reader
 * reaches one: both while the analysis flag ships the feature, the summary ceiling alone while not. The /pricing FAQ
 * and the filing page's monthly-limit card place it (tests/unit/summaryPlanClaims.spec.ts).
 */
export function proFairUseLine(): string {
  return shipped([ANALYSIS_LINES.fairUse])[0]
}

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
