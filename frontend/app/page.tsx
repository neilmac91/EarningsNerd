import type { Metadata } from 'next'

// Rule 2.1: Direct imports, no barrel files
import LandingHero from '@/features/marketing/components/LandingHero'
import MeasuredClaims from '@/features/marketing/components/MeasuredClaims'
import EvidenceSection from '@/features/marketing/components/EvidenceSection'
import SummaryContents from '@/features/marketing/components/SummaryContents'
import ProDepth from '@/features/marketing/components/ProDepth'
import PricingSection from '@/features/marketing/components/PricingSection'
import ReaderQuoteSlot from '@/features/marketing/components/ReaderQuoteSlot'
import ReportingThisWeek from '@/features/calendar/components/ReportingThisWeek'
import ClosingLine from '@/features/marketing/components/ClosingLine'
import { betaPricingActive, resolveAccessMode } from '@/features/marketing/lib/access'
import { DEFAULT_HEADLINE, pageTitleFor } from '@/features/marketing/lib/headline'
import { LOGO_DEV_ENABLED } from '@/lib/featureFlags'
import { SOCIAL_CARD } from '@/lib/socialCard'
import { fetchExampleData, fetchReportingThisWeek, fetchSignupConfig } from '@/lib/serverApi'

const SITE_URL = 'https://www.earningsnerd.io'

const DESCRIPTION =
  'AI summaries of 10-Ks and 10-Qs for investors who still check the source. Figures are checked against the company’s XBRL where they can be, and quotes against the filing’s own text.'

// <title> / og:title follow the default headline variant (A). The client-side experiment may swap
// the H1 to B or C and retitles the document to match (HeroHeadline); crawlers always see A.
export const metadata: Metadata = {
  title: pageTitleFor(DEFAULT_HEADLINE),
  description: DESCRIPTION,
  alternates: {
    canonical: '/',
  },
  openGraph: {
    title: pageTitleFor(DEFAULT_HEADLINE),
    description: DESCRIPTION,
    type: 'website',
    url: '/',
    // Same card as the root layout (a nested `openGraph` replaces the layout's, not merges).
    images: [SOCIAL_CARD],
  },
  twitter: {
    card: 'summary_large_image',
    title: pageTitleFor(DEFAULT_HEADLINE),
    description: DESCRIPTION,
    images: [SOCIAL_CARD.url],
  },
}

// Foundational structured data: Organization + WebSite with a SearchAction
// (ticker search resolves to /company/{ticker}).
const JSON_LD = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Organization',
      '@id': `${SITE_URL}/#organization`,
      name: 'EarningsNerd',
      url: SITE_URL,
      // Google requires a raster logo ≥112px for the Organization rich result.
      logo: `${SITE_URL}/icons/icon-512.png`,
      description: 'AI-powered SEC filing analysis. 10-K and 10-Q summaries sourced from SEC EDGAR.',
    },
    {
      '@type': 'WebSite',
      '@id': `${SITE_URL}/#website`,
      name: 'EarningsNerd',
      url: SITE_URL,
      publisher: { '@id': `${SITE_URL}/#organization` },
      potentialAction: {
        '@type': 'SearchAction',
        target: {
          '@type': 'EntryPoint',
          urlTemplate: `${SITE_URL}/company/{search_term_string}`,
        },
        'query-input': 'required name=search_term_string',
      },
    },
  ],
}

export default async function Home() {
  // The WAITLIST_MODE gate lives in middleware.ts (single source of truth) —
  // keeping this page free of redirects lets it render statically (ISR).
  // Live data is fetched server-side so the first paint shows the real
  // product; every fetcher returns null on failure and the page falls back
  // to static content. The signup config drives the ONE access decision
  // (account CTAs + access line + beta pricing line) and fails closed to the
  // invite copy when the backend is unreachable.
  const [example, reportingThisWeek, signup] = await Promise.all([
    fetchExampleData(),
    fetchReportingThisWeek(),
    fetchSignupConfig(),
  ])
  const accessMode = resolveAccessMode(signup)
  const showBeta = betaPricingActive(signup)

  return (
    <div className="bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
      {/* The one third-party origin on the page (company marks); body-ok for `preconnect`. */}
      {LOGO_DEV_ENABLED && <link rel="preconnect" href="https://img.logo.dev" />}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
      />
      {/* Every section after the hero is one ruled row (LandingRow, D-045), numbered by the `landing-row` counter
          reset here, so a section that omits itself takes no number. The order is pinned by
          tests/unit/landing-sections-mounted.spec.ts. */}
      <main className="[counter-reset:landing-row]">
        {/* Hero: headline (LCP), primary CTA + access line, company search, live example */}
        <LandingHero example={example} accessMode={accessMode} />

        {/* What a summary does: four behaviours */}
        <MeasuredClaims />

        {/* Evidence: where the numbers come from */}
        <EvidenceSection />

        {/* What a summary contains + how it works */}
        <SummaryContents />

        {/* What Pro adds */}
        <ProDepth />

        {/* Pricing: one table */}
        <PricingSection accessMode={accessMode} showBeta={showBeta} />

        {/* Reader quote: renders nothing until a real reader's words fill READER_QUOTE (no placeholder ever ships) */}
        <ReaderQuoteSlot />

        {/* Reporting this week: omits itself entirely when there is no live data */}
        <ReportingThisWeek data={reportingThisWeek} />

        {/* Notable filings is dormant under the brand (docs/brand/01-interview.md, A8; the 2026-10
            audit found microcap 8-Ks under "high-signal") and waits on E90 (tasks/todo.md), which
            remounts it under D-046's curation rule: 10-K and 10-Q filings only, from companies that hold
            a full summary of any filing, newest first, at most six. It returns here, as a LandingRow
            after Reporting this week and before the close; the counter numbers it, and
            tests/unit/landing-sections-mounted.spec.ts takes it back into its lists. The component, its
            fetcher and its spec stay for that day; the fetcher revalidated at 3600 like the rest, so
            dropping it left the route's ISR window where it was. */}

        {/* The close: one line, not a banner */}
        <ClosingLine accessMode={accessMode} />
      </main>
    </div>
  )
}
