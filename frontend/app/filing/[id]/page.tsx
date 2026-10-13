import { formatCompanyName } from '@/lib/formatCompanyName'
import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import FilingPageClient from './page-client'
import {
  fetchFilingServer,
  fetchFilingSummaryServer,
  fetchWhatChangedServer,
  summaryHasDisplayableContent,
  toExcerpt,
} from '@/lib/serverApi'
import type { Filing } from '@/features/filings/api/filings-api'
import { formatLocalDate } from '@/lib/format'
import { SOCIAL_CARD } from '@/lib/socialCard'

const SITE_URL = 'https://www.earningsnerd.io'

// On-demand ISR (see company/[ticker]/page.tsx): rendered on first request, cached, revalidated
// hourly — so a filing page flips from the signup-gate shell to the indexed summary within an
// hour of its summary being generated, and crawls are served from the Vercel cache.
export const revalidate = 3600
export const dynamicParams = true
export async function generateStaticParams(): Promise<Array<{ id: string }>> {
  return []
}

interface FilingPageProps {
  params: Promise<{ id: string }>
}

const isNumericId = (id: string) => /^\d+$/.test(id)

// The filed date, never a bare year: a year after the form reads as a fiscal-year label, which the
// product does not derive. An empty or malformed filing_date drops the clause rather than inventing one.
const filedOn = (filing: Filing) => formatLocalDate(filing.filing_date, 'MMMM d, yyyy')

// '<Company> (<ticker>) 10-K, filed October 31, 2025: AI summary | EarningsNerd'. A stub (no summary to
// show) drops ': AI summary', so the title never promises what the page does not hold.
const filingTitle = (filing: Filing, hasContent: boolean) => {
  const company = filing.company
  const filedDate = filedOn(filing)
  const subject = company
    ? `${formatCompanyName(company.name)} (${company.ticker}) ${filing.filing_type}`
    : filing.filing_type
  const filed = filedDate ? `, filed ${filedDate}` : ''
  return `${subject}${filed}${hasContent ? ': AI summary' : ''} | EarningsNerd`
}

export async function generateMetadata({ params }: FilingPageProps): Promise<Metadata> {
  const { id } = await params

  // Legacy ticker-shaped URLs (/filing/AAPL) render a filings picker that duplicates the
  // company page — canonicalize them onto it.
  if (!isNumericId(id)) {
    const ticker = id.toUpperCase()
    return {
      title: `${ticker} SEC filings | EarningsNerd`,
      alternates: { canonical: `/company/${ticker}` },
    }
  }

  const filingId = Number(id)
  const [filingResult, summaryResult] = await Promise.all([
    fetchFilingServer(filingId),
    fetchFilingSummaryServer(filingId),
  ])
  if (filingResult.status !== 'ok') {
    // Not-found renders a real 404 from the page; unavailable falls back to the generic shell.
    return {
      title: 'SEC filing | EarningsNerd',
      description: 'An SEC filing, as published on SEC EDGAR.',
      alternates: { canonical: `/filing/${filingId}` },
    }
  }

  const filing = filingResult.data
  const summary = summaryResult.status === 'ok' ? summaryResult.data : undefined
  const hasContent = summaryHasDisplayableContent(summary)
  const filedDate = filedOn(filing)
  const companyName = formatCompanyName(filing.company?.name)

  const title = filingTitle(filing, hasContent)
  // With a summary: its own opening sentences (unique per page). Without: what the filing is and
  // where it comes from, with no claim about a summary in either direction (the description is cached
  // for an hour and by scrapers for longer, so a summary state stated here would go stale).
  const filed = filedDate ? `, filed ${filedDate},` : ''
  const description = hasContent
    ? toExcerpt(summary!.business_overview!)
    : companyName
      ? `${companyName}’s ${filing.filing_type}${filed} as published on SEC EDGAR.`
      : `${filing.filing_type}${filed} as published on SEC EDGAR.`

  return {
    title,
    description,
    alternates: { canonical: `/filing/${filing.id}` },
    // No summary yet = a stub page (filing header + sign-up gate). Keep stubs out of the index —
    // they'd read as thousands of near-duplicates — but let crawlers follow the links. The page
    // becomes indexable automatically once a summary exists (next revalidation).
    ...(hasContent ? {} : { robots: { index: false, follow: true } }),
    // This openGraph replaces the root layout's wholesale, so it carries the site card itself (twitter
    // fills its image from it). A filing-specific card waits for founder decision D8.
    openGraph: {
      title,
      description,
      type: 'article',
      url: `${SITE_URL}/filing/${filing.id}`,
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

const buildJsonLd = (filing: Filing) => {
  const company = filing.company
  const crumbs = [
    { '@type': 'ListItem', position: 1, name: 'Home', item: `${SITE_URL}/` },
    ...(company
      ? [
          {
            '@type': 'ListItem',
            position: 2,
            name: `${formatCompanyName(company.name)} (${company.ticker})`,
            item: `${SITE_URL}/company/${company.ticker}`,
          },
        ]
      : []),
    {
      '@type': 'ListItem',
      position: company ? 3 : 2,
      name: `${filing.filing_type} · ${formatLocalDate(filing.filing_date, 'MMM d, yyyy')}`,
      item: `${SITE_URL}/filing/${filing.id}`,
    },
  ]
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs,
  }
}

export default async function FilingPage({ params }: FilingPageProps) {
  const { id } = await params

  // Ticker-shaped URLs keep their existing client-side picker (canonicalized via metadata above).
  if (!isNumericId(id)) return <FilingPageClient />

  const filingId = Number(id)
  const [filingResult, summaryResult, changeResult] = await Promise.all([
    fetchFilingServer(filingId),
    fetchFilingSummaryServer(filingId),
    fetchWhatChangedServer(filingId),
  ])

  // Real 404 status for unknown filing ids (was a 200 "Filing not found" soft-404).
  if (filingResult.status === 'not-found') notFound()

  const filing = filingResult.status === 'ok' ? filingResult.data : undefined
  // `null` = confirmed no summary; `undefined` = unknown (backend unreachable) → client refetches.
  const summary = summaryResult.status === 'ok' ? summaryResult.data : undefined
  // Unknown (backend unreachable) leaves the client to fetch it, as before.
  const changeReport = changeResult.status === 'ok' ? changeResult.data : undefined

  return (
    <>
      {filing && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(buildJsonLd(filing)) }}
        />
      )}
      <FilingPageClient initialFiling={filing} initialSummary={summary} initialChangeReport={changeReport} />
    </>
  )
}
