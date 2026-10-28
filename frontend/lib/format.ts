import { format, parseISO } from 'date-fns'

type NumericInput = number | string | null | undefined

const MISSING_TOKENS = new Set([
  '',
  'n/a',
  'na',
  'nan',
  'undefined',
  'not available',
  'not disclosed',
  'none',
  '--',
  '—',
  'null',
])

const SCALE_THRESHOLDS: Array<{ value: number; suffix: string }> = [
  { value: 1e12, suffix: 'T' },
  { value: 1e9, suffix: 'B' },
  { value: 1e6, suffix: 'M' },
  { value: 1e3, suffix: 'K' },
]

const formatterCache = new Map<string, Intl.NumberFormat>()

const getFormatter = (options: Intl.NumberFormatOptions): Intl.NumberFormat => {
  const key = JSON.stringify(options)
  if (!formatterCache.has(key)) {
    formatterCache.set(key, new Intl.NumberFormat('en-US', options))
  }
  return formatterCache.get(key)!
}

/**
 * Parse a numeric string (e.g. "$1.2B", "3.4%", "(5,000)") into a number.
 */
export const parseNumeric = (value: NumericInput): number | null => {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }

  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }

  const lowered = trimmed.toLowerCase()
  if (MISSING_TOKENS.has(lowered)) {
    return null
  }

  let negative = false
  if (trimmed.startsWith('(') && trimmed.endsWith(')')) {
    negative = true
  }

  let cleaned = trimmed.replace(/[(),]/g, '')
  cleaned = cleaned.replace(/[$]/g, '')

  let multiplier = 1
  const suffixMatch = cleaned.match(/([a-zA-Z]+)$/)
  if (suffixMatch) {
    const suffix = suffixMatch[1].toLowerCase()
    if (suffix === 'k') multiplier = 1e3
    if (suffix === 'm') multiplier = 1e6
    if (suffix === 'b') multiplier = 1e9
    if (suffix === 't') multiplier = 1e12
    cleaned = cleaned.slice(0, -suffix.length)
  }

  cleaned = cleaned.replace(/%$/, '')

  const numeric = Number.parseFloat(cleaned)
  if (!Number.isFinite(numeric)) {
    return null
  }

  const result = (negative ? -numeric : numeric) * multiplier
  return Number.isFinite(result) ? result : null
}

export const fmtScale = (value: NumericInput, options?: { digits?: number }): string => {
  const num = parseNumeric(value)
  if (num === null) {
    return ''
  }

  const digits = options?.digits ?? 1
  const abs = Math.abs(num)

  for (const threshold of SCALE_THRESHOLDS) {
    if (abs >= threshold.value) {
      const scaled = num / threshold.value
      const formatter = getFormatter({
        minimumFractionDigits: Math.min(digits, 2),
        maximumFractionDigits: digits,
      })
      return `${formatter.format(scaled)}${threshold.suffix}`
    }
  }

  const formatter = getFormatter({
    minimumFractionDigits: 0,
    maximumFractionDigits: Math.min(digits, 2),
  })
  return formatter.format(num)
}

/**
 * A share count, scaled ("1.2M"). A count is a magnitude, so the sign is dropped by default; a net
 * figure passes `signed`, which keeps its direction as "+" or "−" (U+2212), never colour alone.
 */
export const fmtShares = (value: NumericInput, options?: { digits?: number; signed?: boolean }): string => {
  const num = parseNumeric(value)
  if (num === null) {
    return ''
  }
  const magnitude = fmtScale(Math.abs(num), { digits: options?.digits ?? 1 })
  if (!options?.signed || num === 0) {
    return magnitude
  }
  return `${num > 0 ? '+' : '\u2212'}${magnitude}`
}

/** An English ordinal: 1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st, 22nd, 23rd, 101st, 111th. */
export const ordinal = (n: number): string => {
  const whole = Math.trunc(n)
  const lastTwo = Math.abs(whole) % 100
  const last = Math.abs(whole) % 10
  const suffix = lastTwo >= 11 && lastTwo <= 13 ? 'th' : last === 1 ? 'st' : last === 2 ? 'nd' : last === 3 ? 'rd' : 'th'
  return `${whole}${suffix}`
}

/**
 * A stored Title Case data label in sentence case, for a control's face (the company page's metric
 * pickers), segment by segment, a segment being a run between whitespace, '-' and '/'. A segment with no
 * lower-case letter is an acronym and stays as written: '&' and '.' sit inside a segment, so 'R&D',
 * 'SG&A' and 'U.S.' stay whole, and an acronym joined to a word by '-' or '/' keeps its capitals
 * ('Non-GAAP EPS' and 'Debt-to-EBITDA' stay, 'Price/EPS Ratio' to 'Price/EPS ratio'). A segment with a
 * capital after its first letter stays as written too ('YoY Growth' to 'YoY growth'). Every other
 * segment goes lower case except the label's first character, which stays as written ('Net Income' to
 * 'Net income', 'Non-Interest Income' to 'Non-interest income', 'Adjusted Non-GAAP Income' to
 * 'Adjusted non-GAAP income'). The stored labels themselves are E34's.
 */
export const sentenceCase = (label: string): string => {
  const first = label.search(/[^\s/-]/)
  return label.replace(/[^\s/-]+/g, (segment: string, offset: number) => {
    if (!/[a-z]/.test(segment) || /[A-Za-z].*[A-Z]/.test(segment)) return segment
    const lower = segment.toLowerCase()
    return offset === first ? segment.charAt(0) + lower.slice(1) : lower
  })
}

/**
 * The glyphs past ASCII that the data face, Geist Mono, draws at its one 0.6em advance: the no-break space Intl puts
 * after a currency code, ¢ £ ¤ ¥ € in its latin file and ₪ ₱ ₴ ₹ ₽ in latin-ext, as a production build serves them. No
 * file draws ₩ or ₫, though latin-ext's range claims both (chief design read the six files on #1652). next/font fetches
 * the faces at build, so tests/e2e/analysis-layout.spec.ts measures each glyph in the built face: a font that drops one
 * fails there. The trend charts' prefix (moneyPrefix), fmtCurrency and the KPI strip's width all read this one list.
 */
export const DATA_FACE_GLYPHS = '\u00a0¢£¤¥€₪₱₴₹₽'
/** The glyphs a currency's en-US sign holds that Geist Mono lacks: KRW's ₩, VND's ₫ and the narrow no-break space in
 *  XOF's "F CFA". The e2e's control: none of them measures at the face's advance. */
export const DATA_FACE_MISSING = '\u202f₩₫'
/** Whether the data face draws a glyph: printable ASCII or one of DATA_FACE_GLYPHS. */
export const dataFaceDraws = (glyph: string): boolean => (glyph >= ' ' && glyph <= '~') || DATA_FACE_GLYPHS.includes(glyph)

export const fmtCurrency = (
  value: NumericInput,
  options?: { currency?: string; digits?: number; compact?: boolean }
): string => {
  const num = parseNumeric(value)
  if (num === null) {
    return ''
  }

  const currency = options?.currency ?? 'USD'
  const digits = options?.digits ?? (Math.abs(num) < 1 ? 2 : 1)
  const compact = options?.compact ?? Math.abs(num) >= 1000
  // A sign the data face lacks would paint in the fallback face, so its currency prints by code, as the trend
  // charts' moneyPrefix does (E203): "KRW 300.9T", not "₩300.9T".
  const symbol = currencySymbol(currency)

  const formatter = getFormatter({
    style: 'currency',
    currency,
    currencyDisplay: symbol && ![...symbol].every(dataFaceDraws) ? 'code' : 'symbol',
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits > 0 ? Math.min(digits, 2) : 0,
  })
  return formatter.format(num)
}

const COMPACT_SCALE: Record<string, number> = { K: 1e3, M: 1e6, B: 1e9, T: 1e12 }

/**
 * The frames of a count-up toward `final`, held in the unit `final` prints in ("CHF 0.0B" … "CHF 22.8B"), so no
 * frame is wider than the value it ends on, as hooks/useCountUp asks of its format. Compact notation on every frame
 * changes unit on the way ("CHF 999.9M" before "CHF 22.8B"), a glyph wider than the final value the KPI strip sizes
 * its cards for. The last frame is fmtCurrency(final, { compact: true }) exactly. The guarantee covers a count from
 * zero, which is why KpiStrip keys each tile by its value: a tween from a larger value would pass wider frames.
 */
export const compactCurrencyCountUp = (final: number, currency = 'USD'): ((value: number) => string) => {
  const last = fmtCurrency(final, { compact: true, currency })
  const digits = Math.abs(final) < 1 ? 2 : 1
  const unit = getFormatter({
    style: 'currency', currency, notation: 'compact', maximumFractionDigits: digits, minimumFractionDigits: digits,
  }).formatToParts(final).find((part) => part.type === 'compact')?.value ?? ''
  const scale = COMPACT_SCALE[unit] ?? 1
  return (value) => value === final ? last : `${fmtCurrency(value / scale, { currency, digits, compact: false })}${unit}`
}

// The engine's ISO 4217 list, where it has one (ES2022), so a well-formed code no currency has ("ABC") prints no
// symbol; without it, a code Intl knows nothing of prints as itself.
const ISO_CURRENCIES = (() => {
  const supported = (Intl as { supportedValuesOf?: (key: 'currency') => string[] }).supportedValuesOf
  return typeof supported === 'function' ? new Set(supported('currency')) : null
})()

/**
 * The en-US symbol of an ISO 4217 currency code: "$" for USD, "¥" for JPY, "CA$" for CAD, "CHF" for
 * a currency the locale writes by its code. Anything that is not such a code (an XBRL unit such as
 * "shares", a missing unit, "XXX" for no currency) gives null: that amount shows with no symbol, never
 * as dollars (lessons/frontend-xbrl-amounts-carry-their-own-currency.md).
 */
export const currencySymbol = (code: string | null | undefined): string | null => {
  if (!code || !/^[A-Z]{3}$/.test(code) || (ISO_CURRENCIES && !ISO_CURRENCIES.has(code))) return null
  try {
    const parts = getFormatter({ style: 'currency', currency: code, currencyDisplay: 'symbol' }).formatToParts(0)
    const symbol = parts.find((part) => part.type === 'currency')?.value ?? null
    return symbol === '¤' ? null : symbol // the generic sign: no currency to name
  } catch {
    return null
  }
}

export const fmtPercent = (
  value: NumericInput,
  options?: { digits?: number; signed?: boolean }
): string => {
  const num = parseNumeric(value)
  if (num === null) {
    return ''
  }

  const digits = options?.digits ?? 1
  const formatter = getFormatter({
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
  const formatted = formatter.format(num)

  if (options?.signed) {
    if (num > 0) {
      return `+${formatted}%`
    }
    if (num < 0) {
      return `${formatted}%`
    }
    return `${formatted}%`
  }

  return `${formatted}%`
}

/**
 * Percentage-POINT delta (e.g. a margin's YoY move) — the value is already in point units
 * (47.3 → 38.3 is "-9.0"), never multiplied by 100 the way a relative-growth fraction is.
 */
export const fmtPercentPoints = (value: NumericInput, options?: { digits?: number }): string => {
  const num = parseNumeric(value)
  if (num === null) {
    return ''
  }
  const digits = options?.digits ?? 1
  const formatter = getFormatter({ minimumFractionDigits: digits, maximumFractionDigits: digits })
  const formatted = formatter.format(num)
  return num > 0 ? `+${formatted}pp` : `${formatted}pp`
}

/**
 * A count with en-US grouping ("12,480"). Every figure in the product reads in one locale whatever the
 * viewer's browser says, so a bare `toLocaleString()` is banned outside this file
 * (earningsnerd/locale-pinned-numbers in eslint.designRules.mjs).
 */
export const fmtCount = (value: number): string => getFormatter({ maximumFractionDigits: 0 }).format(value)

/** A plain decimal with en-US grouping: at least `minDigits` and at most `maxDigits` fraction digits. */
export const fmtDecimal = (value: number, options: { minDigits?: number; maxDigits: number }): string =>
  getFormatter({ minimumFractionDigits: options.minDigits ?? 0, maximumFractionDigits: options.maxDigits }).format(value)

/**
 * Sanitize a string for safe use in download filenames.
 * Removes or replaces characters that could cause XSS or path traversal issues.
 *
 * @param name - The string to sanitize
 * @param fallback - Fallback value if result is empty (default: 'file')
 * @returns Sanitized filename component
 */
export const sanitizeFilename = (name: string | null | undefined, fallback = 'file'): string => {
  if (!name) {
    return fallback
  }

  // Remove path traversal sequences and dangerous characters
  // Keep only alphanumeric, hyphen, underscore, and period
  const sanitized = name
    .replace(/\.\./g, '') // Remove path traversal
    .replace(/[<>:"/\\|?*\x00-\x1f]/g, '') // Remove illegal filename chars
    .replace(/[^a-zA-Z0-9._-]/g, '_') // Replace other special chars with underscore
    .replace(/_+/g, '_') // Collapse multiple underscores
    .replace(/^[._]+|[._]+$/g, '') // Trim leading/trailing dots and underscores
    .slice(0, 100) // Limit length to prevent issues

  return sanitized || fallback
}



/**
 * Format a date string for display in the user's LOCAL calendar, without the UTC-shift bug.
 *
 * `new Date('2026-03-31')` parses as UTC midnight, so `date-fns` then renders the prior day for
 * users west of UTC. We take the date part (handles both 'YYYY-MM-DD' and full ISO datetimes like
 * '2026-03-31T00:00:00+00:00') and build a LOCAL date, so the calendar day is always shown as-is.
 */
export const formatLocalDate = (
  value: string | null | undefined,
  pattern: string,
  fallback = '',
): string => {
  if (!value) return fallback
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  if (!year || !month || !day) return fallback
  const date = new Date(year, month - 1, day)
  // Round-trip, because the Date constructor silently rolls over: (2025, 12, 1) is Jan 2026 and a
  // two-digit year maps into 1900+y, so '2025-13-01' and '0025-08-05' would otherwise render a
  // fabricated day rather than the fallback. Three call sites migrated onto this helper had their
  // own isValid/isNaN guard before, so the shared one has to be at least as strict.
  if (
    Number.isNaN(date.getTime()) ||
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return fallback
  }
  return format(date, pattern)
}

/**
 * Format an INSTANT (a full ISO timestamp with its offset, such as Stripe's `trial_end` or
 * `current_period_end`) as the day it falls on in the viewer's own time zone: the counterpart of
 * formatLocalDate, which keeps a calendar-day value's own day. 2026-10-21T01:05:33Z falls on Oct 20 in
 * New York, so a trial that ends then ends on Oct 20 for a reader there. parseISO rejects a rolled-over
 * day or month, so an unreadable value renders the fallback, as formatLocalDate's does.
 */
export const formatInstant = (
  value: string | null | undefined,
  pattern: string,
  fallback = '',
): string => {
  if (!value) return fallback
  // Bound first: format(parseISO(x)) is the shape the date lint flags, and this helper is the path
  // that lint's message gives a genuine timestamp.
  const instant = parseISO(value)
  return Number.isNaN(instant.getTime()) ? fallback : format(instant, pattern)
}
