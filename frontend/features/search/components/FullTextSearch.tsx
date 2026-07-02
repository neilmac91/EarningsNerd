'use client'

import { useEffect, useMemo, useState } from 'react'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { ArrowSquareOutIcon, CircleNotchIcon, MagnifyingGlassIcon, WarningIcon } from '@/lib/icons'
import { searchFullText, type FullTextSearchHit } from '@/features/search/api/search-api'

// EFTS is a global SEC index (independent of our ENABLE_FPI_FILINGS discovery flag), so the
// foreign-issuer forms are always searchable. EFTS matches on root_form, which folds amendments
// (20-F/A, 6-K/A) into the base form — one chip each covers amendments too.
const FORM_FILTERS = ['10-K', '10-Q', '8-K', '20-F', '6-K', '4'] as const

/**
 * Pure presentational list of full-text search hits. Each row links out to the matched document on
 * SEC EDGAR (the authoritative source). Exported separately so it can be unit-tested without hooks.
 */
export function FullTextSearchResults({ hits }: { hits: FullTextSearchHit[] }) {
  return (
    <ul className="divide-y divide-border-light dark:divide-white/[0.06] overflow-hidden rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e2 dark:shadow-none">
      {hits.map((hit) => {
        const href = hit.document_url || hit.sec_url || undefined
        const rowClass = 'flex items-start justify-between gap-4 px-4 py-3'
        const inner = (
          <>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                {hit.ticker && (
                  <span className="font-mono text-sm font-semibold text-brand-strong dark:text-brand-strong-dark">{hit.ticker}</span>
                )}
                <span className="truncate text-sm text-text-primary-light dark:text-text-secondary-dark">{hit.company ?? 'Unknown filer'}</span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-secondary-light dark:text-text-secondary-dark">
                {hit.form && (
                  <span className="rounded border border-border-light dark:border-white/10 bg-black/[0.03] dark:bg-white/5 px-1.5 py-0.5 uppercase tracking-wide">
                    {hit.form}
                  </span>
                )}
                {hit.filed_date && <span>Filed {hit.filed_date}</span>}
                {hit.period_ending && <span>· Period {hit.period_ending}</span>}
              </div>
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
                className={`${rowClass} transition-colors hover:bg-black/[0.03] dark:hover:bg-white/5`}
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

  const { data, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['full-text-search', query, formsParam, startDate, endDate],
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

  const toggleForm = (form: string) =>
    setForms((prev) => (prev.includes(form) ? prev.filter((f) => f !== form) : [...prev, form]))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-text-heading-light dark:text-text-heading-dark">Search filings</h1>
        <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Full-text search across SEC filings and their exhibits since 2001 — e.g.{' '}
          <span className="text-text-primary-light dark:text-text-primary-dark">&ldquo;going concern&rdquo;</span>,{' '}
          <span className="text-text-primary-light dark:text-text-primary-dark">&ldquo;material weakness&rdquo;</span>, or a product name.
        </p>
      </div>

      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-tertiary-light dark:text-text-secondary-dark" aria-hidden />
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Search the full text of filings…"
          aria-label="Search the full text of SEC filings"
          className="w-full rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-900/60 py-4 pl-12 pr-4 text-lg text-text-primary-light dark:text-text-primary-dark placeholder:text-text-tertiary-light dark:placeholder:text-text-secondary-dark backdrop-blur-sm focus:border-brand-light focus:outline-none"
        />
        {isFetching && (
          <CircleNotchIcon className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {FORM_FILTERS.map((form) => {
          const active = forms.includes(form)
          return (
            <button
              key={form}
              type="button"
              onClick={() => toggleForm(form)}
              aria-pressed={active}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                active
                  ? 'border-brand-light/40 dark:border-brand-dark/40 bg-brand-weak dark:bg-brand-dark/15 text-brand-strong dark:text-brand-strong-dark'
                  : 'border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-black/[0.03] dark:hover:bg-white/10'
              }`}
            >
              {form}
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
          className="rounded-lg border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-900/60 px-2 py-1 text-text-primary-light dark:text-text-primary-dark dark:[color-scheme:dark] focus:border-brand-light focus:outline-none"
        />
        <span>and</span>
        <input
          type="date"
          value={endDate}
          min={startDate || undefined}
          onChange={(e) => setEndDate(e.target.value)}
          aria-label="Filed on or before"
          className="rounded-lg border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-900/60 px-2 py-1 text-text-primary-light dark:text-text-primary-dark dark:[color-scheme:dark] focus:border-brand-light focus:outline-none"
        />
        {(startDate || endDate) && (
          <button
            type="button"
            onClick={() => {
              setStartDate('')
              setEndDate('')
            }}
            className="text-text-secondary-light dark:text-text-secondary-dark underline-offset-2 transition-colors hover:text-text-primary-light dark:hover:text-text-primary-dark hover:underline"
          >
            Clear dates
          </button>
        )}
        {!validRange && <span className="text-warning-light dark:text-warning-dark">Start date must be on or before end date.</span>}
      </div>

      {isError && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-xl border border-error-light/40 dark:border-error-dark/40 bg-error-light/10 dark:bg-error-dark/15 p-4 text-sm text-error-light dark:text-error-dark"
        >
          <span className="flex items-center gap-2">
            <WarningIcon className="h-4 w-4" aria-hidden />
            {error instanceof Error ? error.message : 'Search is temporarily unavailable.'}
          </span>
          <button
            type="button"
            onClick={() => refetch()}
            className="rounded-lg border border-error-light/40 dark:border-error-dark/40 px-3 py-1 text-xs font-medium transition-colors hover:bg-error-light/10 dark:hover:bg-error-dark/15"
          >
            Retry
          </button>
        </div>
      )}

      {query.length === 0 && (
        <p className="rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e2 dark:shadow-none p-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
          Type a query to search the full text of SEC filings.
        </p>
      )}

      {query.length > 0 && !isError && data && (
        data.hits.length > 0 ? (
          <div className="space-y-2">
            <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
              {data.total.toLocaleString()} filing{data.total === 1 ? '' : 's'} match — showing{' '}
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
