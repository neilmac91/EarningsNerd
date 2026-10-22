import type { Filing } from '@/features/filings/api/filings-api'
import { originalDocumentUrl } from '@/features/filings/lib/originalDocumentUrl'
import { formatCompanyName } from '@/lib/formatCompanyName'

export interface RedlineSource {
  filingId: number | null
  /** The company's name in its display casing (formatCompanyName), formatted here where the filing enters. */
  companyName: string
  ticker: string
  reportDate: string
  filingDate: string
  accession: string
  originalUrl: string | null
}

export interface RedlinePair {
  earlier: RedlineSource
  current: RedlineSource
  fictional: boolean
}

export function parseFilingId(value: string): number | null {
  if (!/^[1-9]\d*$/.test(value.trim())) return null
  const id = Number(value)
  return Number.isSafeInteger(id) ? id : null
}

function calendarDate(value: unknown): string | null {
  // Filing dates arrive as ISO datetimes from the ORM. Like filingPeriod/formatLocalDate,
  // retain their stated calendar day rather than shifting it into the browser's timezone.
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d{1,6})?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?)?$/.test(value)) return null
  const day = value.slice(0, 10)
  const date = new Date(`${day}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === day ? day : null
}

/** Validate the API boundary before any content request or cross-filing claim. */
export function validateFilingPair(earlier: Filing, current: Filing, earlierId: number, currentId: number): RedlinePair {
  if (earlierId === currentId || earlier.id !== earlierId || current.id !== currentId) {
    throw new Error('Choose two distinct filing IDs. The returned filings must match those IDs.')
  }
  if (![earlier, current].every((filing) =>
    filing.company && Number.isSafeInteger(filing.company.id) && filing.company.id > 0 &&
    typeof filing.company.name === 'string' && filing.company.name.trim() &&
    typeof filing.company.ticker === 'string' && filing.company.ticker.trim(),
  ) || earlier.company!.id !== current.company!.id) {
    throw new Error('Both filings must belong to the same identified company.')
  }
  if (earlier.filing_type !== '10-K' || current.filing_type !== '10-K') {
    throw new Error('This prototype compares two original 10-K filings. Amendments and other forms are not supported.')
  }
  if (![earlier, current].every((filing) => typeof filing.accession_number === 'string' &&
    /^\d{10}-\d{2}-\d{6}$/.test(filing.accession_number)) || earlier.accession_number === current.accession_number) {
    throw new Error('Each filing needs its own valid accession number.')
  }
  const earlierPeriod = calendarDate(earlier.report_date)
  const currentPeriod = calendarDate(current.report_date)
  const earlierFiled = calendarDate(earlier.filing_date)
  const currentFiled = calendarDate(current.filing_date)
  if (!earlierPeriod || !currentPeriod || !earlierFiled || !currentFiled ||
    earlierPeriod >= currentPeriod || earlierFiled >= currentFiled) {
    throw new Error('Choose an earlier and a later reporting period, with the earlier filing filed first.')
  }
  const source = (filing: Filing, reportDate: string, filingDate: string): RedlineSource => ({
    filingId: filing.id,
    companyName: formatCompanyName(filing.company!.name),
    ticker: filing.company!.ticker,
    reportDate,
    filingDate,
    accession: filing.accession_number,
    originalUrl: originalDocumentUrl(filing),
  })
  return { earlier: source(earlier, earlierPeriod, earlierFiled), current: source(current, currentPeriod, currentFiled), fictional: false }
}
