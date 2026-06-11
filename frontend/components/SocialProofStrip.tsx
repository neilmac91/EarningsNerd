const CLAIMS: readonly string[] = [
  'Every SEC-registered company',
  '10-K & 10-Q coverage',
  'Sourced directly from SEC EDGAR',
  'Financials grounded in XBRL data',
]

export default function SocialProofStrip() {
  return (
    <section className="border-y border-white/[0.06] bg-slate-900/50">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 px-4 py-10 sm:flex-row sm:flex-wrap sm:justify-center sm:gap-x-12 sm:gap-y-4 sm:px-6 lg:px-8">
        {CLAIMS.map((claim) => (
          <div key={claim} className="flex items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-mint-400" aria-hidden="true" />
            <span className="text-sm font-semibold text-slate-300">{claim}</span>
          </div>
        ))}
      </div>
    </section>
  )
}
