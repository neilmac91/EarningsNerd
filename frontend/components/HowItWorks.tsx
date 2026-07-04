import { memo } from 'react'
import { FileTextIcon, LightningIcon, MagnifyingGlassIcon } from '@/lib/icons'

const STEPS = [
  {
    number: '01',
    title: 'Search any company',
    description: 'Find any public company by name or ticker symbol. We cover 500+ companies on SEC EDGAR.',
    icon: MagnifyingGlassIcon,
  },
  {
    number: '02',
    title: 'Pick a filing',
    description: 'Select a 10-K (annual) or 10-Q (quarterly) report. We pull it directly from SEC EDGAR.',
    icon: FileTextIcon,
  },
  {
    number: '03',
    title: 'Get instant insights',
    description: 'Our AI reads the full filing and delivers a structured summary — financials, risks, and trends.',
    icon: LightningIcon,
  },
] as const

function HowItWorks() {
  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="text-center">
        <h2 className="text-3xl font-semibold tracking-tight text-text-primary-light dark:text-text-primary-dark sm:text-4xl">
          How it works
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-text-secondary-light dark:text-text-secondary-dark">
          From SEC filing to actionable insight in minutes, not hours.
        </p>
      </div>

      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {STEPS.map((step) => {
          const Icon = step.icon
          return (
            <div
              key={step.number}
              className="glass-card group relative rounded-2xl p-6 transition duration-base"
            >
              {/* Step number */}
              <div className="mb-4 text-xs font-semibold uppercase tracking-widest text-brand-strong dark:text-brand-strong-dark">
                Step {step.number}
              </div>

              {/* Icon */}
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-strong/10 text-brand-strong dark:bg-brand-dark/15 dark:text-brand-strong-dark transition-colors group-hover:bg-brand-strong/20 dark:group-hover:bg-brand-dark/20">
                <Icon className="h-6 w-6" />
              </div>

              {/* Content */}
              <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
                {step.description}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default memo(HowItWorks)
