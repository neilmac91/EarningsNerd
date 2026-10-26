import { CHART_FONT, chartTheme } from '@/components/ui'
import type { AnalysisMode } from '@/features/analysis/api/analysis-api'
import { annualTickLabel, quarterlyTickLines } from './periodLabels'

/**
 * Every-period x-axis ticks for the trend panels (owner decision D2). Recharts' auto interval
 * was dropping half the labels on a 10-year window; the fix is `interval={0}` on the XAxis plus
 * these COMPACT tick renderings so all 10–12 labels actually fit a half-width panel:
 *
 * - Annual: bare "'16 '17 '18 …" two-digit years — every label centers exactly on its bar/point
 *   (a "FY" prefix on the first tick shifted "'16" visibly off its bar, the AAPL field-test
 *   misalignment). What the ticks mean is stated ONCE by the axis caption underneath
 *   ("Fiscal year" / "Fiscal quarter" — `periodAxisLabel`).
 * - Quarterly: a stacked two-line tick, "Q2" over "'23" (Q2'23 reading order) — a single-line
 *   "Q2'23" at the 11px dense-annotation floor is ~33px wide × 12 periods and cannot fit half
 *   the grid, but the 2-line stack halves the width per tick.
 */

// The tick strings themselves are pure and live with the period vocabulary, so the chart engine
// (features/analysis/lib/charts) reads the same ones without importing this React module.
export { annualTickLabel, quarterlyTickLines } from './periodLabels'

/** How far the caption's baseline sits above the band's bottom, which is the SVG's. Geist Mono's text box runs its
 *  descent, 0.295em (3.2px at 11px, which Chromium lays out as 3px), below the baseline, so at 0 the SVG cut the box
 *  and the "y" in "Fiscal year" ("Fiscal vear"). At 4 the whole box stays inside the SVG with under a pixel to spare,
 *  D1's rule for every chart text (the box inside its SVG, to the edge). */
export const AXIS_CAPTION_OFFSET = 4

/** XAxis band heights: the tick row (one line annual / two stacked quarterly) plus the axis
 *  caption line underneath and its descent (Recharts default height is 30, ticks only). */
export const ANNUAL_AXIS_HEIGHT = 46 + AXIS_CAPTION_OFFSET
export const QUARTERLY_AXIS_HEIGHT = 58 + AXIS_CAPTION_OFFSET

/** The axis caption rendered below the tick row — pass as the XAxis `label` prop. Names what
 *  the compact ticks mean ("Fiscal year" under "'16 '17 …"), the owner-requested pattern. */
export function periodAxisLabel(mode: AnalysisMode, dark: boolean) {
  return {
    value: mode === 'annual' ? 'Fiscal year' : 'Fiscal quarter',
    position: 'insideBottom' as const,
    offset: AXIS_CAPTION_OFFSET,
    style: { fill: chartTheme(dark).label, fontSize: 11, fontFamily: CHART_FONT },
  }
}

interface PeriodAxisTickProps {
  mode: AnalysisMode
  dark: boolean
  /** Injected by Recharts when passed as `tick={<PeriodAxisTick …/>}`. */
  x?: number
  y?: number
  payload?: { value?: string | number }
}

/**
 * Recharts custom XAxis `tick`. 11px data face (the dense-annotation floor) in the theme's
 * chart-label ink — the compactness is what buys `interval={0}` its room.
 */
export function PeriodAxisTick({ mode, dark, x, y, payload }: PeriodAxisTickProps) {
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
      {annualTickLabel(key)}
    </text>
  )
}
