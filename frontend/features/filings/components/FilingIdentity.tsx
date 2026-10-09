import Link from 'next/link'
import type { ReactNode } from 'react'
import { ArrowSquareOutIcon } from '@/lib/icons'
import { cx } from '@/components/ui'
import type { Filing } from '@/features/filings/api/filings-api'
import { periodLabel } from '@/features/filings/lib/filingPeriod'
import { originalDocumentUrl } from '@/features/filings/lib/originalDocumentUrl'
import SupersededFilingNotice from '@/features/filings/components/SupersededFilingNotice'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { formatLocalDate } from '@/lib/format'

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const FOCUS = 'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
// The quiet source link: sage ink, a brand-hairline underline that darkens on hover.
const LINK = cx(
  'rounded-sm text-brand-strong underline decoration-brand-border underline-offset-4 transition-colors duration-fast',
  'hover:decoration-current dark:text-brand-strong-dark dark:decoration-brand-border-dark',
  FOCUS,
)
// A crumb: sage ink, underlined on hover only.
const CRUMB = cx('rounded-sm text-brand-strong hover:underline hover:underline-offset-4 dark:text-brand-strong-dark', FOCUS)

/** A middot between data-face facts. Assistive tech hears a comma instead: the middot is visual
 *  only, and without a separator the facts would run together. */
const Sep = () => (
  <>
    <span aria-hidden="true" className={MUTED}>
      ·
    </span>
    <span className="sr-only">,</span>
  </>
)

/** "fiscal year ended Sep 24, 2022": the period of report as a phrase inside the identity line. */
function periodPhrase(filing: Pick<Filing, 'filing_type' | 'report_date'>): string | null {
  const label = periodLabel(filing)
  return label ? label.charAt(0).toLowerCase() + label.slice(1) : null
}

/** "10-K · fiscal year ended Sep 24, 2022": the current page's crumb. */
export function filingCrumb(filing: Pick<Filing, 'filing_type' | 'report_date' | 'filing_date'>): string {
  const ended = formatLocalDate(filing.report_date, 'MMM d, yyyy')
  const filed = formatLocalDate(filing.filing_date, 'MMM d, yyyy')
  return ended ? `${filing.filing_type} · ${ended}` : filed ? `${filing.filing_type} · filed ${filed}` : filing.filing_type
}

/**
 * The filing identity strip (2026-10 critique P-04): the filing stated once, as the page's signpost.
 * A breadcrumb back to the company; line 1 the company (the page's h1) with its ticker in the data
 * face and a marker only when it is true (Superseded); line 2 one data-face line of facts — form,
 * period of report, filed date, exchange — and a quiet link to the original on SEC EDGAR. The form is
 * weight, never a Badge (the earningsnerd/no-form-code-badge gate) and never the status blue; no
 * decorative "AI analysis" chip. Fiscal-year labels ("FY2022") wait for the filings payload to carry
 * XBRL dei fields, so the period is stated by its end date. `children` is a further line (the page
 * adds the summary's verification tally once one exists).
 */
export function FilingIdentity({ filing, children }: { filing: Filing; children?: ReactNode }) {
  const company = filing.company
  const name = company ? formatCompanyName(company.name) || company.ticker : null
  const period = periodPhrase(filing)
  const filed = formatLocalDate(filing.filing_date, 'MMM d, yyyy')
  const original = originalDocumentUrl(filing)

  return (
    <div className="flex flex-col gap-2">
      <nav aria-label="Breadcrumb" className="mb-3">
        <ol className="flex flex-wrap items-center gap-2 text-sm">
          {company ? (
            <li>
              <Link href={`/company/${company.ticker}`} className={CRUMB}>
                {name}
              </Link>
            </li>
          ) : (
            <li>
              <Link href="/" className={CRUMB}>
                Home
              </Link>
            </li>
          )}
          <li aria-hidden="true" className={MUTED}>
            /
          </li>
          <li aria-current="page" className={MUTED}>
            {filingCrumb(filing)}
          </li>
        </ol>
      </nav>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h1 className="min-w-0 break-words text-2xl font-semibold sm:text-3xl">
          {name ?? `${filing.filing_type} summary`}
        </h1>
        {company?.ticker && (
          <span
            className={cx(
              'rounded-full border border-border-light bg-panel-light px-2.5 py-0.5 font-data text-sm font-semibold',
              'dark:border-white/10 dark:bg-panel-dark',
              MUTED,
            )}
          >
            {company.ticker}
          </span>
        )}
        <SupersededFilingNotice filing={filing} />
      </div>

      <p className={cx('flex flex-wrap items-center gap-x-2.5 gap-y-1 font-data text-xs tabular-nums sm:text-sm', MUTED)}>
        <span className={cx('font-semibold', INK)}>{filing.filing_type}</span>
        {period && (
          <>
            <Sep />
            <span>{period}</span>
          </>
        )}
        {filed && (
          <>
            <Sep />
            <span>filed {filed}</span>
          </>
        )}
        {company?.exchange && (
          <>
            <Sep />
            <span>{company.exchange}</span>
          </>
        )}
        {original && (
          <>
            <Sep />
            <a href={original} target="_blank" rel="noopener noreferrer" className={cx(LINK, 'inline-flex items-center gap-1')}>
              Original on SEC EDGAR
              <ArrowSquareOutIcon aria-hidden="true" className="h-3.5 w-3.5" />
            </a>
          </>
        )}
      </p>

      {children}
    </div>
  )
}
