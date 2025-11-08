import { ArrowRight, BarChart3, CheckCircle2, Lock, Sparkles, Target, Users, TrendingUp, Flame } from 'lucide-react'
import Link from 'next/link'
import CompanySearch from '@/components/CompanySearch'
import EinsteinLogo from '@/components/EinsteinLogo'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import HotFilings from '@/components/HotFilings'

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? 'http://localhost:8000'

async function fetchFromApi<T>(path: string, revalidate = 120): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      next: { revalidate },
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

export default async function Home() {
  const trendingCompanies = await fetchFromApi<Company[]>('/api/companies/trending?limit=6', 180)

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-[520px] w-[520px] rounded-full bg-primary-500/10 blur-3xl" />
        <div className="absolute top-1/3 right-0 h-[420px] w-[420px] rounded-full bg-purple-500/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 h-[360px] w-[360px] -translate-x-1/2 rounded-full bg-blue-500/10 blur-3xl" />
      </div>

      {/* Header */}
      <header className="border-b border-white/10 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-5">
          <Link href="/" className="flex items-center space-x-3">
            <div className="relative">
              <EinsteinLogo className="h-12 w-12 drop-shadow-[0_0_12px_rgba(79,70,229,0.35)]" />
              <div className="absolute -top-1 -right-1 h-3 w-3 animate-pulse rounded-full bg-gradient-to-r from-primary-400 to-sky-400" />
            </div>
            <div>
              <span className="block text-lg font-semibold tracking-widest text-slate-300">EARNINGS</span>
              <span className="bg-gradient-to-r from-sky-400 via-blue-400 to-purple-400 bg-clip-text text-xl font-bold text-transparent">NERD</span>
            </div>
          </Link>

          <nav className="hidden items-center space-x-10 text-sm font-medium text-slate-300 md:flex">
            <Link href="#product" className="transition hover:text-white">Product</Link>
            <Link href="#workflow" className="transition hover:text-white">Workflow</Link>
            <Link href="#insights" className="transition hover:text-white">Insights</Link>
            <Link href="#pricing" className="transition hover:text-white">Pricing</Link>
          </nav>

          <div className="flex items-center space-x-4">
            <Link
              href="/login"
              className="hidden text-sm font-medium text-slate-300 transition hover:text-white md:inline-flex"
            >
              Log in
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center rounded-full bg-gradient-to-r from-sky-500 via-indigo-500 to-purple-500 px-5 py-2 text-sm font-semibold text-white shadow-[0_10px_30px_rgba(79,70,229,0.3)] transition hover:brightness-110"
            >
              Start free trial
            </Link>
          </div>
        </div>
      </header>

      <main>
        {/* Hero with Search Front and Center */}
        <section className="relative mx-auto max-w-5xl px-6 pb-20 pt-20">
          <div className="text-center mb-12">
            <div className="inline-flex items-center space-x-2 rounded-full bg-white/5 px-4 py-2 text-xs uppercase tracking-[0.2em] text-sky-300 ring-1 ring-white/10 mb-6">
              <Sparkles className="h-4 w-4" />
              <span>Purpose-built for financial teams</span>
            </div>
            <h1 className="text-4xl font-semibold leading-tight text-white sm:text-5xl lg:text-6xl mb-6">
              Turn dense SEC filings into actionable intelligence
            </h1>
            <p className="text-lg text-slate-300 max-w-2xl mx-auto">
              EarningsNerd blends institutional-grade data, expert prompts, and investor workflows to surface the why behind every metric, not just the what.
            </p>
          </div>

          {/* Search Front and Center */}
          <div className="mx-auto max-w-2xl">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-8 shadow-[0_20px_60px_rgba(15,23,42,0.45)] backdrop-blur">
              <h2 className="text-2xl font-semibold text-white text-center mb-3">Find a company</h2>
              <p className="text-center text-sm text-slate-300 mb-6">
                Search tickers, names, or exchanges to pull the latest filings instantly.
              </p>
              <div className="rounded-2xl bg-white p-4 shadow-inner">
                <CompanySearch />
              </div>
              <div className="mt-6 flex items-start space-x-3 rounded-2xl bg-white/5 p-4 text-sm text-slate-200">
                <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-400 flex-shrink-0" />
                <p>
                  We fetch filings directly from the SEC, run multi-step parsing, and deliver investor-grade summaries that surface catalysts, risks, and trend lines.
                </p>
              </div>
            </div>
          </div>

          {/* Stats below search */}
          <div className="mt-12 grid gap-6 sm:grid-cols-2 max-w-3xl mx-auto">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-sky-500/10">
              <div className="text-3xl font-semibold text-white">92%</div>
              <p className="mt-2 text-sm text-slate-300">Average time saved reviewing quarterly filings across our customer base.</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 shadow-lg shadow-purple-500/10">
              <div className="text-3xl font-semibold text-white"><span className="text-sky-400">18k+</span></div>
              <p className="mt-2 text-sm text-slate-300">Summaries generated for public companies, powered by audited SEC source data.</p>
            </div>
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/register"
              className="inline-flex items-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow-[0_15px_35px_rgba(15,23,42,0.25)] transition hover:bg-slate-100"
            >
              Start transforming filings
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
            <Link
              href="#workflow"
              className="inline-flex items-center text-sm font-medium text-slate-300 transition hover:text-white"
            >
              See how it works
            </Link>
          </div>
        </section>

        {/* Trending Companies & Recent Filings */}
        <section className="border-y border-white/5 bg-white/5">
          <div className="mx-auto max-w-6xl px-6 py-12">
            <div className="grid md:grid-cols-2 gap-8">
              {/* Trending Companies */}
              <div>
                <div className="flex items-center space-x-2 mb-4">
                  <TrendingUp className="h-5 w-5 text-sky-400" />
                  <h3 className="text-lg font-semibold text-white">Trending Companies</h3>
                </div>
                {trendingCompanies && trendingCompanies.length > 0 ? (
                  <div className="space-y-2">
                    {trendingCompanies.map((company: Company) => (
                      <Link
                        key={company.id}
                        href={`/company/${company.ticker}`}
                        className="block p-3 rounded-lg bg-white/5 hover:bg-white/10 transition-colors border border-white/10"
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-medium text-white">{company.name}</div>
                            <div className="text-sm text-slate-400">{company.ticker}</div>
                          </div>
                          {company.stock_quote?.price !== undefined && company.stock_quote?.price !== null && (
                            <div className="text-right">
                              <div className="text-white font-semibold">
                                {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                              </div>
                              {company.stock_quote.change_percent !== undefined && company.stock_quote.change_percent !== null && (
                                <div className={`text-sm ${
                                  company.stock_quote.change_percent >= 0 ? 'text-green-400' : 'text-red-400'
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
                  <p className="text-slate-400 text-sm">Trending companies will load once the API responds.</p>
                )}
              </div>

              {/* Hot Filings */}
              <div>
                <div className="flex items-center space-x-2 mb-4">
                  <Flame className="h-5 w-5 text-orange-400" />
                  <h3 className="text-lg font-semibold text-white">🔥 Hot Filings</h3>
                </div>
                <HotFilings limit={8} />
              </div>
            </div>
          </div>
        </section>

        {/* Product value */}
        <section id="product" className="mx-auto max-w-6xl px-6 py-20">
          <div className="grid gap-10 lg:grid-cols-[1.2fr_1fr]">
            <div>
              <h2 className="text-3xl font-semibold text-white sm:text-4xl">Every summary delivers the what, the why, and the so what.</h2>
              <p className="mt-4 text-base text-slate-300">
                We combine large language models with EarningsNerds proprietary financial taxonomy to highlight strategic shifts, management tone, and emerging risks. No filler, no vague AI-speakjust the narrative investors care about.
              </p>

              <div className="mt-10 grid gap-6 sm:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                  <BarChart3 className="h-8 w-8 text-sky-400" />
                  <h3 className="mt-4 text-lg font-semibold text-white">Rich financial context</h3>
                  <p className="mt-2 text-sm text-slate-300">
                    Auto-extract revenue, profitability, cash flow, and segment-level details with year-over-year movement baked in.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                  <Target className="h-8 w-8 text-purple-400" />
                  <h3 className="mt-4 text-lg font-semibold text-white">Catalysts & watch items</h3>
                  <p className="mt-2 text-sm text-slate-300">
                    Surface forward guidance, regulatory changes, and management priorities so you can act before the market does.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                  <Users className="h-8 w-8 text-amber-400" />
                  <h3 className="mt-4 text-lg font-semibold text-white">Built for collaboration</h3>
                  <p className="mt-2 text-sm text-slate-300">
                    Share summaries, annotate insights, and integrate with existing diligence workflows or CRM tools.
                  </p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
                  <Lock className="h-8 w-8 text-emerald-400" />
                  <h3 className="mt-4 text-lg font-semibold text-white">Data you can trust</h3>
                  <p className="mt-2 text-sm text-slate-300">
                    SEC-sourced filings, transparent citations, and audit trails baked into every summary.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex flex-col justify-between rounded-3xl border border-white/10 bg-white/5 p-6 shadow-[0_18px_45px_rgba(15,23,42,0.35)]">
              <div>
                <h3 className="text-lg font-semibold text-white">A summary that reads like your lead analyst wrote it</h3>
                <p className="mt-3 text-sm text-slate-300">
                  Executive-ready overviews, granular financial tables, and a risk register geared towards portfolio decisions.
                </p>
              </div>
              <div className="mt-6 space-y-4 rounded-2xl bg-slate-900/50 p-5 text-sm text-slate-300">
                <div className="flex items-start space-x-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-400" />
                  <p>Automated extraction of revenue, EPS, FCF, segment mix, and margin drivers.</p>
                </div>
                <div className="flex items-start space-x-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-400" />
                  <p>Management tone analysis with quotes that support every headline.</p>
                </div>
                <div className="flex items-start space-x-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 text-sky-400" />
                  <p>Guidance, capital allocation, and liquidity signals mapped to investment implications.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Workflow */}
        <section id="workflow" className="border-t border-white/10 bg-white/5">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-center text-3xl font-semibold text-white sm:text-4xl">A workflow that keeps analysts in flow state</h2>
            <p className="mx-auto mt-4 max-w-2xl text-center text-base text-slate-300">
              EarningsNerd orchestrates the entire filing review pipelinefrom ingestion to insightso your team spends time on strategy, not copy-paste.
            </p>

            <div className="mt-12 grid gap-6 md:grid-cols-3">
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
                <div key={step.title} className="group relative overflow-hidden rounded-3xl border border-white/10 bg-slate-900/60 p-8">
                  <div className="absolute inset-0 bg-gradient-to-br from-white/5 via-transparent to-transparent opacity-0 transition group-hover:opacity-100" />
                  <div className="relative">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-sm font-semibold text-white">
                      0{index + 1}
                    </div>
                    <h3 className="mt-6 text-lg font-semibold text-white">{step.title}</h3>
                    <p className="mt-3 text-sm text-slate-300">{step.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Insights/Testimonials */}
        <section id="insights" className="mx-auto max-w-6xl px-6 py-20">
          <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-3xl border border-white/10 bg-white/5 p-8">
              <h3 className="text-2xl font-semibold text-white">What teams ship with EarningsNerd</h3>
              <div className="mt-6 space-y-6 text-sm text-slate-300">
                <div>
                  <span className="text-white">Research Directors</span> deliver pre-market briefings that go beyond headline numbers, complete with management sentiment and strategic commentary.
                </div>
                <div>
                  <span className="text-white">Investor Relations</span> teams align messaging with what investors actually care about by monitoring competitor filings effortlessly.
                </div>
                <div>
                  <span className="text-white">Corporate Strategy</span> leaders prioritize initiatives faster with visibility into capital allocation and regional performance.
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-3xl border border-white/10 bg-slate-900/70 p-6">
                <p className="text-lg text-slate-100">
                  “Our analysts extract what matters from filings in minutes, not hours. EarningsNerd captures management nuance and surfaces the signals we use to rebalance portfolios.”
                </p>
                <div className="mt-4 text-sm text-slate-400">Director of Research, Multi-strategy hedge fund</div>
              </div>
              <div className="rounded-3xl border border-white/10 bg-slate-900/50 p-6">
                <p className="text-lg text-slate-100">
                  “The structured summary means we never miss guidance shifts or hidden risk language. It has become the daily briefing our partners expect.”
                </p>
                <div className="mt-4 text-sm text-slate-400">Principal, Growth Equity firm</div>
              </div>
            </div>
          </div>
        </section>

        {/* Pricing CTA */}
        <section id="pricing" className="border-t border-white/10 bg-gradient-to-r from-slate-900 via-slate-950 to-slate-900">
          <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-6 py-16 text-center">
            <span className="rounded-full border border-white/10 bg-white/5 px-4 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-sky-300">
              Pricing
            </span>
            <h2 className="text-3xl font-semibold text-white sm:text-4xl">Flexible plans for funds, IR, and strategy teams</h2>
            <p className="max-w-2xl text-base text-slate-300">
              Start free, then scale with real-time alerts, CRM integrations, and custom governance. Our customer team builds the perfect bundle for your workflow.
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-4">
              <Link
                href="/register"
                className="inline-flex items-center rounded-full bg-white px-6 py-3 text-sm font-semibold text-slate-900 shadow-[0_15px_35px_rgba(15,23,42,0.25)] transition hover:bg-slate-100"
              >
                Compare plans
              </Link>
              <Link
                href="mailto:hello@earningsnerd.com"
                className="inline-flex items-center rounded-full border border-white/20 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Talk to sales
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-white/10 bg-slate-950/60">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-10 text-sm text-slate-400 md:flex-row md:items-center md:justify-between">
          <div>&copy; {new Date().getFullYear()} EarningsNerd. All rights reserved.</div>
          <div className="flex flex-wrap items-center gap-6">
            <Link href="/privacy" className="transition hover:text-white">Privacy</Link>
            <Link href="/security" className="transition hover:text-white">Security</Link>
            <Link href="mailto:hello@earningsnerd.com" className="transition hover:text-white">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

