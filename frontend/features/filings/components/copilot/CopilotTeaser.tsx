'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { CheckCircleIcon, LockSimpleIcon, SparkleIcon } from '@/lib/icons'
import { analytics } from '@/lib/analytics'
import { Button } from '@/components/ui'

interface CopilotTeaserProps {
  filingId: number
  filingType: string
  ticker: string | null
  companyName: string | null
  isAuthenticated: boolean
  // Opens the contextual upgrade modal (and records the CTA click) instead of a raw /pricing link.
  onUpgrade: () => void
}

const VALUE_PROPS = [
  'Ask anything about this filing in plain English',
  'Every answer cited to the exact filing text, verifiable in one click',
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
  onUpgrade,
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
      <div className="relative overflow-hidden rounded-xl border border-border-light dark:border-white/10 bg-brand-weak dark:bg-white/5 p-3">
        <div aria-hidden="true" className="pointer-events-none select-none space-y-2 blur-[3px]">
          <div className="flex justify-end">
            <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-panel-light dark:bg-white/5 px-3 py-1.5 text-xs text-text-primary-light dark:text-text-primary-dark">
              How did revenue and margins trend?
            </div>
          </div>
          <div className="rounded-2xl rounded-bl-sm border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/[0.07] px-3 py-2 text-xs text-text-secondary-light dark:text-text-secondary-dark">
            Revenue rose 8% to $94.0B [1], with gross margin expanding to 46.2% [F1] on a richer
            product mix [2].
            <div className="mt-2 flex items-center gap-1.5 text-xs text-text-secondary-light dark:text-text-secondary-dark">
              <CheckCircleIcon className="h-3 w-3 text-brand-strong/70 dark:text-brand-strong-dark/70" /> Grounded in 3 excerpts
            </div>
          </div>
        </div>
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-panel-light dark:bg-panel-dark ring-1 ring-brand-border">
            <LockSimpleIcon className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
          </span>
        </div>
      </div>

      {/* Value props */}
      <p className="mt-4 text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{heading}</p>
      <ul className="mt-2 space-y-1.5">
        {VALUE_PROPS.map((prop) => (
          <li key={prop} className="flex items-start gap-2 text-xs text-text-secondary-light dark:text-text-secondary-dark">
            <CheckCircleIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-strong dark:text-brand-strong-dark" aria-hidden="true" />
            {prop}
          </li>
        ))}
      </ul>

      {/* Upsell CTA — opens the contextual upgrade modal and records the click. */}
      <Button className="mt-4 w-full" onClick={onUpgrade} leftIcon={<SparkleIcon className="h-4 w-4" />}>
        Upgrade to Pro
      </Button>
      {!isAuthenticated && (
        <p className="mt-3 text-center text-xs text-text-secondary-light dark:text-text-secondary-dark">
          Already Pro?{' '}
          <Link href="/login" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
            Sign in
          </Link>
        </p>
      )}
    </div>
  )
}
