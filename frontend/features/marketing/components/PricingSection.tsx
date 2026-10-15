'use client'

import { useRef, useState, type KeyboardEvent } from 'react'
import Link from 'next/link'
import { PRO_PRICING } from '@/app/pricing/prices'
import { buttonVariants } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { cx } from '@/components/ui/cx'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import { ACCESS_COPY, type AccessMode } from '@/features/marketing/lib/access'
import analytics from '@/lib/analytics'
import { ENABLE_ANALYSIS, ENABLE_FPI_FILINGS, ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import { CheckIcon, SealCheckIcon } from '@/lib/icons'
import { pricingHref } from '@/features/subscriptions/lib/pricingRoute'
import {
  FREE_COPILOT_QUESTIONS,
  FREE_EARNINGS_ALERT_LIMIT,
  FREE_HISTORY_RETENTION_DAYS,
  FREE_SUMMARY_LIMIT,
} from '@/lib/planLimits'

/**
 * Marketing pricing section (design section 7). Two plan cards under a "Monthly / Annual" billing
 * toggle. The approved offer comes from app/pricing/prices, free-tier caps from the
 * planLimits mirror, the account CTA from the page's ONE access decision, and the trial copy from
 * ENABLE_PRO_TRIAL, which the repo flips in lockstep with the backend's PRO_TRIAL_DAYS.
 * Paid-offer CTAs preserve the selected cycle on /pricing. The beta offer keeps the neutral
 * entry until pricing can resolve account eligibility, rather than selecting a guest trial.
 */

// A plan line keyed to a flag lists only while that flag ships its feature; `off` is what it reads
// while the flag is off, if anything. Multi-Period Analysis and its Excel workbook ship behind
// ENABLE_ANALYSIS (the route 404s while the flag is off; tests/unit/analysis-route-hidden.spec.tsx);
// 20-F filings behind ENABLE_FPI_FILINGS, the mirror of the API's flag (tasks/todo.md F39).
type Flag = 'analysis' | 'fpi'
type PlanLine = { text: string; flag?: Flag; off?: string }
// Read at render, so the flag's value is the one the page ships with.
const isOn = (flag: Flag): boolean => ({ analysis: ENABLE_ANALYSIS, fpi: ENABLE_FPI_FILINGS })[flag]
const shipped = (items: readonly PlanLine[]): string[] =>
  items.flatMap((item) => (!item.flag || isOn(item.flag) ? [item.text] : item.off ? [item.off] : []))

// Free-tier caps are never bare literals (tests/unit/planLimitsLockstep.spec.ts).
const FREE_FEATURES: readonly PlanLine[] = [
  { text: `${FREE_SUMMARY_LIMIT} AI summaries a month` },
  { text: '10-K, 10-Q and 20-F filings from SEC EDGAR', flag: 'fpi', off: '10-K and 10-Q filings from SEC EDGAR' },
  { text: 'Company search and historical filings' },
  { text: `${FREE_COPILOT_QUESTIONS} Ask this Filing questions` },
  { text: `${FREE_EARNINGS_ALERT_LIMIT} earnings-day alerts` },
  { text: 'Multi-Period Analysis demo (locked)', flag: 'analysis' },
  { text: `${FREE_HISTORY_RETENTION_DAYS}-day summary history` },
  { text: 'Unlimited watchlist' },
]

const PRO_FEATURES: readonly PlanLine[] = [
  { text: 'Unlimited summaries' },
  { text: 'Unlimited Multi-Period Analysis', flag: 'analysis' },
  { text: 'Ask this Filing' },
  { text: 'Change Report' },
  { text: 'Hourly filing alerts and 8-K alerts' },
  { text: 'PDF, CSV and Excel exports', flag: 'analysis', off: 'PDF and CSV exports' },
  { text: 'Full summary history' },
  { text: 'Priority support' },
]

const BILLING_OPTIONS = ['monthly', 'annual'] as const
type Billing = (typeof BILLING_OPTIONS)[number]

const PRICE_CLASS =
  /* display figure — deliberate, ramp has no 40 */
  // eslint-disable-next-line no-restricted-syntax -- the 40px display figure sets its own tracking; the ramp has no 40
  'font-data tnum text-[40px] font-semibold leading-[1.1] tracking-[-0.02em] text-text-primary-light dark:text-text-primary-dark'
const MUTED_CLASS = 'text-text-secondary-light dark:text-text-secondary-dark'
// Design: 44px tall, full card width. buttonVariants' md size sets h-10, and min-h-11 lifts the box to
// 44px whatever the stylesheet order. min-h, not h: below a 24rem viewport the Button's narrow state sets
// h-auto so a label can wrap, and a caller's own min-h is the one height it keeps
// (tests/unit/buttonHeightIsAMinimum.spec.ts).
const CTA_CLASS = 'mt-5 min-h-11 w-full'

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
  // Annual first, like the pricing page: the landing leads with the headline per-month price and
  // lets the toggle reveal the monthly plan (and, when enabled, its trial).
  const [billing, setBilling] = useState<Billing>('annual')
  const radioRefs = useRef<Record<Billing, HTMLButtonElement | null>>({ monthly: null, annual: null })

  const access = ACCESS_COPY[accessMode]

  const monthly = billing === 'monthly'
  const showTrial = ENABLE_PRO_TRIAL && monthly && !showBeta
  const proPrice = monthly ? PRO_PRICING.monthlyDisplay : PRO_PRICING.yearlyPerMonthDisplay
  const billingNote = monthly
    ? `Billed monthly. Or ${PRO_PRICING.yearlyPerMonthDisplay} a month, billed annually at ${PRO_PRICING.yearlyDisplay}.`
    : `Billed annually at ${PRO_PRICING.yearlyDisplay}, saving ${PRO_PRICING.annualSavingsDisplay} a year.`

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

  // The ring sits on each radio's className itself, where the ring scan can read it.
  const radioClass = (option: Billing) =>
    [
      'h-9 rounded px-3.5 text-sm font-semibold transition-colors duration-fast motion-reduce:transition-none',
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
                className={cx('focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark', radioClass('monthly'))}
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
                className={cx('focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark', radioClass('annual'))}
              >
                Annual{' '}
                <span className="font-medium">· save {PRO_PRICING.annualSavingsPercent}%</span>
              </button>
            </div>
          </div>

          <div className="mt-10 grid grid-cols-1 items-stretch gap-6 md:grid-cols-2">
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
              <FeatureList items={shipped(FREE_FEATURES)} />
            </Card>

            {/* The design's brand border is a 1px inset ring here (the pricing page's Pro-card
                pattern): Card sets its own border colour and cx has no tailwind-merge, so a
                `dark:border-brand-border-dark` override loses to Card's `dark:border-white/10`
                in the built stylesheet. A ring has no competitor on Card, in either theme. */}
            <Card
              elevation="e3"
              className="flex flex-col p-5 ring-1 ring-inset ring-brand-border dark:ring-brand-border-dark sm:p-7"
            >
              {/* No "Most popular" badge: the beta has no popularity figure behind one, and the brand ring
                  already carries the emphasis. */}
              <h3 className="text-xl">Pro</h3>
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
                href={showBeta ? '/pricing' : pricingHref(cycleName(billing))}
                className={buttonVariants({ variant: 'primary', size: 'md', className: CTA_CLASS })}
              >
                {showTrial ? 'Start 7-day free trial' : 'Upgrade to Pro'}
              </Link>
              {showTrial && (
                <p className={`mt-2 text-xs ${MUTED_CLASS}`}>
                  Card required. One trial per account. Cancel any time in the 7 days at no charge.
                </p>
              )}
              <FeatureList items={shipped(PRO_FEATURES)} />
            </Card>
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}
