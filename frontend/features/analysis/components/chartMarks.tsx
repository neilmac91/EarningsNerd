/**
 * The trend charts' mark glyphs, shared by the plot, its value strip and the card's HTML legend (spec §3.5, §4.1):
 * plain SVG with literal paint, so the PNG export serialises them as drawn.
 */
import type { LegendItem, Marker } from '@/features/analysis/lib/charts/model'
import type { ChartTokens } from '@/features/analysis/lib/charts/theme'

/** A line series' point: circle Ø6, square 6×6 or triangle 8×7, with a 1.5 px surface ring painted under its fill. A
 *  plotted point names its series and period on the shape itself (§3.5, D4); a swatch has no datum. */
export function MarkerShape({ kind, x, y, color, ring, datum }: {
  kind: Marker
  x: number
  y: number
  color: string
  ring: string
  datum?: { series: string; period: string }
}) {
  if (kind === 'square') {
    return <rect x={x - 3} y={y - 3} width={6} height={6} fill={color} stroke={ring} strokeWidth={1.5} paintOrder="stroke" data-series={datum?.series} data-period={datum?.period} />
  }
  if (kind === 'triangle') {
    return <path d={`M${x},${y - 4} L${x + 4},${y + 3} L${x - 4},${y + 3} Z`} fill={color} stroke={ring} strokeWidth={1.5} paintOrder="stroke" data-series={datum?.series} data-period={datum?.period} />
  }
  return <circle cx={x} cy={y} r={3} fill={color} stroke={ring} strokeWidth={1.5} paintOrder="stroke" data-series={datum?.series} data-period={datum?.period} />
}

/** A growth bar broken at the plot edge (§4.1): two 1.5 px surface strokes across it, from y + 2 up to y − 1 and from
 *  y + 5 up to y + 2, each 1 px past the bar on both sides. */
export function BreakMark({ cx, width, y, surface }: { cx: number; width: number; y: number; surface: string }) {
  return (
    <g stroke={surface} strokeWidth={1.5}>
      <line x1={cx - width / 2 - 1} x2={cx + width / 2 + 1} y1={y + 2} y2={y - 1} />
      <line x1={cx - width / 2 - 1} x2={cx + width / 2 + 1} y1={y + 5} y2={y + 2} />
    </g>
  )
}

/** A value-strip row's swatch centred at (x, y): its line's marker, or for equity's bars a 4×8 bar, upright so it
 *  never reads as cash's 6×6 square (the spec leaves its size open). */
export function StripSwatch({ swatch, marker, x, y, color, ring }: { swatch: 'bar' | 'line'; marker?: Marker; x: number; y: number; color: string; ring: string }) {
  if (swatch === 'bar') return <rect x={x - 2} y={y - 4} width={4} height={8} rx={1} fill={color} />
  return <MarkerShape kind={marker ?? 'circle'} x={x} y={y} color={color} ring={ring} />
}

/** A legend item's 16×10 swatch (§3.6), and a tooltip row's: its line with the marker centred, a 10×10 bar square, or
 *  for an absent series a neutral dashed line that claims no palette slot. */
export function LegendSwatch({ item, tokens }: { item: Pick<LegendItem, 'color' | 'swatch' | 'marker'> & { absent?: boolean }; tokens: ChartTokens }) {
  if (item.absent || item.color == null) {
    return (
      <svg width={16} height={10} aria-hidden="true" className="shrink-0">
        <line x1={0} x2={16} y1={5} y2={5} stroke={tokens.tick} strokeWidth={1.5} strokeDasharray="3 2" />
      </svg>
    )
  }
  const color = tokens.series[item.color]
  return (
    <svg width={16} height={10} aria-hidden="true" className="shrink-0">
      {item.swatch === 'bar'
        ? <rect x={3} y={0} width={10} height={10} rx={2} fill={color} />
        : (
          <g>
            <line x1={0} x2={16} y1={5} y2={5} stroke={color} strokeWidth={2} />
            <MarkerShape kind={item.marker ?? 'circle'} x={8} y={5} color={color} ring={tokens.surface} />
          </g>
        )}
    </svg>
  )
}
