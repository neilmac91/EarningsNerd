'use client'

/* =============================================================================
   FilingIndex — features/filings/components/FilingIndex.tsx   (2026-10)
   -----------------------------------------------------------------------------
   The company page's SEC filings list, rebuilt as an INDEX (design review
   2026-10-08 · docs/design/filings-index-review.md · Filings Index Review.dc.html):
     - ONE surface: the section Card. Years and rows are divided by hairlines
       (DataTable manners) — no boxes in boxes, no stripes, no tints.
     - Type carries identity: form codes in the data face, the PERIOD OF REPORT
       as each row's name, the filed date in a data column. Form types are not
       colour-coded (blue is a status colour, sage is the action colour).
     - One primary action per screen: the latest-filing lead. Every row is ONE
       link to its filing; EDGAR is a SIBLING link placed in the actions track —
       never nested inside the row link.
     - States in place: a ledger-shaped skeleton, Notice + RetryButton, a
       filter-empty line that names the filters, an honest no-filings line.
   The page keeps the queries, the SSR seed + A4 year expansion, the prefetch and
   the "Show full history" control (passed in as `footerAction`); the filters
   live here, reset per company by the page's `key`.
============================================================================= */

import Link from 'next/link'
import { useId, useMemo, useState, type ReactNode, type RefObject } from 'react'
import { ArrowRightIcon, ArrowSquareOutIcon, CaretDownIcon, CaretRightIcon } from '@/lib/icons'
import { Badge, Button, buttonVariants, Card, Notice, SegmentedControl, Select, Skeleton, cx } from '@/components/ui'
import { RetryButton, type RetainedFailure } from '@/hooks/useRetainedFailure'
import type { Filing } from '@/features/filings/api/filings-api'
import { fiscalYear, groupByFiscalYear } from '@/features/filings/lib/fiscalYear'
import { periodLabel, sortForms } from '@/features/filings/lib/filingPeriod'
import { recommendedFilingNoun } from '@/features/filings/lib/recommendedFiling'
import FilingsHistoryNote from '@/features/filings/components/FilingsHistoryNote'
import { formatLocalDate } from '@/lib/format'

export type FilingIndexStatus = 'loading' | 'error' | 'ready'

export interface FilingIndexProps {
  /** Display name ("NVIDIA Corp"), for the lead's copy. */
  companyName: string
  /** The FULL loaded list, never pre-filtered: filters, years, Latest and the history note derive from it. */
  filings: Filing[] | undefined
  status: FilingIndexStatus
  /** The filings query's retained failure (useRetainedFailure): the Retry is RetryButton. */
  failure: RetainedFailure
  /** The section heading (tabIndex -1): RetryButton's and "Show full history"'s focus target. */
  headingRef: RefObject<HTMLHeadingElement>
  /** The newest non-superseded filing (selectRecommendedFiling over the FULL list); null hides the lead. */
  latest: Filing | null
  /** Open years (the page owns them: the SSR seed and the A4 top-three rule). */
  expandedYears: ReadonlySet<string>
  onToggleYear: (year: string) => void
  /** The company CIK, for the history note's EDGAR hand-off. */
  cik?: string
  /** The footer's action: the page's "Show full history" Button. */
  footerAction?: ReactNode
}

// One grid template for the column header, every row and the skeleton, so codes, periods and dates
// align down the whole list. Phones: a code column + the period/filed stack (a base track is always
// set — the responsive-grid-base-track rule). md+: form · period · filed · actions.
const ROW_TRACKS = 'grid-cols-[3.5rem_minmax(0,1fr)] gap-x-2 md:grid-cols-[4.5rem_minmax(0,1fr)_8.5rem_7rem] md:gap-x-0'
// Display is set apart from the tracks: `grid` and `hidden` in one class string would resolve by
// stylesheet order (cx does no tailwind-merge).
const ROW_GRID = `grid ${ROW_TRACKS}`
const HAIRLINE = 'border-t border-border-light dark:border-white/10'
const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const ALL = 'all'
const fmt = (iso: string | null | undefined) => formatLocalDate(iso, 'MMM d, yyyy')

export function FilingIndex({
  companyName,
  filings,
  status,
  failure,
  headingRef,
  latest,
  expandedYears,
  onToggleYear,
  cik,
  footerAction,
}: FilingIndexProps) {
  const baseId = useId()
  const headingId = `${baseId}-heading`
  const [form, setForm] = useState<string>(ALL)
  const [year, setYear] = useState('')

  const view = useMemo(() => {
    const all = filings ?? []
    const forms = sortForms(all.map((f) => f.filing_type))
    const years = Array.from(new Set(all.map((f) => fiscalYear(f)).filter(Boolean))).sort((a, b) => Number(b) - Number(a))
    const shown = all.filter((f) => (form === ALL || f.filing_type === form) && (!year || fiscalYear(f) === year))
    const grouped = groupByFiscalYear(shown)
    const groups = Object.keys(grouped)
      .sort((a, b) => Number(b) - Number(a))
      .map((y) => ({ year: y, filings: grouped[y] }))
    // Earliest filing_date in the FULL list; ISO strings compare lexicographically.
    const oldest = all.reduce<string | null>((o, f) => (!o || f.filing_date < o ? f.filing_date : o), null)
    return { all, forms, years, shown, groups, oldest }
  }, [filings, form, year])

  const total = view.all.length
  const filtered = form !== ALL || year !== ''
  const countLabel = filtered ? `${view.shown.length} of ${total} filings` : `${total} ${total === 1 ? 'filing' : 'filings'}`
  const showToolbar = status === 'ready' && total > 0 && (view.forms.length > 1 || view.years.length > 1)

  const chooseYear = (next: string) => {
    setYear(next)
    // A year filter shows its result: open the chosen year's group if it was collapsed.
    if (next && !expandedYears.has(next)) onToggleYear(next)
  }
  const clearFilters = () => {
    setForm(ALL)
    setYear('')
  }

  return (
    <Card as="section" aria-labelledby={headingId}>
      <div className="flex flex-col gap-3 px-4 pt-4 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between sm:gap-4 sm:px-6 sm:pt-6">
        <div className="flex min-w-0 items-baseline gap-3">
          <h2 id={headingId} ref={headingRef} tabIndex={-1} className={cx('text-xl font-semibold outline-none', INK)}>
            SEC filings
          </h2>
          {status === 'ready' && total > 0 && (
            <span className={cx('font-data text-xs tabular-nums', MUTED)}>{countLabel}</span>
          )}
        </div>
        {showToolbar && (
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {view.forms.length > 1 && (
              <SegmentedControl
                label="Filter by form"
                size="adaptive"
                fullWidth
                value={form}
                onChange={setForm}
                options={[{ value: ALL, label: 'All' }, ...view.forms.map((f) => ({ value: f, label: f, mono: true }))]}
              />
            )}
            {view.years.length > 1 && (
              <Select
                aria-label="Filter by report year"
                density="compact"
                className="sm:w-36"
                value={year}
                onChange={(e) => chooseYear(e.target.value)}
              >
                <option value="">All years</option>
                {view.years.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </Select>
            )}
          </div>
        )}
      </div>

      {status === 'ready' && latest && <LatestFilingLead filing={latest} companyName={companyName} />}

      {status === 'loading' && <FilingIndexSkeleton />}

      {status === 'error' && (
        <div className="px-4 pb-5 pt-4 sm:px-6 sm:pb-6">
          <Notice
            variant="error"
            title="Couldn’t load filings"
            description="The filings service didn’t respond. The rest of this page is unaffected."
            action={
              <RetryButton size="sm" failures={[failure]} focusTarget={headingRef}>
                Retry
              </RetryButton>
            }
          />
        </div>
      )}

      {status === 'ready' && total === 0 && (
        <div role="status" className="px-4 pb-6 pt-4 sm:px-6">
          <p className={cx('text-sm font-semibold', INK)}>No filings to show</p>
          <p className={cx('mt-1 max-w-prose text-sm', MUTED)}>
            We haven’t found any periodic reports for this company on EDGAR yet.
          </p>
        </div>
      )}

      {status === 'ready' && total > 0 && (
        <div className="px-4 pt-2 sm:px-6">
          {/* The visible column labels; each row's link already names its form, period and filed date. */}
          <div aria-hidden="true" className={cx('hidden md:grid', ROW_TRACKS, 'pb-2 pt-4 text-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark')}>
            <span>Form</span>
            <span>Period</span>
            <span>Filed</span>
            <span />
          </div>

          {view.groups.length === 0 ? (
            <div role="status" className={cx(HAIRLINE, 'pb-4 pt-4')}>
              <p className={cx('text-sm font-semibold', INK)}>{emptyTitle(form, year)}</p>
              <p className={cx('mt-0.5 text-sm', MUTED)}>0 of {total} filings match these filters.</p>
              <Button variant="ghost" size="sm" className="-ml-3 mt-2" onClick={clearFilters}>
                Clear filters
              </Button>
            </div>
          ) : (
            view.groups.map(({ year: y, filings: rows }) => {
              const open = expandedYears.has(y)
              const listId = `${baseId}-year-${y}`
              return (
                <div key={y} className={HAIRLINE}>
                  <h3 className="text-sm">
                    <button
                      type="button"
                      aria-expanded={open}
                      aria-controls={listId}
                      onClick={() => onToggleYear(y)}
                      className={cx(
                        '-mx-3 flex h-12 w-[calc(100%+1.5rem)] items-center justify-between gap-3 rounded-lg px-3 text-left md:h-11',
                        'transition-colors duration-fast hover:bg-white dark:hover:bg-white/[0.03]',
                        'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
                      )}
                    >
                      <span className={cx('font-data text-sm font-semibold tabular-nums', INK)}>
                        <span className="sr-only">Report year</span>{' '}
                        {y}
                      </span>{' '}
                      <span className={cx('flex items-center gap-2.5 font-data text-xs tabular-nums', MUTED)}>
                        {rows.length} {rows.length === 1 ? 'filing' : 'filings'}
                        <CaretDownIcon
                          aria-hidden="true"
                          className={cx(
                            'h-4 w-4 text-text-tertiary-light transition-transform duration-base motion-reduce:transition-none dark:text-text-secondary-dark',
                            !open && '-rotate-90',
                          )}
                        />
                      </span>
                    </button>
                  </h3>
                  {/* Collapsed lists stay in the DOM (hidden), so aria-controls always resolves. */}
                  <ol id={listId} role="list" hidden={!open}>
                    {rows.map((filing) => (
                      <FilingIndexRow key={filing.id} filing={filing} filings={view.all} isLatest={latest?.id === filing.id} />
                    ))}
                  </ol>
                </div>
              )
            })
          )}
        </div>
      )}

      {status === 'ready' && total > 0 && ((view.oldest && cik) || footerAction) && (
        <div className={cx(HAIRLINE, 'mt-1 flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-6')}>
          <FilingsHistoryNote oldestFilingDate={view.oldest} cik={cik} />
          {footerAction}
        </div>
      )}
    </Card>
  )
}

function emptyTitle(form: string, year: string): string {
  if (form !== ALL && year) return `No ${form} filings in ${year}.`
  if (form !== ALL) return `No ${form} filings.`
  return `No filings in ${year}.`
}

/** The one primary action on the page: an inset well (the card's darker neighbour), no tint, no icon. */
function LatestFilingLead({ filing, companyName }: { filing: Filing; companyName: string }) {
  const filed = fmt(filing.filing_date)
  return (
    <div className="mx-4 mt-4 flex flex-col gap-4 rounded-lg bg-background-light p-4 dark:bg-background-dark sm:mx-6 sm:mt-5 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:p-5">
      <div className="min-w-0">
        <p className={cx('text-xs font-semibold', MUTED)}>Latest filing</p>
        <p className="mt-1.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5">
          <span className={cx('font-data text-sm font-semibold', INK)}>{filing.filing_type}</span>
          <span className={cx('font-heading text-lg font-semibold', INK)}>{periodLabel(filing) ?? `Filed ${filed}`}</span>
        </p>
        <p className={cx('mt-1 text-sm', MUTED)}>
          Filed <span className="tnum">{filed}</span>. {companyName}’s most recent {recommendedFilingNoun(filing)}. Start with its AI summary.
        </p>
      </div>
      <Link
        href={`/filing/${filing.id}`}
        className={buttonVariants({ variant: 'primary', className: 'w-full shrink-0 sm:w-auto' })}
      >
        Summarize this filing
        <ArrowRightIcon aria-hidden="true" className="h-4 w-4" />
      </Link>
    </div>
  )
}

/**
 * One filing: the whole row is ONE link to /filing/{id}, named by its own content (form, period,
 * markers, "Filed …") — no aria-label, so the accessible name matches what is on screen. EDGAR is a
 * sibling anchor positioned in the actions track (44px square on phones, a 32px text link from md).
 */
function FilingIndexRow({ filing, filings, isLatest }: { filing: Filing; filings: Filing[]; isLatest: boolean }) {
  const period = periodLabel(filing)
  const filed = fmt(filing.filing_date)
  const superseded = Boolean(filing.superseded_by_accession)
  const replacement = superseded
    ? filings.find((c) => c.id !== filing.id && c.accession_number === filing.superseded_by_accession)
    : undefined
  const original = filings.find((c) => c.id !== filing.id && c.superseded_by_accession === filing.accession_number)
  const note = superseded
    ? replacement
      ? `Superseded by the ${replacement.filing_type} filed ${fmt(replacement.filing_date)}`
      : 'A later amendment supersedes this filing.'
    : original
      ? `Amends the ${original.filing_type} filed ${fmt(original.filing_date)}`
      : null

  return (
    <li className={cx('relative', HAIRLINE)}>
      <Link
        href={`/filing/${filing.id}`}
        className={cx(
          ROW_GRID,
          '-mx-3 items-start rounded-lg py-3 pl-3 pr-14 md:min-h-12 md:items-center md:py-0 md:pr-3',
          'transition-colors duration-fast hover:bg-white active:bg-brand-weak/60',
          'focus-visible:outline-none focus-visible:shadow-ring-brand',
          'dark:hover:bg-white/[0.03] dark:active:bg-brand-weak-dark dark:focus-visible:shadow-ring-brand-dark',
        )}
      >
        <span className={cx('font-data text-sm font-semibold', INK)}>{filing.filing_type}</span>{' '}
        <span className="min-w-0 md:py-3 md:pr-3">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className={cx('text-sm font-medium', period ? INK : MUTED)}>{period ?? 'No period of report'}</span>{' '}
            {isLatest && <Badge variant="brand">Latest</Badge>}{' '}
            {superseded && (
              <Badge variant="warning" title="A later amendment supersedes this filing. The original remains available.">
                Superseded
              </Badge>
            )}
          </span>
          {note && <span className={cx('mt-0.5 block text-xs', MUTED)}> {note}</span>}
        </span>{' '}
        <span className={cx('col-start-2 mt-1 font-data text-xs tabular-nums md:col-start-auto md:mt-0 md:text-sm', MUTED)}>
          <span className="md:sr-only">Filed</span>{' '}
          {filed}
        </span>
        <span aria-hidden="true" className="hidden justify-end text-text-tertiary-light dark:text-text-secondary-dark md:flex">
          <CaretRightIcon className="h-4 w-4" />
        </span>
      </Link>
      {filing.sec_url && (
        <a
          href={filing.sec_url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`View the ${filing.filing_type} filed ${filed} on SEC EDGAR (opens in a new tab)`}
          className={cx(
            'absolute right-0 top-1/2 inline-flex h-11 w-11 -translate-y-1/2 items-center justify-center gap-1.5 rounded-lg',
            'md:right-7 md:h-8 md:w-auto md:px-2.5',
            'text-text-secondary-light transition-colors duration-fast hover:bg-brand-weak hover:text-brand-strong',
            'focus-visible:outline-none focus-visible:shadow-ring-brand',
            'dark:text-text-secondary-dark dark:hover:bg-brand-weak-dark dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark',
          )}
        >
          <span aria-hidden="true" className="hidden text-xs font-semibold md:inline">EDGAR</span>
          <ArrowSquareOutIcon aria-hidden="true" className="h-[18px] w-[18px] md:h-3.5 md:w-3.5" />
        </a>
      )}
    </li>
  )
}

const BONE_WIDTHS = ['w-3/5', 'w-1/2', 'w-7/12']

/** The ledger's own shape: raw bones (aria-hidden) inside ONE role="status" wrapper (DS §4). */
function FilingIndexSkeleton() {
  return (
    <div role="status" aria-label="Loading filings" className="px-4 pb-4 pt-2 sm:px-6">
      <div aria-hidden="true">
        <div className={cx('hidden md:grid', ROW_TRACKS, 'pb-2 pt-4')}>
          <Skeleton className="h-3 w-9" />
          <Skeleton className="h-3 w-12" />
          <Skeleton className="h-3 w-10" />
        </div>
        {[3, 2].map((count, group) => (
          <div key={group} className={HAIRLINE}>
            <div className="flex h-12 items-center justify-between md:h-11">
              <Skeleton className="h-3.5 w-10" />
              <Skeleton className="h-3 w-16" />
            </div>
            {Array.from({ length: count }, (_, i) => (
              <div key={i} className={cx(ROW_GRID, HAIRLINE, 'items-center py-3 md:min-h-12 md:py-0')}>
                <Skeleton className="h-3.5 w-9" />
                <Skeleton className={cx('h-3.5', BONE_WIDTHS[i % BONE_WIDTHS.length])} />
                <Skeleton className="col-start-2 mt-2 h-3 w-24 md:col-start-auto md:mt-0 md:h-3.5" />
                <span className="hidden justify-end md:flex">
                  <Skeleton className="h-3 w-16" />
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <span className="sr-only">Loading filings…</span>
    </div>
  )
}
