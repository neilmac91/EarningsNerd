import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import NarrativePane, { type NarrativeState } from '@/features/analysis/components/NarrativePane'
import type { AnalysisCitation, AnalysisCompletion } from '@/features/analysis/api/analysis-api'

const citation: AnalysisCitation = {
  n: 1,
  excerpt: 'Revenue = 391,035,000,000 (FY2024)',
  section_ref: 'XBRL · us-gaap:Revenues',
  verified: true,
  fragment_url: null,
  concept: 'revenue',
  period: 'FY2024',
  derived: false,
}

function doneCompletion(overrides: Partial<AnalysisCompletion> = {}): AnalysisCompletion {
  return {
    kind: 'analysis',
    analysis_id: 7,
    narrative: 'Revenue grew to $391.0B [1].',
    citations: [citation],
    grounded: 1,
    unverified: 0,
    cached: false,
    n_periods: 6,
    ...overrides,
  }
}

const doneState = (overrides: Partial<NarrativeState> = {}): NarrativeState => ({
  status: 'done',
  text: 'Revenue grew to $391.0B [1].',
  completion: doneCompletion(),
  ...overrides,
})

describe('NarrativePane citation chips', () => {
  it('keeps source-link resolution separate from an unreconciled dataset value', () => {
    const state = doneState({ completion: doneCompletion({ citations: [{ ...citation, reconciled: false }] }) })
    const { rerender } = render(<NarrativePane state={state} />)
    expect(screen.getByText('1 source link')).toBeInTheDocument()
    expect(screen.getByText('Includes unverified figures')).toBeInTheDocument()
    expect(screen.getByText('Unverified').closest('li')).toHaveTextContent(citation.excerpt)
    expect(screen.getByText('Sources · linked SEC XBRL values and computed figures')).toBeInTheDocument()
    rerender(<NarrativePane state={doneState()} />)
    expect(screen.queryByText('Includes unverified figures')).not.toBeInTheDocument()
    expect(screen.queryByText('Unverified')).not.toBeInTheDocument()
  })

  beforeEach(() => {
    // jsdom doesn't implement scrollIntoView — stub it (same pattern as highlightInDom.spec.ts).
    Element.prototype.scrollIntoView = vi.fn()
  })

  it('renders a chip for a resolved [1] marker', () => {
    render(<NarrativePane state={doneState()} />)
    const chip = screen.getByRole('button', { name: /citation 1: xbrl · us-gaap:revenues/i })
    expect(chip).toHaveTextContent('[1]')
  })

  it('scrolls to and flashes the matching Sources row when a chip is clicked', () => {
    render(<NarrativePane state={doneState()} />)
    const chip = screen.getByRole('button', { name: /citation 1/i })
    const sourceRow = document.getElementById('analysis-source-1')
    expect(sourceRow).not.toBeNull()

    fireEvent.click(chip)
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    expect(sourceRow).toHaveClass('citation-flash')
  })

  it('leaves an unmatched [2] as plain text (no chip)', () => {
    const state = doneState({
      text: 'A claim with no citation [2].',
      completion: doneCompletion({ narrative: 'A claim with no citation [2].' }),
    })
    render(<NarrativePane state={state} />)
    expect(screen.getByText(/\[2\]/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /citation 2/i })).not.toBeInTheDocument()
  })

  it('does not inject chips while streaming (raw markers stay plain text)', () => {
    render(<NarrativePane state={{ status: 'streaming', text: 'Revenue grew [1]', stage: 'writing' }} />)
    expect(screen.getByText(/\[1\]/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /citation 1/i })).not.toBeInTheDocument()
  })

  it('shows mismatch and removed-reference warnings without calling source links verified', () => {
    const state = doneState({ completion: doneCompletion({ unverified: 2, mismatched: 1 }) })
    render(<NarrativePane state={state} />)
    const badge = screen.getByText('1 source link')
    expect(badge).toHaveAttribute(
      'title',
      expect.stringContaining('1 figure printed next to a source link could not be reconciled')
    )
    expect(screen.getByText('Some source references need attention')).toBeInTheDocument()
    expect(
      screen.getByText(/2 model source references did not resolve to the analysis dataset and were removed/)
    ).toHaveTextContent('Check the Sources list before relying on the narrative figure')
    expect(screen.queryByText(/verified citations/)).not.toBeInTheDocument()
  })

  it('omits the unverified caveat from the tooltip when nothing was stripped', () => {
    render(<NarrativePane state={doneState()} />)
    const badge = screen.getByText('1 source link')
    expect(badge.getAttribute('title')).not.toContain('did not resolve')
    expect(screen.queryByText('Some source references need attention')).not.toBeInTheDocument()
  })

  it('replaces the verified/cached badges with a Sample badge in teaser mode (F3)', () => {
    const state = doneState({ completion: doneCompletion({ cached: true }) })
    render(<NarrativePane state={state} sample />)
    // Approximate demo figures must never wear the "verified" claim.
    expect(screen.getByText('Sample data')).toBeInTheDocument()
    expect(screen.queryByText(/source links?/)).not.toBeInTheDocument()
    expect(screen.queryByText('Cached')).not.toBeInTheDocument()
    expect(screen.getByText(/Sources · sample data/)).toBeInTheDocument()
  })
})
