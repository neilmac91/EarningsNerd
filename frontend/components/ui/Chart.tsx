'use client'

/* =============================================================================
   Chart — components/ui/Chart.tsx
   -----------------------------------------------------------------------------
   The charting layer: chrome sub-tokens + Recharts prop factories + a
   Tooltip content component.

   RULES (seriesColor and the chrome tokens encode 1 and 3; 2 and 4 are the charts' to keep):
     1. Series color comes from CHART_SERIES positionally, 1→N, never skipped
        or re-sorted. seriesColor(i) is the only sanctioned lookup.
     2. gain/loss mark DIRECTION only. They are never categorical series
        colors, so "green line" can only ever mean "went up". Direction
        VOCABULARY is the app's ('up' | 'down' | 'flat', owned by
        lib/financialTone.ts) — derive it with the app's directionOf().
     3. The sage brand never appears inside a plot area. Nothing in this file
        imports or emits a brand value.
     4. ≥5 series: color stops carrying alone under red-green CVD — add direct
        labels, markers, or dash patterns (chart.5/6 converge for dichromats).

   All values mirror `chart.*` in tailwind.config.js. CVD-validated
   (deuteranopia/protanopia) and ≥3:1 vs both cream #F4F3EE and navy #0B1120.
============================================================================= */

import { type ReactNode } from 'react'

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
    console.warn(`seriesColor(${index}): >6 series; collapse categories or facet the chart.`)
  }
  // Safe modulo — a negative index (reversed loops, delta math) must never
  // return undefined and silently break every stroke in the chart.
  const n = CHART_SERIES.length
  return CHART_SERIES[((index % n) + n) % n]
}

/** Data face for every number a chart renders — mirrors fontFamily.data.
    Leads with var(--font-geist-mono): next/font self-hosts under a HASHED
    family name, so the literal "Geist Mono" never resolves in production —
    without the var, chart text silently falls back to platform mono. */
export const CHART_FONT =
  'var(--font-geist-mono), "Geist Mono", ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'

export interface ChartTheme {
  grid: string
  axis: string
  label: string
  crosshair: string
  /** Bar-hover FILL wash (Tooltip cursor on bar charts) — chart.1 teal @ 8% / 16%. */
  cursorFill: string
  ref: string
  tipBg: string
  tipBorder: string
  tipShadow: string
  /** The tooltip's series names (text.secondary) and values (text.primary). */
  nameInk: string
  valueInk: string
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
        label: '#9CA3AF', // text.tertiary.dark, chart chrome's de-emphasised ink (the light label is the flat ink)
        crosshair: 'rgba(156,163,175,0.4)',
        cursorFill: 'rgba(62,142,132,0.16)',
        ref: '#9CA3AF',
        tipBg: '#1F2937',
        tipBorder: 'rgba(255,255,255,0.10)',
        tipShadow: 'none', // dark cards/overlays separate by fill + hairline, never shadow
        nameInk: '#D1D5DB', // text.secondary.dark
        valueInk: '#EAECEF', // text.primary.dark
        gain: '#34D399',
        loss: '#FB7185',
        flat: '#9CA3AF',
        gainText: '#34D399',
        lossText: '#FB7185',
      }
    : {
        grid: 'rgba(229,231,235,0.6)',
        axis: '#E5E7EB',
        label: '#6B7280', // the flat ink (text.tertiary was this value until #636A77) — 4.6:1 on the card charts sit on
        crosshair: 'rgba(107,114,128,0.45)',
        cursorFill: 'rgba(62,142,132,0.08)',
        ref: '#6B7280',
        tipBg: '#FBFAF6',
        tipBorder: '#E5E7EB',
        tipShadow: '0 1px 3px 0 rgba(16,24,40,0.10), 0 1px 2px -1px rgba(16,24,40,0.10)', // e2
        nameInk: '#374151', // text.secondary.light
        valueInk: '#1A1A17', // text.primary.light
        gain: '#16A34A', // gain.light — graphic only (3:1); never text
        loss: '#DC2626', // loss.light — graphic only
        flat: '#6B7280',
        gainText: '#15803D', // gain.text — the AA text pair
        lossText: '#B91C1C', // loss.text
      }
}

/* ---------------------------------------------------------------------------
   Recharts prop factories — spread into the composition:

     <CartesianGrid {...gridProps(dark)} />
     <XAxis dataKey="year" {...xAxisProps(dark)} />
     <YAxis {...yAxisProps(dark)} tickFormatter={fmtBillions} />
     <Tooltip cursor={barCursorProps(dark)} content={<ChartTooltip dark={dark} />} />
     <Bar dataKey="value" fill={seriesColor(0)} />
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
  // width 44 is a DEFAULT — currency/ticker labels routinely need more; spread
  // first, then override: <YAxis {...yAxisProps(dark)} width={56} />
  width: 44,
})

/** Pass as Tooltip's `cursor` on BAR charts — the category-band fill wash
    (chart.1 teal @ 8% light / 16% dark; the wash is a highlight, not a
    series). Replaces the two hand-rolled rgba(62,142,132,…) app charts (v2.2). */
export const barCursorProps = (dark: boolean) => ({
  fill: chartTheme(dark).cursorFill,
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
  /** Format a row value — defaults to String(). The row's series `name` is passed as the
   *  second argument so mixed-scale panels (money bars + a % growth line) can route by series
   *  instead of guessing from the value's magnitude. */
  formatValue?: (value: number | string | undefined, name?: string) => string
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
            <span style={{ fontSize: 12, color: t.nameInk, flex: 1 }}>{row.name}</span>
            <span
              style={{
                fontFamily: CHART_FONT,
                fontVariantNumeric: 'tabular-nums',
                fontSize: 12,
                fontWeight: 500,
                color: t.valueInk,
              }}
            >
              {fmt(row.value, row.name)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
