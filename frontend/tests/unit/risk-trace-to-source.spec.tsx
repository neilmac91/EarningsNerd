import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { SummaryRisks } from '@/features/summaries/components/SummaryRisks'
import { normalizeRisk } from '@/lib/formatters'
import type { RiskFactor } from '@/types/summary'

describe('Risk factor Trace-to-Source', () => {
  it('renders a verified link to the exact filing passage', () => {
    const risks: RiskFactor[] = [
      {
        summary: 'Filing excerpt',
        supporting_evidence: 'Supply chain constraints persisted through Q3.',
        source_url: 'https://www.sec.gov/x.htm#:~:text=Supply%20chain%20constraints',
        source_verified: true,
        source_section_ref: 'Filing excerpt',
      },
    ]
    render(<SummaryRisks risks={risks} projection={{ version: 1, verified_count: 1, withheld_count: 0 }} />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toContain('#:~:text=')
    expect(link.getAttribute('aria-label')).toMatch(/verified in filing/i)
    expect(link.textContent).toContain('Verified in filing')
    expect(screen.getByText('Supply chain constraints persisted through Q3.')).toBeTruthy()
    // The section ref lives in the hover/focus panel (ambient provenance), not inline.
    fireEvent.mouseEnter(link)
    expect(screen.getAllByText(/Filing excerpt/).length).toBeGreaterThan(0)
  })

  it('reports withheld evidence without rendering an unverified citation', () => {
    render(<SummaryRisks risks={[]} projection={{ version: 1, verified_count: 0, withheld_count: 1 }} />)
    expect(screen.getByText(/Source-verified risk excerpts are unavailable/)).toBeTruthy()
    expect(screen.getByText(/1 item withheld/)).toBeTruthy()
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('does not render legacy model text without a source projection', () => {
    const risks: RiskFactor[] = [
      { summary: 'Legacy risk', supporting_evidence: 'Evidence text only.' },
    ]
    const { container } = render(<SummaryRisks risks={risks} />)
    expect(container.textContent).not.toContain('Evidence text only.')
    expect(container.textContent).toContain('No source-verified risk excerpts found')
    expect(screen.queryByRole('link')).toBeNull()
  })

  it('normalizeRisk passes provenance fields through', () => {
    const out = normalizeRisk({
      summary: 'r',
      supporting_evidence: 'evidence here long enough to pass',
      source_url: 'https://sec.gov/x.htm#:~:text=evidence',
      source_verified: true,
      source_section_ref: 'Item 1A. Risk Factors',
    })
    expect(out?.source_url).toBe('https://sec.gov/x.htm#:~:text=evidence')
    expect(out?.source_verified).toBe(true)
    expect(out?.source_section_ref).toBe('Item 1A. Risk Factors')
  })

  it('normalizeRisk defaults provenance fields to null when absent', () => {
    const out = normalizeRisk({ summary: 'r', supporting_evidence: 'evidence here long enough' })
    expect(out?.source_url).toBeNull()
    expect(out?.source_verified).toBeNull()
    expect(out?.source_section_ref).toBeNull()
  })
})
