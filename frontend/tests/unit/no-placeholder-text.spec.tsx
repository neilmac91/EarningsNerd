import { render, screen } from '@testing-library/react'
import FinancialMetricsTable from '@/features/summaries/components/FinancialMetricsTable'
import { SummaryBlocks } from '@/features/summaries/components/SummaryBlocks'
import type { RenderedSection, Summary } from '@/features/summaries/api/summaries-api'

describe('UI avoids placeholder copy', () => {
  it('does not render "Not available" placeholders', () => {
    const metrics = [
      {
        metric: 'Operating Cash Flow',
        current_period: '$42,000',
        prior_period: '',
        commentary: '',
      },
    ]

    // Backend render_sections already strips placeholder copy; this pins that the structured
    // renderer never re-introduces it given a clean, realistic payload.
    const sections: RenderedSection[] = [
      {
        id: 'executive-assessment',
        title: 'Executive Assessment',
        blocks: [{ kind: 'paragraph', text: 'Operating cash flow held steady in the quarter.' }],
      },
      {
        id: 'financial-highlights',
        title: 'Financial Highlights',
        blocks: [
          {
            kind: 'metrics',
            headers: ['Metric', 'Current Period', 'Prior Period', 'Change', 'Investor Takeaway'],
            rows: [['Operating Cash Flow', '$42,000', '', '—', '']],
            metric_rows: metrics,
          },
        ],
      },
    ]

    const summary = {
      business_overview: 'x',
      raw_summary: { sections: {} },
    } as unknown as Summary

    render(
      <>
        <FinancialMetricsTable metrics={metrics} />
        <SummaryBlocks sections={sections} summary={summary} />
      </>
    )

    expect(screen.queryByText(/Not available/i)).not.toBeInTheDocument()
  })
})
