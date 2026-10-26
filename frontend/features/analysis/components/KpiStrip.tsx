'use client'

import { Card } from '@/components/ui'
import { useCountUp } from '@/hooks/useCountUp'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { dataDirectionText } from '@/lib/financialTone'
import { formatGrowth, windowGrowth, windowRange } from '@/features/analysis/lib/growth'
import { applySeriesTone } from '@/features/analysis/lib/tonePolicy'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { selectHeadlineFigures } from '@/features/analysis/lib/reportPresentation'
import DataNoteMark from './DataNoteMark'
import GrowthText from './GrowthText'
import SourceValue from './SourceValue'
import { useDataNotes } from './DataNotesContext'
import type { DataNote } from '@/features/analysis/lib/dataNotes'
import type { FactProvenance } from '@/features/analysis/lib/provenance'
import type {
  AnalysisDataset,
  AnalysisPoint,
  GrowthValue,
  SeriesTone,
} from '@/features/analysis/api/analysis-api'

interface Kpi {
  label: string
  concept: string
  point: AnalysisPoint
  note: DataNote | null
  growthNote: DataNote | null
  value: number
  latestAvailable: boolean
  format: (v: number) => string
  tone: SeriesTone | null | undefined
  isPercent: boolean
  /** Window growth: CAGR (annual, non-percent series), window pp change (annual, percent
   *  series — CAGR doesn't apply to a percentage), or same-quarter YoY (quarterly). */
  growth: GrowthValue | null
  growthReconciled?: boolean | null
  growthProvenance?: FactProvenance | null
  growthLabel: string
  /** Basis-window tooltip ("Computed over FY2016–FY2025") — annual cards only. */
  growthTitle?: string
}

function KpiTile({ kpi }: { kpi: Kpi }) {
  const animated = useCountUp(kpi.value, { format: kpi.format })
  const { text, direction } = formatGrowth(kpi.growth, kpi.isPercent)
  const tone = applySeriesTone(kpi.tone, direction)
  return (
    <Card className="relative row-span-3 grid min-w-0 grid-rows-subgrid gap-y-0.5 p-3 sm:p-4" data-analysis-kpi>
      {/* APCA on the panel: the label and period need |Lc| >= 75; secondary holds 90.9 / -77.3 (tertiary is 74.1 in light). */}
      <dt className="min-w-0 text-xs font-medium uppercase tracking-eyebrow text-text-secondary-light dark:text-text-secondary-dark">
        {kpi.label}
      </dt>
      <dd data-kpi-value className="min-w-0 font-figure text-2xl font-semibold tabular-nums lining-nums tracking-normal text-figure-light dark:text-figure-dark">
        <SourceValue largeMarks point={kpi.point} label={kpi.label} concept={kpi.concept} note={kpi.note} comparison={text ? { label: kpi.growthLabel, display: text, provenance: kpi.growthProvenance, reconciled: kpi.growthReconciled, note: kpi.growthNote } : undefined}>{animated}</SourceValue>
      </dd>
      <dd className="flex min-w-0 flex-wrap items-baseline gap-x-1.5 gap-y-0.5 self-start font-figure text-xs tabular-nums lining-nums tracking-normal">
        <span className="text-text-secondary-light dark:text-text-secondary-dark">
          {formatAnalysisPeriod(kpi.point.period)}{kpi.latestAvailable && <span> · latest available</span>}
        </span>
        {text && <span className={`${dataDirectionText[tone]}${kpi.growthTitle ? ' cursor-help' : ''}`} title={kpi.growthTitle}>
          {kpi.growthLabel} <GrowthText text={text} /><DataNoteMark note={kpi.growthNote} />
        </span>}
      </dd>
    </Card>
  )
}

/** Headline strip: latest top line, net income, FCF, net margin — with the window's CAGR/YoY
 *  (or, for the percent-unit net-margin card, the window's pp change — CAGR doesn't apply). */
export default function KpiStrip({ dataset }: { dataset: AnalysisDataset }) {
  const notes = useDataNotes(dataset)
  const kpis: Kpi[] = []
  for (const { series, point } of selectHeadlineFigures(dataset)) {
    const isAnnual = dataset.mode === 'annual'
    // Shared window-growth rule (growth.ts) — same resolution as the metrics table's window column.
    const win = windowGrowth(series)
    const growth: GrowthValue | null = isAnnual ? win.value : point.yoy ?? null
    // The basis window can be narrower than the selected range (a concept first reported
    // mid-window) — the tooltip states the window the figure was actually computed over.
    const window = windowRange(series)
    kpis.push({
      label: series.label,
      concept: series.concept,
      point: { ...point, unit: point.unit ?? series.unit },
      note: notes.noteFor(point),
      growthNote: isAnnual ? notes.noteForWindow(series) : notes.noteForComparison(point, 'yoy'),
      value: point.value as number,
      latestAvailable: point.period !== dataset.periods.at(-1)?.key,
      format: series.concept === 'net_margin' ? (v) => fmtPercent(v, { digits: 1 }) : (v) => fmtCurrency(v, { compact: true, currency: series.unit.split('/')[0] }),
      tone: series.tone,
      isPercent: series.percent,
      growth,
      growthReconciled: isAnnual
        ? (win.isPercent ? series.window_pp_reconciled : series.cagr_reconciled)
        : point.yoy_reconciled,
      growthProvenance: isAnnual
        ? (win.isPercent ? series.window_pp_provenance : series.cagr_provenance)
        : point.yoy_provenance,
      growthLabel: isAnnual ? win.label : 'YoY',
      growthTitle: isAnnual && window ? `Computed over ${formatAnalysisPeriod(window)}` : undefined,
    })
  }
  if (kpis.length === 0) return null

  return (
    <div className="[container-type:inline-size]">
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4 [@container(width<17em)]:grid-cols-1">
        {kpis.map((kpi) => (
          <KpiTile key={kpi.label} kpi={kpi} />
        ))}
      </dl>
    </div>
  )
}
