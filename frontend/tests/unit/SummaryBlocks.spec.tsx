import { render, screen } from '@testing-library/react'
import { SummaryBlocks } from '@/features/summaries/components/SummaryBlocks'
import type { RenderedSection, Summary } from '@/features/summaries/api/summaries-api'

// The single structured web surface (T2): one renderer per Block.kind, a sticky TOC whose anchors
// match every Section.id, the metrics section rendered from server-computed deltas, and the risks
// section rendered with its Trace-to-Source provenance — with NO field-name scaffolding leaking.
const sections: RenderedSection[] = [
  {
    id: 'executive-assessment',
    title: 'Executive Assessment',
    blocks: [
      { kind: 'paragraph', text: 'Revenue surged on data-center demand.' },
      { kind: 'bullets', text: 'Highlights', items: ['Revenue up 85% YoY', 'Gross margin expanded'] },
    ],
  },
  {
    id: 'financial-highlights',
    title: 'Financial Highlights',
    blocks: [
      {
        kind: 'metrics',
        headers: ['Metric', 'Current Period', 'Prior Period', 'Change', 'Investor Takeaway'],
        rows: [['Revenue', '$81.6B', '$44.1B', '+85.0%', 'Data-center growth.']],
        metric_rows: [
          {
            metric: 'Revenue',
            current_period: '$81.6B',
            prior_period: '$44.1B',
            commentary: 'Data-center growth.',
            change_display: '+85.0%',
            change_direction: 'up',
            change_tone: 'gain',
          },
        ],
      },
    ],
  },
  {
    id: 'management-strategy-execution',
    title: 'Management Strategy & Execution',
    blocks: [{ kind: 'quote', text: 'We see unprecedented demand.', speaker: 'CEO' }],
  },
  {
    id: 'business-segment-analysis',
    title: 'Business Segment Analysis',
    blocks: [
      {
        kind: 'table',
        headers: ['Segment', 'Revenue', 'Change', 'Commentary'],
        rows: [['Data Center', '$60B', '+120%', 'AI buildout']],
      },
    ],
  },
  {
    id: 'forward-outlook-investment-implications',
    title: 'Forward Outlook & Investment Implications',
    blocks: [{ kind: 'callout', label: 'Red flag', text: 'Receivables outpaced sales.' }],
  },
  {
    id: 'investment-risks-concerns',
    title: 'Investment Risks & Concerns',
    blocks: [
      {
        kind: 'table',
        headers: ['#', 'Risk', 'Supporting Evidence'],
        rows: [['1', 'Supply concentration', 'Item 1A']],
      },
    ],
  },
]

const summary = {
  business_overview: 'x',
  raw_summary: {
    risk_source_context_version: 1,
    sections: {
      risks: [
        {
          summary: 'Filing excerpt',
          supporting_evidence: 'Item 1A: “substantially dependent on TSMC.”',
          source_url: 'https://www.sec.gov/Archives/edgar/data/1/2/3',
          source_verified: true,
          source_section_ref: 'Filing excerpt',
        },
      ],
      _risk_source_projection: { version: 1, verified_count: 1, withheld_count: 0 },
    },
  },
} as unknown as Summary

describe('SummaryBlocks', () => {
  it('dispatches each block kind to its renderer', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)

    // paragraph + bullets
    expect(screen.getByText('Revenue surged on data-center demand.')).toBeInTheDocument()
    expect(screen.getByText('Revenue up 85% YoY')).toBeInTheDocument()
    // metrics → FinancialMetricsTable: server-computed change chip rendered verbatim (no client math)
    expect(screen.getByText('+85.0%')).toBeInTheDocument()
    expect(screen.getByText('Data-center growth.')).toBeInTheDocument()
    // quote + speaker
    expect(screen.getByText(/We see unprecedented demand/)).toBeInTheDocument()
    expect(screen.getByText(/CEO/)).toBeInTheDocument()
    // generic table (segments)
    expect(screen.getByText('Data Center')).toBeInTheDocument()
    // callout
    expect(screen.getByText('Receivables outpaced sales.')).toBeInTheDocument()
  })

  it('sets whole-figure columns in the data face and keeps commentary that opens with a figure as prose', () => {
    const segments: RenderedSection[] = [
      {
        id: 'business-segment-analysis',
        title: 'Business Segment Analysis',
        blocks: [
          {
            kind: 'table',
            headers: ['Segment', 'Revenue', 'Revenue Change', 'Commentary'],
            // Older retained summaries prefix segment commentary with a machine margin.
            rows: [
              ['iPhone', '$46.2B', '+6.1%', '41% operating margin — higher net sales of iPhone'],
              ['Services', '$26.6B', '-', '$1.2B of the increase came from advertising'],
            ],
          },
        ],
      },
    ]
    render(<SummaryBlocks sections={segments} summary={summary} />)
    expect(screen.getByRole('columnheader', { name: 'Revenue' })).toHaveClass('text-right')
    expect(screen.getByText('$46.2B')).toHaveClass('text-right', 'font-data', 'whitespace-nowrap')
    expect(screen.getByText('+6.1%')).toHaveClass('text-right')
    expect(screen.getByRole('columnheader', { name: 'Commentary' })).toHaveClass('text-left')
    expect(screen.getByText(/41% operating margin/)).not.toHaveClass('text-right')
    expect(screen.getByText(/41% operating margin/)).not.toHaveClass('whitespace-nowrap')
  })

  it('builds a table of contents whose anchors match every section id', () => {
    const { container } = render(<SummaryBlocks sections={sections} summary={summary} />)
    for (const section of sections) {
      expect(container.querySelector(`a[href="#${section.id}"]`)).not.toBeNull()
      // The section itself is an anchor target with the matching id.
      expect(container.querySelector(`#${section.id}`)).not.toBeNull()
    }
  })

  it('renders the risks section with its evidence + trace-to-source provenance', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    expect(screen.getByRole('heading', { level: 4, name: 'Filing excerpt 1' })).toBeInTheDocument()
    expect(screen.getByText(/substantially dependent on TSMC/)).toBeInTheDocument()
    // source_verified: true → the shared SourceTrace renders the "Verified in filing" affordance.
    expect(screen.getByText(/Verified in filing/i)).toBeInTheDocument()
  })

  it('leaks no field-name scaffolding', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    for (const leak of [/Headline:/, /Key Points:/, /Tone:/, /Source Section Ref:/, /Guidance:/]) {
      expect(screen.queryByText(leak)).not.toBeInTheDocument()
    }
  })

  it('renders Trace-to-Source chips on cited quotes, footnotes, and metric takeaways (T4)', () => {
    const verified = (ref: string) => ({
      excerpt: 'a verbatim line from the filing',
      section_ref: ref,
      verified: true,
      fragment_url: `https://www.sec.gov/x.htm#:~:text=${encodeURIComponent(ref)}`,
    })
    const cited: RenderedSection[] = [
      {
        id: 'forward-signals',
        title: 'Forward Signals',
        blocks: [{ kind: 'quote', text: 'We expect double-digit growth.', speaker: 'CEO', evidence: verified('Item 7. MD&A') }],
      },
      {
        id: 'results-that-matter',
        title: 'Results That Matter',
        blocks: [
          {
            kind: 'metrics',
            headers: ['Metric', 'Current Period', 'Investor Takeaway'],
            rows: [['Revenue', '$81.6B', 'Services strength']],
            metric_rows: [
              { metric: 'Revenue', current_period: '$81.6B', prior_period: '', commentary: 'Services strength', commentary_evidence: verified('Item 8') },
            ],
          },
        ],
      },
      {
        id: 'notable-footnotes',
        title: 'Notable Footnotes',
        blocks: [
          {
            kind: 'table',
            headers: ['Item', 'Impact'],
            rows: [['SBC', 'Expense over vesting'], ['Litigation', 'Contingent']],
            // First footnote verified; second uncited (null) → no chip.
            row_evidence: [verified('Note 5'), null],
          },
        ],
      },
    ]
    render(<SummaryBlocks sections={cited} summary={summary} />)
    // One chip each for the quote, the metric takeaway, and the first (only cited) footnote.
    expect(screen.getAllByText(/Verified in filing/i)).toHaveLength(3)
  })

  it('shows an empty state when there are no sections', () => {
    render(<SummaryBlocks sections={[]} summary={summary} />)
    expect(screen.getByText(/No summary found/i)).toBeInTheDocument()
  })

  it('renders tone as a header Badge, not a prose sentence', () => {
    const toneSections: RenderedSection[] = [
      {
        id: 'executive-assessment',
        title: 'Executive Assessment',
        tone: 'positive',
        blocks: [{ kind: 'paragraph', text: 'Record quarter driven by AI demand.' }],
      },
    ]
    render(<SummaryBlocks sections={toneSections} summary={summary} />)
    expect(screen.getByText('positive')).toBeInTheDocument()
    expect(screen.queryByText(/tone was/i)).not.toBeInTheDocument()
  })

  it('renders a compact mobile jump-nav whose anchors mirror the desktop TOC', () => {
    render(<SummaryBlocks sections={sections} summary={summary} />)
    const mobileNav = screen.getByRole('navigation', { name: 'Jump to section' })
    const desktopNav = screen.getByRole('navigation', { name: 'Summary sections' })
    for (const section of sections) {
      expect(mobileNav.querySelector(`a[href="#${section.id}"]`)).not.toBeNull()
      expect(desktopNav.querySelector(`a[href="#${section.id}"]`)).not.toBeNull()
    }
    // Chips are real anchors (keyboard-reachable, no onChange navigation), one per section.
    expect(mobileNav.querySelectorAll('a')).toHaveLength(sections.length)
  })

  it('uses neutral headings instead of model-authored risk labels', () => {
    const riskSections: RenderedSection[] = [
      { id: 'investment-risks-concerns', role: 'risks', title: 'Investment Risks & Concerns', blocks: [] },
    ]
    const untitled = {
      business_overview: 'x',
      raw_summary: {
        risk_source_context_version: 1,
        sections: {
          risks: [
            { summary: 'Filing excerpt', supporting_evidence: 'Item 1A: verbatim quote one.' },
            { summary: 'Filing excerpt', supporting_evidence: 'Item 1A: verbatim quote two.' },
          ],
          _risk_source_projection: { version: 1, verified_count: 2, withheld_count: 0 },
        },
      },
    } as unknown as Summary
    render(<SummaryBlocks sections={riskSections} summary={untitled} />)
    const headings = screen.getAllByRole('heading', { level: 4 }).map((h) => h.textContent)
    expect(headings).toEqual(['Filing excerpt 1', 'Filing excerpt 2'])
    expect(screen.queryByText(/Customer concentration|FX headwinds/)).not.toBeInTheDocument()
  })

  it('matches the risks section by role and renders only owner-projected excerpts', () => {
    const riskSections: RenderedSection[] = [
      { id: 'investment-risks-concerns', role: 'risks', title: 'Investment Risks & Concerns', blocks: [] },
    ]
    const withPlaceholder = {
      business_overview: 'x',
      raw_summary: {
        risk_source_context_version: 1,
        sections: {
          risks: [
            { summary: 'Filing excerpt', supporting_evidence: 'Item 1A: verbatim quote.' },
          ],
          _risk_source_projection: { version: 1, verified_count: 1, withheld_count: 1 },
        },
      },
    } as unknown as Summary
    render(<SummaryBlocks sections={riskSections} summary={withPlaceholder} />)
    expect(screen.getByText('Item 1A: verbatim quote.')).toBeInTheDocument()
    expect(screen.getByText(/1 item withheld/)).toBeInTheDocument()
    expect(screen.queryByText('Vague.')).not.toBeInTheDocument()
  })
})
