import { format } from 'date-fns'
import { ArrowSquareOutIcon } from '@/lib/icons'

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
  const edgarUrl = `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${cik}&type=10-K&dateb=&owner=include&count=40`
  return (
    <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
      Showing filings since {format(new Date(oldestFilingDate), 'MMM d, yyyy')}.{' '}
      <a
        href={edgarUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-brand-strong dark:text-brand-strong-dark hover:underline"
      >
        Full history on SEC EDGAR
        <ArrowSquareOutIcon className="h-3.5 w-3.5" />
      </a>
    </p>
  )
}
