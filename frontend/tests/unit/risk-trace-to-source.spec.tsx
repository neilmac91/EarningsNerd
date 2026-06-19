import React from 'react'
import { render, screen } from '@testing-library/react'
import { SummaryRisks } from '@/features/filings/components/SummaryRisks'
import { normalizeRisk } from '@/lib/formatters'
import type { RiskFactor } from '@/types/summary'

describe('Risk factor Trace-to-Source', () => {
  it('renders a verified link to the exact filing passage', () => {
    const risks: RiskFactor[] = [
      {
        summary: 'Supply concentration',
        supporting_evidence: 'Supply chain constraints persisted through Q3.',
        source_url: 'https://www.sec.gov/x.htm#:~:text=Supply%20chain%20constraints',
        source_verified: true,
        source_section_ref: 'Item 1A. Risk Factors',
      },
    ]
    const { container } = render(<SummaryRisks risks={risks} />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toContain('#:~:text=')
    expect(link.getAttribute('aria-label')).toMatch(/verified source passage/i)
    expect(link.textContent).toContain('Verified in filing')
    expect(container.textContent).toContain('Item 1A. Risk Factors')
  })

  it('labels an unverified citation honestly and links to the plain section', () => {
    const risks: RiskFactor[] = [
      {
        summary: 'Some risk',
        supporting_evidence: 'Paraphrased risk not found verbatim.',
        source_url: 'https://www.sec.gov/x.htm',
        source_verified: false,
        source_section_ref: 'Item 1A. Risk Factors',
      },
    ]
    render(<SummaryRisks risks={risks} />)
    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).toBe('https://www.sec.gov/x.htm')
    expect(link.getAttribute('href')).not.toContain('#:~:text=')
    expect(link.textContent).toContain('Cited — open section')
    expect(screen.queryByText(/Verified in filing/)).toBeNull()
  })

  it('renders cleanly with no provenance fields (backward compatible)', () => {
    const risks: RiskFactor[] = [
      { summary: 'Legacy risk', supporting_evidence: 'Evidence text only.' },
    ]
    const { container } = render(<SummaryRisks risks={risks} />)
    expect(container.textContent).toContain('Evidence text only.')
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
