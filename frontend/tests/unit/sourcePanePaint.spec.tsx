import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { SourceTrace } from '@/features/filings/components/SourceTrace'
import { MetricSourceLink } from '@/features/filings/components/MetricSourceLink'
import CitationChip from '@/features/filings/components/copilot/CitationChip'
import FilingViewer from '@/features/filings/components/copilot/FilingViewer'
import { FilingViewerProvider } from '@/features/filings/components/copilot/FilingViewerContext'
import { __resetCitationHighlightStyleForTests } from '@/features/filings/components/copilot/highlightInDom'

/**
 * The Source pane paints the device only on a passage the server located (D-044; CLAUDE.md rule 12). The
 * device's highlight, `copilot-citation`, takes `.en-mark`'s tint and hairline; any other jump lands in the
 * neutral find highlight, `copilot-find`, so the reader still sees where it landed. What each paint looks like
 * is tests/unit/highlightInDom.spec.ts's; this holds which one a jump registers, through the real chain: a
 * chip as the summary or an Ask answer renders it, the viewer context's request, FilingViewer and
 * highlightInDom, with jsdom given the CSS Custom Highlight API it lacks. Located: a summary chip's verified
 * excerpt, the very text the server checked, and an Ask answer's verified passage. Never located: a summary
 * chip's section heading (every metric chip, a verified XBRL figure's included, a Cited chip, and a verified
 * chip whose excerpt is too short to anchor), an excerpt the server did not locate, and an XBRL fact from
 * Ask, which has no passage even where the text its jump finds holds its label.
 */
const { HEADING, RISK, TAKEAWAY } = vi.hoisted(() => ({
  HEADING: 'Item 8. Financial Statements',
  RISK: 'Tariffs and other measures that are applied to the Company’s products or their components can have a material adverse impact.',
  TAKEAWAY: 'Americas net sales increased during 2025 compared to 2024 primarily due to higher net sales of iPhone and Services.',
}))

vi.mock('@/features/filings/api/filing-content-api', () => ({
  fetchFilingContent: vi.fn(async () => ({
    hasContent: true,
    markdownContent: `# ${HEADING}\n\nProducts net sales rose on iPhone demand. ${TAKEAWAY}\n\n## Risk Factors\n\n${RISK}\n`,
  })),
}))

const DOCUMENT_URL = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'
const LOCATED = 'copilot-citation'
const FIND = 'copilot-find'

const CASES: { jump: string; chip: ReactNode; registers: string; lands: string }[] = [
  // SummaryRisks: a located row's chip carries its excerpt and `source_verified`.
  { jump: 'a located Risks excerpt', chip: <SourceTrace url={DOCUMENT_URL} verified sectionRef="Filing excerpt" excerpt={RISK} />, registers: LOCATED, lands: RISK.slice(0, 40) },
  // EvidenceChip and a metric takeaway: a verified excerpt, passed only when verified.
  { jump: 'a located quote or takeaway excerpt', chip: <SourceTrace url={DOCUMENT_URL} verified sectionRef={HEADING} excerpt={TAKEAWAY} />, registers: LOCATED, lands: TAKEAWAY.slice(0, 40) },
  // Ask: a verified passage of the filing's text (copilot-api admits no other).
  { jump: "an Ask answer's verified passage", chip: <CitationChip citation={{ n: 1, excerpt: TAKEAWAY, section_ref: 'Item 7', verified: true, fragment_url: null }} />, registers: LOCATED, lands: TAKEAWAY.slice(0, 40) },
  // MetricSourceLink: an XBRL fact has no passage, so the jump falls back to the section heading.
  { jump: 'a verified XBRL figure (its section heading)', chip: <MetricSourceLink url={DOCUMENT_URL} verified concept="Total net sales" sectionRef={HEADING} />, registers: FIND, lands: HEADING },
  { jump: 'an unverified metric, Cited (its section heading)', chip: <MetricSourceLink url={DOCUMENT_URL} verified={false} sectionRef={HEADING} />, registers: FIND, lands: HEADING },
  // EvidenceChip withholds an unverified excerpt, so a Cited quote jumps to its heading.
  { jump: 'a Cited quote (its section heading)', chip: <SourceTrace url={DOCUMENT_URL} verified={false} sectionRef={HEADING} excerpt={null} />, registers: FIND, lands: HEADING },
  // SummaryRisks: a row the server did not locate still carries its excerpt, unverified.
  { jump: 'a Risks excerpt the server did not locate', chip: <SourceTrace url={DOCUMENT_URL} verified={false} sectionRef="Filing excerpt" excerpt={RISK} />, registers: FIND, lands: RISK.slice(0, 40) },
  // A verified chip whose excerpt is too short to anchor falls back to the heading.
  { jump: 'a verified chip with an excerpt too short to anchor (its section heading)', chip: <SourceTrace url={DOCUMENT_URL} verified sectionRef={HEADING} excerpt="Q4" />, registers: FIND, lands: HEADING },
  // Ask: an XBRL fact, verified, whose label the text holds (the matcher's leading-slice fallback finds it).
  {
    jump: 'an XBRL fact from Ask, [F1]',
    chip: <CitationChip citation={{ n: 'F1', excerpt: 'Products net sales (FY2025)', section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax', verified: true, fragment_url: null }} />,
    registers: FIND,
    lands: 'Products net sales',
  },
]

describe('the Source pane paints the device only on a passage the server located (D-044)', () => {
  // jsdom has no CSS Custom Highlight API and no constructable stylesheets: give it both, as highlightInDom.spec does.
  const highlights = new Map<string, { range: Range }>()
  const g = globalThis as unknown as { CSSStyleSheet: unknown; Highlight?: unknown; CSS: { highlights?: unknown } }
  const doc = document as unknown as { adoptedStyleSheets?: unknown[] }
  let saved: { CSSStyleSheet: unknown; Highlight: unknown; highlights: unknown; adopted: unknown[] | undefined }

  beforeEach(() => {
    saved = { CSSStyleSheet: g.CSSStyleSheet, Highlight: g.Highlight, highlights: g.CSS.highlights, adopted: doc.adoptedStyleSheets }
    highlights.clear()
    g.CSSStyleSheet = class { replaceSync() {} }
    g.Highlight = class {
      constructor(public range: Range) {}
    }
    g.CSS.highlights = highlights
    doc.adoptedStyleSheets = []
    __resetCitationHighlightStyleForTests()
  })

  afterEach(() => {
    g.CSSStyleSheet = saved.CSSStyleSheet
    g.Highlight = saved.Highlight
    g.CSS.highlights = saved.highlights
    if (saved.adopted === undefined) delete doc.adoptedStyleSheets
    else doc.adoptedStyleSheets = saved.adopted
  })

  it.each(CASES)('$jump registers $registers', async ({ chip, registers, lands }) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
    render(
      <QueryClientProvider client={client}>
        <FilingViewerProvider>
          {chip}
          <FilingViewer embedded filingId={3} filingLabel="AAPL 10-K" secUrl={DOCUMENT_URL} />
        </FilingViewerProvider>
      </QueryClientProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: /^(Source:|Citation) / }))
    await waitFor(() => expect(highlights.size).toBe(1))
    expect([...highlights.keys()]).toEqual([registers])
    // The jump found its text, so the paint is the one this case names, not a passage the reader missed.
    expect(highlights.get(registers)!.range.toString()).toContain(lands)
    expect(screen.queryByText(/Couldn’t pinpoint the exact passage/)).toBeNull()
  })
})
