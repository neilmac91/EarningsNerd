import type { FinancialMetric } from '@/features/summaries/components/FinancialMetricsTable'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import demo from '@/features/analysis/demo/demo-analysis.json'

/**
 * ILLUSTRATIVE, STATIC sample props for the product screens on the marketing landing page.
 *
 * None of this is live data. The product components (FinancialMetricsTable, SourceTrace,
 * CitationChip, KpiStrip, MetricsTable, WhatChanged) render these exactly as they render real
 * payloads. Every figure is from Apple's FY2025 10-K (accession 0000320193-25-000079, filed
 * 2025-10-31), the same filing the live hero example summarises, verified against the SEC
 * companyfacts XBRL on 2026-10-11 (docs/brand/00-audit.md §4); the excerpts are verbatim from that
 * filing's Item 7. The takeaway sentences are editorial. The Multi-Period demo below still comes
 * from the FY2019–FY2024 pipeline snapshot (regenerate it through the pipeline, never by hand).
 */

export const AAPL_FY25_EDGAR_URL =
  'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'

export const SAMPLE_FILING = {
  ticker: 'AAPL',
  companyName: 'Apple Inc.',
  filingType: '10-K',
  fiscalYear: 'FY2025',
  priorFiscalYear: 'FY2024',
  secUrl: AAPL_FY25_EDGAR_URL,
} as const

/** Financial Highlights rows (FinancialMetricsTable). Values: FY2025 vs FY2024 10-K XBRL
 *  (RevenueFromContractWithCustomerExcludingAssessedTax 416,161M vs 391,035M; NetIncomeLoss
 *  112,010M vs 93,736M; EarningsPerShareDiluted 7.46 vs 6.08). The labels are the ones a real
 *  payload carries: the server checks only mapped concepts of at least $1M
 *  (provenance_service.build_metric_source), so the two totals read SEC XBRL and the per-share
 *  figure reads Cited, never a match the product could not have made. */
export const SAMPLE_FINANCIAL_METRICS: FinancialMetric[] = [
  {
    metric: 'Revenue',
    current_period: '$416.2B',
    prior_period: '$391.0B',
    change_display: '+6.4%',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Up 6.4% on the prior year; Services grew fastest.',
    source_url: AAPL_FY25_EDGAR_URL,
    source_verified: true,
    xbrl_concept: 'Revenue',
    source_section_ref: 'Consolidated Statements of Operations',
  },
  {
    metric: 'Net income',
    current_period: '$112.0B',
    prior_period: '$93.7B',
    change_display: '+19.5%',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Grew three times as fast as revenue; the provision for income taxes fell.',
    source_url: AAPL_FY25_EDGAR_URL,
    source_verified: true,
    xbrl_concept: 'NetIncomeLoss',
    source_section_ref: 'Consolidated Statements of Operations',
  },
  {
    metric: 'Diluted EPS',
    current_period: '$7.46',
    prior_period: '$6.08',
    change_display: '+22.7%',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Buybacks lifted EPS above net income growth.',
    source_url: AAPL_FY25_EDGAR_URL,
    // A per-share figure: never checked against XBRL, so never labelled as matched.
    source_verified: false,
    source_section_ref: 'Consolidated Statements of Operations',
  },
]

/** Trace-to-Source demo: one claim and the Item 7 sentence it came from (verbatim). */
export const SAMPLE_TRACE = {
  claim: 'Services net sales rose 13.5% to $109.2B on advertising, the App Store and cloud services.',
  sectionRef: 'Item 7 · Management’s Discussion and Analysis',
  excerpt:
    'Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services.',
  url: AAPL_FY25_EDGAR_URL,
} as const

/** The catch (docs/brand/04-directions.md, D-012): the number a reader remembers is last year's.
 *  Both are the filing's total net sales, FY2024 and FY2025, from the same XBRL fact. */
export const SAMPLE_CATCH = {
  metric: 'Total net sales',
  remembered: '$391.0B',
  rememberedPeriod: 'FY2024',
  inFiling: '$416.2B',
  inFilingPeriod: 'FY2025',
  concept: 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
  url: AAPL_FY25_EDGAR_URL,
} as const

/** Ask this Filing demo: one answer with an XBRL figure chip ([F1]) and a passage chip ([1]).
 *  Services net sales from the Products and Services Performance table: $109,158M vs $96,169M. */
export const SAMPLE_ASK = {
  question: 'How much did Services revenue grow, and what drove it?',
  // Markers are injected as CitationChips by lib/citationMarkers, exactly as CopilotMessage does.
  answer:
    'Services net sales were $109.2B, up 13.5% from $96.2B [F1]. Management attributes the increase to advertising, the App Store and cloud services [1].',
  citations: [
    {
      n: 'F1',
      excerpt: 'Services net sales: $109,158 million (FY2025) vs $96,169 million (FY2024)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax · Services',
      verified: true,
      fragment_url: AAPL_FY25_EDGAR_URL,
    },
    {
      n: 1,
      excerpt:
        'Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services.',
      section_ref: 'Item 7 · Products and Services Performance',
      verified: true,
      fragment_url: AAPL_FY25_EDGAR_URL,
    },
  ] satisfies CopilotCitation[],
} as const

/** Change Report demo (WhatChanged): FY2025 vs FY2024 XBRL deltas. Risk lines are left to the
 *  live report (the page renders skeleton bones in their place). */
export const SAMPLE_CHANGE_REPORT: ChangeReport = {
  has_prior: true,
  comparison_basis: 'Year over year',
  // No prior filing id is known statically; the live report links to the real prior 10-K.
  prior_filing: null,
  metrics: {
    headline: 'Revenue, net income and diluted EPS all rose against the prior fiscal year.',
    data_quality: 'ok',
    items: [
      { metric: 'revenue', label: 'Revenue', direction: 'up', pct: 6.4, current: 416161e6, prior: 391035e6, display: '+6.4%', tone: 'gain' },
      { metric: 'net_income', label: 'Net income', direction: 'up', pct: 19.5, current: 112010e6, prior: 93736e6, display: '+19.5%', tone: 'gain' },
      { metric: 'eps_diluted', label: 'Diluted EPS', direction: 'up', pct: 22.7, current: 7.46, prior: 6.08, display: '+22.7%', tone: 'gain' },
    ],
  },
  reporting_currency: 'USD',
  risks: null,
  key_changes: null,
  has_changes: true,
}

/**
 * Multi-Period Analysis demo: the checked-in sample payload the free-user AnalysisTeaser already
 * renders (Apple, annual, FY2019–FY2024, XBRL-reconciled), narrowed to the three series the
 * landing screen shows. KpiStrip and MetricsTable render it unchanged.
 */
const DEMO_DATASET = demo.dataset as unknown as AnalysisDataset
const LANDING_SERIES = new Set(['revenue', 'net_income', 'net_margin'])

export const SAMPLE_ANALYSIS_DATASET: AnalysisDataset = {
  ...DEMO_DATASET,
  series: DEMO_DATASET.series.filter((series) => LANDING_SERIES.has(series.concept)),
}
