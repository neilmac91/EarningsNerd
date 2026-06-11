import { memo } from 'react'
import { Brain, BarChart3, Shield, Columns3 } from 'lucide-react'

const FEATURES = [
  {
    title: 'AI-Powered Summaries',
    description: 'Turn 100-page filings into structured 5-minute reads. Business overview, financials, risks, and outlook — all in one place.',
    icon: Brain,
  },
  {
    title: 'XBRL-Verified Financials',
    description: 'Financial metrics drawn from the standardized XBRL data filed with the SEC. Revenue, margins, EPS, and more — traced to the source.',
    icon: BarChart3,
  },
  {
    title: 'Risk Factor Analysis',
    description: 'Track new, changed, and evolving risk disclosures. Spot material changes before the market reacts.',
    icon: Shield,
  },
  {
    title: 'Filing Comparison',
    description: 'Compare filings side-by-side across periods. See what changed quarter over quarter at a glance.',
    icon: Columns3,
  },
] as const

function FeatureShowcase() {
  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="text-center">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Everything you need to analyze filings faster
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-slate-400">
          Built for investors who want the signal without the noise.
        </p>
      </div>

      <div className="mt-12 grid gap-6 sm:grid-cols-2">
        {FEATURES.map((feature) => {
          const Icon = feature.icon
          return (
            <div
              key={feature.title}
              className="glass-card group rounded-2xl p-6 transition-all duration-300"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-mint-500/10 text-mint-400 transition-colors group-hover:bg-mint-500/20">
                <Icon className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-white">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                {feature.description}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default memo(FeatureShowcase)
