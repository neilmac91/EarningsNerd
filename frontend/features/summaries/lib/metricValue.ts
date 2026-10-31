// A Financial Highlights figure as the table shows it, in a module without 'use client' so server components (the
// landing page's receipt card) can format a row exactly as the table does: a function exported from a 'use client'
// module is a client reference wherever server code imports it (lessons/frontend-client-exports-need-next-build.md).
import { fmtCurrency, fmtPercent, fmtScale, parseNumeric } from '@/lib/format'

/** Whether a served string holds no value: empty, or the missing-value token alone, which a degraded summary writes
 *  for a figure it lacks (backend/app/services/fallback_summary.py). Its field renders MissingValue in its place. */
export const isMissing = (value: string | null | undefined): boolean => !value?.trim() || value.trim() === '—'

/** A served figure as the field shows it, or '' for one the row does not have (its field renders MissingValue). */
export const formatMetricValue = (value: string): string => {
  if (isMissing(value)) {
    return ''
  }

  const numeric = parseNumeric(value)
  if (numeric === null) {
    return value
  }

  if (value.includes('%')) {
    return fmtPercent(numeric)
  }

  if (value.includes('$')) {
    // Keep the precision the row was served with: a per-share "$7.46" must not display as "$7.5".
    // Compact figures ("$416,161M" to "$416.2B") keep fmtCurrency's own rounding.
    const decimals = Math.abs(numeric) < 1000 ? (value.match(/\.(\d+)/)?.[1].length ?? 0) : 0
    return decimals > 1 ? fmtCurrency(numeric, { digits: Math.min(decimals, 2) }) : fmtCurrency(numeric)
  }

  return fmtScale(numeric, { digits: 2 })
}
