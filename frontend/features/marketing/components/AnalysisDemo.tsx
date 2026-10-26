import KpiStrip from '@/features/analysis/components/KpiStrip'
import MetricsTable from '@/features/analysis/components/MetricsTable'
import DataNotes from '@/features/analysis/components/DataNotes'
import { DataNotesProvider } from '@/features/analysis/components/DataNotesContext'
import RevenueBars, { type RevenuePoint } from '@/features/marketing/components/RevenueBars'
import { ANALYSIS_MODE_LABEL, formatAnalysisWindow } from '@/features/analysis/lib/periodLabels'
import { SAMPLE_ANALYSIS_DATASET } from '@/features/marketing/lib/landing-samples'
import { formatCompanyName } from '@/lib/formatCompanyName'

const { periods } = SAMPLE_ANALYSIS_DATASET
const RANGE = formatAnalysisWindow(periods[0]?.key ?? '', periods[periods.length - 1]?.key ?? '')
const TITLE = `${formatCompanyName(SAMPLE_ANALYSIS_DATASET.company_name)} · ${ANALYSIS_MODE_LABEL[SAMPLE_ANALYSIS_DATASET.mode]} · ${RANGE}`

// The revenue series drives the one chart on the screen; a point with no value has no bar.
const REVENUE_POINTS: RevenuePoint[] = (
  SAMPLE_ANALYSIS_DATASET.series.find((series) => series.concept === 'revenue')?.points ?? []
).flatMap((point) => (point.value == null ? [] : [{ period: point.period, value: point.value }]))

/**
 * The Multi-Period Analysis product screen for the landing page: the REAL KpiStrip and
 * MetricsTable fed the checked-in sample dataset, with a DOM-drawn revenue chart between them and
 * the data notes as the table's fine print under it.
 * A server component: the dataset reaches the two client components through the RSC payload,
 * already narrowed to three series, instead of shipping the demo JSON module to the browser.
 * TrendCharts (recharts) is deliberately not rendered here: it would pull the charting library
 * into the landing route's JS, which has a budget the marketing screens must respect.
 */
export default function AnalysisDemo() {
  return (
    <div className="mockup-frame shadow-e3 dark:shadow-none" data-capture="multi-period-analysis">
      <div className="flex flex-wrap items-center justify-between gap-x-2.5 gap-y-1.5 border-b border-border-light px-4 py-3 dark:border-white/10">
        <span className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{TITLE}</span>
        <span className="whitespace-nowrap font-data text-data-xs text-text-secondary-light dark:text-text-secondary-dark">
          Filed data
        </span>
      </div>

      <DataNotesProvider dataset={SAMPLE_ANALYSIS_DATASET}>
        <div className="flex flex-col gap-3 p-4">
          {/* KpiStrip lays out four columns at lg; the sample's three tiles need three. */}
          <div className="lg:[&>div>dl]:grid-cols-3 [&>div>dl]:[@container(width<17em)]:grid-cols-1">
            <KpiStrip dataset={SAMPLE_ANALYSIS_DATASET} />
          </div>
          <RevenueBars points={REVENUE_POINTS} />
          {/* The table's fine print sits 8px under it, as on the analysis page. */}
          <div className="flex flex-col gap-2">
            <MetricsTable dataset={SAMPLE_ANALYSIS_DATASET} headingLevel="h4" />
            <DataNotes dataset={SAMPLE_ANALYSIS_DATASET} sample />
          </div>
        </div>
      </DataNotesProvider>
    </div>
  )
}
