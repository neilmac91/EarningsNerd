
import { ArrowRight, BarChart3, CheckCircle2, Lock, Sparkles, Target, Users, Flame } from 'lucide-react'
import Link from 'next/link'
import CompanySearch from '@/components/CompanySearch'
import EarningsNerdLogo from '@/components/EarningsNerdLogo'
import HotFilings from '@/components/HotFilings'
import { ThemeToggle } from '@/components/ThemeToggle'
import TrendingCompanies from '@/components/TrendingCompanies'

export default function Home() {
  return (
    <div className="min-h-screen bg-white dark:bg-slate-950 text-gray-900 dark:text-slate-100">
      <div className="absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-40 -left-40 h-[520px] w-[520px] rounded-full bg-primary-500/10 dark:bg-primary-500/10 blur-3xl" />
        <div className="absolute top-1/3 right-0 h-[420px] w-[420px] rounded-full bg-purple-500/10 dark:bg-purple-500/10 blur-3xl" />
        <div className="absolute bottom-0 left-1/2 h-[360px] w-[360px] -translate-x-1/2 rounded-full bg-blue-500/10 dark:bg-blue-500/10 blur-3xl" />
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
          </div>
        </div>
      </header>

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
              <TrendingCompanies />

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
            <div className="mt-6 flex flex-wrap items-center justify-center gap-5">
              <Link
                href="/register"
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
        <div className="mx-auto flex max-w-7xl flex-col gap-8 px-6 py-12 text-sm text-gray-600 dark:text-slate-400 md:flex-row md:items-center md:justify-between">
          <div className="font-medium">&copy; {new Date().getFullYear()} EarningsNerd. All rights reserved.</div>
          <div className="flex flex-wrap items-center gap-8">
            <Link href="/privacy" className="transition-all duration-200 hover:text-gray-900 dark:hover:text-white font-medium">Privacy</Link>
            <Link href="/security" className="transition-all duration-200 hover:text-gray-900 dark:hover:text-white font-medium">Security</Link>
            <Link href="mailto:hello@earningsnerd.com" className="transition-all duration-200 hover:text-gray-900 dark:hover:text-white font-medium">Contact</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

