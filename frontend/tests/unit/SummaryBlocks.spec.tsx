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
    sections: {
      risk_factors: [
        {
          title: 'Supply concentration',
          description: 'Substantially dependent on a small number of foundries.',
          supporting_evidence: 'Item 1A: “substantially dependent on TSMC.”',
          source_url: 'https://www.sec.gov/Archives/edgar/data/1/2/3',
          source_verified: true,
          source_section_ref: 'Item 1A',
        },
      ],
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
    expect(screen.getByText('Substantially dependent on a small number of foundries.')).toBeInTheDocument()
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

  it('matches the risks section by role and filters placeholder-evidence risks', () => {
    const riskSections: RenderedSection[] = [
      { id: 'investment-risks-concerns', role: 'risks', title: 'Investment Risks & Concerns', blocks: [] },
    ]
    const withPlaceholder = {
      business_overview: 'x',
      raw_summary: {
        sections: {
          risk_factors: [
            { title: 'Real', description: 'A concrete, evidenced risk.', supporting_evidence: 'Item 1A: verbatim quote.' },
            { title: 'Filler', description: 'Vague.', supporting_evidence: 'Data not available in provided excerpts.' },
          ],
        },
      },
    } as unknown as Summary
    render(<SummaryBlocks sections={riskSections} summary={withPlaceholder} />)
    expect(screen.getByText('A concrete, evidenced risk.')).toBeInTheDocument()
    expect(screen.queryByText('Vague.')).not.toBeInTheDocument()
  })
})
