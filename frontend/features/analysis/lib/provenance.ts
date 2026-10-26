/** Origin and validation are independent: a calculation is not a source discrepancy. */
export interface FactInput {
  concept: string
  value: number | null
  unit?: string | null
  period_start?: string | null
  period_end?: string | null
  accession?: string | null
  raw_tag?: string | null
  filed_at?: string | null
  source_url?: string | null
  provenance?: FactProvenance | null
}

export interface FactProvenance {
  version: 1
  method: 'reported' | 'calculated' | 'unknown'
  validation: 'passed' | 'needs_review' | 'unavailable'
  reasons: string[]
  formula: string | null
  inputs: FactInput[]
  calculation_version?: string | null
  source_url?: string | null
}

export interface QualityValue {
  provenance?: FactProvenance | null
  reconciled?: boolean | null
}

export function needsSourceCheck(value: QualityValue): boolean {
  return value.provenance ? value.provenance.validation === 'needs_review' : value.reconciled === false
}

export function validationLabel(value: QualityValue): string {
  if (needsSourceCheck(value)) return 'Source check needed'
  if (value.provenance?.validation === 'passed') return 'Automated checks passed'
  return 'Validation unavailable'
}

/** Each reason's words, the same strings as the backend's data_notes.REASONS: the shared notes fixture
 *  (backend/tests/fixtures/analysis_data_notes.json) pins the two maps equal, and the backend's reason gate gives every
 *  reason the backend writes words here. The same message prints for one figure (the dialog, a workbook comment) and for
 *  a note's several (the detail, the PDF, the chart footnotes), in exports as on the page, so no sentence points at one
 *  figure, asks for a selection or names how a figure is drawn (test_analysis_data_notes.py holds both maps to it). */
export const REASONS: Readonly<Record<string, string>> = {
  not_in_dataset: 'Not in our data; never shown as zero.',
  legacy_calculation: 'Calculated before 10 October 2026, when we began keeping each calculation’s inputs; shown as stored, with its inputs not linked.',
  source_check_needed: 'Not yet matched to the filing: our automated check could not confirm the value against the company’s filed data.',
  unsupported_eps_calculation: 'Calculated quarterly earnings per share is not supported. Use a reported quarterly EPS figure.',
  legacy_calculation_not_supported: 'The saved calculation could not be reproduced from compatible source inputs and is unavailable.',
  repair_rolled_back: 'Withdrawn during a data correction and unavailable.',
  incompatible_vintages: 'The inputs come from incompatible versions of the company’s filings.',
  missing_compatible_operand: 'A compatible earlier year-to-date figure is unavailable for the calculation.',
  negative_calculated_value: 'The calculation produced an invalid negative amount and was withheld.',
  missing_inputs: 'The source inputs needed for the calculation are unavailable.',
  missing_input: 'A source input needed for the calculation is unavailable.',
  missing_source: 'The original source could not be established.',
  missing_provenance: 'Detailed source information is unavailable.',
  legacy_unverified: 'The saved figure needs a source check before use.',
  legacy_unreconciled: 'The saved figure needs a source check before use.',
  legacy_unknown: 'Validation details are unavailable for the saved figure. No verification claim is made.',
  legacy_provenance_unavailable: 'Detailed source information is unavailable for the saved figure.',
  incompatible_inputs: 'The source inputs do not have a compatible reporting basis.',
  mixed_vintage: 'The calculation combines figures from different filing versions.',
  mixed_vintages: 'The calculation combines figures from different filing versions.',
  unit_mismatch: 'The source inputs use different units or currencies.',
  period_mismatch: 'The figure’s period ends on a different date from its filing’s reporting period.',
  missing_adjacent_period: 'The immediately preceding period is unavailable.',
  eps_not_additive: 'Quarterly earnings per share cannot be obtained by subtracting annual and year-to-date EPS.',
  eps_requires_reported_quarter: 'A reported quarterly earnings-per-share figure is unavailable.',
  rounded_share_count: 'Rounded weighted-average share counts do not establish an exact quarterly EPS figure.',
  calculation_mismatch: 'Our calculation from the filed inputs does not match the stored figure.',
  missing_calculation_inputs: 'The calculation’s inputs were not found in the same filing, so it could not be checked.',
  zero_where_prior_nonzero: 'Zero where the previous period had a value.',
  magnitude_vs_prior: 'More than ten times the previous period’s value, or less than a tenth of it.',
  eps_sign_vs_net_income: 'Earnings per share and net income have opposite signs for the period.',
  diluted_gt_basic: 'Diluted earnings per share is higher than basic earnings per share for the period.',
  legacy_period_label_mismatch: 'The saved figure carried the wrong fiscal period and was replaced by a corrected figure.',
  rolling_duration_not_fiscal_year: 'The saved figure covers a rolling twelve months, not the company’s fiscal year, and is unavailable.',
  calculation_parent_period_corrected: 'An input to the saved calculation was moved to its correct period, so the calculation was withdrawn and is unavailable.',
  source_conflict: 'The company’s filings report different values. We show the most recent filing’s value.',
}

/** The fine print's words for a note that marks its figure (DataNotes, through noteSummary); any other questioning
 *  reason reads SUMMARY_FALLBACK. The backend's data_notes.SUMMARIES holds the same strings for the exports, which print
 *  none of them yet (WP3); the fixture's summaries pins both. A clause has no semicolon: the summary lists places, and
 *  joins clauses, with "; ". */
export const REASON_SUMMARIES: Readonly<Record<string, string>> = {
  source_check_needed: 'not yet matched to the filing',
  source_conflict: 'the filings report different values (the most recent shown)',
  calculation_mismatch: 'the calculation does not match its filed inputs',
  missing_calculation_inputs: 'the calculation’s filed inputs were not found',
}
export const SUMMARY_FALLBACK = 'questioned by an automated check'

export function reasonText(reason: string): string {
  return Object.hasOwn(REASONS, reason) ? REASONS[reason] : 'The source or calculation basis needs review. Check the original filing.'
}

export function qualityReasons(value: QualityValue): string[] {
  const reasons = [...new Set((value.provenance?.reasons ?? []).map(reasonText))]
  if (reasons.length) return reasons
  if (needsSourceCheck(value)) return ['This figure has an unresolved source check. Review the original filing before use.']
  if (value.provenance?.validation !== 'passed') return ['Detailed validation information is unavailable; no verification claim is made.']
  return []
}

export function sourceUrl(value?: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && ['www.sec.gov', 'sec.gov', 'data.sec.gov'].includes(url.hostname)
      ? url.href : null
  } catch { return null }
}

export const ANALYSIS_DISCLOSURE = 'EarningsNerd provides financial data and AI-assisted commentary for research, not investment advice or a recommendation to trade securities. Figures may be reported or calculated; sources and methods accompany this analysis. Data and commentary may contain errors or omissions. Check material information against original filings before making investment decisions. EarningsNerd is not affiliated with or endorsed by the SEC.'
export const FCF_DEFINITION = 'Free cash flow is operating cash flow minus cash capital expenditures. It excludes finance lease principal payments and may differ from the company’s own free cash flow measure.'
