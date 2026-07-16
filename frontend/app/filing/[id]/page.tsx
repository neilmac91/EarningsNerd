import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import FilingPageClient from './page-client'
import {
  fetchFilingServer,
  fetchFilingSummaryServer,
  summaryHasDisplayableContent,
  toExcerpt,
} from '@/lib/serverApi'
import type { Filing } from '@/features/filings/api/filings-api'
import { formatLocalDate } from '@/lib/format'

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

const filingTitle = (filing: Filing) => {
  const year = filing.filing_date?.slice(0, 4) ?? ''
  const company = filing.company
  return company
    ? `${company.name} (${company.ticker}) ${filing.filing_type} ${year}: AI Summary | EarningsNerd`
    : `${filing.filing_type} ${year} Filing: AI Summary | EarningsNerd`
}

export async function generateMetadata({ params }: FilingPageProps): Promise<Metadata> {
  const { id } = await params

  // Legacy ticker-shaped URLs (/filing/AAPL) render a filings picker that duplicates the
  // company page — canonicalize them onto it.
  if (!isNumericId(id)) {
    const ticker = id.toUpperCase()
    return {
      title: `${ticker} SEC Filings | EarningsNerd`,
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
      title: 'SEC Filing Summary | EarningsNerd',
      description:
        'AI-powered summary of a SEC filing: financial highlights, risk factors, and management commentary.',
      alternates: { canonical: `/filing/${filingId}` },
    }
  }

  const filing = filingResult.data
  const summary = summaryResult.status === 'ok' ? summaryResult.data : undefined
  const hasContent = summaryHasDisplayableContent(summary)
  const filedDate = formatLocalDate(filing.filing_date, 'MMMM d, yyyy')
  const companyName = filing.company?.name ?? 'this company'

  const title = filingTitle(filing)
  // With a summary: its own opening sentences (unique per page). Without: an honest template.
  const description = hasContent
    ? toExcerpt(summary!.business_overview!)
    : `${companyName} ${filing.filing_type} filed ${filedDate}. Read the AI summary of financial highlights, risk factors, and management commentary, sourced from SEC EDGAR.`

  return {
    title,
    description,
    alternates: { canonical: `/filing/${filing.id}` },
    // No summary yet = a stub page (filing header + sign-up gate). Keep stubs out of the index —
    // they'd read as thousands of near-duplicates — but let crawlers follow the links. The page
    // becomes indexable automatically once a summary exists (next revalidation).
    ...(hasContent ? {} : { robots: { index: false, follow: true } }),
    openGraph: {
      title,
      description,
      type: 'article',
      url: `${SITE_URL}/filing/${filing.id}`,
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
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
            name: `${company.name} (${company.ticker})`,
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
  const [filingResult, summaryResult] = await Promise.all([
    fetchFilingServer(filingId),
    fetchFilingSummaryServer(filingId),
  ])

  // Real 404 status for unknown filing ids (was a 200 "Filing not found" soft-404).
  if (filingResult.status === 'not-found') notFound()

  const filing = filingResult.status === 'ok' ? filingResult.data : undefined
  // `null` = confirmed no summary; `undefined` = unknown (backend unreachable) → client refetches.
  const summary = summaryResult.status === 'ok' ? summaryResult.data : undefined

  return (
    <>
      {filing && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(buildJsonLd(filing)) }}
        />
      )}
      <FilingPageClient initialFiling={filing} initialSummary={summary} />
    </>
  )
}
