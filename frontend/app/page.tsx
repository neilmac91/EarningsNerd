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
import CtaBanner from '@/features/marketing/components/CtaBanner'
import { betaPricingActive, resolveAccessMode } from '@/features/marketing/lib/access'
import { DEFAULT_HEADLINE, pageTitleFor } from '@/features/marketing/lib/headline'
import { LOGO_DEV_ENABLED } from '@/lib/featureFlags'
import { fetchExampleData, fetchReportingThisWeek, fetchSignupConfig } from '@/lib/serverApi'

const SITE_URL = 'https://www.earningsnerd.io'

// The reader-quote slot is designed and built but stays unrendered until a real reader supplies a
// quote (design tweak `showQuoteSlot`, off). No placeholder testimonial ever ships.
const SHOW_QUOTE_SLOT = false

const DESCRIPTION =
  'AI summaries of 10-Ks and 10-Qs for investors who read the source. Every figure grounded in SEC XBRL, every claim linked to the passage it came from.'

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
    images: [
      {
        // Same card as the root layout (a nested `openGraph` replaces the layout's, not merges).
        url: '/og-image.png?v=2',
        width: 1200,
        height: 630,
        alt: 'EarningsNerd - SEC filing summaries in minutes',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: pageTitleFor(DEFAULT_HEADLINE),
    description: DESCRIPTION,
    images: ['/og-image.png?v=2'],
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
      <main>
        {/* 2. Hero: headline (LCP), primary CTA + access line, company search, live example */}
        <LandingHero example={example} accessMode={accessMode} />

        {/* 3. Measured claims strip */}
        <MeasuredClaims />

        {/* 4. Evidence: where the numbers come from */}
        <EvidenceSection />

        {/* 5. What a summary contains + how it works */}
        <SummaryContents />

        {/* 6. What Pro adds */}
        <ProDepth />

        {/* 7. Pricing */}
        <PricingSection accessMode={accessMode} showBeta={showBeta} />

        {/* Reader quote: designed, unrendered until a real quote exists */}
        {SHOW_QUOTE_SLOT && <ReaderQuoteSlot />}

        {/* 8. Reporting this week — omits itself entirely when there is no live data */}
        <ReportingThisWeek data={reportingThisWeek} />

        {/* 9. Final CTA */}
        <CtaBanner accessMode={accessMode} />
      </main>
    </div>
  )
}
