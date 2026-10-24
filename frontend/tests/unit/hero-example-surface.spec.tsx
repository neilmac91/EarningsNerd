import React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import HeroExample from '@/features/marketing/components/HeroExample'
import TrustStrip from '@/features/marketing/components/TrustStrip'
import { fetchExampleData, pickEvidence, type ExampleData } from '@/lib/serverApi'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'

vi.mock('@/lib/analytics', () => ({ default: { exampleCtaClicked: vi.fn() } }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  EXAMPLE_FILING_ID: '3',
}))

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
  secUrl: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
  excerpt: 'Net sales rose 6.4% on iPhone and Services.',
  qualityTier: 'full',
  metrics: [
    { label: 'Revenue', value: '$416.2B', deltaPercent: 6.4 },
    { label: 'Net income', value: '$112.0B', deltaPercent: 19.5 },
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
    // Each middot shares an item with the fact before it (E81), so the line is the form's item's parent.
    const facts = screen.getByText('10-K').parentElement!.parentElement as HTMLElement
    expect(facts).toHaveTextContent(/^AAPL\s*·\s*,\s*10-K\s*·\s*,\s*filed Oct 31, 2025$/)
    // tests/e2e/reflow-200.spec.ts reads the built hero: under 200% text the figures wrapping apart, the form codes
    // whole and no line starting with a middot, and at both text sizes where the strip's rules paint, only between two
    // figures, with the first figure's label flush with the card. These pins hold what its boxes cannot say, the date
    // moving under "filed" whole and breaking only after its day, and name the strip's rules: its own above and below,
    // round the list it clips, and each figure's left and top.
    expect(screen.getByText('Oct 31,')).toHaveClass('whitespace-nowrap')
    expect(screen.getByText('Oct 31,').parentElement).toHaveClass('inline-block')
    const strip = screen.getByText('$416.2B').closest('dl') as HTMLElement
    expect(strip.parentElement).toHaveClass('border-y', 'overflow-hidden')
    for (const figure of Array.from(strip.children)) expect(figure).toHaveClass('border-l', 'border-t')
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
    // The filing's words in quotation marks, the closing one after the clip's ellipsis.
    expect(quote.textContent!.length).toBeLessThanOrEqual(184)
    expect(quote.textContent).toMatch(/^“Substantially all of the Company’s manufacturing .* …”$/)
    const chip = screen.getByRole('link', { name: /Located in the filing/ })
    expect(chip).toHaveAttribute('href', LIVE.evidence!.url)
    expect(chip).toHaveAttribute('target', '_blank')
  })

  it('has no evidence row for the static fallback, whose excerpt is not verified here', () => {
    const { container } = render(<HeroExample example={null} />)
    expect(container.querySelector('blockquote')).toBeNull()
    expect(screen.queryByRole('link', { name: /Located in the filing/ })).toBeNull()
  })

  it('claims an XBRL source only for the checked fallback; live figures send the reader to the filing', () => {
    const { container, unmount } = render(<HeroExample example={LIVE} />)
    const live = screen.getByRole('link', { name: 'Source filing\u00a0· check the figures on SEC EDGAR' })
    expect(live).toHaveAttribute('href', LIVE.secUrl)
    expect(container.querySelectorAll('dl [title]')).toHaveLength(0)
    expect(container.innerHTML).not.toMatch(/XBRL/)
    unmount()

    const fallback = render(<HeroExample example={null} />)
    expect(screen.getByRole('link', { name: "Figures from the company's XBRL\u00a0· check them on SEC EDGAR" })).toHaveAttribute(
      'href',
      'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm',
    )
    // The receipt is text in each term, so a keyboard or screen-reader user reaches it; a title hover
    // alone is a receipt only a mouse can read.
    const terms = [...fallback.container.querySelectorAll('dl dt')].map((el) => el.textContent)
    expect(terms).toEqual([
      'Revenue, XBRL concept us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      'Net income, XBRL concept us-gaap:NetIncomeLoss',
      'Diluted EPS, XBRL concept us-gaap:EarningsPerShareDiluted',
    ])
    for (const receipt of fallback.container.querySelectorAll('dl dt span')) expect(receipt).toHaveClass('sr-only')
  })

  it('rings the EDGAR link like every other Tab stop', () => {
    render(<HeroExample example={LIVE} />)
    const edgar = screen.getByRole('link', { name: /on SEC EDGAR$/ })
    for (const cls of ['focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark']) {
      expect(edgar.className.split(/\s+/)).toContain(cls)
    }
  })

  it('leads into the example with a text link, not a tinted box', () => {
    render(<HeroExample example={LIVE} />)
    const cta = screen.getByRole('link', { name: 'Read the full example summary' })
    expect(cta.className.split(/\s+/)).not.toContain('bg-brand-weak')
    expect(cta.className).toContain('text-brand-strong')
  })
})

/**
 * CI's e2e build serves no live example, only the fallback, whose header row has no quality badge. So
 * tests/e2e/hero-example-badge.spec.ts lays the live badge into the built fallback's row and reads the boxes under
 * 200% text (E156). The badge it lays is this render's markup, kept in fixtures/hero-example-live-badge.html: after a
 * change to the badge, run `npx vitest run tests/unit/hero-example-surface.spec.tsx -u` and commit the file (with `-u`
 * before the path, vitest 5 reads the path as the flag's value and runs the whole suite).
 */
describe("the live quality badge the e2e build cannot serve (E156)", () => {
  it('is kept as a fixture, and the fallback row with it laid in is the live row', async () => {
    const live = render(<HeroExample example={LIVE} />)
    const liveRow = live.getByText('Example summary').parentElement as HTMLElement
    const badge = within(liveRow).getByText('Full summary')
    expect(badge.parentElement).toBe(liveRow)
    const [badgeMarkup, liveMarkup] = [badge.outerHTML, liveRow.outerHTML]
    await expect(`${badgeMarkup}\n`).toMatchFileSnapshot('../e2e/fixtures/hero-example-live-badge.html')
    live.unmount()

    const fallback = render(<HeroExample example={null} />)
    const fallbackRow = fallback.getByText('Example summary').parentElement as HTMLElement
    fallbackRow.insertAdjacentHTML('beforeend', badgeMarkup)
    expect(fallbackRow.outerHTML).toBe(liveMarkup)
  })
})

describe('the live hero source link', () => {
  afterEach(() => vi.unstubAllGlobals())

  const folder = 'https://www.sec.gov/Archives/edgar/data/789019/000078901925000001/'
  const document = `${folder}msft-20250630.htm`

  function mockExampleSource(documentUrl: string | null | undefined, secUrl = folder) {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
      ok: true,
      json: async () => url.endsWith('/api/filings/3')
        ? {
          id: 3,
          company: { ticker: 'MSFT', name: 'Microsoft Corporation' },
          filing_type: '10-K',
          filing_date: '2025-07-30',
          sec_url: secUrl,
          document_url: documentUrl,
        }
        : { business_overview: 'Revenue grew during the fiscal year.' },
    })))
  }

  it('carries the API primary document through to the rendered hero instead of the accession folder', async () => {
    mockExampleSource(document)
    const example = await fetchExampleData()
    expect(example?.ticker).toBe('MSFT')
    render(<HeroExample example={example} />)
    expect(screen.getByRole('link', { name: /Source filing.*SEC EDGAR/ })).toHaveAttribute('href', document)
  })

  // One case proves the wiring: originalDocumentUrl.spec.ts holds the helper's matrix of unusable document URLs.
  it('keeps the filing folder fallback when document_url is unusable', async () => {
    mockExampleSource(null)
    expect((await fetchExampleData())?.secUrl).toBe(folder)
  })

  it('uses the static example when the API supplies no usable source URL', async () => {
    mockExampleSource(null, '')
    expect(await fetchExampleData()).toBeNull()
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

  it('reads a v1 summary, whose risks are under risk_factors, as the summary page does', () => {
    const located = [{ supporting_evidence: 'Located in a v1 summary.', source_verified: true, source_url: 'https://www.sec.gov/c' }]
    const v1 = { raw_summary: { risk_source_context_version: 1, sections: { risk_factors: located } } }
    expect(pickEvidence(v1 as Parameters<typeof pickEvidence>[0])).toEqual({
      excerpt: 'Located in a v1 summary.',
      url: 'https://www.sec.gov/c',
    })
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
      'Summaries are generated; risk excerpts are the filing’s own words',
      'One summary per filing, generated once and shared',
      'Not investment advice',
    ])
  })
})
