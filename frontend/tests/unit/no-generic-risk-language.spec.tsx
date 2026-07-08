import { render, screen } from '@testing-library/react'
import { SummaryBlocks } from '@/features/summaries/components/SummaryBlocks'
import type { RenderedSection, Summary } from '@/features/summaries/api/summaries-api'

// Rule-9/3.3.9 gate: risks must carry supporting evidence. Backend render_sections filters
// evidence-less risks; SummaryBlocks renders the risks section from the enriched
// raw_summary.risk_factors (via normalizeRisk) so its Trace-to-Source chips survive. This pins
// that an evidence-backed risk renders (with its excerpt) while a generic, evidence-less one is
// dropped — on the live structured page, not the retired tabs.
describe('Risk factors include supporting evidence', () => {
  it('filters out risks without evidence and renders those with citations', () => {
    const sections: RenderedSection[] = [
      {
        id: 'investment-risks-concerns',
        title: 'Investment Risks & Concerns',
        blocks: [
          {
            kind: 'table',
            headers: ['#', 'Risk', 'Supporting Evidence'],
            rows: [['1', 'Supply chain disruption remains elevated.', 'Item 1A: …']],
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
              summary: 'Supply chain disruption remains elevated.',
              supporting_evidence: 'Item 1A: “Supply chain constraints persisted through Q3.”',
            },
            {
              summary: 'Generic statement with no evidence.',
            },
          ],
        },
      },
    } as unknown as Summary

    render(<SummaryBlocks sections={sections} summary={summary} />)

    expect(screen.getByText('Supply chain disruption remains elevated.')).toBeInTheDocument()
    expect(screen.getByText(/Item 1A:/i)).toBeInTheDocument()
    expect(screen.queryByText('Generic statement with no evidence.')).not.toBeInTheDocument()
  })
})
