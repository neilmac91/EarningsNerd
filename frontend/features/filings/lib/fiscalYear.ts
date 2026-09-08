import type { Filing } from '@/features/filings/api/filings-api'

/** The minimal shape needed to bucket a filing into a report year. */
type DatedFiling = Pick<Filing, 'report_date' | 'filing_date'>

/**
 * The calendar year of the period-of-report (`report_date`), falling back to `filing_date`.
 * The legacy helper name does not imply the issuer's fiscal year: NVIDIA's April 2026 report
 * belongs to fiscal 2027, but its report year here is 2026. A December 2025 report filed in
 * February 2026 still groups under report year 2025.
 *
 * The 4-char slice reads the `YYYY` prefix of the ISO string directly — no `new Date()` — so it
 * can't be shifted across a year boundary by the viewer's timezone. Returns '' for a blank/missing
 * date so the caller can skip it.
 */
export function fiscalYear(filing: DatedFiling): string {
  const source = filing.report_date || filing.filing_date || ''
  return source.slice(0, 4)
}

/**
 * Group filings by report year. Preserves each filing's order within its year; years are not
 * sorted here (the caller sorts the keys for display).
 */
export function groupByFiscalYear<T extends DatedFiling>(filings: T[]): Record<string, T[]> {
  const grouped: Record<string, T[]> = {}
  for (const filing of filings) {
    const year = fiscalYear(filing)
    if (!year) continue
    ;(grouped[year] ??= []).push(filing)
  }
  return grouped
}
