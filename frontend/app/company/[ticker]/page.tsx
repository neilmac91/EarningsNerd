import { formatCompanyName } from '@/lib/formatCompanyName'
import type { Metadata } from 'next'
import { notFound, permanentRedirect } from 'next/navigation'
import CompanyPageClient from './page-client'
import { fetchCompanyServer, fetchCompanyFilingsServer } from '@/lib/serverApi'
import type { Company } from '@/features/companies/api/companies-api'
import { edgarCompanyUrl } from '@/features/companies/lib/edgar'
import { SOCIAL_CARD } from '@/lib/socialCard'

const SITE_URL = 'https://www.earningsnerd.io'

// On-demand ISR: nothing is prerendered at build time (CI builds run with no backend); each
// company page is rendered on first request, cached by Vercel, and revalidated at most twice
// an hour. A crawl of N pages therefore costs the backend at most ~N requests per 30 minutes,
// not one per hit — and a backend outage degrades to the client-fetching shell, never a 500.
export const revalidate = 1800
export const dynamicParams = true
export async function generateStaticParams(): Promise<Array<{ ticker: string }>> {
  return []
}

interface CompanyPageProps {
  params: Promise<{ ticker: string }>
}

export async function generateMetadata({ params }: CompanyPageProps): Promise<Metadata> {
  const { ticker: rawTicker } = await params
  const ticker = rawTicker.toUpperCase()
  const result = await fetchCompanyServer(ticker)
  const company = result.status === 'ok' ? result.data : null
  const displayName = formatCompanyName(company?.name) || ticker

  const unsupported = company?.coverage_status === 'unsupported_foreign'

  // With the company unknown (backend unreachable) the ticker stands alone, never "AAPL (AAPL)".
  const label = company ? `${displayName} (${ticker})` : ticker
  const title = `${label} SEC filings and AI summaries | EarningsNerd`
  // The description says what the page holds: an issuer that files no financial reports with the SEC
  // gets the same sentence its page shows, never a promise of summaries it cannot have.
  const description = unsupported
    ? company?.coverage_reason ||
      `${displayName} does not file financial reports with the SEC, so EarningsNerd has no filings to analyze.`
    : `${label} filings from SEC EDGAR, with AI summaries that show their work.`

  return {
    title,
    description,
    alternates: { canonical: `/company/${ticker}` },
    // Honest empty states are for people, not the index: an unsupported foreign issuer's page
    // has no filings and never will, so keep it out of search results.
    ...(unsupported ? { robots: { index: false, follow: true } } : {}),
    // This openGraph replaces the root layout's wholesale, so it carries the site card itself. A
    // company-specific card waits for founder decision D8.
    openGraph: {
      title,
      description,
      type: 'website',
      url: `${SITE_URL}/company/${ticker}`,
      images: [SOCIAL_CARD],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [SOCIAL_CARD.url],
    },
  }
}

// Breadcrumb + the company as a Corporation entity (name/ticker only — nothing we can't back).
const buildJsonLd = (company: Company) => ({
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: `${SITE_URL}/` },
        {
          '@type': 'ListItem',
          position: 2,
          name: `${formatCompanyName(company.name)} (${company.ticker})`,
          item: `${SITE_URL}/company/${company.ticker}`,
        },
      ],
    },
    {
      '@type': 'Corporation',
      name: formatCompanyName(company.name),
      tickerSymbol: company.ticker,
      url: `${SITE_URL}/company/${company.ticker}`,
      ...(company.cik
        ? { sameAs: [edgarCompanyUrl(company.cik)] }
        : {}),
    },
  ],
})

export default async function CompanyPage({ params }: CompanyPageProps) {
  const { ticker: rawTicker } = await params
  const ticker = rawTicker.toUpperCase()
  // One canonical URL per company: /company/aapl 308s to /company/AAPL (matching the sitemap),
  // so Google never sees the same page under two casings.
  if (rawTicker !== ticker) {
    permanentRedirect(`/company/${encodeURIComponent(ticker)}`)
  }

  const [companyResult, filingsResult] = await Promise.all([
    fetchCompanyServer(ticker),
    fetchCompanyFilingsServer(ticker),
  ])

  // A real 404 status (not a 200 "Company not found" shell) — soft-404s poison the index.
  if (companyResult.status === 'not-found') notFound()

  const company = companyResult.status === 'ok' ? companyResult.data : undefined
  const filings = filingsResult.status === 'ok' ? filingsResult.data : undefined

  return (
    <>
      {company && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(buildJsonLd(company)) }}
        />
      )}
      <CompanyPageClient initialCompany={company} initialFilings={filings} />
    </>
  )
}
