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
  if (needsSourceCheck(value)) return 'Needs review'
  if (value.provenance?.validation === 'passed') return 'Automated checks passed'
  return 'No validation record'
}

const REASONS: Record<string, string> = {
  not_in_dataset: 'Not available in this dataset.',
  legacy_calculation: 'This saved calculation predates the current automated checks. Its inputs need review.',
  source_check_needed: 'This figure has not passed EarningsNerd’s automated consistency checks; check it against the filing before relying on it.',
  unsupported_eps_calculation: 'This quarterly earnings-per-share calculation is not supported. Use a reported quarterly EPS figure.',
  legacy_calculation_not_supported: 'This saved calculation could not be reproduced from compatible source inputs and is unavailable.',
  repair_rolled_back: 'This figure was withdrawn during a data correction and is unavailable.',
  incompatible_vintages: 'The inputs come from incompatible versions of the company’s filings.',
  missing_compatible_operand: 'A compatible earlier year-to-date figure is unavailable for this calculation.',
  negative_calculated_value: 'The calculation produced an invalid negative amount, so this figure is unavailable.',
  missing_inputs: 'The source inputs needed for this calculation are unavailable.',
  missing_input: 'A source input needed for this calculation is unavailable.',
  missing_source: 'The original source could not be established.',
  missing_provenance: 'Detailed source information is unavailable for this figure.',
  legacy_unverified: 'This saved figure has not passed the current automated checks; check it against the filing before relying on it.',
  legacy_unreconciled: 'This saved figure has not passed the current automated checks; check it against the filing before relying on it.',
  legacy_unknown: 'No automated check result is recorded for this figure.',
  legacy_provenance_unavailable: 'Detailed source information is unavailable for this saved figure.',
  incompatible_inputs: 'The source inputs do not have a compatible reporting basis.',
  mixed_vintage: 'The calculation combines figures from different filing versions.',
  mixed_vintages: 'The calculation combines figures from different filing versions.',
  unit_mismatch: 'The source inputs use different units or currencies.',
  period_mismatch: 'The source inputs cover incompatible reporting periods.',
  missing_adjacent_period: 'The immediately preceding period is unavailable.',
  eps_not_additive: 'Quarterly earnings per share cannot be obtained by subtracting annual and year-to-date EPS.',
  eps_requires_reported_quarter: 'A reported quarterly earnings-per-share figure is unavailable.',
  rounded_share_count: 'Rounded weighted-average share counts do not establish an exact quarterly EPS figure.',
  source_conflict: 'Available sources disagree on this figure.',
}

export function reasonText(reason: string): string {
  return REASONS[reason] ?? 'The source or calculation basis needs review. Check the original filing.'
}

export function qualityReasons(value: QualityValue): string[] {
  const reasons = [...new Set((value.provenance?.reasons ?? []).map(reasonText))]
  if (reasons.length) return reasons
  if (needsSourceCheck(value)) return [REASONS.source_check_needed]
  if (value.provenance?.validation !== 'passed') return [REASONS.legacy_unknown]
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
