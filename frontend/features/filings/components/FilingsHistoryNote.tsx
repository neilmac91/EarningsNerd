import { ArrowSquareOutIcon } from '@/lib/icons'
import { formatLocalDate } from '@/lib/format'
import { cx } from '@/components/ui'
import { edgarCompanyUrl } from '@/features/companies/lib/edgar'
import { IDENTITY_LINK } from '@/features/filings/components/FilingIdentity'

interface FilingsHistoryNoteProps {
  oldestFilingDate: string | null
  cik: string | undefined
}

// P0-5 (data-quality plan): the filings list holds only what has been ingested from SEC's
// recent-window feed — a mega-filer like JPM surfaces ~4 reports while EDGAR holds decades.
// State the earliest date shown and hand users the full history on EDGAR. Permanent by design:
// even after the history backfill (P1-6), the pre-2001 tail stays external.
export default function FilingsHistoryNote({ oldestFilingDate, cik }: FilingsHistoryNoteProps) {
  if (!oldestFilingDate || !cik) return null
  // formatLocalDate, not parseISO: `oldestFilingDate` is reduced from `filing.filing_date`, which
  // the API serialises as a full ISO datetime ('2001-03-31T00:00:00+00:00'). parseISO honours that
  // offset and yields a UTC-midnight INSTANT, so date-fns rendered the PREVIOUS day for every
  // viewer behind UTC — the exact bug the old comment claimed parseISO prevented, which only holds
  // for a date-only string. This note is also server-rendered (page.tsx seeds initialFilings), so
  // the mismatch showed up as a hydration error too.
  const filedSince = formatLocalDate(oldestFilingDate, 'MMM d, yyyy')
  if (!filedSince) return null
  // Every form, not only 10-Ks: the link promises the full history, and a 20-F filer has no 10-K list. It is
  // the company link the lead uses, so EDGAR's own defaults stand in for the old owner=include and count=40.
  const edgarUrl = edgarCompanyUrl(cik)
  return (
    <p className="text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
      Showing filings since {filedSince}.{' '}
      <a
        href={edgarUrl}
        target="_blank"
        rel="noopener noreferrer"
        className={cx(IDENTITY_LINK, 'inline-flex items-center gap-1')}
      >
        Full history on SEC.gov
        <ArrowSquareOutIcon aria-hidden="true" className="h-3.5 w-3.5" />
      </a>
    </p>
  )
}
