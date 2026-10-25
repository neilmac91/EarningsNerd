'use client'

import { useId, useRef, useState, type KeyboardEvent } from 'react'
import Link from 'next/link'
import { PRO_PRICING } from '@/app/pricing/prices'
import { buttonVariants } from '@/components/ui/Button'
import { cx } from '@/components/ui/cx'
import { MissingValue } from '@/components/ui/MissingValue'
import FormCodeText from '@/features/marketing/components/FormCodeText'
import LandingRow from '@/features/marketing/components/LandingRow'
import type { AccessMode } from '@/features/marketing/lib/access'
import { usePublicAccess, usePublicReadiness } from './PublicAccessProvider'
import { useOverflowRegion } from '@/hooks/useOverflowRegion'
import analytics from '@/lib/analytics'
import { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import { SealCheckIcon } from '@/lib/icons'
import { pricingHref } from '@/features/subscriptions/lib/pricingRoute'
import {
  ANALYSIS_LINES,
  FILING_FORMS_LINE,
  FREE_COPILOT_QUESTIONS,
  FREE_EARNINGS_ALERT_LIMIT,
  FREE_SUMMARY_LIMIT,
  TRIAL_DAYS,
  shipped,
  type PlanLine,
} from '@/lib/planLimits'

/**
 * Marketing pricing (the landing's pricing row, D-045): one table, the plans as columns and what each includes
 * as rows, under a "Monthly / Annual" billing toggle. The approved offer comes from app/pricing/prices, free-tier
 * caps from the planLimits mirror, the account CTA from the page's ONE access decision, and the trial copy from
 * ENABLE_PRO_TRIAL, which the repo flips in lockstep with the backend's PRO_TRIAL_DAYS. Paid-offer CTAs preserve
 * the selected cycle on /pricing. The beta offer keeps the neutral entry until pricing can resolve account
 * eligibility, rather than selecting a guest trial. /pricing does not render this component and keeps its two
 * plan cards.
 *
 * The table is one native table at every width (DESIGN.md: wide tables scroll within their container). At the
 * default text size it fits a 390px phone; when it is wider than its box (a phone under a 200% text setting) it
 * scrolls inside the box, which is then a named region in the Tab order (useOverflowRegion), so the page never
 * scrolls sideways. `relative` makes the box the containing block of the sr-only text inside it.
 */

/**
 * One row of the plan table: what each plan includes of one thing. Every part is a plan line read through
 * shipped() (lib/planLimits.ts, D-033, D-040), so a row a flag decides lists with its feature: the row lists while
 * its label ships, and a cell with no line (or a flagged line with no `off` while its flag is off) reads as not
 * included. Free-tier caps are never bare literals (tests/unit/planLimitsLockstep.spec.ts), and every line that
 * names Multi-Period Analysis is typed in ANALYSIS_LINES (tests/unit/analysis-route-hidden.spec.tsx).
 */
interface PlanRow {
  readonly label: PlanLine
  readonly free: PlanLine | null
  readonly pro: PlanLine | null
}

const INCLUDED: PlanLine = { text: 'Included' }

const PLAN_ROWS: readonly PlanRow[] = [
  { label: { text: 'Summaries' }, free: { text: `${FREE_SUMMARY_LIMIT} a month` }, pro: { text: 'Unlimited' } },
  { label: { text: 'Filings' }, free: FILING_FORMS_LINE, pro: FILING_FORMS_LINE },
  { label: { text: 'Company search and historical filings' }, free: INCLUDED, pro: INCLUDED },
  { label: { text: 'Ask this Filing' }, free: { text: `${FREE_COPILOT_QUESTIONS} questions` }, pro: INCLUDED },
  { label: ANALYSIS_LINES.landingRow, free: ANALYSIS_LINES.landingFree, pro: ANALYSIS_LINES.landingPro },
  // Both plans read the same report in production, metric deltas only: the XBRL metric changes carry no plan gate, and
  // backend/app/services/change_report_service.py omits the report's risk lines for every reader. Its one plan
  // difference is the Item 1A wording block (backend/app/services/entitlements.py: `section_changes`, and
  // `section_changes_items` for the teaser), served only behind ENABLE_SECTION_CHANGES, which config.py defaults off and
  // no deploy map sets. When the flag ships, this row changes with it (tests/unit/changeReportPlanClaims.spec.tsx fails
  // until it does).
  { label: { text: 'Change Report' }, free: INCLUDED, pro: INCLUDED },
  { label: { text: 'Alerts' }, free: { text: `${FREE_EARNINGS_ALERT_LIMIT} earnings-day alerts` }, pro: { text: 'Hourly filing alerts and 8-K alerts' } },
  { label: { text: 'Exports' }, free: null, pro: ANALYSIS_LINES.exports },
  { label: { text: 'Watchlist' }, free: { text: 'Unlimited' }, pro: { text: 'Unlimited' } },
  { label: { text: 'Priority support' }, free: null, pro: INCLUDED },
]

/** A line's reading under the flags this build ships with, or null where the plan does not include it. */
const reading = (line: PlanLine | null): string | null => (line ? (shipped([line])[0] ?? null) : null)

const CAPTION = 'What each plan includes'

const BILLING_OPTIONS = ['monthly', 'annual'] as const
type Billing = (typeof BILLING_OPTIONS)[number]

const PRICE_CLASS =
  /* display figure — deliberate, ramp has no 40 */
  // eslint-disable-next-line no-restricted-syntax -- the 40px display figure sets its own tracking; the ramp has no 40
  'font-data tnum text-[40px] font-semibold leading-[1.1] tracking-[-0.02em] text-text-primary-light dark:text-text-primary-dark'
const MUTED_CLASS = 'text-text-secondary-light dark:text-text-secondary-dark'
const RULE = 'border-t border-border-light dark:border-white/10'
const ROW_HEADER = `${RULE} py-3 pr-4 text-left align-top text-sm font-medium text-text-primary-light dark:text-text-primary-dark`
const CELL = `${RULE} px-4 py-3 align-top text-sm ${MUTED_CLASS}`
// 44px tall at least: buttonVariants' md size sets h-10, and min-h-11 lifts the box whatever the stylesheet order.
// min-h, not h, and `wrap`: in a table cell on a phone the label wraps inside its button instead of widening the
// column, and a caller's own min-h is the one height the wrap state keeps (tests/unit/buttonHeightIsAMinimum.spec.ts).
const CTA_CLASS = 'min-h-11 max-w-full'

/** A cell's reading, each form code in it one unbroken run so a phone's narrow cell never breaks "10-Q" at its hyphen,
 *  or MissingValue, which a screen reader hears as "Not included". */
function PlanCell({ text }: { text: string | null }) {
  return text !== null ? <FormCodeText text={text} /> : <MissingValue label="Not included" />
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
  const boxRef = useRef<HTMLDivElement>(null)
  const hintId = useId()
  const { overflowing, regionProps } = useOverflowRegion(boxRef, {
    label: `Scrollable table: ${CAPTION}`,
    describedBy: hintId,
  })

  const access = usePublicAccess(accessMode)
  const { readiness } = usePublicReadiness()
  const checkoutAvailable = readiness?.checkout_available === true
  const betaOfferAvailable = showBeta && checkoutAvailable

  const monthly = billing === 'monthly'
  const showTrial = ENABLE_PRO_TRIAL && monthly && !betaOfferAvailable && checkoutAvailable
  const proPrice = monthly ? PRO_PRICING.monthlyDisplay : PRO_PRICING.yearlyPerMonthDisplay
  const billingNote = monthly
    ? `Billed monthly. Or ${PRO_PRICING.yearlyPerMonthDisplay} a month, billed annually at ${PRO_PRICING.yearlyDisplay}.`
    : `Billed annually at ${PRO_PRICING.yearlyDisplay}, saving ${PRO_PRICING.annualSavingsDisplay} a year.`
  const rows = PLAN_ROWS.flatMap((row) => {
    const label = reading(row.label)
    return label === null ? [] : [{ label, free: reading(row.free), pro: reading(row.pro) }]
  })

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

  // The ring sits on each radio's className itself, where the ring scan can read it. min-h, not h: a label that
  // wraps grows its segment instead of spilling out of it. grow: once the segments wrap onto two rows each fills its
  // row; on one row the group is as wide as its two labels, so there is nothing to grow into.
  const radioClass = (option: Billing) =>
    [
      'min-h-9 grow rounded px-3.5 py-1 text-sm font-semibold transition-colors duration-fast motion-reduce:transition-none',
      billing === option
        ? 'bg-brand-weak text-text-primary-light dark:bg-brand-weak-dark dark:text-text-primary-dark'
        : `bg-transparent ${MUTED_CLASS}`,
    ].join(' ')

  return (
    <LandingRow
      id="pricing"
      title="Pricing"
      line="Summaries are generated once per filing and shared. That is what makes unlimited reading possible at this price."
      impression="pricing"
    >
      <div className="flex sm:justify-end">
        {/* One control whose segments wrap whole onto a second row inside it when the two do not fit side by
            side, as SegmentedControl's fullWidth does (DESIGN_SYSTEM.md): at 360px and 200% text the unwrapped
            group ran to 368px, its Annual label on three lines below its segment. */}
        <div
          role="radiogroup"
          aria-label="Billing period"
          onKeyDown={onKeyDown}
          className="inline-flex max-w-full flex-wrap gap-y-1 rounded-lg border border-border-light bg-panel-light p-1 shadow-e1 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
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
            {/* No-break spaces hold the middot to "Annual" and "save" to its figure, so a label too long for its
                row breaks only after the middot: "Annual ·" over "save N%", never a line that starts "·". */}
            Annual&nbsp;<span className="font-medium">· save&nbsp;{PRO_PRICING.annualSavingsPercent}%</span>
          </button>
        </div>
      </div>

      {overflowing && (
        <p id={hintId} className="mt-4 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          Scroll horizontally to read all columns.
        </p>
      )}
      {/* The role is written out, not read from regionProps, so tests/unit/dialogAllowlist.spec.ts can prove it is
          no dialog's. */}
      <div
        ref={boxRef}
        role={overflowing ? 'region' : undefined}
        tabIndex={regionProps.tabIndex}
        aria-label={regionProps['aria-label']}
        aria-describedby={regionProps['aria-describedby']}
        className="relative mt-6 overflow-x-auto rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
      >
        <table className="w-full border-collapse">
          <caption className="sr-only">{CAPTION}</caption>
          <thead>
            <tr>
              <td className="w-[28%] pb-3" />
              <th scope="col" className="w-[36%] px-4 pb-3 text-left align-bottom text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                Free
              </th>
              <th scope="col" className="w-[36%] px-4 pb-3 text-left align-bottom text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                Pro
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row" className={ROW_HEADER}>
                Price
              </th>
              <td className={CELL}>
                <span className={PRICE_CLASS}>$0</span>
                <p className={`mt-1.5 text-sm ${MUTED_CLASS}`}>For reading a few filings a month.</p>
              </td>
              <td className={CELL}>
                <div className="flex flex-wrap items-baseline gap-x-1.5">
                  <span className={PRICE_CLASS}>{proPrice}</span>
                  <span className={`text-sm ${MUTED_CLASS}`}>per month</span>
                </div>
                <p className={`mt-1.5 text-sm ${MUTED_CLASS}`}>{billingNote}</p>
                {betaOfferAvailable && (
                  <p className="mt-1.5 flex items-center gap-1.5 text-sm font-medium text-brand-strong dark:text-brand-strong-dark">
                    <SealCheckIcon aria-hidden="true" className="h-4 w-4 shrink-0" />
                    Free for beta members
                  </p>
                )}
              </td>
            </tr>
            {rows.map((row) => (
              <tr key={row.label}>
                <th scope="row" className={ROW_HEADER}>
                  {row.label}
                </th>
                <td className={CELL}>
                  <PlanCell text={row.free} />
                </td>
                <td className={CELL}>
                  <PlanCell text={row.pro} />
                </td>
              </tr>
            ))}
            <tr>
              <td className={RULE} />
              <td className={`${RULE} px-4 pt-5 align-top`}>
                <Link
                  href={access.href}
                  className={buttonVariants({ variant: 'secondary', size: 'md', wrap: true, className: CTA_CLASS })}
                >
                  {access.cta}
                </Link>
              </td>
              <td className={`${RULE} px-4 pt-5 align-top`}>
                <Link
                  href={betaOfferAvailable ? '/pricing' : pricingHref(cycleName(billing))}
                  className={buttonVariants({ variant: 'primary', size: 'md', wrap: true, className: CTA_CLASS })}
                >
                  {!checkoutAvailable ? 'View plans' : showTrial ? `Start ${TRIAL_DAYS}-day free trial` : 'Upgrade to Pro'}
                </Link>
                {showTrial && (
                  <p className={`mt-2 text-xs ${MUTED_CLASS}`}>
                    Card required. One trial per account. Cancel any time in the {TRIAL_DAYS} days at no charge.
                  </p>
                )}
                {readiness && !checkoutAvailable && (
                  <p className={`mt-2 text-xs ${MUTED_CLASS}`}>Pro activation is currently unavailable.</p>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </LandingRow>
  )
}
