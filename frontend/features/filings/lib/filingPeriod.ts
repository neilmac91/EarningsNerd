import type { Filing } from '@/features/filings/api/filings-api'
import { formatLocalDate } from '@/lib/format'

/**
 * What a filing covers, for the filing index (features/filings/components/FilingIndex.tsx).
 *
 * The row's NAME is its period of report — "Quarter ended Jul 26, 2026", "Fiscal year ended Jan 25,
 * 2026" — because that is what an analyst searches by; the filed date sits in its own column.
 * report_date is a UTC-midnight instant on the wire, so it goes through formatLocalDate (never
 * new Date()/parseISO), exactly like filing_date (tests/unit/filing-date-local-day.spec.tsx).
 *
 * Fiscal labels ("Q2 FY2027") are deliberately NOT derived here: fiscal calendars vary (NVIDIA's year
 * ends in late January), so deriving a quarter from a date is a guess. They wait for the filings
 * payload to carry XBRL dei:DocumentFiscalPeriodFocus / DocumentFiscalYearFocus.
 */

/** Annual reports: the domestic 10-K plus the foreign-issuer 20-F / 40-F (mirrors recommendedFiling.ts). */
const ANNUAL_FORMS = ['10-K', '20-F', '40-F']

/** Display order for the form filter; unknown forms sort to the end, alphabetically. */
export const FORM_ORDER = ['10-K', '10-Q', '20-F', '6-K', '40-F']

export type PeriodKind = 'annual' | 'quarter' | 'period'

/** The form without its amendment suffix: '10-K/A' → '10-K'. */
export function baseForm(filingType: string): string {
  return filingType.replace(/\/A$/i, '')
}

export function isAmendment(filingType: string): boolean {
  return /\/A$/i.test(filingType)
}

export function periodKind(filingType: string): PeriodKind {
  const form = baseForm(filingType).toUpperCase()
  if (ANNUAL_FORMS.includes(form)) return 'annual'
  if (form === '10-Q') return 'quarter'
  return 'period'
}

const LEAD: Record<PeriodKind, string> = {
  annual: 'Fiscal year ended',
  quarter: 'Quarter ended',
  period: 'Period ended',
}

/** "Quarter ended Jul 26, 2026"; null when the filing has no usable period of report. */
export function periodLabel(filing: Pick<Filing, 'filing_type' | 'report_date'>): string | null {
  const date = formatLocalDate(filing.report_date, 'MMM d, yyyy')
  return date ? `${LEAD[periodKind(filing.filing_type)]} ${date}` : null
}

/** Distinct forms in FORM_ORDER, unknown forms last and alphabetical. */
export function sortForms(forms: Iterable<string>): string[] {
  return Array.from(new Set(forms)).sort((a, b) => {
    const ia = FORM_ORDER.indexOf(a)
    const ib = FORM_ORDER.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.localeCompare(b)
  })
}
