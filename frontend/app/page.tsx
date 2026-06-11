import { Suspense } from 'react'
import type { Metadata } from 'next'
import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

// Rule 2.1: Direct imports, no barrel files
import CompanySearch from '@/components/CompanySearch'
import QuickAccessBar from '@/components/QuickAccessBar'
import HotFilings from '@/components/HotFilings'
import TrendingTickers from '@/components/TrendingTickers'
import HeroMockup from '@/components/HeroMockup'
import SocialProofStrip from '@/components/SocialProofStrip'
import HowItWorks from '@/components/HowItWorks'
import FeatureShowcase from '@/components/FeatureShowcase'
import CtaBanner from '@/components/CtaBanner'
import ExampleCtaLink from '@/components/ExampleCtaLink'
import { EXAMPLE_FILING_ID } from '@/lib/featureFlags'

const SITE_URL = 'https://www.earningsnerd.io'

export const metadata: Metadata = {
  title: 'EarningsNerd — Understand any SEC filing in minutes',
  description:
    'AI-powered summaries that turn 100-page 10-Ks and 10-Qs into clear, decision-ready insights. Financials, risks, and trends — sourced directly from SEC EDGAR.',
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
      logo: `${SITE_URL}/assets/earningsnerd-icon-dark.svg`,
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

// Rule 6.2: Hoist static skeleton components outside
function HotFilingsSkeleton() {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-label="Loading hot filings">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="h-28 animate-pulse rounded-xl border border-white/[0.06] bg-white/[0.03]"
        />
      ))}
    </div>
  )
}

function TrendingTickersSkeleton() {
  return (
    <div role="status" aria-live="polite" aria-label="Loading market movers">
      <div className="mb-4 flex items-center gap-2">
        <div className="h-5 w-5 animate-pulse rounded bg-white/10" />
        <div className="h-6 w-32 animate-pulse rounded bg-white/10" />
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-28 w-52 flex-shrink-0 animate-pulse rounded-2xl border border-white/[0.06] bg-white/[0.03]"
          />
        ))}
      </div>
    </div>
  )
}

export default function Home() {
  // The WAITLIST_MODE gate lives in middleware.ts (single source of truth) —
  // keeping this page free of redirects lets it render statically.
  return (
    <div className="bg-slate-950 text-white">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
      />
      {/* ═══════════════════════════════════════════════════════════
          HERO SECTION — Split layout with copy left, mockup right
          ═══════════════════════════════════════════════════════════ */}
      <section className="relative overflow-hidden bg-hero-gradient">
        {/* Ambient glow overlay */}
        <div className="absolute inset-0 bg-hero-glow" aria-hidden="true" />

        <div className="relative mx-auto max-w-7xl px-4 pb-16 pt-16 sm:px-6 md:pb-24 md:pt-20 lg:px-8 lg:pb-28 lg:pt-24">
          <div className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
            {/* Left: Copy + Search */}
            <div>
              <h1 className="text-4xl font-extrabold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
                Understand any{' '}
                <span className="text-gradient-mint">SEC filing</span>{' '}
                in minutes
              </h1>
              <p className="mt-6 max-w-lg text-lg leading-relaxed text-slate-400">
                AI-powered summaries that turn 100-page 10-Ks and 10-Qs into
                clear, decision-ready insights. Financials, risks, and trends —
                all in one place.
              </p>

              {/* CTA buttons */}
              <div className="mt-8 flex flex-wrap items-center gap-4">
                <Link
                  href="/register"
                  className="inline-flex items-center gap-2 rounded-full bg-mint-500 px-7 py-3 text-base font-semibold text-slate-950 shadow-glow-mint transition-all hover:bg-mint-400 hover:shadow-glow-mint-lg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
                >
                  Get Started Free
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <ExampleCtaLink
                  href={EXAMPLE_FILING_ID ? `/filing/${EXAMPLE_FILING_ID}?entry=hero_example` : '/company/AAPL'}
                  placement="hero"
                  className="inline-flex items-center gap-2 rounded-full border border-white/20 px-7 py-3 text-base font-medium text-slate-300 transition-all hover:border-white/40 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
                >
                  See an Example
                </ExampleCtaLink>
              </div>

              {/* Search bar */}
              <div className="mt-10">
                <CompanySearch />
              </div>

              {/* Quick access tickers */}
              <QuickAccessBar />
            </div>

            {/* Right: Product mockup */}
            <div className="hidden lg:block">
              <div className="animate-float">
                <HeroMockup />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════════════════════════════════════════════════════
          SOCIAL PROOF STRIP
          ═══════════════════════════════════════════════════════════ */}
      <SocialProofStrip />

      {/* ═══════════════════════════════════════════════════════════
          HOT FILINGS
          ═══════════════════════════════════════════════════════════ */}
      <section id="hot-filings" className="py-20 sm:py-24">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <div className="mb-8 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-white">
              <span aria-hidden="true">🔥</span> Trending Filings
            </h2>
          </div>
          <Suspense fallback={<HotFilingsSkeleton />}>
            <HotFilings limit={4} />
          </Suspense>
        </div>
      </section>

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
          MARKET MOVERS / TRENDING TICKERS
          ═══════════════════════════════════════════════════════════ */}
      <section id="trending" className="py-20 sm:py-24">
        <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
          <Suspense fallback={<TrendingTickersSkeleton />}>
            <TrendingTickers />
          </Suspense>
        </div>
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
