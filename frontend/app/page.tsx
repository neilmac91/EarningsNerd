'use client'

import { ArrowRight, BarChart3, CheckCircle2, Lock, Sparkles, Target, Users, TrendingUp, Flame } from 'lucide-react'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import CompanySearch from '@/components/CompanySearch'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import HotFilings from '@/components/HotFilings'
import { ThemeToggle } from '@/components/ThemeToggle'

type StockQuote = {
  price?: number | null
  change?: number | null
  change_percent?: number | null
  currency?: string | null
}

type Company = {
  id: number
  ticker: string
  name: string
  exchange?: string | null
  stock_quote?: StockQuote | null
}

// Import getApiUrl from api.ts for consistency
// For server components, we need to handle this differently
const getServerApiUrl = () => {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, '')
  }
  return process.env.NODE_ENV === 'production' 
    ? 'https://api.earningsnerd.io' 
    : 'http://localhost:8000'
}

const API_BASE_URL = getServerApiUrl()

async function fetchFromApi<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        accept: 'application/json',
      },
    })

    if (!response.ok) {
      console.warn(`[home] Failed to fetch ${path}: ${response.status}`)
      return null
    }

    return (await response.json()) as T
  } catch (error) {
    console.warn(`[home] Error fetching ${path}:`, error)
    return null
  }
}

export default function Home() {
  const [trendingCompanies, setTrendingCompanies] = useState<Company[] | null>(null)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [newsletterEmail, setNewsletterEmail] = useState('')
  const [showOnboarding, setShowOnboarding] = useState(false)

  useEffect(() => {
    fetchFromApi<Company[]>('/api/companies/trending?limit=6').then(setTrendingCompanies)
  }, [])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const hasToken = !!window.localStorage.getItem('token')
    const onboardingFlag = window.localStorage.getItem('onboarding')
    if (hasToken && onboardingFlag === '1') {
      setShowOnboarding(true)
    }
  }, [])

  const handleNewsletterSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!newsletterEmail.trim()) return
    const subject = encodeURIComponent('EarningsNerd newsletter')
    const body = encodeURIComponent(`Please add me to the EarningsNerd newsletter: ${newsletterEmail.trim()}`)
    window.location.href = `mailto:hello@earningsnerd.com?subject=${subject}&body=${body}`
    setNewsletterEmail('')
  }

  const handleCloseOnboarding = () => {
    setShowOnboarding(false)
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem('onboarding')
    }
  }

  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 text-gray-900 dark:text-slate-100">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div
          className="absolute -top-40 -left-40 h-[520px] w-[520px] rounded-full bg-primary-500/20 dark:bg-primary-500/20 blur-3xl animate-float"
          style={{ animationDelay: '0s' }}
        />
        <div
          className="absolute top-1/3 right-0 h-[420px] w-[420px] rounded-full bg-purple-500/20 dark:bg-purple-500/20 blur-3xl animate-float"
          style={{ animationDelay: '1s' }}
        />
        <div
          className="absolute bottom-0 left-1/2 h-[360px] w-[360px] -translate-x-1/2 rounded-full bg-blue-500/20 dark:bg-blue-500/20 blur-3xl animate-float"
          style={{ animationDelay: '2s' }}
        />
      </div>

      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-gray-200/60 dark:border-white/5 backdrop-blur-xl bg-white/70 dark:bg-slate-950/70 supports-[backdrop-filter]:bg-white/60 dark:supports-[backdrop-filter]:bg-slate-950/60">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center transition-transform hover:scale-105 duration-200">
            <EarningsNerdLogo
              variant="full"
              iconClassName="h-10 w-10 md:h-12 md:w-12"
              hideTagline
            />
          </Link>

          <nav className="hidden items-center space-x-8 text-sm font-medium text-gray-600 dark:text-slate-400 md:flex">
            <Link href="#product" className="transition-all duration-200 hover:text-gray-900 dark:hover:text-white relative after:absolute after:bottom-0 after:left-0 after:h-[2px] after:w-0 after:bg-gradient-to-r after:from-sky-500 after:to-indigo-500 hover:after:w-full after:transition-all after:duration-300">
              Product
            </Link>
            <Link href="#workflow" className="transition-all duration-200 hover:text-gray-900 dark:hover:text-white relative after:absolute after:bottom-0 after:left-0 after:h-[2px] after:w-0 after:bg-gradient-to-r after:from-sky-500 after:to-indigo-500 hover:after:w-full after:transition-all after:duration-300">
              Workflow
            </Link>
            <Link href="#insights" className="transition-all duration-200 hover:text-gray-900 dark:hover:text-white relative after:absolute after:bottom-0 after:left-0 after:h-[2px] after:w-0 after:bg-gradient-to-r after:from-sky-500 after:to-indigo-500 hover:after:w-full after:transition-all after:duration-300">
              Insights
            </Link>
            <Link href="#pricing" className="transition-all duration-200 hover:text-gray-900 dark:hover:text-white relative after:absolute after:bottom-0 after:left-0 after:h-[2px] after:w-0 after:bg-gradient-to-r after:from-sky-500 after:to-indigo-500 hover:after:w-full after:transition-all after:duration-300">
              Pricing
            </Link>
          </nav>

          <div className="flex items-center space-x-3">
            <ThemeToggle />
            <Link
              href="/login"
              className="hidden text-sm font-medium text-gray-600 dark:text-slate-400 transition-all duration-200 hover:text-gray-900 dark:hover:text-white md:inline-flex px-3 py-2 rounded-lg hover:bg-gray-100/50 dark:hover:bg-white/5"
            >
              Log in
            </Link>
            <Link
              href="/register"
              className="group relative inline-flex items-center rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition-all duration-300 hover:shadow-xl hover:shadow-indigo-500/40 hover:scale-105"
            >
              <span className="relative z-10">Start free trial</span>
              <div className="absolute inset-0 rounded-full bg-gradient-to-r from-sky-400 via-indigo-400 to-purple-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </Link>
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="md:hidden inline-flex items-center justify-center rounded-full border border-gray-200/60 dark:border-white/10 bg-white/70 dark:bg-slate-950/70 p-2 text-gray-700 dark:text-slate-200 shadow-sm"
              aria-label="Open navigation menu"
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-nav"
            >
              <span className="sr-only">Open menu</span>
              <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
          </div>
        </div>
      </header>
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true">
          <div
            className="absolute inset-0 bg-slate-950/40 backdrop-blur-sm"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <div
            id="mobile-nav"
            className="absolute right-4 top-4 w-[calc(100%-2rem)] max-w-sm rounded-3xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-slate-950 p-6 shadow-2xl"
          >
            <div className="flex items-center justify-between">
              <EarningsNerdLogo variant="full" iconClassName="h-9 w-9" hideTagline />
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(false)}
                className="inline-flex items-center justify-center rounded-full border border-gray-200/60 dark:border-white/10 p-2 text-gray-600 dark:text-slate-300"
                aria-label="Close navigation menu"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="6" y1="6" x2="18" y2="18" />
                  <line x1="6" y1="18" x2="18" y2="6" />
                </svg>
              </button>
            </div>

            <div className="mt-6 space-y-4 text-sm font-medium text-gray-700 dark:text-slate-200">
              <Link href="#product" onClick={() => setIsMobileMenuOpen(false)} className="block">
                Product
              </Link>
              <Link href="#workflow" onClick={() => setIsMobileMenuOpen(false)} className="block">
                Workflow
              </Link>
              <Link href="#insights" onClick={() => setIsMobileMenuOpen(false)} className="block">
                Insights
              </Link>
              <Link href="#pricing" onClick={() => setIsMobileMenuOpen(false)} className="block">
                Pricing
              </Link>
            </div>

            <div className="mt-6 space-y-3">
              <Link
                href="/login"
                onClick={() => setIsMobileMenuOpen(false)}
                className="block rounded-full border border-gray-200/60 dark:border-white/10 px-4 py-2 text-center text-sm font-semibold text-gray-700 dark:text-slate-200"
              >
                Log in
              </Link>
              <Link
                href="/register"
                onClick={() => setIsMobileMenuOpen(false)}
                className="block rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-4 py-2 text-center text-sm font-semibold text-white"
              >
                Start free trial
              </Link>
            </div>
          </div>
        </div>
      )}

      {showOnboarding && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/50 px-6 py-10 backdrop-blur-sm">
          <div className="w-full max-w-2xl rounded-3xl border border-white/10 bg-white p-8 shadow-2xl dark:bg-slate-950">
            <div className="flex items-start justify-between gap-6">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-500 dark:text-slate-400">
                  Welcome to EarningsNerd
                </div>
                <h2 className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
                  Your first insight is moments away
                </h2>
                <p className="mt-2 text-sm text-gray-600 dark:text-slate-300">
                  Follow this quick path to generate your first AI summary.
                </p>
              </div>
              <button
                type="button"
                onClick={handleCloseOnboarding}
                className="rounded-full border border-gray-200/60 dark:border-white/10 p-2 text-gray-600 dark:text-slate-300"
                aria-label="Close onboarding"
              >
                ✕
              </button>
            </div>
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {[
                {
                  title: '1. Search a company',
                  detail: 'Use the search bar to pull any ticker or company name.',
                },
                {
                  title: '2. Open a filing',
                  detail: 'Pick a 10-K, 10-Q, or 8-K to analyze.',
                },
                {
                  title: '3. Generate a summary',
                  detail: 'We create an executive-ready brief in minutes.',
                },
              ].map((step) => (
                <div key={step.title} className="rounded-2xl border border-gray-200/60 dark:border-white/10 bg-gray-50 dark:bg-slate-900/60 p-4 text-sm">
                  <div className="font-semibold text-gray-900 dark:text-white">{step.title}</div>
                  <p className="mt-2 text-gray-600 dark:text-slate-300">{step.detail}</p>
                </div>
              ))}
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleCloseOnboarding}
                className="rounded-full bg-gray-900 px-5 py-2 text-sm font-semibold text-white hover:bg-gray-800 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100"
              >
                Start searching
              </button>
              <Link
                href="/pricing"
                onClick={handleCloseOnboarding}
                className="text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-slate-300 dark:hover:text-white"
              >
                Review plans
              </Link>
            </div>
          </div>
        </div>
      )}

      <main>
        {/* Hero with Search Front and Center */}
        <section className="relative mx-auto max-w-6xl px-6 pb-24 pt-24 md:pt-32">
          <div className="text-center mb-16">
            <div className="inline-flex items-center space-x-2 rounded-full bg-gradient-to-r from-sky-50 to-indigo-50 dark:from-white/5 dark:to-white/5 px-5 py-2.5 text-xs font-semibold uppercase tracking-[0.15em] text-sky-600 dark:text-sky-300 ring-1 ring-sky-500/20 dark:ring-white/10 mb-8 backdrop-blur-sm shadow-lg shadow-sky-500/5">
              <Sparkles className="h-4 w-4 animate-pulse" />
              <span>Purpose-built for financial teams</span>
            </div>
            <h1 className="text-5xl font-bold leading-[1.1] text-gray-900 dark:text-white sm:text-6xl lg:text-7xl mb-8 tracking-tight">
              Turn dense SEC filings into{' '}
              <span className="bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 bg-clip-text text-transparent">
                actionable intelligence
              </span>
            </h1>
            <p className="text-xl text-gray-600 dark:text-slate-300 max-w-3xl mx-auto leading-relaxed font-light">
              EarningsNerd blends institutional-grade data, expert prompts, and investor workflows to surface the <span className="font-medium text-gray-900 dark:text-white">why</span> behind every metric, not just the what.
            </p>
          </div>

          {/* Search Front and Center */}
          <div className="mx-auto max-w-3xl">
            <div className="group relative rounded-3xl border border-gray-200/60 dark:border-white/10 bg-white/80 dark:bg-white/5 p-10 shadow-2xl shadow-gray-900/10 dark:shadow-black/30 backdrop-blur-xl transition-all duration-500 hover:shadow-3xl hover:shadow-gray-900/15 dark:hover:shadow-black/40 hover:border-gray-300/60 dark:hover:border-white/20">
              <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-sky-500/5 via-indigo-500/5 to-purple-500/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              <div className="relative">
                <h2 className="text-3xl font-bold text-gray-900 dark:text-white text-center mb-4 tracking-tight">
                  Find a company
                </h2>
                <p className="text-center text-base text-gray-600 dark:text-slate-400 mb-8 font-light">
                  Search tickers, names, or exchanges to pull the latest filings instantly.
                </p>
                <div className="rounded-2xl bg-gray-50/50 dark:bg-slate-900/30 p-5 shadow-inner ring-1 ring-gray-200/50 dark:ring-white/5">
                  <CompanySearch />
                </div>
                <div className="mt-7 flex items-start space-x-4 rounded-2xl bg-gradient-to-br from-sky-50/50 to-indigo-50/50 dark:from-white/5 dark:to-white/5 p-5 text-sm text-gray-700 dark:text-slate-200 ring-1 ring-sky-500/10 dark:ring-white/5">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-500 dark:text-sky-400 flex-shrink-0" />
                  <p className="leading-relaxed">
                    We fetch filings directly from the SEC, run multi-step parsing, and deliver investor-grade summaries that surface catalysts, risks, and trend lines.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Stats below search */}
          <div className="mt-16 grid gap-8 sm:grid-cols-2 max-w-4xl mx-auto">
            <div className="group relative overflow-hidden rounded-3xl border border-gray-200/60 dark:border-white/10 bg-gradient-to-br from-white to-gray-50/30 dark:from-white/5 dark:to-white/5 p-8 shadow-xl shadow-sky-500/10 transition-all duration-300 hover:shadow-2xl hover:shadow-sky-500/20 hover:scale-105">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-sky-500/10 to-transparent rounded-full blur-2xl" />
              <div className="relative">
                <div className="text-5xl font-bold bg-gradient-to-r from-sky-600 to-indigo-600 dark:from-sky-400 dark:to-indigo-400 bg-clip-text text-transparent mb-3">
                  92%
                </div>
                <p className="text-base text-gray-700 dark:text-slate-300 leading-relaxed font-light">
                  Average time saved reviewing quarterly filings across our customer base.
                </p>
                <p className="mt-2 text-xs uppercase tracking-wider text-gray-500 dark:text-slate-400">
                  Based on 2024 customer survey
                </p>
              </div>
            </div>
            <div className="group relative overflow-hidden rounded-3xl border border-gray-200/60 dark:border-white/10 bg-gradient-to-br from-white to-purple-50/30 dark:from-white/5 dark:to-white/5 p-8 shadow-xl shadow-purple-500/10 transition-all duration-300 hover:shadow-2xl hover:shadow-purple-500/20 hover:scale-105">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-purple-500/10 to-transparent rounded-full blur-2xl" />
              <div className="relative">
                <div className="text-5xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 dark:from-indigo-400 dark:to-purple-400 bg-clip-text text-transparent mb-3">
                  18k+
                </div>
                <p className="text-base text-gray-700 dark:text-slate-300 leading-relaxed font-light">
                  Summaries generated for public companies, powered by audited SEC source data.
                </p>
                <p className="mt-2 text-xs uppercase tracking-wider text-gray-500 dark:text-slate-400">
                  Since launch in 2023
                </p>
              </div>
            </div>
          </div>

          <div className="mt-14 flex flex-wrap items-center justify-center gap-5">
            <Link
              href="/register"
              className="group relative inline-flex items-center rounded-full bg-gradient-to-r from-gray-900 to-gray-800 dark:from-white dark:to-gray-100 px-8 py-4 text-base font-semibold text-white dark:text-gray-900 shadow-xl shadow-gray-900/30 dark:shadow-white/20 transition-all duration-300 hover:shadow-2xl hover:shadow-gray-900/40 dark:hover:shadow-white/30 hover:scale-105"
            >
              <span>Start transforming filings</span>
              <ArrowRight className="ml-2 h-5 w-5 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="#workflow"
              className="inline-flex items-center text-base font-medium text-gray-600 dark:text-slate-300 transition-all duration-200 hover:text-gray-900 dark:hover:text-white group px-4 py-4"
            >
              <span>See how it works</span>
              <ArrowRight className="ml-2 h-5 w-5 opacity-50 transition-all group-hover:opacity-100 group-hover:translate-x-1" />
            </Link>
          </div>
        </section>

        {/* Trending Companies & Recent Filings */}
        <section className="border-y border-gray-200/50 dark:border-white/5 bg-gradient-to-b from-gray-50/80 via-white/50 to-gray-50/80 dark:from-slate-900/30 dark:via-transparent dark:to-slate-900/30">
          <div className="mx-auto max-w-7xl px-6 py-20">
            <div className="grid lg:grid-cols-2 gap-10">
              {/* Trending Companies */}
              <div>
                <div className="flex items-center space-x-3 mb-6">
                  <div className="rounded-xl bg-gradient-to-br from-sky-500 to-indigo-500 p-2.5 shadow-lg shadow-sky-500/30">
                    <TrendingUp className="h-5 w-5 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">Trending Companies</h3>
                </div>
                {trendingCompanies && trendingCompanies.length > 0 ? (
                  <div className="space-y-3">
                    {trendingCompanies.map((company: Company) => (
                      <Link
                        key={company.id}
                        href={`/company/${company.ticker}`}
                        className="group block p-5 rounded-2xl bg-white dark:bg-white/5 hover:bg-gradient-to-br hover:from-white hover:to-gray-50/50 dark:hover:from-white/10 dark:hover:to-white/5 transition-all duration-300 border border-gray-200/60 dark:border-white/10 hover:border-gray-300 dark:hover:border-white/20 hover:shadow-lg hover:shadow-gray-900/5 dark:hover:shadow-black/20"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-semibold text-gray-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                              {company.name}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-slate-400 font-medium mt-1">
                              {company.ticker}
                            </div>
                          </div>
                          {company.stock_quote?.price !== undefined && company.stock_quote?.price !== null && (
                            <div className="text-right">
                              <div className="text-gray-900 dark:text-white font-bold text-lg">
                                {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                              </div>
                              {company.stock_quote.change_percent !== undefined && company.stock_quote.change_percent !== null && (
                                <div className={`text-sm font-semibold mt-1 ${
                                  company.stock_quote.change_percent >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                                }`}>
                                  {fmtPercent(company.stock_quote.change_percent, { digits: 2, signed: true })}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-2xl bg-white/50 dark:bg-white/5 p-8 text-center border border-gray-200/60 dark:border-white/10">
                    <p className="text-gray-500 dark:text-slate-400 text-sm">Trending companies will load once the API responds.</p>
                  </div>
                )}
              </div>

              {/* Hot Filings */}
              <div>
                <div className="flex items-center space-x-3 mb-6">
                  <div className="rounded-xl bg-gradient-to-br from-orange-500 to-red-500 p-2.5 shadow-lg shadow-orange-500/30">
                    <Flame className="h-5 w-5 text-white" />
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">Hot Filings</h3>
                </div>
                <HotFilings limit={8} />
              </div>
            </div>
          </div>
        </section>

        {/* Product value */}
        <section id="product" className="mx-auto max-w-7xl px-6 py-28">
          <div className="grid gap-16 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <div className="inline-block mb-6">
                <span className="rounded-full bg-gradient-to-r from-sky-500/10 to-indigo-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-sky-600 dark:text-sky-400 ring-1 ring-sky-500/20">
                  Product
                </span>
              </div>
              <h2 className="text-4xl font-bold text-gray-900 dark:text-white sm:text-5xl leading-tight tracking-tight mb-6">
                Every summary delivers the what, the why, and the{' '}
                <span className="bg-gradient-to-r from-sky-500 to-indigo-500 bg-clip-text text-transparent">
                  so what
                </span>
              </h2>
              <p className="mt-4 text-base text-gray-600 dark:text-slate-300">
                We combine large language models with EarningsNerds proprietary financial taxonomy to highlight strategic shifts, management tone, and emerging risks. No filler, no vague AI-speakjust the narrative investors care about.
              </p>

              <div className="mt-12 grid gap-6 sm:grid-cols-2">
                <div className="group rounded-2xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-white/5 p-7 transition-all duration-300 hover:shadow-xl hover:shadow-sky-500/10 hover:border-sky-500/30 dark:hover:border-sky-500/30 hover:-translate-y-1">
                  <div className="rounded-xl bg-gradient-to-br from-sky-500 to-sky-600 p-3 w-fit shadow-lg shadow-sky-500/30">
                    <BarChart3 className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="mt-5 text-lg font-bold text-gray-900 dark:text-white">Rich financial context</h3>
                  <p className="mt-3 text-sm text-gray-600 dark:text-slate-300 leading-relaxed">
                    Auto-extract revenue, profitability, cash flow, and segment-level details with year-over-year movement baked in.
                  </p>
                </div>
                <div className="group rounded-2xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-white/5 p-7 transition-all duration-300 hover:shadow-xl hover:shadow-purple-500/10 hover:border-purple-500/30 dark:hover:border-purple-500/30 hover:-translate-y-1">
                  <div className="rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 p-3 w-fit shadow-lg shadow-purple-500/30">
                    <Target className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="mt-5 text-lg font-bold text-gray-900 dark:text-white">Catalysts & watch items</h3>
                  <p className="mt-3 text-sm text-gray-600 dark:text-slate-300 leading-relaxed">
                    Surface forward guidance, regulatory changes, and management priorities so you can act before the market does.
                  </p>
                </div>
                <div className="group rounded-2xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-white/5 p-7 transition-all duration-300 hover:shadow-xl hover:shadow-amber-500/10 hover:border-amber-500/30 dark:hover:border-amber-500/30 hover:-translate-y-1">
                  <div className="rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 p-3 w-fit shadow-lg shadow-amber-500/30">
                    <Users className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="mt-5 text-lg font-bold text-gray-900 dark:text-white">Built for collaboration</h3>
                  <p className="mt-3 text-sm text-gray-600 dark:text-slate-300 leading-relaxed">
                    Share summaries, annotate insights, and integrate with existing diligence workflows or CRM tools.
                  </p>
                </div>
                <div className="group rounded-2xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-white/5 p-7 transition-all duration-300 hover:shadow-xl hover:shadow-emerald-500/10 hover:border-emerald-500/30 dark:hover:border-emerald-500/30 hover:-translate-y-1">
                  <div className="rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 p-3 w-fit shadow-lg shadow-emerald-500/30">
                    <Lock className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="mt-5 text-lg font-bold text-gray-900 dark:text-white">Data you can trust</h3>
                  <p className="mt-3 text-sm text-gray-600 dark:text-slate-300 leading-relaxed">
                    SEC-sourced filings, transparent citations, and audit trails baked into every summary.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex flex-col justify-between rounded-3xl border border-gray-200 dark:border-white/10 bg-white dark:bg-white/5 p-6 shadow-[0_18px_45px_rgba(0,0,0,0.1)] dark:shadow-[0_18px_45px_rgba(15,23,42,0.35)]">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">A summary that reads like your lead analyst wrote it</h3>
                <p className="mt-3 text-sm text-gray-600 dark:text-slate-300">
                  Executive-ready overviews, granular financial tables, and a risk register geared towards portfolio decisions.
                </p>
              </div>
              <div className="mt-6 space-y-4 rounded-2xl bg-gray-100 dark:bg-slate-900/50 p-5 text-sm text-gray-700 dark:text-slate-300">
                <div className="flex items-start space-x-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-500 dark:text-sky-400" />
                  <p>Automated extraction of revenue, EPS, FCF, segment mix, and margin drivers.</p>
                </div>
                <div className="flex items-start space-x-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-500 dark:text-sky-400" />
                  <p>Management tone analysis with quotes that support every headline.</p>
                </div>
                <div className="flex items-start space-x-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-500 dark:text-sky-400" />
                  <p>Guidance, capital allocation, and liquidity signals mapped to investment implications.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Workflow */}
        <section id="workflow" className="border-t border-gray-200/50 dark:border-white/10 bg-gradient-to-b from-gray-50/80 via-white/50 to-gray-50/80 dark:from-slate-900/30 dark:via-transparent dark:to-slate-900/30">
          <div className="mx-auto max-w-7xl px-6 py-28">
            <div className="text-center mb-6">
              <span className="inline-block rounded-full bg-gradient-to-r from-sky-500/10 to-indigo-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-sky-600 dark:text-sky-400 ring-1 ring-sky-500/20">
                Workflow
              </span>
            </div>
            <h2 className="text-center text-4xl font-bold text-gray-900 dark:text-white sm:text-5xl tracking-tight">
              A workflow that keeps analysts in{' '}
              <span className="bg-gradient-to-r from-sky-500 to-indigo-500 bg-clip-text text-transparent">
                flow state
              </span>
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-center text-base text-gray-600 dark:text-slate-300">
              EarningsNerd orchestrates the entire filing review pipelinefrom ingestion to insightso your team spends time on strategy, not copy-paste.
            </p>

            <div className="mt-16 grid gap-8 md:grid-cols-3">
              {[
                {
                  title: 'Ingest & parse',
                  description: 'We pull 10-Ks, 10-Qs, and 8-Ks minutes after they hit EDGAR, normalize the text, and extract tables automatically.'
                },
                {
                  title: 'Analyze & prioritize',
                  description: 'Our financial taxonomy highlights the sections and metrics that matter: revenue drivers, segment shifts, capex, and risk deviations.'
                },
                {
                  title: 'Summarize & act',
                  description: 'Receive a clean narrative, trend table, and watch list you can paste into investment memos, send to clients, or drop into Slack.'
                }
              ].map((step, index) => (
                <div key={step.title} className="group relative overflow-hidden rounded-3xl border border-gray-200/60 dark:border-white/10 bg-white dark:bg-slate-900/60 p-10 transition-all duration-300 hover:shadow-2xl hover:shadow-gray-900/10 dark:hover:shadow-black/30 hover:border-sky-500/30 dark:hover:border-sky-500/30 hover:-translate-y-2">
                  <div className="absolute inset-0 bg-gradient-to-br from-sky-50/50 via-indigo-50/30 to-transparent dark:from-sky-500/5 dark:via-indigo-500/5 dark:to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
                  <div className="relative">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-indigo-500 text-lg font-bold text-white shadow-lg shadow-sky-500/30">
                      0{index + 1}
                    </div>
                    <h3 className="mt-8 text-xl font-bold text-gray-900 dark:text-white">{step.title}</h3>
                    <p className="mt-4 text-base text-gray-600 dark:text-slate-300 leading-relaxed">{step.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Insights/Testimonials */}
        <section id="insights" className="mx-auto max-w-7xl px-6 py-28">
          <div className="grid gap-12 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-3xl border border-gray-200/60 dark:border-white/10 bg-gradient-to-br from-white to-gray-50/30 dark:from-white/5 dark:to-white/5 p-10 shadow-xl shadow-gray-900/5 dark:shadow-black/20">
              <div className="inline-block mb-6">
                <span className="rounded-full bg-gradient-to-r from-sky-500/10 to-indigo-500/10 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-sky-600 dark:text-sky-400 ring-1 ring-sky-500/20">
                  Insights
                </span>
              </div>
              <h3 className="text-3xl font-bold text-gray-900 dark:text-white tracking-tight">What teams ship with EarningsNerd</h3>
              <div className="mt-8 space-y-8 text-base text-gray-600 dark:text-slate-300">
                <div>
                  <span className="text-gray-900 dark:text-white font-semibold">Research Directors</span> deliver pre-market briefings that go beyond headline numbers, complete with management sentiment and strategic commentary.
                </div>
                <div>
                  <span className="text-gray-900 dark:text-white font-semibold">Investor Relations</span> teams align messaging with what investors actually care about by monitoring competitor filings effortlessly.
                </div>
                <div>
                  <span className="text-gray-900 dark:text-white font-semibold">Corporate Strategy</span> leaders prioritize initiatives faster with visibility into capital allocation and regional performance.
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="group rounded-3xl border border-gray-200/60 dark:border-white/10 bg-gradient-to-br from-gray-50 to-white dark:from-slate-900/70 dark:to-slate-900/50 p-8 shadow-lg shadow-gray-900/5 dark:shadow-black/20 transition-all duration-300 hover:shadow-xl hover:shadow-sky-500/10 hover:-translate-y-1">
                <p className="text-lg text-gray-900 dark:text-slate-100 leading-relaxed font-light italic">
                  "Our analysts extract what matters from filings in minutes, not hours. EarningsNerd captures management nuance and surfaces the signals we use to rebalance portfolios."
                </p>
                <div className="mt-6 flex items-center space-x-3">
                  <div className="h-px flex-1 bg-gradient-to-r from-gray-300 to-transparent dark:from-white/10"></div>
                  <div className="text-sm font-medium text-gray-700 dark:text-slate-300">Director of Research, Multi-strategy hedge fund</div>
                </div>
              </div>
              <div className="group rounded-3xl border border-gray-200/60 dark:border-white/10 bg-gradient-to-br from-white to-gray-50 dark:from-slate-900/50 dark:to-slate-900/70 p-8 shadow-lg shadow-gray-900/5 dark:shadow-black/20 transition-all duration-300 hover:shadow-xl hover:shadow-purple-500/10 hover:-translate-y-1">
                <p className="text-lg text-gray-900 dark:text-slate-100 leading-relaxed font-light italic">
                  "The structured summary means we never miss guidance shifts or hidden risk language. It has become the daily briefing our partners expect."
                </p>
                <div className="mt-6 flex items-center space-x-3">
                  <div className="h-px flex-1 bg-gradient-to-r from-gray-300 to-transparent dark:from-white/10"></div>
                  <div className="text-sm font-medium text-gray-700 dark:text-slate-300">Principal, Growth Equity firm</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing CTA */}
        <section id="pricing" className="relative border-t border-gray-200/50 dark:border-white/10 bg-gradient-to-br from-gray-50 via-white to-gray-50 dark:from-slate-900 dark:via-slate-950 dark:to-slate-900 overflow-hidden">
          <div className="absolute inset-0 bg-grid-gray-200/50 dark:bg-grid-white/5 [mask-image:radial-gradient(white,transparent_70%)]" style={{ backgroundSize: '30px 30px', backgroundImage: 'linear-gradient(to right, rgb(229 231 235 / 0.3) 1px, transparent 1px), linear-gradient(to bottom, rgb(229 231 235 / 0.3) 1px, transparent 1px)' }}></div>
          <div className="relative mx-auto flex max-w-4xl flex-col items-center gap-8 px-6 py-24 text-center">
            <span className="rounded-full border border-sky-500/20 dark:border-white/10 bg-gradient-to-r from-sky-50 to-indigo-50 dark:from-white/5 dark:to-white/5 px-5 py-2 text-xs font-semibold uppercase tracking-wider text-sky-600 dark:text-sky-300 shadow-lg shadow-sky-500/10">
              Pricing
            </span>
            <h2 className="text-4xl font-bold text-gray-900 dark:text-white sm:text-5xl tracking-tight leading-tight">
              Flexible plans for funds, IR, and{' '}
              <span className="bg-gradient-to-r from-sky-500 to-indigo-500 bg-clip-text text-transparent">
                strategy teams
              </span>
            </h2>
            <p className="max-w-2xl text-lg text-gray-600 dark:text-slate-300 leading-relaxed font-light">
              Start free, then scale with real-time alerts, CRM integrations, and custom governance. Our customer team builds the perfect bundle for your workflow.
            </p>
            <div className="mt-8 grid w-full gap-6 md:grid-cols-2">
              <div className="rounded-3xl border border-gray-200/60 dark:border-white/10 bg-white/80 dark:bg-white/5 p-6 text-left shadow-lg shadow-gray-900/5">
                <div className="text-sm font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-400">Free</div>
                <div className="mt-2 text-4xl font-bold text-gray-900 dark:text-white">$0</div>
                <div className="text-sm text-gray-500 dark:text-slate-400">per month</div>
                <ul className="mt-5 space-y-3 text-sm text-gray-600 dark:text-slate-300">
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-sky-500" />
                    5 summaries per month
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-sky-500" />
                    Company search + filing access
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-sky-500" />
                    Basic AI summary
                  </li>
                </ul>
              </div>
              <div className="rounded-3xl border border-indigo-500/40 bg-gradient-to-br from-slate-900 to-slate-950 p-6 text-left shadow-xl shadow-indigo-500/20">
                <div className="text-sm font-semibold uppercase tracking-wider text-indigo-200">Pro</div>
                <div className="mt-2 text-4xl font-bold text-white">$19</div>
                <div className="text-sm text-indigo-200">per month</div>
                <ul className="mt-5 space-y-3 text-sm text-indigo-100">
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-indigo-300" />
                    Unlimited summaries + exports
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-indigo-300" />
                    Multi-year comparisons
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 text-indigo-300" />
                    Priority support
                  </li>
                </ul>
              </div>
            </div>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-5">
              <Link
                href="/pricing"
                className="group relative inline-flex items-center rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-8 py-4 text-base font-semibold text-white shadow-2xl shadow-indigo-500/40 transition-all duration-300 hover:shadow-3xl hover:shadow-indigo-500/50 hover:scale-105"
              >
                <span className="relative z-10">Compare plans</span>
                <div className="absolute inset-0 rounded-full bg-gradient-to-r from-sky-400 via-indigo-400 to-purple-400 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              </Link>
              <Link
                href="mailto:hello@earningsnerd.com"
                className="inline-flex items-center rounded-full border-2 border-gray-300 dark:border-white/20 px-8 py-4 text-base font-semibold text-gray-900 dark:text-white transition-all duration-300 hover:bg-gray-900 hover:text-white dark:hover:bg-white dark:hover:text-gray-900 hover:scale-105"
              >
                Talk to sales
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-gray-200/50 dark:border-white/10 bg-gradient-to-b from-gray-50 to-white dark:from-slate-950/60 dark:to-slate-950">
        <div className="mx-auto max-w-7xl px-6 py-14">
          <div className="grid gap-10 lg:grid-cols-[1.2fr_2fr]">
            <div>
              <EarningsNerdLogo variant="full" iconClassName="h-10 w-10" hideTagline />
              <p className="mt-4 text-sm text-gray-600 dark:text-slate-400 leading-relaxed">
                AI earnings intelligence for funds, IR teams, and strategy leaders who want instant clarity on SEC filings.
              </p>
            </div>
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-3 text-sm text-gray-600 dark:text-slate-400">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-500">Product</div>
                <Link href="/pricing" className="block hover:text-gray-900 dark:hover:text-white">Pricing</Link>
                <Link href="/compare" className="block hover:text-gray-900 dark:hover:text-white">Compare filings</Link>
                <Link href="/dashboard" className="block hover:text-gray-900 dark:hover:text-white">Dashboard</Link>
                <Link href="/security" className="block hover:text-gray-900 dark:hover:text-white">Security</Link>
              </div>
              <div className="space-y-3 text-sm text-gray-600 dark:text-slate-400">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-500">Company</div>
                <Link href="/#insights" className="block hover:text-gray-900 dark:hover:text-white">Customer stories</Link>
                <Link href="mailto:hello@earningsnerd.com" className="block hover:text-gray-900 dark:hover:text-white">Contact</Link>
                <Link href="mailto:hello@earningsnerd.com?subject=Partnerships" className="block hover:text-gray-900 dark:hover:text-white">Partnerships</Link>
                <Link href="mailto:hello@earningsnerd.com?subject=Careers" className="block hover:text-gray-900 dark:hover:text-white">Careers</Link>
              </div>
              <div className="space-y-3 text-sm text-gray-600 dark:text-slate-400">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-500">Resources</div>
                <Link href="/#product" className="block hover:text-gray-900 dark:hover:text-white">Product tour</Link>
                <Link href="/#workflow" className="block hover:text-gray-900 dark:hover:text-white">Workflow</Link>
                <Link href="/#pricing" className="block hover:text-gray-900 dark:hover:text-white">Plan guide</Link>
                <Link href="mailto:hello@earningsnerd.com?subject=Support" className="block hover:text-gray-900 dark:hover:text-white">Support</Link>
              </div>
              <div className="space-y-3 text-sm text-gray-600 dark:text-slate-400">
                <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-slate-500">Legal</div>
                <Link href="/privacy" className="block hover:text-gray-900 dark:hover:text-white">Privacy</Link>
                <Link href="/security" className="block hover:text-gray-900 dark:hover:text-white">Security</Link>
                <Link href="mailto:hello@earningsnerd.com?subject=Compliance" className="block hover:text-gray-900 dark:hover:text-white">Compliance</Link>
              </div>
            </div>
          </div>

          <div className="mt-12 flex flex-col items-start gap-6 rounded-3xl border border-gray-200/60 dark:border-white/10 bg-white/80 dark:bg-white/5 p-6 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white">Get weekly earnings intelligence</div>
              <p className="mt-1 text-sm text-gray-600 dark:text-slate-400">
                Join the digest for new filings, risk shifts, and catalyst alerts.
              </p>
            </div>
            <form onSubmit={handleNewsletterSubmit} className="flex w-full max-w-md flex-col gap-3 sm:flex-row">
              <input
                type="email"
                value={newsletterEmail}
                onChange={(event) => setNewsletterEmail(event.target.value)}
                placeholder="you@fund.com"
                className="w-full flex-1 rounded-full border border-gray-200/60 dark:border-white/10 bg-white dark:bg-slate-950 px-4 py-3 text-sm text-gray-900 dark:text-white placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-sky-500"
                required
              />
              <button
                type="submit"
                className="rounded-full bg-gray-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-gray-800 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-100"
              >
                Join digest
              </button>
            </form>
          </div>

          <div className="mt-10 flex flex-col gap-4 text-xs text-gray-500 dark:text-slate-500 sm:flex-row sm:items-center sm:justify-between">
            <div>&copy; {new Date().getFullYear()} EarningsNerd. All rights reserved.</div>
            <div className="flex flex-wrap items-center gap-6">
              <span>Built on SEC EDGAR data</span>
              <span>Secure payments via Stripe</span>
              <span>Customer-first support</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

