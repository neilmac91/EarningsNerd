'use client'

import { Card } from '@/components/ui'
import { useCountUp } from '@/hooks/useCountUp'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionText } from '@/lib/financialTone'
import { formatGrowth, windowGrowth, windowRange } from '@/features/analysis/lib/growth'
import { applySeriesTone } from '@/features/analysis/lib/tonePolicy'
import type {
  AnalysisDataset,
  AnalysisSeries,
  GrowthValue,
  SeriesTone,
} from '@/features/analysis/api/analysis-api'

interface Kpi {
  label: string
  value: number
  format: (v: number) => string
  tone: SeriesTone | null | undefined
  isPercent: boolean
  /** Window growth: CAGR (annual, non-percent series), window pp change (annual, percent
   *  series — CAGR doesn't apply to a percentage), or same-quarter YoY (quarterly). */
  growth: GrowthValue | null
  growthLabel: string
  /** Basis-window tooltip ("Computed over FY2016..FY2025") — annual cards only. */
  growthTitle?: string
}

const latestPoint = (series: AnalysisSeries | undefined) => {
  if (!series) return null
  for (let i = series.points.length - 1; i >= 0; i -= 1) {
    const point = series.points[i]
    if (point.value !== null && point.value !== undefined) return point
  }
  return null
}

function KpiTile({ kpi }: { kpi: Kpi }) {
  const animated = useCountUp(kpi.value, { format: kpi.format })
  const { text, direction } = formatGrowth(kpi.growth, kpi.isPercent)
  const tone = applySeriesTone(kpi.tone, direction)
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
        {kpi.label}
      </div>
      <div className="tnum font-data mt-1 text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        {animated}
      </div>
      {text && (
        <div
          className={`tnum font-data mt-0.5 text-xs ${directionText[tone]}${kpi.growthTitle ? ' cursor-help' : ''}`}
          title={kpi.growthTitle}
        >
          {kpi.growthLabel} {text}
        </div>
      )}
    </Card>
  )
}

/** Headline strip: latest top line, net income, FCF, net margin — with the window's CAGR/YoY
 *  (or, for the percent-unit net-margin card, the window's pp change — CAGR doesn't apply). */
export default function KpiStrip({ dataset }: { dataset: AnalysisDataset }) {
  const byConcept = Object.fromEntries(dataset.series.map((s) => [s.concept, s]))

  const specs: { concept: string; label?: string; format?: (v: number) => string }[] = [
    { concept: byConcept['revenue'] ? 'revenue' : 'net_interest_income' },
    { concept: 'net_income' },
    { concept: 'free_cash_flow' },
    { concept: 'net_margin', format: (v) => fmtPercent(v, { digits: 1 }) },
  ]

  const kpis: Kpi[] = []
  for (const spec of specs) {
    const series = byConcept[spec.concept]
    const point = latestPoint(series)
    if (!series || !point) continue
    const isAnnual = dataset.mode === 'annual'
    // Shared window-growth rule (growth.ts) — same resolution as the metrics table's window column.
    const win = windowGrowth(series)
    const growth: GrowthValue | null = isAnnual ? win.value : point.yoy ?? null
    // The basis window can be narrower than the selected range (a concept first reported
    // mid-window) — the tooltip states the window the figure was actually computed over.
    const window = windowRange(series)
    kpis.push({
      label: `${series.label} (${point.period})`,
      value: point.value as number,
      format: spec.format ?? ((v: number) => fmtCurrency(v, { compact: true })),
      tone: series.tone,
      isPercent: series.percent,
      growth,
      growthLabel: isAnnual ? win.label : 'YoY',
      growthTitle: isAnnual && window ? `Computed over ${window}` : undefined,
    })
  }
  if (kpis.length === 0) return null

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {kpis.map((kpi) => (
        <KpiTile key={kpi.label} kpi={kpi} />
      ))}
    </div>
  )
}
