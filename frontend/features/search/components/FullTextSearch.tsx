'use client'

import { queryKeys } from '@/lib/queryKeys'
import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/client'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { ArrowSquareOutIcon, MagnifyingGlassIcon, WarningIcon } from '@/lib/icons'
import { searchFullText, type FullTextSearchHit } from '@/features/search/api/search-api'
import { FieldSpinner, cx, inputClasses } from '@/components/ui'
import { fmtCount } from '@/lib/format'
import { SEARCH_QUERY_MAX, clampQuery } from '@/features/search/lib/queryLimit'

// EFTS is a global SEC index (independent of our ENABLE_FPI_FILINGS discovery flag), so the
// foreign-issuer forms are always searchable. EFTS matches on root_form, which folds amendments
// (20-F/A, 6-K/A) into the base form — one chip each covers amendments too. A form whose code is a
// bare number is labelled by its name ("Form 4"), so the chip reads as a form, not a count.
const FORM_FILTERS = [
  { form: '10-K', label: '10-K' },
  { form: '10-Q', label: '10-Q' },
  { form: '8-K', label: '8-K' },
  { form: '20-F', label: '20-F' },
  { form: '6-K', label: '6-K' },
  { form: '4', label: 'Form 4' },
] as const

/** A value in a hit's meta line, a form code or a date: one unbreakable run, so it never splits at its hyphen. */
const Value = ({ children, className }: { children: ReactNode; className?: string }) => (
  <span className={cx('whitespace-nowrap', className)}>{children}</span>
)

/** The middot after a fact, kept to it by a no-break space, so a wrapped line never starts with one.
 *  Assistive tech hears a comma (FilingIdentity's Sep). */
const Sep = () => (
  <>
    {'\u00a0'}
    <span aria-hidden="true">·</span>
    <span className="sr-only">,</span>
  </>
)

/**
 * Pure presentational list of full-text search hits. Each row links out to the matched document on
 * SEC EDGAR (the authoritative source). Exported separately so it can be unit-tested without hooks.
 * Nothing in a row truncates: the company name wraps under its ticker, and the meta line wraps between
 * its facts, each value whole.
 */
export function FullTextSearchResults({ hits }: { hits: FullTextSearchHit[] }) {
  return (
    // The list clips its rows, and a row's meta line holds sr-only commas, which are absolutely positioned:
    // `relative` makes the list their containing block, so the clip holds them
    // (lessons/frontend-sr-only-needs-a-positioned-clip.md).
    <ul className="relative divide-y divide-border-light dark:divide-white/[0.06] overflow-hidden rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e2 dark:shadow-none">
      {hits.map((hit) => {
        const href = hit.document_url || hit.sec_url || undefined
        const rowClass = 'flex items-start justify-between gap-4 px-4 py-3'
        // The meta line's facts. Each is one run (inline-block) holding its label, its value and the middot after
        // it, so the line breaks only at the space between two facts; a fact wider than the whole line wraps inside,
        // after its label, the value whole.
        const facts = [
          // A form code is text in the data face, never a chip (DESIGN.md › Chips).
          hit.form && <Value key="form" className="font-data text-text-primary-light dark:text-text-primary-dark">{hit.form}</Value>,
          hit.filed_date && <Fragment key="filed">Filed <Value>{hit.filed_date}</Value></Fragment>,
          hit.period_ending && <Fragment key="period">Period <Value>{hit.period_ending}</Value></Fragment>,
        ].filter(Boolean)
        const inner = (
          <>
            <div className="min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-2">
                {hit.ticker && (
                  <span className="font-mono text-sm font-semibold text-brand-strong dark:text-brand-strong-dark">{hit.ticker}</span>
                )}
                <span className="min-w-0 break-words text-sm text-text-primary-light dark:text-text-primary-dark">{hit.company ?? 'Unknown filer'}</span>
              </div>
              <p className="mt-1 text-xs text-text-secondary-light dark:text-text-secondary-dark">
                {facts.map((fact, i) => (
                  <Fragment key={i}>
                    {i > 0 && ' '}
                    <span className="inline-block">
                      {fact}
                      {i < facts.length - 1 && <Sep />}
                    </span>
                  </Fragment>
                ))}
              </p>
            </div>
            {/* Only the linkable rows get the external-link affordance. */}
            {href && <ArrowSquareOutIcon className="mt-1 h-4 w-4 shrink-0 text-text-secondary-light dark:text-text-secondary-dark" aria-hidden />}
          </>
        )
        return (
          <li key={`${hit.accession_no}:${hit.document ?? ''}`}>
            {/* Render a real link only when a URL exists; otherwise a plain row (no empty <a>). */}
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                // The list clips its rows (overflow-hidden), so the ring sits inside the row. Hover brightens
                // to the product's row tint (DESIGN_SYSTEM.md section 6), never darkens.
                className={`${rowClass} transition-colors hover:bg-brand-weak focus-visible:outline-none focus-visible:shadow-ring-brand-inset dark:hover:bg-white/5 dark:focus-visible:shadow-ring-brand-inset-dark`}
              >
                {inner}
              </a>
            ) : (
              <div className={rowClass}>{inner}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export default function FullTextSearch() {
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')
  const [forms, setForms] = useState<string[]>([])
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // Debounce the raw input into the query that actually drives the request.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(input.trim()), 350)
    return () => clearTimeout(timer)
  }, [input])

  const formsParam = useMemo(() => (forms.length ? forms.join(',') : undefined), [forms])

  // ISO date strings sort lexicographically == chronologically. While the user is mid-edit the
  // range can be inverted (start > end); don't fire a request that the upstream would 400/502 on.
  const validRange = !startDate || !endDate || startDate <= endDate

  const inputRef = useRef<HTMLInputElement>(null)
  const search = useQuery({
    queryKey: queryKeys.fullTextSearch(query, formsParam, startDate, endDate),
    queryFn: () =>
      searchFullText({
        q: query,
        forms: formsParam,
        startdt: startDate || undefined,
        enddt: endDate || undefined,
      }),
    enabled: query.length > 0 && validRange,
    placeholderData: keepPreviousData, // keep prior results visible while refining (no flash)
    staleTime: 5 * 60 * 1000,
  })
  const { data, isFetching } = search
  // The alert keeps its failure through any refetch until the query's own data replaces it (a focused
  // Retry in it included; keepPreviousData's placeholder does not count); a new query is another query,
  // so typing one drops the old failure.
  const failure = useRetainedFailure(search, queryKeys.fullTextSearch(query, formsParam, startDate, endDate))
  // The backend's own detail (the 429 and 502 sentences) reads verbatim, or the surface's sentence when
  // the body carried none: `backendDetail` is unset for a lost connection, a non-string detail, an HTML
  // gateway page, and lib/api/client's status fallbacks or axios's "Request failed with status code N".
  const backendDetail = failure.error instanceof ApiError ? failure.error.backendDetail : undefined
  const errorText =
    typeof backendDetail === 'string' && backendDetail ? backendDetail : 'Search did not load. Try again in a minute.'

  const toggleForm = (form: string) =>
    setForms((prev) => (prev.includes(form) ? prev.filter((f) => f !== form) : [...prev, form]))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-text-heading-light dark:text-text-heading-dark">Search filings</h1>
        <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Full-text search across SEC filings and their exhibits since 2001. Try{' '}
          <span className="text-text-primary-light dark:text-text-primary-dark">&ldquo;going concern&rdquo;</span>,{' '}
          <span className="text-text-primary-light dark:text-text-primary-dark">&ldquo;material weakness&rdquo;</span>, or a product name.
        </p>
      </div>

      <div className="relative">
        <MagnifyingGlassIcon
          aria-hidden
          className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-text-tertiary-light dark:text-text-secondary-dark"
        />
        <input
          ref={inputRef}
          value={input}
          // The backend refuses a longer query (routers/search.py, `q: str = Query(..., max_length=...)`), counted
          // in code points; the field clamps the trimmed query it sends by code points too, where a native maxLength
          // would count UTF-16 units and the leading whitespace the trim drops (features/search/lib/queryLimit.ts,
          // held to the router by tests/unit/searchQueryLimitParity.spec.tsx).
          onChange={(e) => setInput(clampQuery(e.target.value, SEARCH_QUERY_MAX))}
          placeholder="Search the full text of filings…"
          aria-label="Search the full text of SEC filings"
          aria-busy={isFetching || undefined}
          className={inputClasses({ leadingIcon: true, trailingIcon: true })}
        />
        {/* Inset always reserved, not only while fetching: see CompanySearch. */}
        {isFetching && <FieldSpinner />}
      </div>

      <div className="flex flex-wrap gap-2">
        {FORM_FILTERS.map((filter) => {
          const active = forms.includes(filter.form)
          // An unselected toggle brightens like a result row (brand-weak); in dark it rests on white/5,
          // so its hover steps to white/10, as the product's other chip toggles do.
          return (
            <button
              key={filter.form}
              type="button"
              onClick={() => toggleForm(filter.form)}
              aria-pressed={active}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${
                active
                  ? 'border-brand-border dark:border-brand-dark/40 bg-brand-weak dark:bg-brand-dark/15 text-brand-strong dark:text-brand-strong-dark'
                  : 'border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:bg-white/10'
              }`}
            >
              {filter.label}
            </button>
          )
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondary-light dark:text-text-secondary-dark">
        <span>Filed between</span>
        <input
          type="date"
          value={startDate}
          max={endDate || undefined}
          onChange={(e) => setStartDate(e.target.value)}
          aria-label="Filed on or after"
          className="rounded-lg border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark px-2 py-1 text-text-primary-light dark:text-text-primary-dark dark:[color-scheme:dark] focus:border-brand focus:shadow-ring-brand focus:outline-none focus:ring-0 focus:ring-offset-0 dark:focus:border-brand-dark dark:focus:shadow-ring-brand-dark"
        />
        <span>and</span>
        <input
          type="date"
          value={endDate}
          min={startDate || undefined}
          onChange={(e) => setEndDate(e.target.value)}
          aria-label="Filed on or before"
          className="rounded-lg border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark px-2 py-1 text-text-primary-light dark:text-text-primary-dark dark:[color-scheme:dark] focus:border-brand focus:shadow-ring-brand focus:outline-none focus:ring-0 focus:ring-offset-0 dark:focus:border-brand-dark dark:focus:shadow-ring-brand-dark"
        />
        {(startDate || endDate) && (
          <button
            type="button"
            onClick={() => {
              setStartDate('')
              setEndDate('')
            }}
            className="rounded text-text-secondary-light dark:text-text-secondary-dark underline-offset-2 transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark hover:underline focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
          >
            Clear dates
          </button>
        )}
        {!validRange && <span className="text-warning-light dark:text-warning-dark">Start date must be on or before end date.</span>}
      </div>

      {failure.failed && (
        // The message takes the line it needs (12rem at least, so it never thins to a word a line) and
        // Retry wraps under it when the two do not fit; the glyph keeps its size.
        <div
          role="alert"
          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-error-light/40 dark:border-error-dark/40 bg-error-light/10 dark:bg-error-dark/15 p-4 text-sm text-error-light dark:text-error-dark"
        >
          <span className="flex min-w-0 flex-[1_1_12rem] items-start gap-2">
            <WarningIcon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <span className="min-w-0 break-words">{errorText}</span>
          </span>
          {/* When the alert goes while Retry holds focus (the search lands), focus moves to the field,
              except after a tap, which would raise the touch keyboard. */}
          <RetryButton size="sm" failures={[failure]} focusTarget={inputRef} textField>
            Retry
          </RetryButton>
        </div>
      )}

      {query.length === 0 && (
        <p className="rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e2 dark:shadow-none p-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Type a query to search the full text of SEC filings.
        </p>
      )}

      {/* While a failure is held, no hits render: during its Retry, `data` is the previous query's
          results (keepPreviousData), which must not show under this query. */}
      {query.length > 0 && !failure.failed && data && (
        data.hits.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
              {fmtCount(data.total)} filing{data.total === 1 ? '' : 's'} match · showing{' '}
              {data.count}
            </p>
            <FullTextSearchResults hits={data.hits} />
          </div>
        ) : (
          <p className="rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e2 dark:shadow-none p-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            No filings match &ldquo;{query}&rdquo;.
          </p>
        )
      )}
    </div>
  )
}
