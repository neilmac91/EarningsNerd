import { ArrowRightIcon } from '@/lib/icons'
import ExampleCtaLink from '@/components/ExampleCtaLink'
import CompanyLogo from '@/components/CompanyLogo'
import { exampleFilingHref } from '@/lib/featureFlags'
import type { ExampleData } from '@/lib/serverApi'

// Static fallback mirrors HeroExample's verified Apple FY 2022 figures.
const FALLBACK = {
  ticker: 'AAPL',
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
  const ticker = example?.ticker ?? FALLBACK.ticker
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
      className="group block rounded-2xl border border-border-light bg-panel-light p-4 transition-colors hover:border-brand-strong/30 dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-brand-dark/30 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
    >
      <div className="flex items-center justify-between">
        <div className="flex min-w-0 items-center gap-2">
          <CompanyLogo ticker={ticker} name={companyName} size={20} priority />
          <span className="truncate text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{companyName}</span>
          <span className="flex-shrink-0 rounded-full bg-brand-weak px-2 py-0.5 text-xs text-text-secondary-light dark:bg-white/10 dark:text-text-secondary-dark">
            {filingLabel}
          </span>
        </div>
        <span className="flex-shrink-0 text-xs text-text-tertiary-light dark:text-text-secondary-dark">Example</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        {metrics.map((metric) => (
          <div key={metric.label}>
            <div className="text-xs text-text-secondary-light dark:text-text-secondary-dark">{metric.label}</div>
            <div className="text-sm font-bold tabular-nums text-text-primary-light dark:text-text-primary-dark">{metric.value}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-1 text-sm font-medium text-brand-strong dark:text-brand-strong-dark">
        Read the full summary
        <ArrowRightIcon
          className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5"
          aria-hidden="true"
        />
      </div>
    </ExampleCtaLink>
  )
}

export default ExampleSummaryCard
