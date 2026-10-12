import Link from 'next/link'
import { Fragment, type ReactNode } from 'react'
import { ArrowSquareOutIcon, CheckCircleIcon } from '@/lib/icons'
import { cx } from '@/components/ui'
import CompanyLogo from '@/components/CompanyLogo'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import { displayCik, edgarCompanyUrl } from '@/features/companies/lib/edgar'
import {
  IDENTITY_CRUMB,
  IDENTITY_FACTS,
  IDENTITY_LINK,
  Sep,
  TickerPill,
  periodPhrase,
} from '@/features/filings/components/FilingIdentity'
import { directionOf, directionText } from '@/lib/financialTone'
import { fmtCurrency, fmtPercent, formatLocalDate } from '@/lib/format'
import { formatCompanyName } from '@/lib/formatCompanyName'

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'

interface CompanyIdentityProps {
  company: Company
  /** The newest filing that still stands (selectRecommendedFiling); null drops the latest-filing line. */
  latest: Filing | null
  /** The latest filing's summary exists (the page's summary probe came back with one). */
  summaryReady?: boolean
  /** The lead's actions: the watchlist toggle and the page's one primary action. */
  actions?: ReactNode
}

/** Facts in one data-face line, a middot between each (Sep: assistive tech hears a comma). */
function Facts({ children }: { children: ReactNode[] }) {
  const facts = children.filter(Boolean)
  return (
    <p className={IDENTITY_FACTS}>
      {facts.map((fact, i) => (
        <Fragment key={i}>
          {i > 0 && <Sep />}
          {fact}
        </Fragment>
      ))}
    </p>
  )
}

/**
 * The company page's lead (2026-10 critique, 1b): the filing page's identity vocabulary (P-04)
 * reused. A breadcrumb, the company as the page's h1 with its ticker in the data face, one line of
 * facts (exchange, quote, CIK, the company's filings on SEC EDGAR) and one line naming the latest
 * filing by form, period of report and filed date, then the page's actions: one primary, the
 * watchlist beside it as a secondary. Sector and the fiscal-year convention wait for the company
 * payload to carry them, so the lead states only what the API returns.
 */
export function CompanyIdentity({ company, latest, summaryReady = false, actions }: CompanyIdentityProps) {
  const name = formatCompanyName(company.name) || company.ticker
  const price = company.stock_quote?.price
  const change = company.stock_quote?.change_percent
  const latestFiled = latest ? formatLocalDate(latest.filing_date, 'MMM d, yyyy') : ''
  const latestPeriod = latest ? periodPhrase(latest) : null

  return (
    <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between lg:gap-8">
      <div className="flex min-w-0 flex-col gap-2">
        <nav aria-label="Breadcrumb" className="mb-3">
          <ol className="flex flex-wrap items-center gap-2 text-sm">
            <li>
              <Link href="/" className={IDENTITY_CRUMB}>
                Home
              </Link>
            </li>
            <li aria-hidden="true" className={MUTED}>
              /
            </li>
            <li aria-current="page" className={MUTED}>
              {name}
            </li>
          </ol>
        </nav>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <CompanyLogo decorative ticker={company.ticker} name={name} size={36} priority />
          <h1 className="min-w-0 break-words text-2xl font-semibold sm:text-3xl">{name}</h1>
          <TickerPill ticker={company.ticker} />
        </div>

        <Facts>
          {[
            company.exchange && <span key="exchange">{company.exchange}</span>,
            price != null && (
              <span key="quote">
                <span className={cx('font-semibold', INK)}>{fmtCurrency(price, { digits: 2, compact: false })}</span>
                {change != null && (
                  <>
                    {' '}
                    <span className={cx('font-medium', directionText[directionOf(change)])}>
                      {fmtPercent(change, { digits: 2, signed: true })}
                    </span>
                  </>
                )}
              </span>
            ),
            company.cik && <span key="cik">CIK {displayCik(company.cik)}</span>,
            company.cik && (
              <a
                key="edgar"
                href={edgarCompanyUrl(company.cik)}
                target="_blank"
                rel="noopener noreferrer"
                className={cx(IDENTITY_LINK, 'inline-flex items-center gap-1')}
              >
                Company on SEC EDGAR
                <ArrowSquareOutIcon aria-hidden="true" className="h-3.5 w-3.5" />
              </a>
            ),
          ]}
        </Facts>

        {latest && (
          <Facts>
            {[
              <span key="form">
                Latest filing <span className={cx('font-semibold', INK)}>{latest.filing_type}</span>
              </span>,
              latestPeriod && <span key="period">{latestPeriod}</span>,
              latestFiled && <span key="filed">filed {latestFiled}</span>,
              summaryReady && (
                <span key="ready" className="inline-flex items-center gap-1">
                  <CheckCircleIcon aria-hidden="true" className="h-3.5 w-3.5 text-brand-strong dark:text-brand-strong-dark" />
                  summary ready
                </span>
              ),
            ]}
          </Facts>
        )}
      </div>

      {actions && <div className="flex flex-col gap-2 sm:flex-row sm:items-center lg:shrink-0">{actions}</div>}
    </div>
  )
}
