import { memo } from 'react'
import { Search, FileText, Zap } from 'lucide-react'

const STEPS = [
  {
    number: '01',
    title: 'Search any company',
    description: 'Find any public company by name or ticker symbol. We cover 500+ companies on SEC EDGAR.',
    icon: Search,
  },
  {
    number: '02',
    title: 'Pick a filing',
    description: 'Select a 10-K (annual) or 10-Q (quarterly) report. We pull it directly from SEC EDGAR.',
    icon: FileText,
  },
  {
    number: '03',
    title: 'Get instant insights',
    description: 'Our AI reads the full filing and delivers a structured summary — financials, risks, and trends.',
    icon: Zap,
  },
] as const

function HowItWorks() {
  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="text-center">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          How it works
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-slate-400">
          From SEC filing to actionable insight in minutes, not hours.
        </p>
      </div>

      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {STEPS.map((step) => {
          const Icon = step.icon
          return (
            <div
              key={step.number}
              className="glass-card group relative rounded-2xl p-6 transition-all duration-300"
            >
              {/* Step number */}
              <div className="mb-4 text-xs font-bold uppercase tracking-widest text-mint-500">
                Step {step.number}
              </div>

              {/* Icon */}
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-mint-500/10 text-mint-400 transition-colors group-hover:bg-mint-500/20">
                <Icon className="h-6 w-6" />
              </div>

              {/* Content */}
              <h3 className="text-lg font-semibold text-white">{step.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
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
