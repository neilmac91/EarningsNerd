import { ArrowRight } from 'lucide-react'
import ExampleCtaLink from '@/components/ExampleCtaLink'
import { exampleFilingHref } from '@/lib/featureFlags'

/**
 * Compact example card for small screens, where the full hero mockup is hidden
 * — so mobile visitors still see the product (real Apple FY 2022 10-K figures)
 * with a one-tap path into the pre-generated example summary.
 */
function ExampleSummaryCard() {
  return (
    <ExampleCtaLink
      href={exampleFilingHref('hero_mobile_example')}
      placement="hero_mobile_card"
      className="group block rounded-2xl border border-white/10 bg-white/[0.03] p-4 transition-colors hover:border-mint-500/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint-500"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-5 w-5 rounded-full bg-gradient-to-br from-mint-400 to-cyan-400" aria-hidden="true" />
          <span className="text-sm font-semibold text-white">Apple Inc.</span>
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">10-K · FY 2022</span>
        </div>
        <span className="text-xs text-slate-400">Example</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <div>
          <div className="text-xs text-slate-400">Revenue</div>
          <div className="text-sm font-bold text-white">$394.3B</div>
        </div>
        <div>
          <div className="text-xs text-slate-400">Net Income</div>
          <div className="text-sm font-bold text-white">$99.8B</div>
        </div>
        <div>
          <div className="text-xs text-slate-400">Diluted EPS</div>
          <div className="text-sm font-bold text-white">$6.11</div>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-1 text-sm font-medium text-mint-400">
        Read the full summary
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
      </div>
    </ExampleCtaLink>
  )
}

export default ExampleSummaryCard
