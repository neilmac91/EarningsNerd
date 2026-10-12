import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { FeedItem } from '@/features/dashboard/api/dashboard-api'
import FilingFeed from '@/features/dashboard/components/FilingFeed'

/**
 * The feed's overflow link keeps its count. D-030 keeps a number out of sage ink, and the founder's
 * review of #1251 sent back a version of this link that had satisfied the colour rule by deleting the
 * count (lessons/brand-a-colour-rule-recolours-a-value-and-never-deletes-it.md). The count is the
 * watchlist's size, never the capped feed's length, and it rests in the secondary ink inside the sage
 * link; without it, "See all companies".
 */
const api = vi.hoisted(() => ({ getDashboardFeed: vi.fn() }))
vi.mock('@/features/dashboard/api/dashboard-api', () => ({ getDashboardFeed: api.getDashboardFeed }))
vi.mock('@/features/dashboard/components/WhatChangedCard', () => ({
  default: ({ item }: { item: FeedItem }) => <article>{item.company.ticker}</article>,
}))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

const item = (n: number): FeedItem => ({
  filing_id: n,
  accession_number: null,
  company: { id: n, ticker: `T${n}`, name: `Company ${n}` },
  filing_type: '10-Q',
  filing_date: '2026-03-02',
  period_end_date: null,
  summary_id: null,
  summary_status: 'ready',
  what_changed: null,
})

function renderFeed(watchlistCount?: number) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><FilingFeed watchlistCount={watchlistCount} /></QueryClientProvider>)
}

describe('FilingFeed overflow link', () => {
  it('keeps the watchlist count in its label, in the secondary ink inside the sage link', async () => {
    api.getDashboardFeed.mockResolvedValue(Array.from({ length: 7 }, (_, i) => item(i + 1)))
    renderFeed(30)
    const link = await screen.findByRole('link', { name: 'See all 30 companies' })
    expect(link).toHaveAttribute('href', '/dashboard/watchlist')
    expect(link.className).toContain('text-brand-strong')
    const count = within(link).getByText('30')
    expect(count.className).toContain('text-text-secondary-light')
    expect(count.className).not.toMatch(/text-brand/)
  })

  it('names no count when the watchlist size is not known', async () => {
    api.getDashboardFeed.mockResolvedValue(Array.from({ length: 7 }, (_, i) => item(i + 1)))
    renderFeed(undefined)
    await screen.findByRole('link', { name: 'See all companies' })
  })
})
