import { describe, expect, it } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import StreamingSummaryDisplay from '@/app/filing/[id]/StreamingSummaryDisplay'
import type { Filing } from '@/features/filings/api/filings-api'

const filing: Filing = {
  id: 3,
  company_id: 1,
  filing_type: '10-K',
  filing_date: '2026-02-01',
  period_end_date: '2025-12-31',
  accession_number: '0000320193-26-000001',
  document_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/',
  company: { id: 1, ticker: 'AAPL', name: 'APPLE INC.' },
} as Filing

const renderAt = (stage: string, elapsedSeconds = 0) =>
  render(
    <StreamingSummaryDisplay
      streamingText=""
      stage={stage}
      message=""
      filing={filing}
      elapsedSeconds={elapsedSeconds}
    />,
  )

// The progress card had a progressbar with an aria-label but no live region, so screen-reader
// users heard nothing while generation ran. The status node announces STAGE transitions only.
describe('StreamingSummaryDisplay live region', () => {
  it('announces the active pipeline stage through a polite status region', async () => {
    renderAt('parsing')
    await act(async () => {})
    // SkeletonText carries its own role="status" (DS §4), so locate ours by its announcement.
    const status = screen.getByText('Extracting financial statements, risk factors & MD&A.')
    expect(status).toHaveAttribute('role', 'status')
    expect(status).toHaveAttribute('aria-live', 'polite')
    expect(status.className).toContain('sr-only')
  })

  it('names the filing type when retrieving from EDGAR', async () => {
    renderAt('fetching')
    await act(async () => {})
    expect(screen.getByText('Retrieving 10-K filing from EDGAR.')).toHaveAttribute('aria-live', 'polite')
  })

  it('changes only on stage transitions, not on progress ticks', async () => {
    const { rerender } = renderAt('analyzing', 5)
    await act(async () => {})
    const live = () => screen.getByText(/^(Cross-referencing standardized XBRL financials|Generating investment analysis)\.$/)
    const before = live().textContent
    rerender(
      <StreamingSummaryDisplay streamingText="" stage="analyzing" message="" filing={filing} elapsedSeconds={20} />,
    )
    await act(async () => {})
    expect(live().textContent).toBe(before)
    rerender(
      <StreamingSummaryDisplay streamingText="" stage="summarizing" message="" filing={filing} elapsedSeconds={21} />,
    )
    await act(async () => {})
    expect(live()).toHaveTextContent('Generating investment analysis.')
  })

  it('has a generic announcement for early and unknown stages', async () => {
    const { rerender } = renderAt('queued')
    await act(async () => {})
    expect(screen.getByText('Starting summary generation.')).toHaveAttribute('aria-live', 'polite')
    rerender(<StreamingSummaryDisplay streamingText="" stage="mystery" message="" filing={filing} />)
    await act(async () => {})
    expect(screen.getByText('Generating your analysis.')).toHaveAttribute('aria-live', 'polite')
  })
})
