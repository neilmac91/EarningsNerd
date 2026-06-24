'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckIcon, CircleNotchIcon, MagnifyingGlassIcon, PlusIcon } from '@/lib/icons'
import { searchCompanies, Company } from '@/features/companies/api/companies-api'
import { addToWatchlist } from '@/features/watchlist/api/watchlist-api'
import analytics from '@/lib/analytics'

/**
 * Add-from-search for the watchlist page: type a company, pick it, and it's tracked — without
 * having to visit the company page first. Reuses the shared `searchCompanies` query.
 */
export default function WatchlistAddSearch() {
  const queryClient = useQueryClient()
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [justAdded, setJustAdded] = useState<string | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query), 300)
    return () => clearTimeout(t)
  }, [query])

  // Close the dropdown on outside click.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const { data: companies, isLoading } = useQuery({
    queryKey: ['companies', debounced],
    queryFn: () => searchCompanies(debounced),
    enabled: debounced.length > 0,
    staleTime: 5 * 60 * 1000,
  })

  const addMutation = useMutation({
    mutationFn: addToWatchlist,
    onSuccess: (_data, ticker) => {
      queryClient.invalidateQueries({ queryKey: ['watchlist-insights'] })
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      analytics.watchlistAdded(ticker)
      setJustAdded(ticker)
      setQuery('')
      setOpen(false)
      setTimeout(() => setJustAdded(null), 2500)
    },
  })

  const handleSelect = (company: Company) => {
    addMutation.mutate(company.ticker)
  }

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-text-tertiary-light dark:text-text-secondary-dark" />
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          placeholder="Add a company to your watchlist (e.g., AAPL, Apple)…"
          aria-label="Search for a company to add to your watchlist"
          className="w-full rounded-xl border border-border-light dark:border-border-dark bg-panel-light dark:bg-panel-dark py-3 pl-11 pr-4 text-text-primary-light dark:text-text-primary-dark placeholder:text-text-tertiary-light dark:placeholder:text-text-secondary-dark shadow-sm focus:border-brand-light focus:outline-none focus:ring-2 focus:ring-brand-light/40"
        />
        {(isLoading || addMutation.isPending) && (
          <CircleNotchIcon className="absolute right-3 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        )}
      </div>

      {justAdded && (
        <p className="mt-2 flex items-center gap-1.5 text-sm text-success-light dark:text-success-dark">
          <CheckIcon className="h-4 w-4" />
          Added <span className="font-semibold">{justAdded}</span> to your watchlist.
        </p>
      )}

      {addMutation.isError && (
        <p className="mt-2 text-sm text-error-light dark:text-error-dark">Couldn&apos;t add that company. Please try again.</p>
      )}

      {open && debounced.length > 0 && companies && companies.length > 0 && (
        <div
          role="listbox"
          aria-label="Company results"
          className="absolute z-20 mt-2 max-h-80 w-full overflow-y-auto rounded-xl border border-border-light dark:border-border-dark bg-panel-light dark:bg-panel-dark shadow-lg"
        >
          {companies.map((company) => (
            <button
              key={company.id}
              type="button"
              role="option"
              aria-selected={false}
              onClick={() => handleSelect(company)}
              disabled={addMutation.isPending}
              className="flex w-full items-center justify-between gap-3 border-b border-border-light dark:border-border-dark px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-brand-weak dark:hover:bg-white/5 disabled:opacity-50"
            >
              <span className="min-w-0">
                <span className="block truncate font-medium text-text-primary-light dark:text-text-primary-dark">{company.name}</span>
                <span className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">{company.ticker}</span>
              </span>
              <PlusIcon className="h-4 w-4 flex-shrink-0 text-brand-strong dark:text-brand-strong-dark" />
            </button>
          ))}
        </div>
      )}

      {open && debounced.length > 0 && !isLoading && companies && companies.length === 0 && (
        <div className="absolute z-20 mt-2 w-full rounded-xl border border-border-light dark:border-border-dark bg-panel-light dark:bg-panel-dark p-4 text-center text-sm text-text-tertiary-light dark:text-text-secondary-dark shadow-lg">
          No companies found matching &quot;{debounced}&quot;
        </div>
      )}
    </div>
  )
}
