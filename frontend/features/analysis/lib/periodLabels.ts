/** Presentation only: API keys, snapshot identity and period selection keep their original keys. */
export function formatAnalysisPeriod(period: string, style: 'long' | 'short' = 'long'): string {
  const quarter = /^(\d{4})Q([1-4])$/.exec(period)
  if (!quarter) return period
  const [, year, number] = quarter
  return `Q${number} ${style === 'short' ? `’${year.slice(-2)}` : year}`
}
