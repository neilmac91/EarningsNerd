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
  for (let exponent = -12; exponent <= 20; exponent++) {
    for (const mantissa of [1, 2, 2.5, 5]) {
      const step = Number(`${mantissa}e${exponent}`) // parsed, so 1e-4 is exactly the double 0.0001
      const first = Math.floor(lo / step + 1e-9) * step
      const last = Math.ceil(hi / step - 1e-9) * step
      const intervals = Math.round((last - first) / step)
      if (intervals >= nmin && intervals <= nmax) {
        const ticks = Array.from({ length: intervals + 1 }, (_, i) => clean(first + i * step, step))
        return { domain: [ticks[0], ticks[intervals]], ticks, step }
      }
    }
  }
  // Reached only past the grid (1e-12 to 5e20 a step, far beyond any filer's figure in any currency); one
  // interval, with zero once.
  return { domain: [lo, hi], ticks: [...new Set([lo, 0, hi])], step: hi - lo }
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

/** `value.toFixed(digits)` rounded as the metrics table rounds, half away from zero on the decimal a value prints as
 *  (Intl's halfExpand), never on its binary double: $143.35M is 143.3499… as a double, which toFixed prints "143.3"
 *  where the table prints "143.4" (M15). Pinned to en-US, without grouping: `group` adds it. */
const FIXED = new Map<number, Intl.NumberFormat>()
export function fixed(value: number, digits: number): string {
  let format = FIXED.get(digits)
  if (!format) FIXED.set(digits, (format = new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: false })))
  return format.format(value)
}

/** |value| in its own unit at `significant` figures, at most `finest` decimals in a K, M, B or T unit and cents at the
 *  finest in dollars (F$): a mantissa that rounds to 1,000 steps up a unit, so 999,960 reads "1.00M", never "1000K". */
function ownUnit(value: number, significant: number, finest = 2): string {
  const abs = Math.abs(value)
  const at = (unit: MoneyUnit) => {
    const mantissa = abs / unit.div
    const magnitude = Math.floor(Math.log10(mantissa))
    const digits = Math.max(0, Math.min(unit.suffix ? finest : 2, significant - 1 - magnitude))
    const text = fixed(mantissa, digits)
    // Rounding up to the next power of ten can add a figure ("9.996" → "10.00"): one decimal fewer keeps the count.
    const shown = digits + Math.floor(Math.log10(Number(text))) + 1
    return digits > 0 && shown > significant ? fixed(mantissa, digits - 1) : text
  }
  let unit = moneyUnit(abs)
  if (Number(at(unit)) >= 1000 && unit.suffix !== 'T') unit = moneyUnit(abs * 1000)
  return `${at(unit)}${unit.suffix}`
}

/** A2's decimal count: the fewest decimals that print the step exactly. A2 names 0, 1 or 2; a finer step (a
 *  growth panel whose values all lie within ±0.1% steps by 0.025) takes the decimals it needs, so its ticks stay
 *  distinct and exact ("+0.025%", never "+0.03%" twice over). */
const decimalsOf = (value: number) => {
  for (let digits = 0; digits < 15; digits++) {
    if (Math.abs(Number(value.toFixed(digits)) - value) < 1e-9 * Math.max(1, Math.abs(value))) return digits
  }
  return 15
}

// en-US grouping on digits `fixed` has already rounded.
const group = (text: string) => {
  const [whole, fraction] = text.split('.')
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + (fraction ? `.${fraction}` : '')
}

/** The currency signs past ASCII that Geist Mono draws, read from its faces' cmaps: £ ¥ ¢ € ¤ in the latin face and
 *  ₪ ₱ ₴ ₹ ₽ in latin-ext. It has no ₩ or ₫ in any subset (E203). */
export const DATA_FACE_SIGNS = '£¥¢€¤₪₱₴₹₽'

/** The symbol an amount carries: the currency's own, a code-like symbol ("CHF") followed by a space, or
 *  nothing when the unit is no currency code. A symbol with a sign the data face does not draw prints the code
 *  instead ("KRW 120,000T"), so no plot paints a glyph in the fallback face (G2; E203). */
export function moneyPrefix(currency: string | null): string {
  const symbol = currencySymbol(currency)
  if (!symbol) return ''
  if ([...symbol].some((glyph) => glyph > '\u007f' && !DATA_FACE_SIGNS.includes(glyph))) return `${currency} `
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
  // 3 significant figures on the largest |value|: one decimal fewer when rounding carries it to the next power
  // of ten (999.7M on a $B axis reads "$1.00B", not "$1.000B").
  const magnitude = Math.floor(Math.log10(Math.max(maxAbs / unit.div, 1e-9)))
  const fit = Math.max(0, 2 - magnitude)
  const d0 = fit > 0 && Math.floor(Math.log10(Number(fixed(maxAbs / unit.div, fit)) || 1)) > magnitude ? fit - 1 : fit
  const format = (value: number, digits: number, printed: boolean) => {
    if (value === 0) return `${prefix}0`
    const sign = value < 0 ? MINUS : ''
    const scaled = Math.abs(value / unit.div)
    if (printed && scaled < Math.pow(10, 1 - digits)) return `${sign}${prefix}${ownUnit(value, 3)}`
    return `${sign}${prefix}${group(fixed(scaled, digits))}${unit.suffix}`
  }
  return {
    kind: 'money',
    unit,
    tick: (value) => format(value, tickDigits, false),
    value: (value, digits = d0) => format(value, digits, true),
    d0,
  }
}

/** A1 and A2 over the values given: an axis's domain, ticks and formats. The engine's own percent panels clip their
 *  outliers first (A3); a renderer that cannot print a clipped value at the plot edge (A3b) passes every value, so
 *  nothing is hidden. Today's Recharts charts do. */
export function valueAxis(values: number[], cap: number, kind: AxisFormat['kind'], currency: string | null = null): NiceAxis & { format: AxisFormat } {
  const axis = niceAxis(values, cap)
  return { ...axis, format: kind === 'money' ? moneyFormat(values, axis.step, axis.ticks, currency) : percentFormat(axis.step, kind === 'growth') }
}

/** Two significant figures in the value's own unit, for a near-zero bar's label (A13b): "−$3.6M",
 *  "$85M", "$997K". */
export function compactMoney(value: number, currency: string | null): string {
  const prefix = moneyPrefix(currency)
  if (value === 0) return `${prefix}0`
  return `${value < 0 ? MINUS : ''}${prefix}${ownUnit(value, 2)}`
}

/** A tooltip's amount (spec §3.1): 4 significant figures in its own unit ("$14.34B", "$1.234B", "−$987.6M"), cents at
 *  the finest in dollars, with A2's sign and zero rules. */
export function tooltipMoney(value: number, currency: string | null): string {
  const prefix = moneyPrefix(currency)
  if (value === 0) return `${prefix}0`
  return `${value < 0 ? MINUS : ''}${prefix}${ownUnit(value, 4, 3)}`
}

/** A2 for a percent axis: margins unsigned, growth signed ("+50%", "0%", "−50%"). */
export function percentFormat(step: number, signed: boolean): AxisFormat {
  const tickDigits = decimalsOf(step)
  const format = (value: number, digits: number) => {
    if (value === 0) return signed ? `0${digits ? `.${'0'.repeat(digits)}` : ''}%` : '0%'
    const abs = Math.abs(value)
    // 0 dp from 1,000% as printed: 999.96% reads "1,000%", never "1,000.0%".
    const shown = Number(fixed(abs, digits)) >= 1000 ? 0 : digits
    let text = group(fixed(abs, shown))
    if (Number(text.replace(/,/g, '')) === 0) text = fixed(abs, Math.max(1, shown))
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
