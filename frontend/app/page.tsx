import type { Metadata } from 'next'

// Rule 2.1: Direct imports, no barrel files
import CompanySearch from '@/features/companies/components/CompanySearch'
import QuickAccessBar from '@/features/marketing/components/QuickAccessBar'
import NotableFilings from '@/features/filings/components/NotableFilings'
import HeroExample from '@/features/marketing/components/HeroExample'
import ExampleSummaryCard from '@/features/marketing/components/ExampleSummaryCard'
import ReportingThisWeek from '@/features/calendar/components/ReportingThisWeek'
import SocialProofStrip from '@/features/marketing/components/SocialProofStrip'
import HowItWorks from '@/features/marketing/components/HowItWorks'
import FeatureShowcase from '@/features/marketing/components/FeatureShowcase'
import AccuracySection from '@/features/marketing/components/AccuracySection'
import CtaBanner from '@/features/marketing/components/CtaBanner'
import ExampleCtaLink from '@/features/marketing/components/ExampleCtaLink'
import { exampleFilingHref } from '@/lib/featureFlags'
import {
  fetchExampleData,
  fetchNotableFilings,
  fetchReportingThisWeek,
} from '@/lib/serverApi'

const SITE_URL = 'https://www.earningsnerd.io'

export const metadata: Metadata = {
  title: 'EarningsNerd | Understand any SEC filing in minutes',
  description:
    'Read any 10-K or 10-Q in minutes. AI summaries of financials, risks, and trends, sourced directly from SEC EDGAR.',
  alternates: {
    canonical: '/',
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
  // to static content.
  const [example, notable, reportingThisWeek] = await Promise.all([
    fetchExampleData(),
    fetchNotableFilings(),
    fetchReportingThisWeek(),
  ])

  return (
    <div className="bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
      />
      {/* ═══════════════════════════════════════════════════════════
          HERO SECTION — Split layout with copy left, mockup right
          ═══════════════════════════════════════════════════════════ */}
      <section className="bg-background-light dark:bg-background-dark">
        <div className="mx-auto max-w-7xl px-4 pb-16 pt-16 sm:px-6 md:pb-24 md:pt-20 lg:px-8 lg:pb-28 lg:pt-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
            {/* Left: Copy + Search */}
            <div>
              <h1 className="text-4xl font-semibold leading-[1.1] tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-5xl lg:text-6xl">
                Understand any{' '}
                <span className="text-brand-strong dark:text-brand-strong-dark">SEC filing</span>{' '}
                in minutes
              </h1>
              <p className="mt-6 max-w-lg text-lg leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
                AI summaries that turn 100-page SEC filings into a clear
                five-minute read. Financials, risks, and trends, all in one
                place.
              </p>

              {/* Primary action: search. One hero, one action — registration
                  lives in the header; the example link is the zero-effort path. */}
              <div className="mt-8">
                <CompanySearch autoFocusDesktop />
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                <ExampleCtaLink
                  href={exampleFilingHref('hero_example')}
                  placement="hero"
                  className="inline-flex items-center gap-1 font-medium text-brand-strong dark:text-brand-strong-dark underline underline-offset-4 decoration-brand-strong/40 transition-colors hover:decoration-brand-strong dark:decoration-brand-dark/40 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                >
                  See a live example →
                </ExampleCtaLink>
                <span className="text-text-tertiary-light dark:text-text-secondary-dark">
                  Free account · 5 AI summaries a month · no credit card
                </span>
              </div>

              {/* Quick access tickers */}
              <QuickAccessBar />

              {/* Compact example for small screens (full example card is lg-only) */}
              <div className="mt-8 lg:hidden">
                <ExampleSummaryCard example={example} />
              </div>
            </div>

            {/* Right: Live example summary (decorative float retired — DS v2 motion pass) */}
            <div className="hidden lg:block">
              <HeroExample example={example} />
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════
          SOCIAL PROOF STRIP
          ═══════════════════════════════════════════════════════════ */}
      <SocialProofStrip />

      {/* ═══════════════════════════════════════════════════════════
          REPORTING THIS WEEK — omits itself entirely when empty
          ═══════════════════════════════════════════════════════════ */}
      <ReportingThisWeek data={reportingThisWeek} />

      {/* ═══════════════════════════════════════════════════════════
          NOTABLE FILINGS — market-wide EDGAR discovery; omits itself when empty
          ═══════════════════════════════════════════════════════════ */}
      <NotableFilings data={notable} />

      {/* ═══════════════════════════════════════════════════════════
          HOW IT WORKS
          ═══════════════════════════════════════════════════════════ */}
      <section className="py-20 sm:py-24">
        <HowItWorks />
      </section>

      {/* ═══════════════════════════════════════════════════════════
          FEATURE SHOWCASE
          ═══════════════════════════════════════════════════════════ */}
      <section className="py-20 sm:py-24">
        <FeatureShowcase />
      </section>

      {/* ═══════════════════════════════════════════════════════════
          WHERE THE NUMBERS COME FROM (objection handling)
          ═══════════════════════════════════════════════════════════ */}
      <section className="py-20 sm:py-24">
        <AccuracySection />
      </section>

      {/* ═══════════════════════════════════════════════════════════
          FINAL CTA
          ═══════════════════════════════════════════════════════════ */}
      <section className="pb-20 sm:pb-24">
        <CtaBanner />
      </section>
    </div>
  )
}
