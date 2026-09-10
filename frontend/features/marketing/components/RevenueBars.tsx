import { fmtCurrency } from '@/lib/format'

export interface RevenuePoint {
  /** Period key as the dataset spells it ("FY2019"). */
  period: string
  /** Reported value in whole currency units (USD), never pre-scaled. */
  value: number
}

const BILLION = 1e9
/** Gridline spacing in billions: one hairline per $100B. */
const TICK_STEP = 100
const CHART_HEIGHT = 'h-[140px]'
const Y_AXIS_WIDTH = 'w-8'

const AXIS_LABEL = 'font-data tnum text-data-xs leading-none text-chart-label-light dark:text-chart-label-dark'

/**
 * The Multi-Period screen's revenue bar chart, drawn as plain DOM (design "Revenue · USD,
 * billions"). Deliberately NOT TrendCharts: that component pulls recharts into the route, and the
 * landing page carries a JS budget the marketing screens must not spend. Server-safe: no hooks,
 * no theme context; chart chrome uses the chart.axis / chart.label tokens, the single series uses
 * chart-1 (the first colour of the sequence, DESIGN_SYSTEM §10).
 *
 * The axis tops out one full tick above the tallest bar so its value label never collides with
 * the top of the plot: ticks every $100B up to (ceil(max / 100) + 1) * 100.
 */
export default function RevenueBars({ points }: { points: ReadonlyArray<RevenuePoint> }) {
  const maxBillions = Math.max(0, ...points.map((point) => point.value / BILLION))
  const top = (Math.ceil(maxBillions / TICK_STEP) + 1) * TICK_STEP
  const ticks = Array.from({ length: top / TICK_STEP + 1 }, (_, index) => index * TICK_STEP)
  const bars = points.map((point) => ({
    period: point.period,
    label: fmtCurrency(point.value, { compact: true, digits: 0 }),
    heightPct: (point.value / BILLION / top) * 100,
  }))
  const columns = { gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` }
  const first = bars[0]?.period ?? ''
  const last = bars[bars.length - 1]?.period ?? ''
  const chartLabel = `Revenue by fiscal year, ${first} to ${last}: ${bars.map((bar) => bar.label).join(', ')}`

  return (
    <div className="rounded-lg border border-border-light bg-white p-3.5 dark:border-white/10 dark:bg-white/5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
        <span className="text-xs font-semibold text-text-primary-light dark:text-text-primary-dark">Revenue</span>
        <span className="whitespace-nowrap font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
          USD, billions
        </span>
      </div>

      <div role="img" aria-label={chartLabel} className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
        {/* Y axis: tick labels, centred on their gridline. */}
        <div aria-hidden="true" className={`relative ${CHART_HEIGHT} ${Y_AXIS_WIDTH}`}>
          {ticks.map((tick) => (
            <span
              key={tick}
              className={`absolute right-0 translate-y-1/2 ${AXIS_LABEL}`}
              style={{ bottom: `${(tick / top) * 100}%` }}
            >
              {tick}
            </span>
          ))}
        </div>

        <div className={`relative ${CHART_HEIGHT}`}>
          <div aria-hidden="true" className="absolute inset-0">
            {ticks.map((tick) => (
              <span
                key={tick}
                className="absolute inset-x-0 border-t border-chart-axis-light dark:border-chart-axis-dark"
                style={{ bottom: `${(tick / top) * 100}%` }}
              />
            ))}
          </div>
          <div className="relative grid h-full items-end gap-2" style={columns}>
            {bars.map((bar) => (
              <div key={bar.period} className="flex h-full min-w-0 flex-col items-center justify-end">
                <span className="mb-1 whitespace-nowrap font-data tnum text-data-xs leading-none text-text-secondary-light dark:text-text-secondary-dark">
                  {bar.label}
                </span>
                <div className="w-full rounded-t-sm bg-chart-1" style={{ height: `${bar.heightPct}%` }} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Period labels share the plot's column grid, offset by the axis width. */}
      <div aria-hidden="true" className="mt-1.5 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
        <span className={Y_AXIS_WIDTH} />
        <div className="grid gap-2" style={columns}>
          {bars.map((bar) => (
            <span key={bar.period} className={`text-center ${AXIS_LABEL}`}>
              {bar.period}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
