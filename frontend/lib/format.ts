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

  const formatter = getFormatter({
    style: 'currency',
    currency,
    notation: compact ? 'compact' : 'standard',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits > 0 ? Math.min(digits, 2) : 0,
  })
  return formatter.format(num)
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


