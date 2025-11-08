export const nonEmpty = (s?: string) => !!s && s.replace(/[ #*_>\-\s]/g, '').length > 0

export const showSection = (markdown?: string) => (nonEmpty(markdown) ? markdown : null)

export const fmtUSD = (n?: number) =>
  typeof n === 'number'
    ? new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        notation: n >= 1e9 ? 'compact' : 'standard',
        maximumFractionDigits: 1,
      }).format(n)
    : ''

export const fmtPct = (n?: number) => (typeof n === 'number' ? `${(n * 100).toFixed(1)}%` : '')

export const fmtEPS = (n?: number) => (typeof n === 'number' ? n.toFixed(2) : '')
