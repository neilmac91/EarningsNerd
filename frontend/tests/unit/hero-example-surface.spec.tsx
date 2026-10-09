import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import HeroExample from '@/features/marketing/components/HeroExample'
import TrustStrip from '@/features/marketing/components/TrustStrip'
import { pickEvidence, type ExampleData } from '@/lib/serverApi'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'

vi.mock('@/lib/analytics', () => ({ default: { exampleCtaClicked: vi.fn() } }))

/**
 * The hero example as the product on one surface (2026-10 critique, homepage 1d): identity in the
 * data face, the summary's opening, a hairline figure strip and, when the live summary has one, one
 * evidence row. No browser-frame mockup, no card inside the card, no sparkle chip, no tinted CTA.
 */

const EXCERPT =
  'Substantially all of the Company’s manufacturing is performed in whole or in part by outsourcing partners located primarily in Asia, and the Company relies on single-source suppliers for many components.'
const LIVE: ExampleData = {
  filingId: 3,
  ticker: 'AAPL',
  companyName: 'Apple Inc.',
  filingType: '10-K',
  filingDate: '2025-10-31',
  secUrl: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/',
  excerpt: 'Net sales rose 6.4% on iPhone and Services.',
  qualityTier: 'full',
  metrics: [
    { label: 'Revenue', value: '$416.2B', deltaPercent: 6.4 },
    { label: 'Net Income', value: '$112.0B', deltaPercent: 19.5 },
    { label: 'Diluted EPS', value: '$7.46', deltaPercent: -1.2 },
  ],
  evidence: { excerpt: EXCERPT, url: 'https://www.sec.gov/Archives/edgar/data/320193/doc.htm#:~:text=Substantially' },
}

describe('HeroExample', () => {
  it('is one surface: no browser frame, no nested card, no sparkle chip', () => {
    const { container } = render(<HeroExample example={null} />)
    const surface = screen.getByRole('region', { name: 'Example summary' })
    expect(surface.className).toContain('rounded-xl')
    expect(container.querySelector('.mockup-frame, .mockup-frame-titlebar')).toBeNull()
    expect(container.textContent).not.toMatch(/AI summary/)
    // Nothing inside the surface draws a box of its own.
    expect(within(surface).queryAllByText(/./).some((el) => /\brounded-lg\b.*\bborder\b|\bborder\b.*\brounded-lg\b/.test(el.className))).toBe(false)
  })

  it('states the filing in the data face and its figures in one hairline strip, direction in a glyph', () => {
    render(<HeroExample example={LIVE} />)
    expect(screen.getByText('10-K').parentElement).toHaveTextContent(/^AAPL\s*·\s*,\s*10-K\s*·\s*,\s*filed Oct 31, 2025$/)
    const strip = screen.getByText('$416.2B').closest('dl') as HTMLElement
    expect(strip.className).toMatch(/border-y/)
    expect(strip.className).toMatch(/divide-x/)
    expect(within(strip).getAllByRole('term')).toHaveLength(3)
    expect(within(strip).getAllByText('▲')).toHaveLength(2)
    for (const glyph of within(strip).getAllByText(/^[▲▼]$/)) expect(glyph).toHaveAttribute('aria-hidden', 'true')
    expect(within(strip).getByText('▼').parentElement).toHaveTextContent('▼-1.2%')
  })

  it('shows one evidence row from the live summary: its opening clause, the excerpt, a chip into the filing', () => {
    const { container } = render(<HeroExample example={LIVE} />)
    // Headed by its own opening clause (the filing's words), as the filing page heads evidence rows.
    const heading = excerptHeadings([EXCERPT])[0]
    expect(heading.startsWith('Substantially all of the Company’s manufacturing')).toBe(true)
    expect(screen.getByText(heading).className).toContain('font-semibold')
    const quote = container.querySelector('blockquote') as HTMLElement
    expect(quote.textContent!.length).toBeLessThanOrEqual(182)
    expect(quote.textContent).toMatch(/^Substantially all of the Company’s manufacturing .* …$/)
    const chip = screen.getByRole('link', { name: /Located in the filing/ })
    expect(chip).toHaveAttribute('href', LIVE.evidence!.url)
    expect(chip).toHaveAttribute('target', '_blank')
  })

  it('has no evidence row for the static fallback, whose excerpt is not verified here', () => {
    const { container } = render(<HeroExample example={null} />)
    expect(container.querySelector('blockquote')).toBeNull()
    expect(screen.queryByRole('link', { name: /Located in the filing/ })).toBeNull()
  })

  it('leads into the example with a text link, not a tinted box', () => {
    render(<HeroExample example={LIVE} />)
    const cta = screen.getByRole('link', { name: 'Read the full example summary' })
    expect(cta.className.split(/\s+/)).not.toContain('bg-brand-weak')
    expect(cta.className).toContain('text-brand-strong')
  })
})

describe('pickEvidence', () => {
  const summary = (risks: unknown, version: number | null = 1) =>
    ({ raw_summary: { risk_source_context_version: version, sections: { risks } } }) as Parameters<typeof pickEvidence>[0]

  it('takes the first risk the server located in the filing text', () => {
    expect(
      pickEvidence(summary([
        { supporting_evidence: 'Not located.', source_verified: false, source_url: 'https://www.sec.gov/a' },
        { supporting_evidence: '  Located excerpt.  ', source_verified: true, source_url: 'https://www.sec.gov/b' },
      ])),
    ).toEqual({ excerpt: 'Located excerpt.', url: 'https://www.sec.gov/b' })
  })

  it('needs the source owner, drops a non-https link, and tolerates junk', () => {
    const located = [{ supporting_evidence: 'Located.', source_verified: true, source_url: 'javascript:alert(1)' }]
    expect(pickEvidence(summary(located, null))).toBeNull()
    expect(pickEvidence(summary(located))).toEqual({ excerpt: 'Located.', url: null })
    expect(pickEvidence(summary([null, 'x', 7, { source_verified: true, supporting_evidence: '  ' }]))).toBeNull()
    expect(pickEvidence(summary('not a list'))).toBeNull()
    expect(pickEvidence({})).toBeNull()
  })
})

describe('TrustStrip', () => {
  it('states what the product does and does not do, scoped to what it establishes', () => {
    render(<TrustStrip />)
    const items = within(screen.getByRole('list', { name: 'About the data' })).getAllByRole('listitem')
    expect(items.map((li) => li.textContent)).toEqual([
      'Data sourced from SEC EDGAR',
      'Figures cite their XBRL fact or filing passage where a match is found',
      'Summaries are generated; quoted excerpts are the filing’s own words',
      'Not investment advice',
    ])
  })
})
