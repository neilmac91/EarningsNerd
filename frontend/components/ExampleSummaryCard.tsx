import { ArrowRight } from 'lucide-react'
import ExampleCtaLink from '@/components/ExampleCtaLink'
import { exampleFilingHref } from '@/lib/featureFlags'
import type { ExampleData } from '@/lib/serverApi'

// Static fallback mirrors HeroExample's verified Apple FY 2022 figures.
const FALLBACK = {
  companyName: 'Apple Inc.',
  filingLabel: '10-K · FY 2022',
  metrics: [
    { label: 'Revenue', value: '$394.3B' },
    { label: 'Net Income', value: '$99.8B' },
    { label: 'Diluted EPS', value: '$6.11' },
  ],
}

/**
 * Compact example card for small screens, where the full hero example is
 * hidden — so mobile visitors still see the product with a one-tap path into
 * the pre-generated example summary. Renders live data when available.
 */
function ExampleSummaryCard({ example }: { example: ExampleData | null }) {
  const companyName = example?.companyName ?? FALLBACK.companyName
  const filingLabel = example ? example.filingType : FALLBACK.filingLabel
  const metrics =
    example && example.metrics.length > 0
      ? example.metrics.slice(0, 3)
      : FALLBACK.metrics

  return (
    <ExampleCtaLink
      href={exampleFilingHref('hero_mobile_example')}
      placement="hero_mobile_card"
      className="group block rounded-2xl border border-white/10 bg-white/[0.03] p-4 transition-colors hover:border-mint-500/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
    >
      <div className="flex items-center justify-between">
        <div className="flex min-w-0 items-center gap-2">
          <div
            className="h-5 w-5 flex-shrink-0 rounded-full bg-gradient-to-br from-mint-400 to-cyan-400"
            aria-hidden="true"
          />
          <span className="truncate text-sm font-semibold text-white">{companyName}</span>
          <span className="flex-shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">
            {filingLabel}
          </span>
        </div>
        <span className="flex-shrink-0 text-xs text-slate-400">Example</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <div className="text-xs text-slate-400">{metric.label}</div>
            <div className="text-sm font-bold tabular-nums text-white">{metric.value}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-1 text-sm font-medium text-mint-400">
        Read the full summary
        <ArrowRight
          className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </ExampleCtaLink>
  )
}

export default ExampleSummaryCard
