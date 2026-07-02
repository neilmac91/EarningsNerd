import { memo } from 'react'
import { BrainIcon, ChartBarIcon, ColumnsIcon, ShieldIcon } from '@/lib/icons'

const FEATURES = [
  {
    title: 'AI-Powered Summaries',
    description: 'Turn 100-page filings into structured 5-minute reads. Business overview, financials, risks, and outlook — all in one place.',
    icon: BrainIcon,
  },
  {
    title: 'XBRL-Verified Financials',
    description: 'Financial metrics drawn from the standardized XBRL data filed with the SEC. Revenue, margins, EPS, and more — traced to the source.',
    icon: ChartBarIcon,
  },
  {
    title: 'Risk Factor Analysis',
    description: 'Track new, changed, and evolving risk disclosures. Spot material changes before the market reacts.',
    icon: ShieldIcon,
  },
  {
    title: 'Filing Comparison',
    description: 'Compare filings side-by-side across periods. See what changed quarter over quarter at a glance.',
    icon: ColumnsIcon,
  },
] as const

function FeatureShowcase() {
  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="text-center">
        <h2 className="text-3xl font-bold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-4xl">
          Everything you need to analyze filings faster
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-text-secondary-light dark:text-text-secondary-dark">
          Built for investors who want the signal without the noise.
        </p>
      </div>

      <div className="mt-12 grid gap-6 sm:grid-cols-2">
        {FEATURES.map((feature) => {
          const Icon = feature.icon
          return (
            <div
              key={feature.title}
              className="glass-card group rounded-2xl p-6 transition duration-base"
            >
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-strong/10 text-brand-strong dark:bg-brand-dark/15 dark:text-brand-strong-dark transition-colors group-hover:bg-brand-strong/20 dark:group-hover:bg-brand-dark/20">
                <Icon className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
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
