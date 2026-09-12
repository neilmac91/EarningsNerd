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
 * payloads. Every figure is from Apple's FY2022 10-K (accession 0000320193-22-000108), the same
 * XBRL-verified snapshot HeroExample falls back to, and the excerpts are verbatim from that
 * filing's MD&A. The takeaway sentences are editorial. Replace each block by capturing the live
 * surface (design/landing-redesign/RATIONALE.md, "Screens the founder must capture").
 */

export const AAPL_FY22_EDGAR_URL =
  'https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/'

export const SAMPLE_FILING = {
  ticker: 'AAPL',
  companyName: 'Apple Inc.',
  filingType: '10-K',
  fiscalYear: 'FY2022',
  priorFiscalYear: 'FY2021',
  secUrl: AAPL_FY22_EDGAR_URL,
} as const

/** Financial Highlights rows (FinancialMetricsTable). Values: FY2022 vs FY2021 10-K XBRL. */
export const SAMPLE_FINANCIAL_METRICS: FinancialMetric[] = [
  {
    metric: 'Revenue',
    current_period: '$394.3B',
    prior_period: '$365.8B',
    change_display: '+7.8%',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Growth held at 8% on iPhone, Services and Mac.',
    source_url: AAPL_FY22_EDGAR_URL,
    source_verified: true,
    xbrl_concept: 'Revenue',
    source_section_ref: 'Consolidated Statements of Operations',
  },
  {
    metric: 'Net income',
    current_period: '$99.8B',
    prior_period: '$94.7B',
    change_display: '+5.4%',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Profit grew more slowly than revenue.',
    source_url: AAPL_FY22_EDGAR_URL,
    source_verified: true,
    xbrl_concept: 'NetIncomeLoss',
    source_section_ref: 'Consolidated Statements of Operations',
  },
  {
    metric: 'Diluted EPS',
    current_period: '$6.11',
    prior_period: '$5.61',
    change_display: '+8.9%',
    change_direction: 'up',
    change_tone: 'gain',
    commentary: 'Buybacks lifted EPS above net income growth.',
    source_url: AAPL_FY22_EDGAR_URL,
    source_verified: true,
    xbrl_concept: 'EPS Diluted',
    source_section_ref: 'Consolidated Statements of Operations',
  },
]

/** Trace-to-Source demo: one verified claim and the MD&A sentence it came from (verbatim). */
export const SAMPLE_TRACE = {
  claim: 'Net sales rose 8% to $394.3B, led by iPhone, Services and Mac.',
  sectionRef: 'Item 7 · Management’s Discussion and Analysis',
  excerpt:
    'Total net sales increased 8% or $28.5 billion during 2022 compared to 2021, driven primarily by higher net sales of iPhone, Services and Mac.',
  url: AAPL_FY22_EDGAR_URL,
} as const

/** Ask this Filing demo: one answer with an XBRL figure chip ([F1]) and a passage chip ([1]). */
export const SAMPLE_ASK = {
  question: 'How much did Services revenue grow, and what drove it?',
  // Markers are injected as CitationChips by lib/citationMarkers, exactly as CopilotMessage does.
  answer:
    'Services net sales were $78.1B, up 14.2% from $68.4B [F1]. Management attributes the increase to advertising, cloud services and the App Store [1].',
  citations: [
    {
      n: 'F1',
      excerpt: 'Services net sales: $78,129 million (FY2022) vs $68,425 million (FY2021)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax · Services',
      verified: true,
      fragment_url: AAPL_FY22_EDGAR_URL,
    },
    {
      n: 1,
      excerpt:
        'Services net sales increased during 2022 compared to 2021 due primarily to higher net sales from advertising, cloud services and the App Store.',
      section_ref: 'Item 7 · Products and Services Performance',
      verified: true,
      fragment_url: AAPL_FY22_EDGAR_URL,
    },
  ] satisfies CopilotCitation[],
} as const

/** Change Report demo (WhatChanged): FY2022 vs FY2021 XBRL deltas. Risk lines are left to the
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
      { metric: 'revenue', label: 'Revenue', direction: 'up', pct: 7.8, current: 394328e6, prior: 365817e6, display: '+7.8%', tone: 'gain' },
      { metric: 'net_income', label: 'Net income', direction: 'up', pct: 5.4, current: 99803e6, prior: 94680e6, display: '+5.4%', tone: 'gain' },
      { metric: 'eps_diluted', label: 'Diluted EPS', direction: 'up', pct: 8.9, current: 6.11, prior: 5.61, display: '+8.9%', tone: 'gain' },
    ],
  },
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
