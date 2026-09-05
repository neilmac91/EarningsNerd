import Link from 'next/link'
import { Badge } from '@/components/ui'
import type { Filing } from '@/features/filings/api/filings-api'

/** Preserve access to the original; resolve a replacement only from filings already loaded. */
export default function SupersededFilingNotice({
  filing,
  filings = [],
}: {
  filing: Filing
  filings?: Filing[]
}) {
  if (!filing.superseded_by_accession) return null
  const replacement = filings.find((candidate) =>
    candidate.id !== filing.id && candidate.accession_number === filing.superseded_by_accession,
  )
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Badge variant="warning" title="A later amendment supersedes this filing. The original remains available.">
        Superseded
      </Badge>
      {replacement && (
        <Link
          href={`/filing/${replacement.id}`}
          className="text-sm font-medium text-brand-strong underline underline-offset-2 dark:text-brand-strong-dark"
        >
          View amendment
        </Link>
      )}
    </span>
  )
}
