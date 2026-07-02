'use client'

/* =============================================================================
   Chart — components/ui/Chart.tsx
   -----------------------------------------------------------------------------
   The charting layer: chrome sub-tokens + Recharts-style prop factories +
   a Tooltip content component + a self-contained Sparkline.

   ENCODED RULES (not advisory — the helpers make the wrong thing hard):
     1. Series color comes from CHART_SERIES positionally, 1→N, never skipped
        or re-sorted. seriesColor(i) is the only sanctioned lookup.
     2. gain/loss mark DIRECTION only — a sparkline stroke, delta bars around
        a zero line. They are never categorical series colors, so "green line"
        can only ever mean "went up". Use directionTone(), not raw hexes.
     3. The sage brand never appears inside a plot area. Nothing in this file
        imports or emits a brand value.
     4. ≥5 series: color stops carrying alone under red-green CVD — add direct
        labels, markers, or dash patterns (chart.5/6 converge for dichromats).

   All values mirror `chart.*` in tailwind.config.js. CVD-validated
   (deuteranopia/protanopia) and ≥3:1 vs both cream #F4F3EE and navy #0B1120.
============================================================================= */

import { type CSSProperties, type ReactNode } from 'react'
import { MOTION } from '../../lib/motion'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'

/** Categorical sequence — teal, honey, cornflower, coral, slate-blue, periwinkle. */
export const CHART_SERIES = [
  '#3E8E84', // 1 teal
  '#B8812F', // 2 honey
  '#5B7CC0', // 3 cornflower
  '#CF7159', // 4 coral
  '#6E7E9C', // 5 slate-blue
  '#8B7BC0', // 6 periwinkle
] as const

/** Positional series color — 0-indexed. Charts should never need more than 6. */
export function seriesColor(index: number): string {
  if (process.env.NODE_ENV !== 'production' && index >= CHART_SERIES.length) {
    console.warn(`seriesColor(${index}): >6 series — collapse categories or facet the chart.`)
  }
  return CHART_SERIES[index % CHART_SERIES.length]
}

/** Data face for every number a chart renders — mirrors fontFamily.data. */
export const CHART_FONT =
  '"Geist Mono", ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'

export interface ChartTheme {
  grid: string
  axis: string
  label: string
  crosshair: string
  ref: string
  tipBg: string
  tipBorder: string
  tipShadow: string
  /** Direction tones — GRAPHIC values (3:1 floor). Text labels use gainText/lossText. */
  gain: string
  loss: string
  flat: string
  gainText: string
  lossText: string
}

/** Chrome sub-tokens per theme. Mirrors chart.{grid,axis,label,crosshair,ref,tip}. */
export function chartTheme(dark: boolean): ChartTheme {
  return dark
    ? {
        grid: 'rgba(255,255,255,0.06)',
        axis: 'rgba(255,255,255,0.10)',
        label: '#9CA3AF', // text.secondary.dark — tertiary fails on navy
        crosshair: 'rgba(156,163,175,0.4)',
        ref: '#9CA3AF',
        tipBg: '#1F2937',
        tipBorder: 'rgba(255,255,255,0.10)',
        tipShadow: 'none', // dark cards/overlays separate by fill + hairline, never shadow
        gain: '#34D399',
        loss: '#FB7185',
        flat: '#9CA3AF',
        gainText: '#34D399',
        lossText: '#FB7185',
      }
    : {
        grid: 'rgba(229,231,235,0.6)',
        axis: '#E5E7EB',
        label: '#6B7280', // text.tertiary — 4.6:1 on the card charts sit on
        crosshair: 'rgba(107,114,128,0.45)',
        ref: '#6B7280',
        tipBg: '#FBFAF6',
        tipBorder: '#E5E7EB',
        tipShadow: '0 1px 3px 0 rgba(16,24,40,0.10), 0 1px 2px -1px rgba(16,24,40,0.10)', // e2
        gain: '#16A34A', // gain.light — graphic only (3:1); never text
        loss: '#DC2626', // loss.light — graphic only
        flat: '#6B7280',
        gainText: '#15803D', // gain.text — the AA text pair
        lossText: '#B91C1C', // loss.text
      }
}

export type Direction = 'gain' | 'loss' | 'flat'

/** Direction from a numeric delta (or first→last of a series). */
export function direction(delta: number): Direction {
  return delta > 0 ? 'gain' : delta < 0 ? 'loss' : 'flat'
}

/** GRAPHIC stroke/fill for a direction (sparkline stroke, delta bars). */
export function directionTone(dir: Direction, dark: boolean): string {
  const t = chartTheme(dark)
  return dir === 'gain' ? t.gain : dir === 'loss' ? t.loss : t.flat
}

/** TEXT color for a direction (delta labels next to a chart). */
export function directionTextTone(dir: Direction, dark: boolean): string {
  const t = chartTheme(dark)
  return dir === 'gain' ? t.gainText : dir === 'loss' ? t.lossText : t.flat
}

/* ---------------------------------------------------------------------------
   Recharts prop factories — spread into the composition:

     const reduced = usePrefersReducedMotion()  // the shared hook (hooks/)
     <CartesianGrid {...gridProps(dark)} />
     <XAxis dataKey="q" {...xAxisProps(dark)} />
     <YAxis {...yAxisProps(dark)} tickFormatter={fmtBillions} />
     <Tooltip cursor={crosshairProps(dark)} content={<ChartTooltip dark={dark} />} />
     <ReferenceLine {...zeroLineProps(dark)} />
     <Line dataKey="dataCenter" stroke={seriesColor(0)} {...lineProps(reduced)} />
--------------------------------------------------------------------------- */

export const gridProps = (dark: boolean) => ({
  stroke: chartTheme(dark).grid,
  vertical: false as const, // horizontal guides only — quarters don't need columns
})

const tick = (dark: boolean) => ({
  fill: chartTheme(dark).label,
  fontSize: 12, // 11 (data-xs) allowed for dense numeric annotations
  fontFamily: CHART_FONT,
})

export const xAxisProps = (dark: boolean) => ({
  axisLine: { stroke: chartTheme(dark).axis },
  tickLine: false as const,
  tick: tick(dark),
  tickMargin: 8,
})

export const yAxisProps = (dark: boolean) => ({
  axisLine: false as const, // the gridlines carry the y scale
  tickLine: false as const,
  tick: tick(dark),
  tickMargin: 8,
  width: 44,
})

/** Pass as Tooltip's `cursor` — the hover crosshair. */
export const crosshairProps = (dark: boolean) => ({
  stroke: chartTheme(dark).crosshair,
  strokeWidth: 1,
  strokeDasharray: '3 3',
})

/** Zero line for delta/surprise charts (solid). For other references use refLineProps. */
export const zeroLineProps = (dark: boolean) => ({
  y: 0,
  stroke: chartTheme(dark).ref,
  strokeWidth: 1,
  isFront: false as const,
})

/** Named reference (guidance, consensus) — dashed so it never reads as an axis. */
export const refLineProps = (dark: boolean) => ({
  stroke: chartTheme(dark).ref,
  strokeWidth: 1,
  strokeDasharray: '4 3',
})

/** Line props — pass the shared usePrefersReducedMotion() flag. Token-timed:
    MOTION.slow replaces Recharts' raw ~1500ms library default. */
export const lineProps = (reduced: boolean) => ({
  strokeWidth: 2,
  dot: false as const,
  activeDot: { r: 3.5, strokeWidth: 0 },
  isAnimationActive: !reduced,
  animationDuration: MOTION.slow,
})

/* ---------------------------------------------------------------------------
   ChartTooltip — Recharts custom `content`. Panel + hairline + e2 (light) /
   shadow none (dark); values in the data face with tabular numerals.
--------------------------------------------------------------------------- */

export interface ChartTooltipProps {
  dark?: boolean
  active?: boolean
  label?: ReactNode
  payload?: Array<{ name?: string; value?: number | string; color?: string }>
  /** Format a row value — defaults to String(). */
  formatValue?: (value: number | string | undefined) => string
}

export function ChartTooltip({ dark = false, active, label, payload, formatValue }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const t = chartTheme(dark)
  const fmt = formatValue ?? ((v: number | string | undefined) => String(v ?? ''))
  return (
    <div
      style={{
        background: t.tipBg,
        border: `1px solid ${t.tipBorder}`,
        boxShadow: t.tipShadow,
        borderRadius: 12,
        padding: '10px 12px',
        minWidth: 148,
      }}
    >
      <div
        style={{
          fontFamily: CHART_FONT,
          fontVariantNumeric: 'tabular-nums',
          fontSize: 11,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: t.label,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div style={{ display: 'grid', gap: 4 }}>
        {payload.map((row, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span
              aria-hidden="true"
              style={{ width: 8, height: 8, borderRadius: 2, background: row.color ?? seriesColor(i), flex: 'none' }}
            />
            <span style={{ fontSize: 12, color: dark ? '#9CA3AF' : '#374151', flex: 1 }}>{row.name}</span>
            <span
              style={{
                fontFamily: CHART_FONT,
                fontVariantNumeric: 'tabular-nums',
                fontSize: 12,
                fontWeight: 500,
                color: dark ? '#D7DADC' : '#1A1A17',
              }}
            >
              {fmt(row.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------------------
   Sparkline — self-contained SVG, no Recharts. Direction-toned: the stroke is
   gain/loss/flat GRAPHIC tone from the series' own first→last delta (or an
   explicit `dir`). Optional draw-in animation, disabled under reduced motion.
--------------------------------------------------------------------------- */

export interface SparklineProps {
  data: number[]
  dark?: boolean
  /** Override the auto first→last direction (e.g. "lower is better" metrics). */
  dir?: Direction
  width?: number
  height?: number
  strokeWidth?: number
  /** Soft area fill under the line (gain.soft / loss.soft tint). Default true. */
  fill?: boolean
  /** Draw-in on mount. Auto-disabled by prefers-reduced-motion. Default false. */
  animate?: boolean
  className?: string
  style?: CSSProperties
  /** Accessible summary, e.g. "Revenue, last 8 quarters, up 94%". */
  label?: string
}

export function Sparkline({
  data,
  dark = false,
  dir,
  width = 96,
  height = 28,
  strokeWidth = 1.5,
  fill = true,
  animate = false,
  className,
  style,
  label,
}: SparklineProps) {
  const reduced = usePrefersReducedMotion() // before the early return — hooks are unconditional
  if (data.length < 2) return null
  const d = dir ?? direction(data[data.length - 1] - data[0])
  const stroke = directionTone(d, dark)
  const pad = strokeWidth
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const pts = data.map((v, i) => [
    pad + (i / (data.length - 1)) * (width - pad * 2),
    pad + (1 - (v - min) / span) * (height - pad * 2),
  ])
  const line = pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' ')
  const area = `${line} ${(width - pad).toFixed(2)},${height} ${pad},${height}`
  // Generous overestimate of path length for the dash draw-in.
  const dash = width * 2 + height * 2

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={className}
      style={{ display: 'block', overflow: 'visible', ...style }}
    >
      {fill && <polygon points={area} fill={stroke} opacity={dark ? 0.14 : 0.1} />}
      <polyline
        points={line}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
        style={
          animate && !reduced
            ? {
                strokeDasharray: dash,
                strokeDashoffset: dash,
                // Keyframes live in globals.css (the shared layer), token-timed.
                animation: 'en-spark-draw var(--duration-slow) var(--ease-standard) forwards',
              }
            : undefined
        }
      />
    </svg>
  )
}
