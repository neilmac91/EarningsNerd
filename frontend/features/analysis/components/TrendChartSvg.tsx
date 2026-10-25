'use client'
/**
 * The trend charts' spec renderer (docs/design/analysis-trend-charts-spec-2026-10.md §3.7, §4): one ChartModel drawn
 * from its ChartLayout as one SVG. The engine gives every string, position and colour index; this file only paints:
 * gridlines at round(y) + 0.5, y tick labels at the gutter, line paths through their points (cut by the plot's clip),
 * the marker and break-mark shapes, the off-scale rows' baselines, the value strip and the notes band (§4.0). Paint is
 * literal SVG attributes in the theme's hexes, never classes or var(), so the PNG export serialises the plot whole.
 * Text renders with geometric precision: under full font hinting at 1× (headless Chrome's default, and some desktops)
 * Blink otherwise snaps each advance to a whole pixel, 7 px where the plan counts Geist Mono's 6.6 (spec G1, D8).
 * The data-* attributes are the ones the DOM checks read (§4.0, D4, D12, D14; step 6, E194): a mark in a series' colour
 * names its series and period, a line run its periods space-separated, and the value strip's swatches sit in its
 * data-strip group.
 */
import { Group } from '@visx/group'
import { Bar, LinePath } from '@visx/shape'
import { CHART_FONT } from '@/components/ui/Chart'
import { noteGlyphs, OFF_GLYPH, OFF_ROW, STRIP_LABEL_X, STRIP_MARKER_X, type ChartLayout, type PanelBox } from '@/features/analysis/lib/charts/layout'
import type { ChartModel, ModelMark, ModelPoint } from '@/features/analysis/lib/charts/model'
import type { ChartTokens } from '@/features/analysis/lib/charts/theme'
import { BreakMark, MarkerShape, StripSwatch } from './chartMarks'

const gridY = (y: number) => Math.round(y) + 0.5

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

function PanelAxis({ box, layout, tokens }: { box: PanelBox; layout: ChartLayout; tokens: ChartTokens }) {
  const { axis, caption } = box.panel
  return (
    <g>
      {box.captionY != null && caption && <text x={0} y={box.captionY} fill={tokens.tick}>{caption}</text>}
      {axis.ticks.map((tick) => (
        <line key={tick} x1={layout.plotLeft} x2={layout.plotRight} y1={gridY(box.y(tick))} y2={gridY(box.y(tick))}
          stroke={tick === 0 ? tokens.zero : tokens.grid} strokeWidth={1} />
      ))}
      {axis.ticks.map((tick) => (
        <text key={tick} x={layout.gutter - 8} y={box.y(tick)} dy="0.32em" textAnchor="end" fill={tokens.tick}>{axis.format.tick(tick)}</text>
      ))}
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
        <text key={`${bar.seriesKey}:${bar.period}`} x={bar.x + bar.width / 2} y={bar.label.y} textAnchor="middle" fill={tokens.value}>{bar.label.text}</text>
      ))}
      {box.gaps.map((gap) => <text key={gap.period} x={gap.x} y={gap.y} textAnchor="middle" fill={tokens.tick}>{gap.text}</text>)}
      {box.nearZero.map((label) => <text key={label.period} x={label.x} y={label.y} textAnchor="middle" fill={tokens.value}>{label.text}</text>)}
    </g>
  )
}

/** A3b: the dashed rule on a clipped edge, then each off-scale value in its row: the arrow in its series' colour and
 *  the true value in the value ink (§3.4). */
function OffScale({ box, layout, tokens }: { box: PanelBox; layout: ChartLayout; tokens: ChartTokens }) {
  const [low, high] = box.panel.axis.domain
  return (
    <g>
      {([['above', box.offAbove, high, '↑'], ['below', box.offBelow, low, '↓']] as const).map(([side, band, edge, arrow]) => band && (
        <g key={side}>
          <line x1={layout.plotLeft} x2={layout.plotRight} y1={gridY(box.y(edge))} y2={gridY(box.y(edge))} stroke={tokens.tick} strokeWidth={1} strokeDasharray="2 2" />
          {band.items.map((item) => (
            <g key={`${item.seriesKey}:${item.period}`}>
              <text x={item.left} y={band.top + 10 + OFF_ROW * item.row} fill={tokens.series[item.color]} data-series={item.seriesKey} data-period={item.period}>{arrow}</text>
              <text x={item.left + OFF_GLYPH} y={band.top + 10 + OFF_ROW * item.row} fill={tokens.value}>{item.text}</text>
            </g>
          ))}
        </g>
      ))}
    </g>
  )
}

export default function TrendChartSvg({ model, layout, tokens, label, uid }: {
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
        <Group key={box.panel.id} data-panel={box.panel.id} data-axis-step={box.panel.axis.step} data-axis-domain={box.panel.axis.domain.join(',')}>
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
          <text key={period.key} x={layout.x(period.key)} y={layout.xTickY} textAnchor="middle" fill={tokens.tick}>
            {period.tick.map((line, i) => <tspan key={line} x={layout.x(period.key)} dy={i === 0 ? 0 : 12}>{line}</tspan>)}
          </text>
        ))}
      </g>
      {layout.stripTop != null && model.strip.map((row, i) => (
        <g key={row.label} data-strip={row.label}>
          <StripSwatch swatch={row.swatch} marker={row.marker} x={STRIP_MARKER_X} y={layout.stripRowY[i] - 4} color={tokens.series[row.color]} ring={tokens.surface} />
          <text x={STRIP_LABEL_X} y={layout.stripRowY[i]} fill={tokens.tick}>{row.short}</text>
          {model.periods.map((period) => (
            <text key={period.key} x={layout.x(period.key)} y={layout.stripRowY[i]} textAnchor="middle" fill={tokens.value}>{row.cells[period.key]}</text>
          ))}
        </g>
      ))}
      {/* The notes band is a visual index of the footnotes under the card, which carry the same letters. */}
      <g aria-hidden="true">
        {model.notesBand && <text x={0} y={layout.notesY} fill={tokens.tick}>Notes</text>}
        {noteGlyphs(model, layout).map((glyph) => (
          <text key={`${glyph.period}:${glyph.text}`} x={glyph.x} y={layout.notesY} textAnchor="middle" fill={glyph.tone === 'review' ? tokens.review : tokens.tick}>{glyph.text}</text>
        ))}
      </g>
    </svg>
  )
}
