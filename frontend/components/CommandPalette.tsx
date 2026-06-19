'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { Search, Loader2, FileText, ExternalLink } from 'lucide-react'
import { format, parseISO } from 'date-fns'

import { searchFullText, type SearchHit } from '@/features/search/api/search-api'
import { ApiError } from '@/lib/api/client'
import { OPEN_COMMAND_PALETTE_EVENT } from '@/lib/commandPalette'
import analytics from '@/lib/analytics'

const FORM_FILTERS: { label: string; value: string }[] = [
  { label: 'All filings', value: '' },
  { label: '10-K', value: '10-K' },
  { label: '10-Q', value: '10-Q' },
  { label: '8-K', value: '8-K' },
]

const fmtDate = (value: string | null): string | null => {
  if (!value) return null
  try {
    return format(parseISO(value), 'MMM d, yyyy')
  } catch {
    return value
  }
}

/**
 * Global ⌘K command palette for EDGAR full-text search. Mounted once in the root
 * layout; opens on Cmd/Ctrl+K (or the `open-command-palette` event from the
 * header button) and searches the full text of SEC filings via /api/search/full-text.
 */
export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [forms, setForms] = useState('')
  const [highlightIndex, setHighlightIndex] = useState(0)
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const lastTracked = useRef<string>('')

  // Cmd/Ctrl+K toggles; the header button opens via a custom event; Escape closes.
  // Bound once (empty deps): the toggle uses a functional update and Escape's
  // setOpen(false) is a no-op bailout when already closed, so `open` isn't needed.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((o) => !o)
      } else if (e.key === 'Escape') {
        setOpen(false)
      }
    }
    const onOpen = () => setOpen(true)
    document.addEventListener('keydown', onKeyDown)
    window.addEventListener(OPEN_COMMAND_PALETTE_EVENT, onOpen)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener(OPEN_COMMAND_PALETTE_EVENT, onOpen)
    }
  }, [])

  // Lock background scroll and focus the input while open. On close, reset the
  // analytics dedupe so reopening and repeating a search is tracked as new.
  useEffect(() => {
    if (!open) {
      lastTracked.current = ''
      return
    }
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const t = setTimeout(() => {
      inputRef.current?.focus()
      inputRef.current?.select()
    }, 0)
    return () => {
      document.body.style.overflow = previousOverflow
      clearTimeout(t)
    }
  }, [open])

  // Debounce the query.
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(query.trim()), 300)
    return () => clearTimeout(t)
  }, [query])

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['search-full-text', debouncedQuery, forms],
    queryFn: () => searchFullText({ q: debouncedQuery, forms: forms || undefined }),
    enabled: open && debouncedQuery.length > 0,
    retry: (failureCount, err) =>
      err instanceof ApiError && err.isRetryable ? failureCount < 2 : false,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 4000),
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  })

  const hits = useMemo(() => data?.hits ?? [], [data])

  useEffect(() => {
    setHighlightIndex(0)
  }, [debouncedQuery, forms])

  // Keep the highlighted row in view (no-op outside a real browser).
  useEffect(() => {
    if (!open) return
    const el = document.getElementById(`cmdk-option-${highlightIndex}`)
    if (el && typeof el.scrollIntoView === 'function') {
      try {
        el.scrollIntoView({ block: 'nearest' })
      } catch {
        /* jsdom / unsupported environments */
      }
    }
  }, [highlightIndex, open])

  // Track one analytics event per distinct completed search while open.
  useEffect(() => {
    if (
      open &&
      debouncedQuery.length > 0 &&
      !isLoading &&
      !isError &&
      data &&
      debouncedQuery !== lastTracked.current
    ) {
      analytics.filingsSearched(debouncedQuery, data.total)
      lastTracked.current = debouncedQuery
    }
  }, [open, debouncedQuery, isLoading, isError, data])

  const close = () => setOpen(false)

  const goToHit = (hit: SearchHit | undefined, forceExternal = false) => {
    if (!hit) return
    close()
    if (hit.ticker && !forceExternal) {
      // Keep the user in-app, where they can open the filing and generate a summary.
      router.push(`/company/${hit.ticker}`)
    } else if (hit.document_url && typeof window !== 'undefined') {
      // No ticker (e.g. some funds/individuals), or an explicit "open on SEC"
      // (Cmd/Ctrl+Enter) — open the matched filing on EDGAR.
      window.open(hit.document_url, '_blank', 'noopener,noreferrer')
    }
  }

  const onInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      if (hits.length === 0) return
      e.preventDefault()
      setHighlightIndex((i) => (i + 1) % hits.length)
    } else if (e.key === 'ArrowUp') {
      if (hits.length === 0) return
      e.preventDefault()
      setHighlightIndex((i) => (i <= 0 ? hits.length - 1 : i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      // Cmd/Ctrl+Enter opens the filing on SEC directly; plain Enter goes in-app.
      goToHit(hits[highlightIndex] ?? hits[0], e.metaKey || e.ctrlKey)
    }
  }

  if (!open) return null

  const showResults = hits.length > 0
  const showEmpty =
    !isLoading && !isError && debouncedQuery.length > 0 && hits.length === 0

  return (
    <div
      className="fixed inset-0 z-[70] flex items-start justify-center bg-black/60 p-4 pt-[12vh] backdrop-blur-sm"
      role="presentation"
      onMouseDown={close}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Search SEC filings"
        onMouseDown={(e) => e.stopPropagation()}
        className="flex max-h-[70vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-border-light bg-background-light shadow-2xl dark:border-border-dark dark:bg-background-dark"
      >
        {/* Search input */}
        <div className="flex items-center gap-3 border-b border-border-light px-4 dark:border-border-dark">
          <Search
            className="h-5 w-5 shrink-0 text-text-tertiary-light dark:text-text-tertiary-dark"
            aria-hidden="true"
          />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKeyDown}
            placeholder="Search the full text of SEC filings…"
            role="combobox"
            aria-expanded={showResults}
            aria-controls="cmdk-results"
            aria-activedescendant={showResults ? `cmdk-option-${highlightIndex}` : undefined}
            aria-autocomplete="list"
            aria-label="Search SEC filings"
            className="w-full bg-transparent py-4 text-base text-text-primary-light outline-none placeholder:text-text-tertiary-light dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
          />
          {isLoading && (
            <Loader2 className="h-4 w-4 shrink-0 animate-spin text-mint-500" aria-hidden="true" />
          )}
          <kbd className="hidden shrink-0 rounded-md border border-border-light px-1.5 py-0.5 font-mono text-[10px] text-text-tertiary-light dark:border-border-dark dark:text-text-tertiary-dark sm:block">
            ESC
          </kbd>
        </div>

        {/* Form filters */}
        <div className="flex items-center gap-2 border-b border-border-light px-4 py-2 dark:border-border-dark">
          {FORM_FILTERS.map((f) => (
            <button
              key={f.value || 'all'}
              type="button"
              onClick={() => setForms(f.value)}
              aria-pressed={forms === f.value}
              className={`rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                forms === f.value
                  ? 'bg-mint-500 text-slate-950'
                  : 'bg-panel-light text-text-secondary-light hover:bg-border-light dark:bg-panel-dark dark:text-text-secondary-dark dark:hover:bg-border-dark'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Results / states */}
        <div
          id="cmdk-results"
          role="listbox"
          aria-label="Filing results"
          className="min-h-0 flex-1 overflow-y-auto"
        >
          {isError && (
            <div role="alert" className="flex items-center justify-between gap-3 p-4">
              <p className="text-sm text-red-500">
                {error instanceof ApiError ? error.detail : 'Search is temporarily unavailable.'}
              </p>
              <button
                type="button"
                onClick={() => refetch()}
                className="shrink-0 rounded-md border border-border-light px-3 py-1.5 text-xs font-medium text-text-secondary-light hover:bg-panel-light dark:border-border-dark dark:text-text-secondary-dark dark:hover:bg-panel-dark"
              >
                Try again
              </button>
            </div>
          )}

          {!isError && debouncedQuery.length === 0 && (
            <p className="px-4 py-10 text-center text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
              Find any 10-K, 10-Q, or 8-K mentioning a phrase — e.g. &ldquo;going concern&rdquo;,
              &ldquo;material weakness&rdquo;, or a product name.
            </p>
          )}

          {showEmpty && (
            <p className="px-4 py-10 text-center text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
              No filings match &ldquo;{debouncedQuery}&rdquo;.
            </p>
          )}

          {showResults &&
            hits.map((hit, index) => {
              const filed = fmtDate(hit.filed_date)
              return (
                <div
                  key={`${hit.accession_no}-${index}`}
                  id={`cmdk-option-${index}`}
                  role="option"
                  aria-selected={index === highlightIndex}
                  onMouseEnter={() => setHighlightIndex(index)}
                  onClick={() => goToHit(hit)}
                  className={`flex cursor-pointer items-center gap-3 border-b border-border-light px-4 py-3 last:border-b-0 dark:border-border-dark ${
                    index === highlightIndex ? 'bg-panel-light dark:bg-panel-dark' : ''
                  }`}
                >
                  <FileText
                    className="h-4 w-4 shrink-0 text-text-tertiary-light dark:text-text-tertiary-dark"
                    aria-hidden="true"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                        {hit.company || hit.ticker || hit.accession_no}
                      </span>
                      {hit.ticker && (
                        <span className="shrink-0 font-mono text-xs font-semibold text-mint-600 dark:text-mint-400">
                          {hit.ticker}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
                      {hit.form && (
                        <span className="rounded bg-panel-light px-1.5 py-0.5 font-medium text-text-secondary-light dark:bg-panel-dark dark:text-text-secondary-dark">
                          {hit.form}
                        </span>
                      )}
                      {filed && <span>{filed}</span>}
                    </div>
                  </div>
                  {hit.document_url && (
                    <a
                      href={hit.document_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="shrink-0 rounded-md p-1.5 text-text-tertiary-light transition-colors hover:text-mint-600 dark:text-text-tertiary-dark dark:hover:text-mint-400"
                      aria-label={`View ${hit.form || 'filing'} on SEC EDGAR`}
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
              )
            })}
        </div>

        {/* Footer hint */}
        <div className="flex items-center justify-between border-t border-border-light px-4 py-2 text-[11px] text-text-tertiary-light dark:border-border-dark dark:text-text-tertiary-dark">
          <span>↑↓ to navigate · ↵ to open · esc to close</span>
          <span>
            {data?.total
              ? `${data.total.toLocaleString()} ${data.total === 1 ? 'filing' : 'filings'} matched`
              : 'EDGAR full-text search'}
          </span>
        </div>
      </div>
    </div>
  )
}
