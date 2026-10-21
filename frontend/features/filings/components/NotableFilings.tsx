import NotableFilingCard from '@/features/filings/components/NotableFilingCard'
import FormCodeText from '@/features/marketing/components/FormCodeText'
import LandingRow from '@/features/marketing/components/LandingRow'
import type { NotableFilingsResponse } from '@/lib/serverApi'

/**
 * The label column's one line: what the feed is under D-046 (F3), in the terms of the backend's query
 * (backend/app/services/notable_filings_service.py, `_fetch`): the past week's window, the two forms it serves,
 * companies that hold a summary the filing page shows, and its order. It says nothing the query does not do, so no
 * "high-signal" and no "across the whole market" (docs/brand/00-audit.md, T7).
 */
const LINE = 'The past week’s 10-K and 10-Q filings from companies with a summary to read, newest first.'

/**
 * Notable filings, a ruled row of the landing page (D-045) after Reporting this week. The backend serves D-046's
 * curation rule from its own query (E90): 10-K and 10-Q filings only, from companies that hold a summary the filing
 * page shows, newest first, one per company, at most six. This renders the cards it is served, in the order it
 * serves them, each opening its company page (NotableFilingCard), two across from 40rem at the reader's text size
 * as Reporting this week's lines are, never four (earningsnerd/no-four-up-grid). Each form code in the line is one
 * unbroken run (FormCodeText).
 *
 * Renders nothing at all when there is nothing to show: the backend answers an empty list while its flag is off, in
 * a week with fewer than three such companies, and on its own failure, and a failed read is null. The row then takes
 * no number among the rows, and the close follows the row before it.
 */
export default function NotableFilings({
  data,
}: {
  data: NotableFilingsResponse | null
}) {
  const filings = data?.filings ?? []
  if (filings.length === 0) return null

  return (
    <LandingRow id="notable-filings" title="Notable filings" line={<FormCodeText text={LINE} />} impression="notable_filings">
      <ul className="grid grid-cols-1 gap-4 [@media(min-width:40rem)]:grid-cols-2">
        {filings.map((filing) => (
          <li key={`${filing.ticker}-${filing.filed_date}`}>
            <NotableFilingCard filing={filing} asOf={data?.timestamp ?? ''} />
          </li>
        ))}
      </ul>
    </LandingRow>
  )
}
