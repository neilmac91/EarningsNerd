import { FileCheck, Database, BadgeCheck } from 'lucide-react'

const PILLARS = [
  {
    title: 'Straight from SEC EDGAR',
    description:
      'Every summary is generated from the official filing a company submits to the SEC — not third-party rewrites or news coverage.',
    icon: FileCheck,
  },
  {
    title: 'Grounded in XBRL',
    description:
      'Financial metrics are drawn from the structured XBRL data filed alongside each report, the same machine-readable figures the SEC receives.',
    icon: Database,
  },
  {
    title: 'Honest about quality',
    description:
      'Each summary gets a deterministic quality check. If a section is thin or financial data could not be verified, we say so — and you can regenerate.',
    icon: BadgeCheck,
  },
] as const

/**
 * Objection-handling section: answers "how do I know the AI is right?" with
 * the product's real mechanisms (EDGAR sourcing, XBRL grounding, the quality
 * verdict) rather than generic feature claims.
 */
function AccuracySection() {
  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
      <div className="text-center">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Where the numbers come from
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-lg text-slate-400">
          AI summaries are only useful if you can trust them. Ours are anchored
          to the source.
        </p>
      </div>

      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {PILLARS.map((pillar) => {
          const Icon = pillar.icon
          return (
            <div key={pillar.title} className="glass-card rounded-2xl p-6">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-mint-500/10 text-mint-400">
                <Icon className="h-6 w-6" aria-hidden="true" />
              </div>
              <h3 className="text-lg font-semibold text-white">{pillar.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">
                {pillar.description}
              </p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

export default AccuracySection
