import { CHART_FONT, chartTheme } from '@/components/ui'
import type { AnalysisMode } from '@/features/analysis/api/analysis-api'

/**
 * Every-period x-axis ticks for the trend panels (owner decision D2). Recharts' auto interval
 * was dropping half the labels on a 10-year window; the fix is `interval={0}` on the XAxis plus
 * these COMPACT tick renderings so all 10–12 labels actually fit a half-width panel:
 *
 * - Annual: "FY '16 '17 '18 …" — the FY prefix stated once on the first tick, bare '17-style
 *   two-digit years after it.
 * - Quarterly: a stacked two-line tick, "Q2" over "'23" (Q2'23 reading order) — a single-line
 *   "Q2'23" at the 11px dense-annotation floor is ~33px wide × 12 periods and cannot fit half
 *   the grid, but the 2-line stack halves the width per tick.
 */

const ANNUAL_KEY = /^FY(\d{4})$/
const QUARTER_KEY = /^(\d{4})(Q[1-4])$/

/** "FY2016" → "'16" (first tick: "FY '16"). Unrecognized keys pass through untouched. */
export function annualTickLabel(key: string, index: number): string {
  const match = ANNUAL_KEY.exec(key)
  if (!match) return key
  const short = `'${match[1].slice(2)}`
  return index === 0 ? `FY ${short}` : short
}

/** "2023Q2" → ["Q2", "'23"] (quarter over year); null for unrecognized keys. */
export function quarterlyTickLines(key: string): [string, string] | null {
  const match = QUARTER_KEY.exec(key)
  if (!match) return null
  return [match[2], `'${match[1].slice(2)}`]
}

/** Extra XAxis height needed by the two-line quarterly tick (Recharts default is 30). */
export const QUARTERLY_AXIS_HEIGHT = 42

interface PeriodAxisTickProps {
  mode: AnalysisMode
  dark: boolean
  /** Injected by Recharts when passed as `tick={<PeriodAxisTick …/>}`. */
  x?: number
  y?: number
  index?: number
  payload?: { value?: string | number }
}

/**
 * Recharts custom XAxis `tick`. 11px data face (the dense-annotation floor) in the theme's
 * chart-label ink — the compactness is what buys `interval={0}` its room.
 */
export function PeriodAxisTick({ mode, dark, x, y, index, payload }: PeriodAxisTickProps) {
  const key = String(payload?.value ?? '')
  const fill = chartTheme(dark).label
  const shared = {
    x,
    textAnchor: 'middle' as const,
    fill,
    fontSize: 11,
    fontFamily: CHART_FONT,
  }
  if (mode === 'quarterly') {
    const lines = quarterlyTickLines(key)
    if (lines) {
      return (
        <text {...shared} y={y} dy={10}>
          <tspan x={x}>{lines[0]}</tspan>
          <tspan x={x} dy={12}>
            {lines[1]}
          </tspan>
        </text>
      )
    }
  }
  return (
    <text {...shared} y={y} dy={10}>
      {annualTickLabel(key, index ?? 0)}
    </text>
  )
}
