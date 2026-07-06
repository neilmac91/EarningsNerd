import { fmtPercent, fmtPercentPoints } from '@/lib/format'
import { directionOf, type Direction } from '@/lib/financialTone'
import type { AnalysisSeries, GrowthValue } from '@/features/analysis/api/analysis-api'

/**
 * Render a YoY/QoQ delta consistently everywhere it appears (metrics table, KPI strip): "n/m"
 * for a sign-flip crossing (flat tone — it isn't a real up/down move), percentage points for a
 * `percent`-unit series (margins — the value is already pp, never ×100), relative percentage
 * for everything else.
 */
export function formatGrowth(
  value: GrowthValue | null | undefined,
  isPercent: boolean
): { text: string; direction: Direction } {
  if (value === null || value === undefined) return { text: '', direction: 'flat' }
  // The "nm" sentinel is a bare string over the wire (convention, not schema) — treat ANY
  // non-number as n/m so a backend rename degrades to an honest "n/m", never a garbage figure.
  if (typeof value !== 'number') return { text: 'n/m', direction: 'flat' }
  if (isPercent) return { text: fmtPercentPoints(value, { digits: 1 }), direction: directionOf(value) }
  return { text: fmtPercent(value * 100, { digits: 1, signed: true }), direction: directionOf(value) }
}

/**
 * A series' whole-window growth figure (annual mode): CAGR for monetary/per-share series, the
 * window's percentage-point change for percent-unit series (compounding doesn't apply to a
 * percentage, so CAGR is always null there). ONE resolution rule shared by every consumer
 * (KPI strip, metrics table) so the same dataset field is never honored in one place and
 * silently ignored in another.
 */
export function windowGrowth(series: Pick<AnalysisSeries, 'percent' | 'cagr' | 'window_pp'>): {
  value: number | null
  isPercent: boolean
  label: 'CAGR' | 'Chg'
} {
  return series.percent
    ? { value: series.window_pp ?? null, isPercent: true, label: 'Chg' }
    : { value: series.cagr ?? null, isPercent: false, label: 'CAGR' }
}

/** The basis window the series' window figure was computed over ("FY2016..FY2025") — can be
 *  narrower than the selected range (a concept first reported mid-window). Same one-rule-for-
 *  every-consumer contract as windowGrowth. */
export function windowRange(
  series: Pick<AnalysisSeries, 'percent' | 'cagr_window' | 'window_pp_range'>
): string | null {
  return (series.percent ? series.window_pp_range : series.cagr_window) ?? null
}
