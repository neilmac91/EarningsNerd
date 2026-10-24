/** A period key as the API writes it ("FY2025", "2026Q2"), the export's `_PERIOD_KEY`; a window key joins two
 *  ("FY2016..FY2025"). */
export const ANALYSIS_PERIOD_KEY = String.raw`(?:FY)?\d{4}(?:Q[1-4])?`
const WINDOW = new RegExp(String.raw`^(${ANALYSIS_PERIOD_KEY})\.\.(${ANALYSIS_PERIOD_KEY})$`)
const WINDOW_KEY = new RegExp(String.raw`\b(${ANALYSIS_PERIOD_KEY})\.\.(${ANALYSIS_PERIOD_KEY})\b`, 'g')
const QUARTER_KEY = /\b\d{4}Q[1-4]\b/g

/** Presentation only: API keys, snapshot identity and period selection keep their original keys. A window key
 *  ("FY2016..FY2025", a CAGR's basis window) reads as its range (formatAnalysisWindow). */
export function formatAnalysisPeriod(period: string, style: 'long' | 'short' = 'long'): string {
  const window = WINDOW.exec(period)
  if (window) return formatAnalysisWindow(window[1], window[2], style)
  const quarter = /^(\d{4})Q([1-4])$/.exec(period)
  if (!quarter) return period
  const [, year, number] = quarter
  return `Q${number} ${style === 'short' ? `’${year.slice(-2)}` : year}`
}

/** The one way the analysis page prints a period window: its two ends joined by an unspaced en-dash, the voice
 *  guide's range form ("FY2016–FY2025", "Q1 2024–Q4 2025"), as the exports print it (`period_label` in
 *  backend/app/services/analysis_export_metadata.py). tests/unit/analysisPeriodWindows.spec.tsx holds it. */
export function formatAnalysisWindow(start: string, end: string, style: 'long' | 'short' = 'long'): string {
  return `${formatAnalysisPeriod(start, style)}–${formatAnalysisPeriod(end, style)}`
}

/** Every period key in a run of prose in its display form, windows first and then quarters, as the PDF's
 *  `period_label` reads its narrative. The caller hands it text nodes, never link destinations or code. */
export function formatAnalysisPeriods(text: string): string {
  return text
    .replace(WINDOW_KEY, (_key, start: string, end: string) => formatAnalysisWindow(start, end))
    .replace(QUARTER_KEY, (period) => formatAnalysisPeriod(period))
}
