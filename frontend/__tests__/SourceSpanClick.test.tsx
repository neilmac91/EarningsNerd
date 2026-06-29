import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import CitationChip from '@/features/filings/components/copilot/CitationChip'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'

// Mock PostHog at the transport layer (not the analytics helper) so the REAL
// analytics.sourceSpanClicked runs and we can assert the on-the-wire snake_case payload —
// i.e. the full chain CitationChip → requestHighlight → analytics → posthog.capture.
const mockCapture = vi.fn()
vi.mock('posthog-js', () => ({
  default: { capture: (event: string, properties?: Record<string, unknown>) => mockCapture(event, properties) },
}))
// analytics.ts imports Sentry at module load (used by identify/reset, not by this path).
vi.mock('@sentry/nextjs', () => ({ setUser: vi.fn() }))

const textCitation: CopilotCitation = {
  n: 1,
  excerpt: 'Revenue increased to $391.0B this year.',
  section_ref: 'Item 7 — MD&A',
  verified: true,
  fragment_url: 'https://www.sec.gov/x#:~:text=Revenue',
}

const xbrlCitation: CopilotCitation = {
  n: 'F1',
  excerpt: 'Revenue = $391.04B USD (FY2024)',
  section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
  verified: false,
  fragment_url: 'https://www.sec.gov/filing',
}

const sourceSpanCalls = () => mockCapture.mock.calls.filter(([event]) => event === 'source_span_click')

describe('source_span_click instrumentation (item 1.8)', () => {
  beforeEach(() => mockCapture.mockClear())

  it('emits the snake_case payload when a cited passage is opened in-app', () => {
    render(
      <FilingViewerProvider filingId={42} ticker="BABA" filingType="20-F">
        <CitationChip citation={textCitation} />
      </FilingViewerProvider>,
    )
    // In-app chip is a button (it drives requestHighlight); clicking it = verifying the claim.
    fireEvent.click(screen.getByRole('button', { name: /citation 1: item 7 — md&a/i }))

    const calls = sourceSpanCalls()
    expect(calls).toHaveLength(1)
    expect(calls[0][1]).toEqual({
      filing_id: 42,
      ticker: 'BABA',
      filing_type: '20-F',
      citation_index: '1',
      citation_kind: 'text',
      verified: true,
      action: 'scroll_highlight',
    })
  })

  it('tags XBRL figure citations as citation_kind "xbrl" (carries the verified flag through)', () => {
    render(
      <FilingViewerProvider filingId={42} ticker="BABA" filingType="20-F">
        <CitationChip citation={xbrlCitation} />
      </FilingViewerProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: /citation f1/i }))

    const calls = sourceSpanCalls()
    expect(calls).toHaveLength(1)
    expect(calls[0][1]).toMatchObject({
      citation_index: 'F1',
      citation_kind: 'xbrl',
      verified: false,
      action: 'scroll_highlight',
    })
  })

  it('does NOT emit without filing context (propless provider / FREE teaser)', () => {
    render(
      <FilingViewerProvider>
        <CitationChip citation={textCitation} />
      </FilingViewerProvider>,
    )
    // The provider is still mounted, so the chip is the in-app button and the highlight still
    // fires — but with no filingId there is nothing to attribute, so no event is emitted.
    fireEvent.click(screen.getByRole('button', { name: /citation 1: item 7 — md&a/i }))
    expect(sourceSpanCalls()).toHaveLength(0)
  })
})
