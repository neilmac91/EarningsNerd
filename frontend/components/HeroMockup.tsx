'use client'

import { memo } from 'react'

/**
 * A static browser-frame mockup showing an EarningsNerd summary page.
 * Used in the hero section to give visitors a preview of the product.
 */
function HeroMockup() {
  return (
    <div className="relative" aria-hidden="true">
      {/* Ambient glow behind the mockup */}
      <div className="absolute -inset-4 rounded-3xl bg-mint-500/10 blur-3xl" aria-hidden="true" />

      {/* Browser frame */}
      <div className="mockup-frame relative shadow-2xl">
        {/* Title bar */}
        <div className="mockup-frame-titlebar flex items-center gap-2 px-4 py-3">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-red-500/70" />
            <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
            <span className="h-3 w-3 rounded-full bg-green-500/70" />
          </div>
          <div className="mx-auto flex-1 max-w-xs">
            <div className="rounded-md bg-white/5 px-3 py-1 text-center text-xs text-slate-500">
              earningsnerd.io/filing/aapl-10k
            </div>
          </div>
        </div>

        {/* Page content mockup */}
        <div className="space-y-4 p-5">
          {/* Header area */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="h-6 w-6 rounded-full bg-gradient-to-br from-mint-400 to-cyan-400" />
              <span className="text-sm font-semibold text-white">Apple Inc.</span>
              <span className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-400">10-K</span>
            </div>
            <span className="text-xs text-slate-500">FY 2022</span>
          </div>

          {/* Executive summary section */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-mint-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-mint-400">
                Executive Snapshot
              </span>
            </div>
            <div className="space-y-1.5">
              <div className="h-2.5 w-full rounded bg-white/[0.08]" />
              <div className="h-2.5 w-11/12 rounded bg-white/[0.06]" />
              <div className="h-2.5 w-4/5 rounded bg-white/[0.05]" />
            </div>
          </div>

          {/* Metrics grid */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
              <div className="text-[10px] text-slate-500">Revenue</div>
              <div className="mt-1 text-sm font-bold text-white">$394.3B</div>
              <div className="mt-0.5 text-[10px] font-medium text-emerald-400">+7.8%</div>
            </div>
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
              <div className="text-[10px] text-slate-500">Net Income</div>
              <div className="mt-1 text-sm font-bold text-white">$99.8B</div>
              <div className="mt-0.5 text-[10px] font-medium text-emerald-400">+5.4%</div>
            </div>
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] p-3">
              <div className="text-[10px] text-slate-500">Diluted EPS</div>
              <div className="mt-1 text-sm font-bold text-white">$6.11</div>
              <div className="mt-0.5 text-[10px] font-medium text-emerald-400">+8.9%</div>
            </div>
          </div>

          {/* Risk factors preview */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-amber-400" />
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                Risk Factors
              </span>
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <div className="h-1 w-1 rounded-full bg-amber-400/60" />
                <div className="h-2 w-3/4 rounded bg-white/[0.06]" />
              </div>
              <div className="flex items-center gap-2">
                <div className="h-1 w-1 rounded-full bg-amber-400/60" />
                <div className="h-2 w-2/3 rounded bg-white/[0.06]" />
              </div>
              <div className="flex items-center gap-2">
                <div className="h-1 w-1 rounded-full bg-amber-400/60" />
                <div className="h-2 w-4/5 rounded bg-white/[0.06]" />
              </div>
            </div>
          </div>

          {/* Mini sparkline chart */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.03] p-4">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Revenue Trend
              </span>
              <span className="text-[10px] text-slate-500">4 quarters</span>
            </div>
            <svg viewBox="0 0 200 40" className="h-8 w-full" aria-hidden="true">
              <defs>
                <linearGradient id="mockup-chart-gradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10B981" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#10B981" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path
                d="M0 35 L50 28 L100 22 L150 15 L200 8"
                stroke="#10B981"
                strokeWidth="2"
                fill="none"
                strokeLinecap="round"
              />
              <path
                d="M0 35 L50 28 L100 22 L150 15 L200 8 L200 40 L0 40Z"
                fill="url(#mockup-chart-gradient)"
              />
            </svg>
          </div>
        </div>
      </div>
    </div>
  )
}

export default memo(HeroMockup)
