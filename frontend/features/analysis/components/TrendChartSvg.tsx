'use client'
/**
 * The trend charts' spec renderer (docs/design/analysis-trend-charts-spec-2026-10.md §3.7, §4): one ChartModel drawn
 * from its ChartLayout as one SVG. The engine gives every string, position and colour index; this file only paints:
 * gridlines at round(y) + 0.5, y tick labels at the gutter, line paths through their points (cut by the plot's clip),
 * the marker and break-mark shapes, the off-scale rows' baselines, the value strip and the notes band (§4.0). Paint is
 * literal SVG attributes in the theme's hexes, never classes or var(), so the PNG export serialises the plot whole.
 * Text renders with geometric precision: under full font hinting at 1× (headless Chrome's default, and some desktops)
 * Blink otherwise snaps each advance to a whole pixel, 7 px where the plan counts Geist Mono's 6.6 (spec G1, D8).
 * The data-* attributes are the ones the DOM checks read (§4.0, D3, D4, D12, D14; step 6, E194): a mark in a series'
 * colour names its series and period, a line run its periods space-separated, the value strip's swatches sit in its
 * data-strip group, each panel names its plot rect (data-plot, "x y width height"), and every text its role
 * (data-text, TextRole). GutterOverlay repeats the gutter's text for A7's sticky gutter, from the same pieces.
 */
import { memo } from 'react'
import { Group } from '@visx/group'
import { Bar, LinePath } from '@visx/shape'
import { CHART_FONT } from '@/components/ui/Chart'
import { CAPTION, captionBacking, FONT_PX, gutterOverlayWidth, noteGlyphs, OFF_GLYPH, OFF_ROW, STRIP_LABEL_X, STRIP_MARKER_X, type ChartLayout, type GutterCut, type PanelBox } from '@/features/analysis/lib/charts/layout'
import type { ChartModel, ModelMark, ModelPoint, StripRow } from '@/features/analysis/lib/charts/model'
import type { ChartTokens } from '@/features/analysis/lib/charts/theme'
import { BreakMark, MarkerShape, StripSwatch } from './chartMarks'

const gridY = (y: number) => Math.round(y) + 0.5

/** What each `<text>` is, as its data-text attribute names it for the DOM checks (D3: only a bar label, an A13b label
 *  or a gap's "—"/"n/m" may sit inside a plot rect). */
export type TextRole = 'caption' | 'tick' | 'x' | 'label' | 'gap' | 'near-zero' | 'off-arrow' | 'off-value' | 'strip-name' | 'strip' | 'notes' | 'note'

/** A line's valued points split at each gap: the path never joins across a missing value (§3.4). */
function runsOf(points: ModelPoint[]): ModelPoint[][] {
  const runs: ModelPoint[][] = []
  let run: ModelPoint[] = []
  for (const point of points) {
    if (point.value == null) {
      if (run.length) runs.push(run)
      run = []
    } else run.push(point)
  }
  if (run.length) runs.push(run)
  return runs
}

/** A panel's caption, left-aligned in its band (§3.6). */
function Caption({ box, tokens }: { box: PanelBox; tokens: ChartTokens }) {
  return box.captionY != null && box.panel.caption ? <text x={0} y={box.captionY} fill={tokens.tick} data-text="caption">{box.panel.caption}</text> : null
}

/** A panel's y tick labels, right-aligned 8 px left of the plot (D5, D11). */
function TickLabels({ box, layout, tokens }: { box: PanelBox; layout: ChartLayout; tokens: ChartTokens }) {
  const { axis } = box.panel
  return axis.ticks.map((tick) => (
    <text key={tick} x={layout.gutter - 8} y={box.y(tick)} dy="0.32em" textAnchor="end" fill={tokens.tick} data-text="tick">{axis.format.tick(tick)}</text>
  ))
}

/** An expanded value-strip row's name: its series' swatch, then its short name, inside the gutter (§3.10). */
function StripName({ row, y, tokens }: { row: StripRow; y: number; tokens: ChartTokens }) {
  return (
    <>
      <StripSwatch swatch={row.swatch} marker={row.marker} x={STRIP_MARKER_X} y={y - 4} color={tokens.series[row.color]} ring={tokens.surface} />
      <text x={STRIP_LABEL_X} y={y} fill={tokens.tick} data-text="strip-name">{row.short}</text>
    </>
  )
}

/** A panel's gridlines from x1 to x2, 1 px at round(y) + 0.5: the zero tick's in «t.zero», the rest in «t.grid». */
function GridLines({ box, x1, x2, tokens }: { box: PanelBox; x1: number; x2: number; tokens: ChartTokens }) {
  return box.panel.axis.ticks.map((tick) => (
    <line key={tick} x1={x1} x2={x2} y1={gridY(box.y(tick))} y2={gridY(box.y(tick))} stroke={tick === 0 ? tokens.zero : tokens.grid} strokeWidth={1} />
  ))
}

/** A3b's dashed rule on each clipped edge of a panel, from x1 to x2. */
function EdgeRules({ box, x1, x2, tokens }: { box: PanelBox; x1: number; x2: number; tokens: ChartTokens }) {
  const [low, high] = box.panel.axis.domain
  return ([[box.offAbove, high], [box.offBelow, low]] as const).map(([band, edge]) => band && (
    <line key={edge} x1={x1} x2={x2} y1={gridY(box.y(edge))} y2={gridY(box.y(edge))} stroke={tokens.tick} strokeWidth={1} strokeDasharray="2 2" />
  ))
}

function PanelAxis({ box, layout, tokens }: { box: PanelBox; layout: ChartLayout; tokens: ChartTokens }) {
  return (
    <g>
      <Caption box={box} tokens={tokens} />
      <GridLines box={box} x1={layout.plotLeft} x2={layout.plotRight} tokens={tokens} />
      <TickLabels box={box} layout={layout} tokens={tokens} />
    </g>
  )
}

function Lines({ mark, box, layout, tokens, clipId }: { mark: ModelMark; box: PanelBox; layout: ChartLayout; tokens: ChartTokens; clipId: string }) {
  const color = tokens.series[mark.color]
  // An off-scale point keeps its true y, so its segment runs toward it and the clip cuts it at the plot edge (§3.4).
  const runs = runsOf(mark.points)
  return (
    <g>
      <g clipPath={`url(#${clipId})`}>
        {runs.filter((run) => run.length > 1).map((run) => (
          <LinePath key={run[0].period} data={run} x={(point) => layout.x(point.period)} y={(point) => box.y(point.value as number)}
            stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" fill="none"
            data-series={mark.seriesKey} data-period={run.map((point) => point.period).join(' ')} />
        ))}
      </g>
      {mark.points.map((point) => point.value == null || point.offscale ? null : (
        <MarkerShape key={point.period} kind={mark.marker ?? 'circle'} x={layout.x(point.period)} y={box.y(point.value)} color={color}
          ring={tokens.surface} datum={{ series: mark.seriesKey, period: point.period }} />
      ))}
    </g>
  )
}

function Bars({ box, tokens, marks }: { box: PanelBox; tokens: ChartTokens; marks: Map<string, ModelMark> }) {
  return (
    <g>
      {box.bars.map((bar) => {
        const mark = marks.get(bar.seriesKey)
        if (!mark) return null
        const cx = bar.x + bar.width / 2
        return (
          <g key={`${bar.seriesKey}:${bar.period}`}>
            <Bar x={bar.x} y={bar.y} width={bar.width} height={bar.height} rx={mark.kind === 'growth' ? 0 : 2} fill={tokens.series[mark.color]}
              data-series={bar.seriesKey} data-period={bar.period} data-v={bar.value} data-zero={bar.zero} />
            {/* A growth bar past the axis is broken 6 px inside its clipped end (§4.1). */}
            {bar.clipped && <BreakMark cx={cx} width={bar.width} y={bar.value >= 0 ? bar.y + 6 : bar.y + bar.height - 9} surface={tokens.surface} />}
          </g>
        )
      })}
      {box.bars.map((bar) => bar.label && (
        <text key={`${bar.seriesKey}:${bar.period}`} x={bar.x + bar.width / 2} y={bar.label.y} textAnchor="middle" fill={tokens.value} data-text="label">{bar.label.text}</text>
      ))}
      {box.gaps.map((gap) => <text key={gap.period} x={gap.x} y={gap.y} textAnchor="middle" fill={tokens.tick} data-text="gap">{gap.text}</text>)}
      {box.nearZero.map((label) => <text key={label.period} x={label.x} y={label.y} textAnchor="middle" fill={tokens.value} data-text="near-zero">{label.text}</text>)}
    </g>
  )
}

/** A3b: the dashed rule on a clipped edge, then each off-scale value in its row: the arrow in its series' colour and
 *  the true value in the value ink (§3.4). */
function OffScale({ box, layout, tokens }: { box: PanelBox; layout: ChartLayout; tokens: ChartTokens }) {
  return (
    <g>
      <EdgeRules box={box} x1={layout.plotLeft} x2={layout.plotRight} tokens={tokens} />
      {([['above', box.offAbove, '↑'], ['below', box.offBelow, '↓']] as const).map(([side, band, arrow]) => band && (
        <g key={side}>
          {band.items.map((item) => (
            <g key={`${item.seriesKey}:${item.period}`}>
              <text x={item.left} y={band.top + 10 + OFF_ROW * item.row} fill={tokens.series[item.color]} data-series={item.seriesKey} data-period={item.period} data-text="off-arrow">{arrow}</text>
              <text x={item.left + OFF_GLYPH} y={band.top + 10 + OFF_ROW * item.row} fill={tokens.value} data-text="off-value">{item.text}</text>
            </g>
          ))}
        </g>
      ))}
    </g>
  )
}

/** Memoised: its card re-renders as its viewport scrolls (the sticky gutter's cover), and the plan has not changed. */
export default memo(function TrendChartSvg({ model, layout, tokens, label, uid }: {
  model: ChartModel
  layout: ChartLayout
  tokens: ChartTokens
  label: string
  /** Unique on the page, for the panels' clip paths. */
  uid: string
}) {
  const marks = new Map(model.panels.flatMap((panel) => panel.marks.map((mark) => [mark.seriesKey, mark] as const)))
  return (
    <svg width={layout.width} height={layout.height} viewBox={`0 0 ${layout.width} ${layout.height}`} role="img" aria-label={label}
      fontFamily={CHART_FONT} fontSize={11} textRendering="geometricPrecision" style={{ display: 'block' }}>
      <defs>
        {layout.panels.map((box) => (
          <clipPath key={box.panel.id} id={`${uid}-${box.panel.id}`}>
            <rect x={layout.plotLeft} y={box.top - 1} width={layout.plotRight - layout.plotLeft} height={box.height + 2} />
          </clipPath>
        ))}
      </defs>
      {layout.panels.map((box) => (
        <Group key={box.panel.id} data-panel={box.panel.id} data-axis-step={box.panel.axis.step} data-axis-domain={box.panel.axis.domain.join(',')}
          data-plot={`${layout.plotLeft} ${box.top} ${layout.plotRight - layout.plotLeft} ${box.height}`}>
          <PanelAxis box={box} layout={layout} tokens={tokens} />
          {box.panel.marks.some((mark) => mark.kind !== 'line') && <Bars box={box} tokens={tokens} marks={marks} />}
          {box.panel.marks.filter((mark) => mark.kind === 'line').map((mark) => (
            <Lines key={mark.seriesKey} mark={mark} box={box} layout={layout} tokens={tokens} clipId={`${uid}-${box.panel.id}`} />
          ))}
          <OffScale box={box} layout={layout} tokens={tokens} />
        </Group>
      ))}
      <g>
        {model.periods.map((period) => (
          <text key={period.key} x={layout.x(period.key)} y={layout.xTickY} textAnchor="middle" fill={tokens.tick} data-text="x">
            {period.tick.map((line, i) => <tspan key={line} x={layout.x(period.key)} dy={i === 0 ? 0 : 12}>{line}</tspan>)}
          </text>
        ))}
      </g>
      {layout.stripTop != null && model.strip.map((row, i) => (
        <g key={row.label} data-strip={row.label}>
          <StripName row={row} y={layout.stripRowY[i]} tokens={tokens} />
          {model.periods.map((period) => (
            <text key={period.key} x={layout.x(period.key)} y={layout.stripRowY[i]} textAnchor="middle" fill={tokens.value} data-text="strip">{row.cells[period.key]}</text>
          ))}
        </g>
      ))}
      {/* The notes band is a visual index of the footnotes under the card, which carry the same letters. */}
      <g aria-hidden="true">
        {model.notesBand && <text x={0} y={layout.notesY} fill={tokens.tick} data-text="notes">Notes</text>}
        {noteGlyphs(model, layout).map((glyph) => (
          <text key={`${glyph.period}:${glyph.text}`} x={glyph.x} y={layout.notesY} textAnchor="middle" fill={tokens.note} data-text="note">{glyph.text}</text>
        ))}
      </g>
    </svg>
  )
})

/**
 * A7's sticky gutter (E193): while a plot that scrolls has scrolled its own y axis away, this layer repeats the gutter at
 * the viewport's left edge, at the positions the plot draws them: the surface over the gutter, each panel's caption on
 * a surface backing as wide as the caption (it runs past the gutter), the tick labels, "Notes" and the expanded strip's
 * row names. Past the gutter it covers the column a scroll leaves cut at its edge (layout.ts gutterCover), carrying the
 * plot's gridlines and edge rules across it, and the rest of any value that runs past its column across that edge
 * (gutterCuts). The caller sticks it over the plot, outside the plot's node, so the PNG export never draws it.
 */
export function GutterOverlay({ model, layout, tokens, cover, cuts }: { model: ChartModel; layout: ChartLayout; tokens: ChartTokens; cover: number; cuts: GutterCut[] }) {
  const width = gutterOverlayWidth(layout, cover, cuts)
  return (
    <svg width={width} height={layout.height} viewBox={`0 0 ${width} ${layout.height}`} aria-hidden="true"
      fontFamily={CHART_FONT} fontSize={11} textRendering="geometricPrecision" style={{ display: 'block' }}>
      <rect x={0} y={0} width={cover} height={layout.height} fill={tokens.surface} />
      {cuts.map((cut) => <rect key={`${cut.y}:${cut.width}`} data-cut x={cut.x} y={cut.y} width={cut.width} height={cut.height} fill={tokens.surface} />)}
      {layout.panels.map((box) => (
        <g key={box.panel.id}>
          {cover > layout.plotLeft && <GridLines box={box} x1={layout.plotLeft} x2={cover} tokens={tokens} />}
          {cover > layout.plotLeft && <EdgeRules box={box} x1={layout.plotLeft} x2={cover} tokens={tokens} />}
          {captionBacking(box) > 0 && <rect x={0} y={box.captionY! - FONT_PX} width={captionBacking(box)} height={CAPTION} fill={tokens.surface} />}
          <Caption box={box} tokens={tokens} />
          <TickLabels box={box} layout={layout} tokens={tokens} />
        </g>
      ))}
      {layout.stripTop != null && model.strip.map((row, i) => <StripName key={row.label} row={row} y={layout.stripRowY[i]} tokens={tokens} />)}
      {model.notesBand && <text x={0} y={layout.notesY} fill={tokens.tick} data-text="notes">Notes</text>}
    </svg>
  )
}
