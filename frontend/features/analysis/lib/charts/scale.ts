/**
 * Scale, tick and number-format rules for the trend charts (docs/design/analysis-trend-charts-spec-2026-10.md
 * §3.1: A1, A1b, A2, A3, F$). Pure and data-only: ticks never depend on the view's size, so the card, the
 * expanded view and the PNG export print the same ticks. Every string uses U+2212 for minus and prints zero
 * as "$0" or "0%".
 */
import { currencySymbol } from '@/lib/format'

export const MINUS = '−'

export interface NiceAxis {
  domain: [number, number]
  ticks: number[]
  step: number
}

const clean = (value: number, step: number) => (Math.abs(value) < step * 1e-9 ? 0 : +value.toPrecision(12))

/** A1: zero-anchored; the smallest step m·10^e (m ∈ {1, 2, 2.5, 5}) giving nmin..nmax intervals, so
 *  the densest legal grid wins. The domain ends on ticks and the data max is never appended. */
function niceCore(values: number[], nmax: number, nmin: number): NiceAxis {
  const lo = Math.min(0, ...values)
  const hi = Math.max(0, ...values)
  // No value, or only zeros (a one-period window's growth): the zero rule alone, labelled "0%" or "$0".
  if (lo === hi) return { domain: [0, 1], ticks: [0], step: 1 }
  for (let exponent = -3; exponent <= 14; exponent++) {
    for (const mantissa of [1, 2, 2.5, 5]) {
      const step = mantissa * Math.pow(10, exponent)
      const first = Math.floor(lo / step + 1e-9) * step
      const last = Math.ceil(hi / step - 1e-9) * step
      const intervals = Math.round((last - first) / step)
      if (intervals >= nmin && intervals <= nmax) {
        const ticks = Array.from({ length: intervals + 1 }, (_, i) => clean(first + i * step, step))
        return { domain: [ticks[0], ticks[intervals]], ticks, step }
      }
    }
  }
  return { domain: [lo, hi], ticks: [lo, 0, hi], step: hi - lo }
}

/**
 * A1 with A1b: when every value on one side of zero lies within 5% of the chosen step (PLUG's equity of
 * −$3.6M against +$4.6B), that side gets 10% of a step of room and no tick, instead of a whole empty
 * interval. Ticks stay uniform and zero stays a tick.
 */
export function niceAxis(values: number[], nmax: number, nmin = 2): NiceAxis {
  const base = niceCore(values, nmax, nmin)
  for (const side of [-1, 1] as const) {
    const tiny = (value: number, step: number) => Math.sign(value) === side && Math.abs(value) <= 0.05 * step
    const onSide = values.filter((value) => Math.sign(value) === side)
    if (!onSide.length || !onSide.every((value) => tiny(value, base.step))) continue
    const rest = values.filter((value) => Math.sign(value) !== side)
    if (!rest.some((value) => Math.sign(value) === -side)) continue
    const axis = niceCore(rest, nmax, nmin)
    if (!onSide.every((value) => Math.abs(value) <= 0.05 * axis.step)) continue
    const room = clean(0.1 * axis.step, axis.step)
    return { ...axis, domain: side < 0 ? [-room, axis.domain[1]] : [axis.domain[0], room] }
  }
  return base
}

export interface MoneyUnit {
  div: number
  suffix: '' | 'K' | 'M' | 'B' | 'T'
}

export function moneyUnit(maxAbs: number): MoneyUnit {
  if (maxAbs >= 1e12) return { div: 1e12, suffix: 'T' }
  if (maxAbs >= 1e9) return { div: 1e9, suffix: 'B' }
  if (maxAbs >= 1e6) return { div: 1e6, suffix: 'M' }
  if (maxAbs >= 1e3) return { div: 1e3, suffix: 'K' }
  return { div: 1, suffix: '' }
}

const decimalsOf = (value: number) => {
  for (let digits = 0; digits <= 2; digits++) {
    if (Math.abs(Number(value.toFixed(digits)) - value) < 1e-9 * Math.max(1, Math.abs(value))) return digits
  }
  return 2
}

// en-US grouping without the locale-dependent formatters (earningsnerd/locale-pinned-numbers): the
// digits are already fixed by toFixed.
const group = (text: string) => {
  const [whole, fraction] = text.split('.')
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction ? `.${fraction}` : '')
}

/** The symbol an amount carries: the currency's own, a code-like symbol ("CHF") followed by a space, or
 *  nothing when the unit is no currency code. */
export function moneyPrefix(currency: string | null): string {
  const symbol = currencySymbol(currency)
  if (!symbol) return ''
  return /^[A-Z]{2,}$/.test(symbol) ? `${symbol} ` : symbol
}

export interface AxisFormat {
  kind: 'money' | 'percent' | 'growth'
  unit: MoneyUnit
  /** A tick label: one unit and one decimal count for the whole axis. */
  tick: (value: number) => string
  /** A printed value (bar label, legend, strip) at `digits` decimals in the axis unit. */
  value: (value: number, digits?: number) => string
  /** Decimals giving 3 significant figures on the largest |value| (A3's d0). */
  d0: number
}

/**
 * A2 for an amount axis. The unit comes from the largest |tick| as well as the data, so an axis that
 * overshoots to 1,000M reads "$1B", never "−$1,000M". A printed value with fewer than 2 significant
 * figures at the axis precision prints in its own unit to 3 (BYND's equity "−$997K", not "−$0.001B");
 * ticks never take that step, so one axis keeps one unit.
 */
export function moneyFormat(values: number[], step: number, ticks: number[], currency: string | null): AxisFormat {
  const prefix = moneyPrefix(currency)
  const maxAbs = Math.max(0, ...values.map(Math.abs))
  const unit = moneyUnit(Math.max(maxAbs, ...ticks.map(Math.abs)))
  const tickDigits = decimalsOf(step / unit.div)
  const d0 = Math.max(0, 2 - Math.floor(Math.log10(Math.max(maxAbs / unit.div, 1e-9))))
  const format = (value: number, digits: number, printed: boolean) => {
    if (value === 0) return `${prefix}0`
    const sign = value < 0 ? MINUS : ''
    const scaled = Math.abs(value / unit.div)
    if (printed && scaled < Math.pow(10, 1 - digits)) {
      const own = moneyUnit(Math.abs(value))
      const mantissa = Math.abs(value) / own.div
      return `${sign}${prefix}${mantissa.toFixed(Math.max(0, Math.min(2, 2 - Math.floor(Math.log10(mantissa)))))}${own.suffix}`
    }
    return `${sign}${prefix}${group(scaled.toFixed(digits))}${unit.suffix}`
  }
  return {
    kind: 'money',
    unit,
    tick: (value) => format(value, tickDigits, false),
    value: (value, digits = d0) => format(value, digits, true),
    d0,
  }
}

/** Two significant figures in the value's own unit, for a near-zero bar's label (A13b): "−$3.6M",
 *  "$85M", "$997K". */
export function compactMoney(value: number, currency: string | null): string {
  const prefix = moneyPrefix(currency)
  if (value === 0) return `${prefix}0`
  const own = moneyUnit(Math.abs(value))
  const mantissa = Math.abs(value) / own.div
  return `${value < 0 ? MINUS : ''}${prefix}${mantissa.toFixed(Math.max(0, 1 - Math.floor(Math.log10(mantissa))))}${own.suffix}`
}

/** A2 for a percent axis: margins unsigned, growth signed ("+50%", "0%", "−50%"). */
export function percentFormat(step: number, signed: boolean): AxisFormat {
  const tickDigits = decimalsOf(step)
  const format = (value: number, digits: number) => {
    if (value === 0) return signed ? `0${digits ? `.${'0'.repeat(digits)}` : ''}%` : '0%'
    const abs = Math.abs(value)
    const shown = abs >= 1000 ? 0 : digits
    let text = group(abs.toFixed(shown))
    if (Number(text.replace(/,/g, '')) === 0) text = abs.toFixed(Math.max(1, shown))
    return `${value < 0 ? MINUS : signed ? '+' : ''}${text}%`
  }
  return {
    kind: signed ? 'growth' : 'percent',
    unit: { div: 1, suffix: '' },
    tick: (value) => format(value, tickDigits).replace(/^0\.0+%$/, '0%'),
    value: (value, digits = 1) => format(value, digits),
    d0: 1,
  }
}

/**
 * A3, percent panels only: a value is an outlier when it exceeds 5× its own series' median |value|
 * (10 pp at least), and outliers are clipped only when they would own at least 2/3 of the axis. Every
 * clipped value is printed (layout.ts plans where). Amount panels never clip.
 */
export function outlierCut(series: number[][]): { clip: boolean; inRange: (value: number, seriesIndex: number) => boolean } {
  const median = (values: number[]) => {
    const sorted = values.map(Math.abs).sort((a, b) => a - b)
    if (!sorted.length) return 0
    const mid = sorted.length >> 1
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  }
  const thresholds = series.map((values) => 5 * Math.max(median(values), 10))
  const all = series.flat()
  const inRange = series.flatMap((values, i) => values.filter((value) => Math.abs(value) <= thresholds[i]))
  const extent = (values: number[]) => Math.max(0, ...values) - Math.min(0, ...values)
  const clip = inRange.length < all.length && extent(all) >= 3 * extent(inRange)
  return { clip, inRange: (value, i) => !clip || Math.abs(value) <= thresholds[i] }
}

export const linear = (domain: [number, number], range: [number, number]) => (value: number) =>
  range[0] + ((value - domain[0]) / (domain[1] - domain[0] || 1)) * (range[1] - range[0])
