'use client'

import { useEffect, useLayoutEffect, useRef, type CSSProperties } from 'react'
import { Card } from '@/components/ui'
import { useCountUp } from '@/hooks/useCountUp'
import { compactCurrencyCountUp, fmtPercent } from '@/lib/format'
import { dataDirectionText } from '@/lib/financialTone'
import { formatGrowth, windowGrowth, windowRange } from '@/features/analysis/lib/growth'
import { applySeriesTone } from '@/features/analysis/lib/tonePolicy'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { selectHeadlineFigures } from '@/features/analysis/lib/reportPresentation'
import { kpiValueGlyphs, kpiWidestCss } from '@/features/analysis/lib/kpiStripLayout'
import { isCalculated } from '@/features/analysis/lib/provenance'
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

/** The strip's columns follow its widest value, not a fixed breakpoint, so a long value never leaves its card (E197).
 *  --kpi-value is that value at the advances the strip measures (--kpi-figure, --kpi-mark: the face's 0.6em until it
 *  has, so a server-rendered strip, the landing demo's, lays out at 0.6em until it hydrates; where a browser snaps
 *  glyphs that is up to half a pixel a glyph off, inside the card's padding), and --kpi-card adds the card's padding
 *  (p-3, sm:p-4) and its 1px border. Below lg: two cards when every
 *  value fits half the strip, else one. From lg: one card per tile, four at most (--kpi-cols), when they fit; else
 *  two, else one, never three of four. The `min()` term is a step: when --kpi-card exceeds a column of --kpi-cols, its
 *  multiplied excess lifts the minimum to half the strip. Each share keeps 0.5px back, so layout rounding cannot drop
 *  a column whose cards fit it exactly; a card within that half pixel of a share gets the next count the rule allows
 *  (two of four, or one). Below 17em of its own text size the strip still takes one card, whatever its values. */
const KPI_GRID = 'grid gap-3 [--kpi-figure:0.9rem] [--kpi-mark:0.4125rem] [--kpi-card:calc(var(--kpi-value)_+_1.5rem_+_2px)] sm:[--kpi-card:calc(var(--kpi-value)_+_2rem_+_2px)] [--kpi-half:calc((100%_-_0.75rem)_/_2_-_0.5px)] [--kpi-each:calc((100%_-_(var(--kpi-cols)_-_1)_*_0.75rem)_/_var(--kpi-cols)_-_0.5px)] [grid-template-columns:repeat(auto-fill,minmax(max(var(--kpi-card),var(--kpi-half)),1fr))] lg:[grid-template-columns:repeat(auto-fill,minmax(max(var(--kpi-each),var(--kpi-card),min(var(--kpi-half),calc(var(--kpi-each)_+_(var(--kpi-card)_-_var(--kpi-each))_*_1000000))),1fr))] [@container(width<17em)]:grid-cols-1'

/** Drawn hidden beside the strip: ten glyphs in the value's classes (KpiTile's dd) and a dagger as DataNoteMark draws
 *  it at the value's weight (its raise, which `large` sets, moves it up but not across). Their widths give the advances
 *  this browser paints, which the face's 0.6em only approximates where glyphs snap to whole pixels. */
const PROBE = '0000000000'
const PROBES = 'pointer-events-none invisible absolute h-0 w-0 overflow-hidden'
const FIGURE_PROBE = 'block w-max whitespace-pre font-figure text-2xl font-semibold tabular-nums lining-nums tracking-normal'
// Layout effects warn on the server; the measurement only runs in a browser.
const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect

/** Headline strip: latest top line, net income, FCF, net margin — with the window's CAGR/YoY
 *  (or, for the percent-unit net-margin card, the window's pp change — CAGR doesn't apply). */
export default function KpiStrip({ dataset }: { dataset: AnalysisDataset }) {
  const notes = useDataNotes(dataset)
  const strip = useRef<HTMLDListElement>(null)
  const figureProbe = useRef<HTMLSpanElement>(null)
  const markProbe = useRef<HTMLSpanElement>(null)
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
      // A count-up frame is never wider than the value it ends on (compactCurrencyCountUp), so the final value sizes the card.
      format: series.concept === 'net_margin' ? (v) => fmtPercent(v, { digits: 1 }) : compactCurrencyCountUp(point.value as number, series.unit.split('/')[0]),
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
  // The advances as painted, before paint and again whenever the probes resize: the face arriving after its fallback,
  // or a new text size.
  const shown = kpis.length > 0
  useIsomorphicLayoutEffect(() => {
    const [dl, figure, mark] = [strip.current, figureProbe.current, markProbe.current?.firstElementChild]
    if (!dl || !figure || !mark) return
    // The used width, a layout size: a transformed ancestor would skew a client rect, and resize nothing to measure again.
    const measure = () => {
      for (const [name, probe, glyphs] of [['--kpi-figure', figure, PROBE.length], ['--kpi-mark', mark, 1]] as const) {
        const width = parseFloat(getComputedStyle(probe).width)
        if (width > 0) dl.style.setProperty(name, `${width / glyphs}px`)
      }
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(figure)
    observer.observe(mark)
    return () => observer.disconnect()
  }, [shown])
  if (!shown) return null
  // The strip's widest value on one line, its figure and marks, at the measured advances (E197): CA$968.0M with its
  // dagger is 9 figure glyphs, 1 mark and its 2px gap, 8.6375rem at the face's 0.6em.
  const widest = kpiWidestCss(kpis.map((kpi) => kpiValueGlyphs(kpi.format(kpi.value), isCalculated(kpi.point), kpi.note?.letter)))
  const grid = { '--kpi-value': widest, '--kpi-cols': Math.min(4, kpis.length) } as CSSProperties

  return (
    <div className="[container-type:inline-size]">
      <div aria-hidden="true" className={PROBES}>
        <span ref={figureProbe} className={FIGURE_PROBE}>{PROBE}</span>
        <span ref={markProbe} className="block w-max font-semibold"><DataNoteMark calculated /></span>
      </div>
      <dl ref={strip} className={KPI_GRID} style={grid}>
        {/* Keyed by its value too, so a new value counts up from zero in its own unit: a tween from the old value would
            draw frames wider than the card sized for the new one ("$999.9M" on the way from $1.0B to $80.0M). */}
        {kpis.map((kpi) => (
          <KpiTile key={`${kpi.label}:${kpi.value}`} kpi={kpi} />
        ))}
      </dl>
    </div>
  )
}
