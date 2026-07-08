import type { Filing } from '@/features/filings/api/filings-api'

/** The minimal shape needed to bucket a filing into a fiscal year. */
type DatedFiling = Pick<Filing, 'report_date' | 'filing_date'>

/**
 * The fiscal year a filing belongs to.
 *
 * Uses the period-of-report (`report_date`) when present, falling back to `filing_date`. This is
 * the fix for the "FY2025 10-K filed 2026-02 shows under 2026" bug: annual/quarterly reports are
 * filed weeks-to-months after the period they cover, so `filing_date` mis-buckets them by a year.
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
 * Group filings by fiscal year. Preserves each filing's order within its year; years are not
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
