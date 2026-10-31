/**
 * How Financial trends hands a series to the trend charts' engine (E195 (D), D-067): a slot per point, and the describer
 * its values stop and tooltip read each year through. Pure, so the card and the engine's sweeps over every bar case
 * (tests/unit/chartPlan.ts, chart-readout.spec.ts) build them the same way.
 */
import type { FundamentalPoint } from '@/features/fundamentals/api/fundamentals-api'
import type { BarCategory } from '@/features/analysis/lib/charts/barChart'
import { periodHeader, type ReadoutDescriber } from '@/features/analysis/lib/charts/readout'

/** Each point's slot: its fiscal year names it ("FY2025", ticked "2025"), and a point the backend names no year for
 *  takes its period end's year, as the axis has always ticked it. The engine places a bar and reads a year by its key,
 *  so a key is never given twice (buildBarChart refuses it): a name two points share keys each by its place. */
export function slotsOf(points: FundamentalPoint[]): BarCategory[] {
  const names = points.map((point) => (point.fiscal_year != null ? `FY${point.fiscal_year}` : point.period_end?.slice(0, 4) ?? ''))
  return points.map((point, i) => {
    const name = names[i]
    const own = name !== '' && names.indexOf(name) === names.lastIndexOf(name)
    return {
      key: own ? name : `${name || 'period'}#${i}`,
      tick: point.fiscal_year != null ? String(point.fiscal_year) : name,
      long: name || 'Period unavailable',
    }
  })
}

/** Each year as the tooltip prints it and the values stop says it ("FY2025 · year ended Sep 27, 2025"), and a figure
 *  the backend derived (a margin, working capital, the current ratio) read as calculated from its own provenance. The
 *  card has no data notes: its badge and Sources & checks say what needs a check. `slots` are `slotsOf(points)`. */
export function trendDescriber(slots: BarCategory[], points: FundamentalPoint[]): ReadoutDescriber {
  const pointAt = new Map(slots.map((slot, i) => [slot.key, points[i]]))
  return {
    header: (period) => periodHeader(period.long, 'year', pointAt.get(period.key)?.period_end),
    calculated: (_mark, key) => pointAt.get(key)?.provenance?.method === 'calculated',
  }
}
