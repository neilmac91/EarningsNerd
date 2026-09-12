'use client'

import { useRef, useState, type KeyboardEvent } from 'react'
import Link from 'next/link'
import { useFeatureFlagVariantKey } from 'posthog-js/react'
import { PRICE_VARIANTS } from '@/app/pricing/prices'
import { Badge } from '@/components/ui/Badge'
import { buttonVariants } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import { ACCESS_COPY, type AccessMode } from '@/features/marketing/lib/access'
import analytics from '@/lib/analytics'
import { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import { CheckIcon, SealCheckIcon } from '@/lib/icons'
import {
  FREE_COPILOT_QUESTIONS,
  FREE_EARNINGS_ALERT_LIMIT,
  FREE_HISTORY_RETENTION_DAYS,
  FREE_SUMMARY_LIMIT,
} from '@/lib/planLimits'

/**
 * Marketing pricing section (design section 7). Two plan cards under a "Monthly / Annual" billing
 * toggle. The design's copy is the spec; the numbers are not: prices come from app/pricing/prices
 * (the same `pricing-experiment` PostHog arm the pricing page reads), free-tier caps from the
 * planLimits mirror, the account CTA from the page's ONE access decision, and the trial copy from
 * ENABLE_PRO_TRIAL, which the repo flips in lockstep with the backend's PRO_TRIAL_DAYS. Both Pro
 * CTAs land on /pricing, where checkout (and the account-state logic around it) lives.
 */

// Free-tier caps are never bare literals (tests/unit/planLimitsLockstep.spec.ts).
const FREE_FEATURES = [
  `${FREE_SUMMARY_LIMIT} AI summaries a month`,
  'Every 10-K, 10-Q and 20-F on SEC EDGAR',
  'Company search and historical filings',
  `${FREE_COPILOT_QUESTIONS} Ask this Filing questions`,
  `${FREE_EARNINGS_ALERT_LIMIT} earnings-day alerts`,
  'Multi-Period Analysis demo (locked)',
  `${FREE_HISTORY_RETENTION_DAYS}-day summary history`,
  'Unlimited watchlist',
]

const PRO_FEATURES = [
  'Unlimited summaries',
  'Unlimited Multi-Period Analysis',
  'Ask this Filing',
  'Change Report',
  'Hourly filing alerts and 8-K alerts',
  'PDF, CSV and Excel exports',
  'Full summary history',
  'Priority support',
]

const BILLING_OPTIONS = ['monthly', 'annual'] as const
type Billing = (typeof BILLING_OPTIONS)[number]

// Same display rule as the pricing page's local fmtUsd: whole dollars stay whole, otherwise cents.
const fmtUsd = (n: number): string => (Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`)

const PRICE_CLASS =
  'font-data tnum text-[40px] font-semibold leading-[1.1] tracking-[-0.02em] text-text-primary-light dark:text-text-primary-dark'
const MUTED_CLASS = 'text-text-secondary-light dark:text-text-secondary-dark'
// Design: 44px tall, full card width. buttonVariants' md size sets h-10; h-11 is emitted later in
// the height scale, so it wins (verified against the built stylesheet, not assumed).
const CTA_CLASS = 'mt-5 h-11 w-full'

function FeatureList({ items }: { items: readonly string[] }) {
  return (
    <ul className="mt-6 flex flex-col gap-2.5">
      {items.map((item) => (
        <li key={item} className={`flex items-start gap-2.5 text-sm ${MUTED_CLASS}`}>
          <CheckIcon
            aria-hidden="true"
            className="mt-0.5 h-4 w-4 shrink-0 text-brand-strong dark:text-brand-strong-dark"
          />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  )
}

export default function PricingSection({
  accessMode,
  showBeta,
}: {
  accessMode: AccessMode
  showBeta: boolean
}) {
  // Monthly first, as designed (the pricing page defaults to annual; the landing leads with the
  // headline number and lets the toggle reveal the annual saving).
  const [billing, setBilling] = useState<Billing>('monthly')
  const radioRefs = useRef<Record<Billing, HTMLButtonElement | null>>({ monthly: null, annual: null })

  const variant = useFeatureFlagVariantKey('pricing-experiment')
  const prices = variant === 'price_29' ? PRICE_VARIANTS.price_29 : PRICE_VARIANTS.control
  const access = ACCESS_COPY[accessMode]

  const monthly = billing === 'monthly'
  const proPrice = monthly ? prices.monthlyDisplay : fmtUsd(prices.yearly / 12)
  const billingNote = monthly
    ? `Billed monthly. Or ${prices.yearlyDisplay} a year, 2 months free.`
    : `Billed annually at ${prices.yearlyDisplay}. Two months free against monthly.`

  // The pricing page's Switch speaks 'monthly' | 'yearly'; keep the funnel event's vocabulary.
  const cycleName = (option: Billing) => (option === 'monthly' ? 'monthly' : 'yearly')

  const select = (next: Billing) => {
    if (next !== billing) analytics.billingCycleToggled(cycleName(billing), cycleName(next))
    setBilling(next)
    radioRefs.current[next]?.focus()
  }

  // Roving focus per the ARIA radio-group pattern: arrows move AND check (wrapping), Home/End jump.
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const count = BILLING_OPTIONS.length
    const index = BILLING_OPTIONS.indexOf(billing)
    let next: Billing | undefined
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = BILLING_OPTIONS[(index + 1) % count]
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = BILLING_OPTIONS[(index - 1 + count) % count]
    else if (e.key === 'Home') next = BILLING_OPTIONS[0]
    else if (e.key === 'End') next = BILLING_OPTIONS[count - 1]
    if (!next) return
    e.preventDefault()
    select(next)
  }

  const radioClass = (option: Billing) =>
    [
      'h-9 rounded px-3.5 text-sm font-semibold transition-colors duration-fast motion-reduce:transition-none',
      'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
      billing === option
        ? 'bg-brand-weak text-text-primary-light dark:bg-brand-weak-dark dark:text-text-primary-dark'
        : `bg-transparent ${MUTED_CLASS}`,
    ].join(' ')

  return (
    <section
      id="pricing"
      aria-labelledby="pricing-h"
      className="border-t border-border-light py-20 dark:border-white/10 sm:py-24"
    >
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="pricing">
          <div className="flex flex-wrap items-end justify-between gap-6">
            {/* max-w-xl (not the section-lead 2xl) keeps the toggle beside the heading at lg, as designed. */}
            <div className="max-w-xl">
              <h2 id="pricing-h" className="text-3xl lg:text-4xl">
                Pricing
              </h2>
              <p className={`mt-4 text-lg ${MUTED_CLASS}`}>
                Summaries are generated once per filing and shared. That is what makes unlimited reading
                possible at this price.
              </p>
            </div>
            <div
              role="radiogroup"
              aria-label="Billing period"
              onKeyDown={onKeyDown}
              className="inline-flex rounded-lg border border-border-light bg-panel-light p-1 shadow-e1 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
            >
              <button
                ref={(el) => {
                  radioRefs.current.monthly = el
                }}
                type="button"
                role="radio"
                aria-checked={monthly}
                tabIndex={monthly ? 0 : -1}
                onClick={() => select('monthly')}
                className={radioClass('monthly')}
              >
                Monthly
              </button>
              <button
                ref={(el) => {
                  radioRefs.current.annual = el
                }}
                type="button"
                role="radio"
                aria-checked={!monthly}
                tabIndex={monthly ? -1 : 0}
                onClick={() => select('annual')}
                className={radioClass('annual')}
              >
                Annual{' '}
                <span className="font-medium text-brand-strong dark:text-brand-strong-dark">· 2 months free</span>
              </button>
            </div>
          </div>

          <div className="mt-10 grid items-stretch gap-6 md:grid-cols-2">
            <Card className="flex flex-col p-5 sm:p-7">
              <h3 className="text-xl">Free</h3>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className={PRICE_CLASS}>$0</span>
              </div>
              <p className={`mt-1.5 text-sm ${MUTED_CLASS}`}>For reading a few filings a month.</p>
              <Link
                href={access.href}
                className={buttonVariants({ variant: 'secondary', size: 'md', className: CTA_CLASS })}
              >
                {access.cta}
              </Link>
              <FeatureList items={FREE_FEATURES} />
            </Card>

            {/* The design's brand border is a 1px inset ring here (the pricing page's Pro-card
                pattern): Card sets its own border colour and cx has no tailwind-merge, so a
                `dark:border-brand-border-dark` override loses to Card's `dark:border-white/10`
                in the built stylesheet. A ring has no competitor on Card, in either theme. */}
            <Card
              elevation="e3"
              className="flex flex-col p-5 ring-1 ring-inset ring-brand-border dark:ring-brand-border-dark sm:p-7"
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-xl">Pro</h3>
                <Badge variant="solid">Most popular</Badge>
              </div>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className={PRICE_CLASS}>{proPrice}</span>
                <span className={`text-sm ${MUTED_CLASS}`}>per month</span>
              </div>
              <p className={`mt-1.5 text-sm ${MUTED_CLASS}`}>{billingNote}</p>
              {showBeta && (
                <p className="mt-1.5 flex items-center gap-1.5 text-sm font-medium text-brand-strong dark:text-brand-strong-dark">
                  <SealCheckIcon aria-hidden="true" className="h-4 w-4" />
                  Free for beta members
                </p>
              )}
              <Link
                href="/pricing"
                className={buttonVariants({ variant: 'primary', size: 'md', className: CTA_CLASS })}
              >
                {ENABLE_PRO_TRIAL ? 'Start 7-day free trial' : 'Upgrade to Pro'}
              </Link>
              {ENABLE_PRO_TRIAL && (
                <p className={`mt-2 text-xs ${MUTED_CLASS}`}>
                  Card required. One trial per account. Cancel any time in the 7 days at no charge.
                </p>
              )}
              <FeatureList items={PRO_FEATURES} />
            </Card>
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}
