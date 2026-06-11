import ExampleCtaLink from '@/components/ExampleCtaLink'
import { exampleFilingHref } from '@/lib/featureFlags'

/**
 * Browser-framed preview of a real EarningsNerd summary (Apple's FY 2022 10-K,
 * filed Oct 2022 — all figures are the actual filed values). The whole card is
 * a link into the pre-generated example so the hero demonstrates the product
 * instead of decorating it.
 */
function HeroMockup() {
  return (
    <div className="relative">
      {/* Ambient glow behind the mockup */}
      <div className="absolute -inset-4 rounded-3xl bg-mint-500/10 blur-3xl" aria-hidden="true" />

      <ExampleCtaLink
        href={exampleFilingHref('hero_visual_example')}
        placement="hero_visual"
        className="group block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-mint-500"
      >
        {/* Browser frame */}
        <div className="mockup-frame relative shadow-2xl transition-shadow group-hover:shadow-glow-mint">
          {/* Title bar */}
          <div className="mockup-frame-titlebar flex items-center gap-2 px-4 py-3">
            <div className="flex gap-1.5" aria-hidden="true">
              <span className="h-3 w-3 rounded-full bg-red-500/70" />
              <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
              <span className="h-3 w-3 rounded-full bg-green-500/70" />
            </div>
            <div className="mx-auto flex-1 max-w-xs">
              <div className="rounded-md bg-white/5 px-3 py-1 text-center text-xs text-slate-400">
                earningsnerd.io — example summary
              </div>
            </div>
          </div>

          {/* Page content */}
          <div className="space-y-4 p-5">
            {/* Header area */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="h-6 w-6 rounded-full bg-gradient-to-br from-mint-400 to-cyan-400" aria-hidden="true" />
                <span className="text-sm font-semibold text-white">Apple Inc.</span>
                <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">10-K</span>
              </div>
              <span className="text-xs text-slate-400">FY 2022 · filed Oct 2022</span>
            </div>

            {/* Executive snapshot — real FY 2022 figures */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
              <div className="mb-2 flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full bg-mint-400" aria-hidden="true" />
                <span className="text-xs font-semibold uppercase tracking-wider text-mint-400">
                  Executive Snapshot
                </span>
              </div>
              <p className="text-xs leading-relaxed text-slate-300">
                Net sales rose 8% to $394.3B, led by iPhone and Services growth.
                Gross margin expanded to 43.3%, and operating cash flow reached
                a record $122.2B.
              </p>
            </div>

            {/* Metrics grid — actual FY 2022 10-K values */}
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
                <div className="text-xs text-slate-400">Revenue</div>
                <div className="mt-1 text-sm font-bold text-white">$394.3B</div>
                <div className="mt-0.5 text-xs font-medium text-emerald-400">+7.8%</div>
              </div>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
                <div className="text-xs text-slate-400">Net Income</div>
                <div className="mt-1 text-sm font-bold text-white">$99.8B</div>
                <div className="mt-0.5 text-xs font-medium text-emerald-400">+5.4%</div>
              </div>
              <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
                <div className="text-xs text-slate-400">Diluted EPS</div>
                <div className="mt-1 text-sm font-bold text-white">$6.11</div>
                <div className="mt-0.5 text-xs font-medium text-emerald-400">+8.9%</div>
              </div>
            </div>

            {/* Risk factors — real Item 1A themes from the FY 2022 10-K */}
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
              <div className="mb-2 flex items-center gap-2">
                <div className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden="true" />
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                  Risk Factors
                </span>
              </div>
              <ul className="space-y-1.5 text-xs text-slate-300">
                <li className="flex items-center gap-2">
                  <span className="h-1 w-1 flex-shrink-0 rounded-full bg-amber-400/60" aria-hidden="true" />
                  Supply chain concentration in Asia
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-1 w-1 flex-shrink-0 rounded-full bg-amber-400/60" aria-hidden="true" />
                  Global economic conditions and FX headwinds
                </li>
                <li className="flex items-center gap-2">
                  <span className="h-1 w-1 flex-shrink-0 rounded-full bg-amber-400/60" aria-hidden="true" />
                  App Store regulatory scrutiny
                </li>
              </ul>
            </div>

            {/* Footer CTA inside the frame */}
            <div className="flex items-center justify-between rounded-xl border border-mint-500/20 bg-mint-500/5 px-4 py-3">
              <span className="text-xs font-medium text-mint-300">
                Read the full example summary
              </span>
              <span className="text-xs text-mint-400 transition-transform group-hover:translate-x-0.5" aria-hidden="true">
                →
              </span>
            </div>
          </div>
        </div>
      </ExampleCtaLink>
    </div>
  )
}

export default HeroMockup
