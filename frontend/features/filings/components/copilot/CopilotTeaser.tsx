'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { CheckCircle2, Lock, Sparkles } from 'lucide-react'
import { analytics } from '@/lib/analytics'

interface CopilotTeaserProps {
  filingId: number
  filingType: string
  ticker: string | null
  companyName: string | null
  isAuthenticated: boolean
}

const VALUE_PROPS = [
  'Ask anything about this filing in plain English',
  'Every answer cited to the exact filing text — verify in one click',
  'Exact figures pulled from XBRL, never guessed',
]

/**
 * FREE locked teaser for the Copilot rail: a blurred sample Q&A (to show the value), the value
 * props, and the upsell CTA. Fires `paywall_prompt_shown` once when shown — the client-confirmed
 * paywall moment (mirrors the summary paywall instrumentation), distinct from the server `paywall_hit`.
 */
export default function CopilotTeaser({
  filingId,
  filingType,
  ticker,
  companyName,
  isAuthenticated,
}: CopilotTeaserProps) {
  useEffect(() => {
    analytics.paywallPromptShown({ filingId, ticker, filingType, entryPoint: 'copilot_rail' })
  }, [filingId, ticker, filingType])

  // "Ask AAPL’s 10-K anything" when we know the issuer; otherwise the cleaner "Ask this 10-K
  // anything" (avoids the awkward possessive "this filing’s 10-K").
  const subjectName = ticker || companyName
  const heading = subjectName
    ? `Ask ${subjectName}’s ${filingType} anything`
    : `Ask this ${filingType} anything`

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      {/* Blurred sample answer — conveys the value without giving it away. Decorative (aria-hidden). */}
      <div className="relative overflow-hidden rounded-xl border border-white/10 bg-slate-800/40 p-3">
        <div aria-hidden="true" className="pointer-events-none select-none space-y-2 blur-[3px]">
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-mint-500/15 px-3 py-1.5 text-xs text-slate-100">
              How did revenue and margins trend?
            </div>
          </div>
          <div className="rounded-2xl rounded-bl-sm border border-white/10 bg-slate-800/60 px-3 py-2 text-xs text-slate-200">
            Revenue rose 8% to $94.0B [1], with gross margin expanding to 46.2% [F1] on a richer
            product mix [2].
            <div className="mt-2 flex items-center gap-1.5 text-[10px] text-slate-500">
              <CheckCircle2 className="h-3 w-3 text-mint-500/70" /> Grounded in 3 excerpts
            </div>
          </div>
        </div>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900/80 ring-1 ring-mint-500/30">
            <Lock className="h-4 w-4 text-mint-300" />
          </span>
        </div>
      </div>

      {/* Value props */}
      <p className="mt-4 text-sm font-semibold text-white">{heading}</p>
      <ul className="mt-2 space-y-1.5">
        {VALUE_PROPS.map((prop) => (
          <li key={prop} className="flex items-start gap-2 text-xs text-slate-300">
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-mint-400" aria-hidden="true" />
            {prop}
          </li>
        ))}
      </ul>

      {/* Upsell CTA */}
      <Link
        href="/pricing"
        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-mint-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition-colors hover:bg-mint-400"
      >
        <Sparkles className="h-4 w-4" />
        Upgrade to Pro
      </Link>
      {!isAuthenticated && (
        <p className="mt-3 text-center text-xs text-slate-500">
          Already Pro?{' '}
          <Link href="/login" className="text-mint-300 hover:underline">
            Sign in
          </Link>
        </p>
      )}
    </div>
  )
}
