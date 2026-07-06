'use client'

import { Card } from '@/components/ui'
import { useCountUp } from '@/hooks/useCountUp'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionText } from '@/lib/financialTone'
import { formatGrowth } from '@/features/analysis/lib/growth'
import { toneForConcept } from '@/features/analysis/lib/tonePolicy'
import type { AnalysisDataset, AnalysisSeries, GrowthValue } from '@/features/analysis/api/analysis-api'

interface Kpi {
  label: string
  value: number
  format: (v: number) => string
  concept: string
  isPercent: boolean
  /** Window growth: CAGR (annual, non-percent series), window pp change (annual, percent
   *  series — CAGR doesn't apply to a percentage), or same-quarter YoY (quarterly). */
  growth: GrowthValue | null
  growthLabel: string
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
  const tone = toneForConcept(kpi.concept, direction)
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark">
        {kpi.label}
      </div>
      <div className="tnum font-data mt-1 text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        {animated}
      </div>
      {text && (
        <div className={`tnum font-data mt-0.5 text-xs ${directionText[tone]}`}>
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
    const growth: GrowthValue | null = isAnnual
      ? (series.percent ? series.window_pp : series.cagr) ?? null
      : point.yoy ?? null
    kpis.push({
      label: `${series.label} (${point.period})`,
      value: point.value as number,
      format: spec.format ?? ((v: number) => fmtCurrency(v, { compact: true })),
      concept: series.concept,
      isPercent: series.percent,
      growth,
      growthLabel: isAnnual ? (series.percent ? 'Chg' : 'CAGR') : 'YoY',
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
