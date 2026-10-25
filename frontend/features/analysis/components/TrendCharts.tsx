'use client'

import dynamic from 'next/dynamic'
import { useContext, useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Rectangle,
  Tooltip,
  XAxis,
  YAxis,
  usePlotArea,
  useXAxisScale,
  useYAxisScale,
  type TooltipContentProps,
} from 'recharts'
import { toast } from 'sonner'

import { ThemeContext } from '@/components/ThemeProvider'
import { useOverflowRegion } from '@/hooks/useOverflowRegion'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import {
  AxisSeriesTag,
  Card,
  ChartTooltip,
  CHART_FONT,
  chartTheme,
  barCursorProps,
  cx,
  gridProps,
  lineProps,
  seriesColor,
  xAxisProps,
  yAxisProps,
} from '@/components/ui'
import { ArrowsInSimpleIcon, ArrowsOutSimpleIcon, ImageSquareIcon } from '@/lib/icons'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import analytics from '@/lib/analytics'
import { CHARTS_V2 } from '@/lib/featureFlags'
import { chartDataNotes, exportFilename, exportPanelPng, exportSourceText } from '@/features/analysis/lib/chartExport'
import { AXIS_CAPS, chartCurrency, chartTopLine, MIXED_CURRENCY } from '@/features/analysis/lib/charts/model'
import { valueAxis } from '@/features/analysis/lib/charts/scale'
import {
  ANNUAL_AXIS_HEIGHT,
  PeriodAxisTick,
  QUARTERLY_AXIS_HEIGHT,
  periodAxisLabel,
} from '@/features/analysis/lib/periodAxis'
import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'
import { formatCompanyName } from '@/lib/formatCompanyName'
import ChartControl from './ChartControl'
import DataNotesLink from './DataNotesLink'
import { useDataNotes } from './DataNotesContext'
import type { DataNote, DataNotesModel } from '@/features/analysis/lib/dataNotes'
import { formatAnalysisPeriod } from '@/features/analysis/lib/periodLabels'
import { layoutChartNotes, type ChartNotePosition } from '@/features/analysis/lib/chartNoteLayout'

const bySeries = (dataset: AnalysisDataset): Record<string, AnalysisSeries> =>
  Object.fromEntries(dataset.series.map((s) => [s.concept, s]))

/** A y-axis from the chart engine (A1, A2): zero-anchored ticks on the densest legal grid under the panel's cap, one
 *  unit, the filer's currency. Percent axes take every value: Recharts cannot print a clipped value at the plot edge,
 *  so none is clipped (A3 waits for the engine's own renderer). */
type EngineAxis = ReturnType<typeof valueAxis>

/** Wide enough for the axis's widest tick label as Recharts draws it: in yAxisProps' font size at Geist Mono's 0.6 em
 *  advance, set in from the plot by its tick margin and the tick length Recharts keeps when the tick line is off. */
const Y_TICK = yAxisProps(false)
const RECHARTS_TICK_SIZE = 6
const axisWidth = (axis: EngineAxis, min: number) => {
  const glyphs = Math.max(0, ...axis.ticks.map((tick) => [...axis.format.tick(tick)].length))
  return Math.max(min, Math.ceil(glyphs * Y_TICK.tick.fontSize * 0.6) + RECHARTS_TICK_SIZE + Y_TICK.tickMargin)
}

/** An axis's tick label, kept on one line. Recharts breaks a label at a space when its own measure (not in Geist Mono)
 *  finds it wider than the axis, which drew "CHF 20B" as "CHF" over "20B"; it never breaks at a no-break space. */
const tickLabel = (axis: EngineAxis) => (value: number) => axis.format.tick(value).replace(/ /g, '\u00a0')

const CHART_MARGIN = { top: 24, right: 16, left: 8, bottom: 0 }
/** Every quarterly period keeps this much of the plot's width on a phone, where the chart viewport scrolls instead. */
const QUARTER_SLOT = 28

/** A quarterly plot's minimum width: QUARTER_SLOT a period plus its axes and margins (never under the 144 px reserved
 *  before the axes fitted their labels). A card within one slot of that width fits the plot instead of scrolling a
 *  sliver, so the minimum steps down one slot once the card (100%) reaches it: the clamp climbs 1000 px for each px. */
const quarterlyMinWidth = (periods: number, axes: number) => {
  const full = periods * QUARTER_SLOT + Math.max(144, axes)
  return `calc(${full}px - clamp(0px, (100% - ${full - QUARTER_SLOT}px) * 1000, ${QUARTER_SLOT}px))`
}

/** A tooltip prints the axis's own formats: amounts at the panel's 3 significant figures, percents at 1 dp. */
const tooltipValue = (axis: EngineAxis, value: number) => (axis.format.kind === 'money' ? axis.format.value(value) : axis.format.value(value, 1))

const numbersIn = (rows: Record<string, string | number | null>[], keys: string[]) =>
  rows.flatMap((row) => keys.map((key) => row[key]).filter((value): value is number => typeof value === 'number'))

// The bar panel's series→(label, color) pairing — ONE definition referenced by both the legend
// and the plotted Bar/Line JSX, so the swatches can never drift from what's actually drawn.
const BAR_COLOR = seriesColor(0)
const GROWTH_LINE_COLOR = seriesColor(1)
const GROWTH_LINE_LABEL = 'YoY growth'
const MAX_BAR_SIZE = 44

/** A panel's series legend: swatch + label per line, mirroring ChartTooltip's own swatch recipe
 *  (8×8 square, 2px radius) so a multi-line panel's series are identifiable without hovering.
 *  A single-series panel needs no legend — the title already names the one line. */
function PanelLegend({ items, notes }: { items: { label: string; color: string }[]; notes: DataNote[] }) {
  if (items.length < 2 && notes.length === 0) return null
  return (
    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
      {(items.length >= 2 ? items : []).map((item) => (
        <span
          key={item.label}
          className="inline-flex items-center gap-1.5 text-xs text-text-secondary-light dark:text-text-secondary-dark"
        >
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 shrink-0 rounded-sm"
            style={{ background: item.color }}
          />
          {item.label}
        </span>
      ))}
      <DataNotesLink notes={notes} />
    </div>
  )
}

interface NoteDotProps {
  cx?: number
  cy?: number
  value?: number | null
  payload?: { period?: string }
}

/** A concern is visible at its own plotted point; the legend link opens its full note. */
function NoteDot({ cx, cy, value, color, dark, note, position }: NoteDotProps & { color: string; dark: boolean; note: DataNote | null; position?: ChartNotePosition }) {
  if (!note || value == null || !Number.isFinite(cx) || !Number.isFinite(cy)) return <g />
  return (
    <g aria-label={`Data note ${note.letter}`}>
      <circle cx={cx} cy={cy} r={4} fill={chartTheme(dark).tipBg} stroke={color} strokeWidth={2} />
      <text x={position?.x ?? cx} y={position?.y ?? cy! - 9} textAnchor="middle" fill={chartTheme(dark).label} stroke={chartTheme(dark).tipBg} strokeWidth={3} strokeLinejoin="round" paintOrder="stroke" fontFamily={CHART_FONT} fontSize={11}>{note.letter}</text>
    </g>
  )
}

interface ChartNoteDatum { key: string; period: string; value: number; letter: string | null; axis: 'left' | 'right' | 'value' | 'growth' }

function useChartNotePosition(anchors: ChartNoteDatum[], anchorKey: string) {
  const plot = usePlotArea()
  const xScale = useXAxisScale()
  const leftScale = useYAxisScale('left')
  const rightScale = useYAxisScale('right')
  const valueScale = useYAxisScale('value')
  const growthScale = useYAxisScale('growth')
  const scales = { left: leftScale, right: rightScale, value: valueScale, growth: growthScale }
  // Values and comparisons keep their actual axes. Only projected pixels share this pass,
  // so a bar endpoint and its growth point cannot independently choose overlapping letters.
  return plot && xScale ? layoutChartNotes(anchors.map((anchor) => {
    const yScale = scales[anchor.axis]
    return {
      key: anchor.key, letter: anchor.letter, x: xScale(anchor.period, { position: 'middle' }) ?? Number.NaN, y: yScale?.(anchor.value) ?? Number.NaN,
    }
  }), plot).get(anchorKey) : undefined
}

function PositionedNoteDot({ anchors, anchorKey, ...props }: NoteDotProps & {
  color: string; dark: boolean; note: DataNote; anchors: ChartNoteDatum[]; anchorKey: string
}) {
  const position = useChartNotePosition(anchors, anchorKey)
  return <NoteDot {...props} position={position} />
}

interface NoteBarProps {
  x?: number
  y?: number
  width?: number
  height?: number
  payload?: { period?: string }
}

function NoteBar({ x, y, width, height, color, dark, note, position }: NoteBarProps & { color: string; dark: boolean; note: DataNote | null; position?: ChartNotePosition }) {
  if (x == null || y == null || width == null || height == null) return <g />
  return (
    <g aria-label={note ? `Data note ${note.letter}` : undefined}>
      <Rectangle x={x} y={y} width={width} height={height} radius={[4, 4, 0, 0]}
        fill={color} />
      {/* Recharts supplies y at the value endpoint and signed height back to the baseline. */}
      {note && <text x={position?.x ?? x + width / 2} y={position?.y ?? y + (height < 0 ? 18 : -10)} textAnchor="middle" fill={chartTheme(dark).label} stroke={chartTheme(dark).tipBg} strokeWidth={3} strokeLinejoin="round" paintOrder="stroke" fontFamily={CHART_FONT} fontSize={11}>{note.letter}</text>}
    </g>
  )
}

function PositionedNoteBar({ anchors, anchorKey, ...props }: NoteBarProps & {
  color: string; dark: boolean; note: DataNote; anchors: ChartNoteDatum[]; anchorKey: string
}) {
  const position = useChartNotePosition(anchors, anchorKey)
  return <NoteBar {...props} position={position} />
}

/** A keyboard stop is useful only while there is more plot to scroll into view. */
function ChartViewport({ label, children, onKeyboardNavigationChange }: {
  label: string
  children: React.ReactNode
  onKeyboardNavigationChange: (active: boolean) => void
}) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const { regionProps } = useOverflowRegion(viewportRef, {
    label: `${label} chart. Scroll horizontally to view all periods.`,
  })
  const takeKeyboardNavigation = (surface: SVGElement, viewport: HTMLDivElement) => {
    onKeyboardNavigationChange(true)
    // Recharts prioritizes a retained hover over its keyboard index. An ordinary scoped
    // mouse leave releases that hover; the real key event then selects the next period.
    surface.dispatchEvent(new MouseEvent('mouseout', { bubbles: true, relatedTarget: viewport }))
  }
  return <div ref={viewportRef} data-analysis-chart-scroll {...regionProps}
    onFocusCapture={(event) => {
      if (event.target instanceof SVGElement && event.target.getAttribute('role') === 'application'
        && event.target.matches(':focus-visible')) takeKeyboardNavigation(event.target, event.currentTarget)
    }}
    onBlurCapture={() => onKeyboardNavigationChange(false)}
    onPointerMoveCapture={() => onKeyboardNavigationChange(false)}
    onPointerDownCapture={() => onKeyboardNavigationChange(false)}
    onKeyDownCapture={(event) => {
      // Recharts moves one period per arrow. Native pixel scrolling on that same key can
      // drift away from the selected period; the outer region keeps its native scrolling.
      if (event.target instanceof SVGElement && event.target.getAttribute('role') === 'application'
        && ['ArrowLeft', 'ArrowRight', 'Enter'].includes(event.key)) {
        takeKeyboardNavigation(event.target, event.currentTarget)
        if (event.key !== 'Enter') event.preventDefault()
      }
    }}
    className="overflow-x-auto rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark has-[:focus-visible]:shadow-ring-brand dark:has-[:focus-visible]:shadow-ring-brand-dark [&_svg[role=application]:focus-visible]:outline-none">
    {children}
  </div>
}

/** Keep a keyboard-selected mark and its live tooltip inside the horizontal viewport. */
function ChartTooltipStatus({ active, keyboardNavigation, coordinateX, plotRef, children }: {
  active: boolean
  keyboardNavigation: boolean
  coordinateX?: number
  plotRef: React.RefObject<HTMLDivElement>
  children: React.ReactNode
}) {
  const statusRef = useRef<HTMLDivElement>(null)
  // Recharts repositions the wrapper after measuring its contents. Measure each render,
  // including that second layout pass, rather than retaining a stale tooltip rectangle.
  useLayoutEffect(() => {
    const status = statusRef.current
    const plot = plotRef.current
    const viewport = plot?.parentElement
    if (!active || !status || !plot || !viewport) return
    let frame = viewport.getBoundingClientRect()
    const focused = document.activeElement
    if (keyboardNavigation && focused instanceof SVGElement && focused.getAttribute('role') === 'application'
      && plot.contains(focused) && coordinateX != null) {
      const pointX = plot.getBoundingClientRect().left + coordinateX
      const halfMark = MAX_BAR_SIZE / 2
      if (pointX - halfMark < frame.left || pointX + halfMark > frame.right) {
        viewport.scrollBy({ left: pointX - frame.left - frame.width / 2, behavior: 'instant' })
        frame = viewport.getBoundingClientRect()
      }
    }
    // A wide tooltip may need to wrap on phones. Only its presentation moves; its series,
    // period, note identities and values still come directly from Recharts' active payload.
    status.style.maxWidth = `${viewport.clientWidth}px`
    status.style.transform = 'none'
    const tip = status.getBoundingClientRect()
    const shift = Math.max(frame.left - tip.left, Math.min(0, frame.right - tip.right))
    status.style.transform = `translateX(${shift}px)`
  })
  return <div ref={statusRef} role="status" style={{ width: 'max-content' }}>{children}</div>
}

interface PanelSpec {
  title: string
  /** [concept, display label] pairs; only concepts present in the dataset render. */
  lines: [string, string][]
  /** The ONE concept (from `lines`) plotted on a RIGHT value axis — mixed-magnitude panels (equity
   *  dwarfs debt/cash on the balance sheet) get a second scale. Deliberately a single concept, not
   *  an array: the colored-right-axis binding (spine + head-tag in that series' hue) only reads
   *  unambiguously when the right scale carries exactly one series, so the type forbids more. */
  rightAxis?: string
  /** Bar series (first panel: the top line as bars + growth as a line). */
  bar?: [string, string]
  /** Right-axis growth line derived from the bar concept's yoy. */
  growthLine?: boolean
  /** Amounts or percents, and A1's interval caps: the left (or only) axis's, and the right axis's. */
  kind: 'money' | 'percent'
  caps: { left: number; right?: number }
}

function PanelCard({
  panel,
  dataset,
  series,
  exportEnabled,
  notes,
}: {
  panel: PanelSpec
  dataset: AnalysisDataset
  series: Record<string, AnalysisSeries>
  exportEnabled: boolean
  notes: DataNotesModel
}) {
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const reduced = usePrefersReducedMotion()
  const [expanded, setExpanded] = useState(false)
  const [keyboardNavigation, setKeyboardNavigation] = useState(false)
  const plotRef = useRef<HTMLDivElement>(null)
  // The quarterly table usually shows QoQ, so it cannot replace keyboard access to chart YoY.
  const keyboardLabel = `${panel.title} chart values. Use Left and Right arrows to inspect periods.`

  // One series→(concept, label, color, axis) mapping drives the legend AND the plotted <Line>s —
  // built once so the two can't disagree on color/label pairing.
  const lineEntries = panel.lines
    .filter(([concept]) => series[concept])
    .map(([concept, label], index) => ({
      concept,
      label,
      color: seriesColor(index),
      right: concept === panel.rightAxis,
    }))
  // The right axis carries EXACTLY ONE series (the type guarantees it) — bind the colored spine +
  // head-tag to it. A second scale only helps when a LEFT series is also present (equity alone
  // stays single-axis).
  const rightEntry = lineEntries.find((e) => e.right)
  const dualAxis = Boolean(rightEntry) && lineEntries.some((e) => !e.right)
  const barSeries = panel.bar && series[panel.bar[0]] ? series[panel.bar[0]] : null
  if (!barSeries && lineEntries.length === 0) return null

  const plottedSeries = barSeries ? [barSeries] : lineEntries.map(({ concept }) => series[concept])
  const { panelNotes, unavailable: unavailableNotes, exportNotes } = chartDataNotes(dataset, plottedSeries, notes, !!panel.growthLine)
  const noteAt = (concept: string, period: string, growth = false) => {
    const point = series[concept]?.points.find((entry) => entry.period === period)
    return point ? growth ? notes.noteForComparison(point, 'yoy') : notes.noteFor(point) : null
  }
  const renderDot = (concept: string, color: string, growth = false) => function ChartNoteDot(props: NoteDotProps) {
    const period = props.payload?.period ?? ''
    const note = noteAt(concept, period, growth)
    return note
      ? <PositionedNoteDot {...props} color={color} dark={dark} note={note} anchors={chartNotes} anchorKey={`${concept}:${period}:${growth ? 'growth' : 'value'}`} />
      : <NoteDot {...props} color={color} dark={dark} note={note} />
  }

  // One row per period; keys are concept names (+ `growth` for the yoy line).
  const data = dataset.periods.map((period) => {
    const row: Record<string, string | number | null> = { period: period.key }
    for (const { concept } of lineEntries) {
      row[concept] = series[concept].points.find((p) => p.period === period.key)?.value ?? null
    }
    if (barSeries) {
      const point = barSeries.points.find((p) => p.period === period.key)
      row[barSeries.concept] = point?.value ?? null
      if (panel.growthLine) {
        // A sign-flip ("nm") isn't a plottable percentage — render it as a gap, same as a
        // missing value, rather than coercing the sentinel into NaN.
        row.growth = typeof point?.yoy === 'number' ? point.yoy * 100 : null
      }
    }
    return row
  })
  // The axes, from the engine. A panel's amounts share one currency, or the chart says so instead of drawing.
  const currency = panel.kind === 'money' ? chartCurrency(dataset, plottedSeries.map((s) => s.concept)) : { currency: null, mixed: false }
  const leftEntries = lineEntries.filter((entry) => !(dualAxis && entry.right))
  // A lone right-axis series (equity without debt or cash) sits on the left axis with its own cap.
  const leftCap = !barSeries && leftEntries.every((entry) => entry.right) ? panel.caps.right ?? panel.caps.left : panel.caps.left
  const leftAxis = valueAxis(numbersIn(data, barSeries ? [barSeries.concept] : leftEntries.map((entry) => entry.concept)), leftCap, panel.kind, currency.currency)
  const growthAxis = valueAxis(numbersIn(data, ['growth']), panel.caps.right ?? AXIS_CAPS.growth, 'growth')
  const rightAxis = dualAxis && rightEntry ? valueAxis(numbersIn(data, [rightEntry.concept]), panel.caps.right ?? panel.caps.left, panel.kind, currency.currency) : null
  const axisOf = (dataKey: string) => (dataKey === 'growth' ? growthAxis : rightAxis && dataKey === rightEntry?.concept ? rightAxis : leftAxis)
  const leftWidth = axisWidth(leftAxis, 64)
  const rightWidth = barSeries ? axisWidth(growthAxis, 48) : rightAxis ? axisWidth(rightAxis, 64) : 0
  if (currency.mixed) {
    // No one scale can carry two currencies, and no amount is ever printed as dollars by default.
    return (
      <Card as="section" className="min-w-0 p-cap-5">
        <h2 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{panel.title}</h2>
        <p className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">{MIXED_CURRENCY}</p>
      </Card>
    )
  }

  const chartNotes: ChartNoteDatum[] = data.flatMap((row): ChartNoteDatum[] => {
    const period = String(row.period)
    if (barSeries) {
      const value = row[barSeries.concept]
      return [
        ...(typeof value === 'number' ? [{ key: `${barSeries.concept}:${period}:value`, period, value, letter: noteAt(barSeries.concept, period)?.letter ?? null, axis: 'value' as const }] : []),
        ...(typeof row.growth === 'number' ? [{ key: `${barSeries.concept}:${period}:growth`, period, value: row.growth, letter: noteAt(barSeries.concept, period, true)?.letter ?? null, axis: 'growth' as const }] : []),
      ]
    }
    return lineEntries.flatMap(({ concept, right }) => {
      const value = row[concept]
      return typeof value === 'number' ? [{ key: `${concept}:${period}:value`, period, value, letter: noteAt(concept, period)?.letter ?? null, axis: dualAxis && right ? 'right' : 'left' }] : []
    })
  })

  // Route by SERIES, not by value magnitude: each value prints in its own axis's format, so a micro-cap's
  // $850 bar or a +1,400% growth spike never falls through a magnitude heuristic to the wrong one.
  const formatTooltip = (v: number | string | undefined, dataKey: string) => {
    const num = Number(v)
    return Number.isFinite(num) ? tooltipValue(axisOf(dataKey), num) : String(v ?? '')
  }

  const renderTooltip = ({ active, label, payload, coordinate }: TooltipContentProps) => (
    <ChartTooltipStatus active={active} keyboardNavigation={keyboardNavigation} coordinateX={coordinate?.x} plotRef={plotRef}>
      <ChartTooltip
        dark={dark}
        active={active}
        label={formatAnalysisPeriod(String(label ?? ''))}
        payload={payload?.map((entry) => {
          const growth = entry.dataKey === 'growth'
          const concept = growth ? barSeries?.concept : String(entry.dataKey ?? '')
          const note = concept ? noteAt(concept, String(label ?? ''), growth) : null
          return {
            name: `${entry.name ?? ''}${note ? ` · note ${note.letter}` : ''}`,
            // Format by the original data key before the display name gains a note letter.
            value: formatTooltip(typeof entry.value === 'number' ? entry.value : String(entry.value ?? ''), String(entry.dataKey ?? '')),
            color: entry.color,
          }
        })}
      />
    </ChartTooltipStatus>
  )

  const legendItems = barSeries
    ? [
        { label: barSeries.label, color: BAR_COLOR },
        ...(panel.growthLine ? [{ label: GROWTH_LINE_LABEL, color: GROWTH_LINE_COLOR }] : []),
      ]
    : // Symmetric (left)/(right) is a legend-only decoration: the words positively bind the LEFT
      // series (which can't be color-bound — the left axis may carry two hues), while the on-plot
      // colored right axis + head-tag bind the right. The color/label pairing itself stays shared.
      lineEntries.map(({ label, color, right }) => ({
        label: dualAxis ? `${label} (${right ? 'right' : 'left'})` : label,
        color,
      }))

  const exportPng = async () => {
    if (!plotRef.current) return
    const downloaded = await exportPanelPng(
      plotRef.current,
      exportFilename(dataset, panel.title, 'png'),
      // Company + ticker anchor the standalone image (the on-screen page carries them in its
      // picker, a shared PNG doesn't); metric title + the SAME legendItems the on-screen
      // PanelLegend draws frame the plot. The `< 2` gate mirrors PanelLegend: a single-series
      // panel is named by the title alone, so it shows no legend here either.
      {
        dark,
        header: {
          company: formatCompanyName(dataset.company_name),
          ticker: dataset.ticker,
          title: panel.title,
          legend: legendItems.length >= 2 ? legendItems : [],
          ...exportSourceText(dataset),
          notes: exportNotes,
        },
      }
    ).catch(() => false)
    if (downloaded) {
      analytics.exportGenerated({
        surface: 'analysis',
        format: 'png',
        ticker: dataset.ticker,
        mode: dataset.mode,
        periodKey: dataset.period_key,
        panel: panel.title,
      })
    } else {
      // No image was made: no plot, an image or canvas that failed, a face it could not embed (chartExport stops
      // rather than draw the plot in another font), or a throw. Say so; a click must never do nothing.
      toast.error('Could not create the chart image. Try again.')
    }
  }

  return (
    <Card as="section" className={cx('min-w-0 p-cap-5', expanded && 'md:col-span-2')}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          {/* h2: the chart panels sit beside the narrative's and the metrics table's h2 sections
              under the page h1 (an h3 here skipped a level). */}
          <h2 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            {panel.title}
          </h2>
          <PanelLegend items={legendItems} notes={panelNotes} />
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {exportEnabled && (
            <ChartControl label="Download chart as PNG" onClick={() => void exportPng()}>
              <ImageSquareIcon className="h-5 w-5" aria-hidden="true" />
            </ChartControl>
          )}
          <ChartControl
            label={expanded ? 'Collapse chart' : 'Expand chart'}
            expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <ArrowsInSimpleIcon className="h-5 w-5" aria-hidden="true" />
            ) : (
              <ArrowsOutSimpleIcon className="h-5 w-5" aria-hidden="true" />
            )}
          </ChartControl>
        </div>
      </div>
      <ChartViewport label={panel.title} onKeyboardNavigationChange={setKeyboardNavigation}>
      <div
        ref={plotRef}
        data-analysis-chart={panel.title}
        // Keep every quarterly tick readable on touch screens; only the chart viewport scrolls, never the page.
        style={dataset.mode === 'quarterly'
          ? { minWidth: quarterlyMinWidth(dataset.periods.length, leftWidth + rightWidth + CHART_MARGIN.left + CHART_MARGIN.right) }
          : undefined}
        className={cx(
          'w-full transition-[height] duration-base ease-standard motion-reduce:transition-none',
          expanded ? 'h-96' : 'h-56'
        )}
      >
        <ResponsiveContainer width="100%" height="100%">
          {barSeries ? (
            <ComposedChart accessibilityLayer aria-label={keyboardLabel} data={data} margin={CHART_MARGIN}>
              <CartesianGrid {...gridProps(dark)} />
              <XAxis
                dataKey="period"
                {...xAxisProps(dark)}
                // Every period gets a tick (owner decision D2) — Recharts' auto interval was
                // dropping half of a 10-year window. The compact PeriodAxisTick buys the room,
                // and the axis caption underneath names what the bare ticks mean.
                interval={0}
                height={dataset.mode === 'quarterly' ? QUARTERLY_AXIS_HEIGHT : ANNUAL_AXIS_HEIGHT}
                tick={<PeriodAxisTick mode={dataset.mode} dark={dark} />}
                label={periodAxisLabel(dataset.mode, dark)}
              />
              <YAxis yAxisId="value" {...yAxisProps(dark)} width={leftWidth}
                domain={leftAxis.domain} ticks={leftAxis.ticks} interval={0} tickFormatter={tickLabel(leftAxis)} />
              <YAxis
                yAxisId="growth"
                orientation="right"
                {...yAxisProps(dark)}
                width={rightWidth}
                domain={growthAxis.domain}
                ticks={growthAxis.ticks}
                interval={0}
                tickFormatter={tickLabel(growthAxis)}
              />
              <Tooltip
                cursor={barCursorProps(dark)}
                content={renderTooltip}
                isAnimationActive={false}
              />
              <Bar
                yAxisId="value"
                dataKey={barSeries.concept}
                name={barSeries.label}
                fill={BAR_COLOR}
                radius={[4, 4, 0, 0]}
                maxBarSize={MAX_BAR_SIZE}
                isAnimationActive={!reduced}
                animationDuration={lineProps(reduced).animationDuration}
                shape={(props: unknown) => {
                  const bar = props as NoteBarProps
                  const period = bar.payload?.period ?? ''
                  const note = noteAt(barSeries.concept, period)
                  return note
                    ? <PositionedNoteBar {...bar} color={BAR_COLOR} dark={dark} note={note} anchors={chartNotes} anchorKey={`${barSeries.concept}:${period}:value`} />
                    : <NoteBar {...bar} color={BAR_COLOR} dark={dark} note={null} />
                }}
              />
              {panel.growthLine && (
                <Line
                  yAxisId="growth"
                  dataKey="growth"
                  name={GROWTH_LINE_LABEL}
                  stroke={GROWTH_LINE_COLOR}
                  {...lineProps(reduced)}
                  dot={renderDot(barSeries.concept, GROWTH_LINE_COLOR, true)}
                  connectNulls={false}
                />
              )}
            </ComposedChart>
          ) : (
            // Dual-axis panels reserve top room for the right axis's head-tag (the named scale).
            <LineChart accessibilityLayer aria-label={keyboardLabel} data={data} margin={CHART_MARGIN}>
              <CartesianGrid {...gridProps(dark)} />
              <XAxis
                dataKey="period"
                {...xAxisProps(dark)}
                // Every period gets a tick (owner decision D2) — Recharts' auto interval was
                // dropping half of a 10-year window. The compact PeriodAxisTick buys the room,
                // and the axis caption underneath names what the bare ticks mean.
                interval={0}
                height={dataset.mode === 'quarterly' ? QUARTERLY_AXIS_HEIGHT : ANNUAL_AXIS_HEIGHT}
                tick={<PeriodAxisTick mode={dataset.mode} dark={dark} />}
                label={periodAxisLabel(dataset.mode, dark)}
              />
              <YAxis
                yAxisId="left"
                {...yAxisProps(dark)}
                width={leftWidth}
                domain={leftAxis.domain}
                ticks={leftAxis.ticks}
                interval={0}
                tickFormatter={tickLabel(leftAxis)}
              />
              {rightEntry && rightAxis && (
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  {...yAxisProps(dark)}
                  width={rightWidth}
                  domain={rightAxis.domain}
                  ticks={rightAxis.ticks}
                  interval={0}
                  tickFormatter={tickLabel(rightAxis)}
                  // The right axis is the ONE colored scale: a 2px spine + tick nibs in its single
                  // series' hue bind that line to this scale by color, and the head-tag names it.
                  // Tick NUMBERS stay neutral (yAxisProps' tick fill, spread first) — no top-level
                  // `stroke`, which would tint them below the text-contrast floor.
                  axisLine={{ stroke: rightEntry.color, strokeWidth: 2 }}
                  tickLine={{ stroke: rightEntry.color, strokeWidth: 1 }}
                  label={<AxisSeriesTag color={rightEntry.color} label={rightEntry.label} dark={dark} />}
                />
              )}
              <Tooltip content={renderTooltip} isAnimationActive={false} />
              {lineEntries.map(({ concept, label, color, right }) => (
                <Line
                  key={concept}
                  yAxisId={dualAxis && right ? 'right' : 'left'}
                  dataKey={concept}
                  name={label}
                  stroke={color}
                  {...lineProps(reduced)}
                  dot={renderDot(concept, color)}
                  connectNulls={false}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      </ChartViewport>
      {unavailableNotes.length > 0 && (
        <p className="mt-2 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          {unavailableNotes.join(' ')}
        </p>
      )}
    </Card>
  )
}

/**
 * The four trend panels (revenue+growth, margins, cash, balance sheet), all straight from the
 * deterministic dataset via the design-system chart factories. Panels whose concepts are absent
 * (gross margin for a bank) collapse silently. Per-panel controls: PNG download (Pro), expand
 * to full grid width. (Data labels were removed after the AAPL field test — on dense real-world
 * series they collide into unreadable stacks; values live in the tooltip and metrics grid.)
 */
function RechartsTrendCharts({
  dataset,
  exportEnabled = false,
}: {
  dataset: AnalysisDataset
  /** Shows the per-panel PNG download (the page passes this on the Pro results surface only). */
  exportEnabled?: boolean
}) {
  const notes = useDataNotes(dataset)
  const series = useMemo(() => bySeries(dataset), [dataset])

  // The engine's top line (revenue, else net interest income, else premiums earned, with a value in the window), as
  // the KPI strip and the notes read it; with none, the panel is not drawn.
  const topLine = chartTopLine(dataset)

  const panels: PanelSpec[] = [
    {
      title: topLine ? `${topLine.label} & growth` : 'Top line & growth',
      lines: [],
      bar: topLine ? [topLine.concept, topLine.label] : undefined,
      growthLine: true,
      kind: 'money',
      caps: { left: AXIS_CAPS.topline, right: AXIS_CAPS.growth },
    },
    {
      title: 'Margins',
      lines: [
        ['gross_margin', 'Gross'],
        ['operating_margin', 'Operating'],
        ['net_margin', 'Net'],
      ],
      kind: 'percent',
      caps: { left: AXIS_CAPS.margins },
    },
    {
      // One axis (spec D1, D4): operating cash flow and net income are a median 1.5× apart, and a
      // second scale drew 29% of the pairs in the wrong order (REGN's FY2025 free cash flow, $4.08B,
      // above its $4.50B net income). Only JPM's quarterly window passes 10×.
      title: 'Cash generation',
      lines: [
        ['operating_cash_flow', 'Operating CF'],
        ['free_cash_flow', 'Free cash flow'],
        ['net_income', 'Net income'],
      ],
      kind: 'money',
      caps: { left: AXIS_CAPS.cash },
    },
    {
      // Equity routinely dwarfs debt/cash — a right axis keeps the smaller series readable
      // without breaking the "every pixel is a citable dollar value" promise an indexed view
      // would (audit D2).
      title: 'Balance sheet',
      lines: [
        ['long_term_debt', 'Long-term debt'],
        ['shareholders_equity', 'Equity'],
        ['cash_and_equivalents', 'Cash'],
      ],
      rightAxis: 'shareholders_equity',
      kind: 'money',
      caps: { left: AXIS_CAPS.debtcash, right: AXIS_CAPS.equity },
    },
  ]

  // Panels whose concepts are entirely absent collapse silently (a bank has no gross margin) —
  // filtered HERE so the grid (and the all-empty null return) is decided before any Card mounts.
  const visiblePanels = panels.filter((panel) => {
    const hasBar = panel.bar ? Boolean(series[panel.bar[0]]) : false
    const hasLine = panel.lines.some(([concept]) => series[concept])
    return hasBar || hasLine
  })
  if (visiblePanels.length === 0) return null

  return (
    <ChartErrorBoundary noun={visiblePanels.length > 1 ? 'charts' : 'chart'}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {visiblePanels.map((panel) => (
          <PanelCard
            key={panel.title}
            panel={panel}
            dataset={dataset}
            series={series}
            exportEnabled={exportEnabled}
            notes={notes}
          />
        ))}
      </div>
    </ChartErrorBoundary>
  )
}

/** The spec renderer (lib/featureFlags CHARTS_V2, E192), its own chunk so the flag-off route loads none of it. */
const TrendChartsV2 = dynamic(() => import('./TrendChartsV2'))

export default function TrendCharts({ dataset, exportEnabled = false }: { dataset: AnalysisDataset; exportEnabled?: boolean }) {
  return CHARTS_V2
    ? <TrendChartsV2 dataset={dataset} exportEnabled={exportEnabled} />
    : <RechartsTrendCharts dataset={dataset} exportEnabled={exportEnabled} />
}
