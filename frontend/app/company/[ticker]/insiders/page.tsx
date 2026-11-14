import type { Metadata } from 'next'
import { notFound, permanentRedirect } from 'next/navigation'
import InsidersPageClient from './page-client'
import { ENABLE_INSIDER_ACTIVITY, LOGO_DEV_ENABLED } from '@/lib/featureFlags'

// The company's insider (Form 4) activity in full (ADR 0009): the page the company page's Insider activity card
// links to. Its content is read in the browser by a signed-in beta account, so the server renders a shell that
// names no company and fetches nothing: one cached shell per ticker, rendered on its first request.
export const revalidate = false
export const dynamicParams = true
export async function generateStaticParams(): Promise<Array<{ ticker: string }>> {
  return []
}

// A reader's page, not a search result: a crawler sees the shell alone. The client retitles the document with the
// company's name once it knows it (page-client.tsx).
export const metadata: Metadata = {
  title: 'Insider activity | EarningsNerd',
  description: 'Open-market insider trades at a company, from the Form 4 filings on SEC EDGAR.',
  robots: { index: false, follow: true },
}

interface InsidersPageProps {
  params: Promise<{ ticker: string }>
}

export default async function InsidersPage({ params }: InsidersPageProps) {
  // The route exists only where the build shows insider activity at all (the company page's card links here).
  if (!ENABLE_INSIDER_ACTIVITY) notFound()

  const { ticker: rawTicker } = await params
  const ticker = rawTicker.toUpperCase()
  // One URL per company, as the company page: /company/aapl/insiders 308s to /company/AAPL/insiders.
  if (rawTicker !== ticker) {
    permanentRedirect(`/company/${encodeURIComponent(ticker)}/insiders`)
  }

  return (
    <>
      {LOGO_DEV_ENABLED && <link rel="preconnect" href="https://img.logo.dev" />}
      <InsidersPageClient />
    </>
  )
}
