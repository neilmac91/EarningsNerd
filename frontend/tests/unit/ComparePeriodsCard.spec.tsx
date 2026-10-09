import React, { type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ComparePeriodsCard } from '@/features/filings/components/ComparePeriodsCard'
import type { Filing } from '@/features/filings/api/filings-api'
import type { ChangeReport, WhatChangedMetricItem } from '@/features/summaries/api/summaries-api'

const api = vi.hoisted(() => ({ getWhatChanged: vi.fn() }))
vi.mock('@/features/summaries/api/summaries-api', () => ({ getWhatChanged: api.getWhatChanged }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const FILING: Filing = {
  id: 3,
  filing_type: '10-K',
  filing_date: '2025-10-31T00:00:00+00:00',
  report_date: '2025-09-27T00:00:00+00:00',
  accession_number: '0000320193-25-000079',
  document_url: 'https://www.sec.gov/doc/3',
  sec_url: 'https://www.sec.gov/edgar/3',
}

const item = (metric: string, label: string, display: string, direction: WhatChangedMetricItem['direction'], tone: WhatChangedMetricItem['tone']): WhatChangedMetricItem => ({
  metric,
  label,
  direction,
  pct: null,
  current: 1,
  prior: 1,
  display,
  tone,
})

const REPORT: ChangeReport = {
  has_prior: true,
  comparison_basis: 'Year over year',
  prior_filing: { filing_id: 2, filing_type: '10-K', filing_date: '2024-11-01T00:00:00+00:00', period_end_date: '2024-09-28T00:00:00+00:00' },
  metrics: {
    headline: 'Revenue rose 6.4%.',
    items: [
      item('revenue', 'Revenue', '+6.4%', 'up', 'gain'),
      item('total_debt', 'Total debt', '−7.3%', 'down', 'gain'),
      item('rnd', 'Research and development', '+9.9%', 'up', 'flat'),
      item('net_income', 'Net income', '−3.4%', 'down', 'loss'),
    ],
    data_quality: 'ok',
  },
  risks: null,
  key_changes: null,
  has_changes: true,
}

function renderCard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ComparePeriodsCard filing={FILING} />
    </QueryClientProvider>,
  )
}

afterEach(() => api.getWhatChanged.mockReset())

describe('ComparePeriodsCard', () => {
  it('is one labelled aside that names the two periods it compares', async () => {
    api.getWhatChanged.mockResolvedValue(REPORT)
    renderCard()
    const card = screen.getByRole('complementary', { name: 'Compare periods' })
    expect(within(card).getByText('10-K · year ended Sep 27, 2025')).toBeInTheDocument()
    // The prior period on its own line once the report names it, so no date breaks across lines.
    expect(await within(card).findByText('vs year ended Sep 28, 2024')).toBeInTheDocument()
    expect(api.getWhatChanged).toHaveBeenCalledWith(3)
  })

  it('shows three metric rows, each with its served change and its reading in words', async () => {
    api.getWhatChanged.mockResolvedValue(REPORT)
    renderCard()
    const rows = within(await screen.findByRole('list')).getAllByRole('listitem')
    expect(rows).toHaveLength(3)
    expect(rows[0]).toHaveTextContent(/^Revenue▲\+6\.4%Favorable$/)
    // A fall in debt reads as favorable: the tone is the server's, not the sign's.
    expect(rows[1]).toHaveTextContent(/^Total debt▼−7\.3%Favorable$/)
    expect(rows[2]).toHaveTextContent(/^Research and development▲\+9\.9%Neutral$/)
    // The glyph is visual only; the signed string carries the direction.
    expect(within(rows[0]).getByText('▲')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('1 more in the change report.')).toBeInTheDocument()
  })

  it('links to the change report on the filing page', async () => {
    api.getWhatChanged.mockResolvedValue(REPORT)
    renderCard()
    expect(await screen.findByRole('link', { name: 'Open change report' })).toHaveAttribute('href', '/filing/3#what-changed')
  })

  it('shows the list’s own shape while it loads', () => {
    api.getWhatChanged.mockReturnValue(new Promise(() => {}))
    renderCard()
    expect(screen.getByRole('status', { name: 'Loading the comparison' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Open change report' })).toBeNull()
  })

  it('says so plainly when there is no earlier report, or nothing comparable, and offers no link', async () => {
    api.getWhatChanged.mockResolvedValue({ ...REPORT, has_prior: false, prior_filing: null, metrics: null, has_changes: false })
    const { unmount } = renderCard()
    expect(await screen.findByText('No earlier annual report to compare with yet.')).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
    unmount()

    api.getWhatChanged.mockResolvedValue({ ...REPORT, metrics: null, has_changes: false })
    renderCard()
    expect(await screen.findByText('These two annual reports share no comparable figures yet.')).toBeInTheDocument()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('keeps a failure in place with a Retry that fetches again', async () => {
    api.getWhatChanged.mockRejectedValueOnce(new Error('down'))
    renderCard()
    expect(await screen.findByText('Couldn’t load the comparison')).toBeInTheDocument()
    api.getWhatChanged.mockResolvedValue(REPORT)
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Retry' })))
    expect(await screen.findByRole('link', { name: 'Open change report' })).toBeInTheDocument()
    expect(api.getWhatChanged).toHaveBeenCalledTimes(2)
  })
})
