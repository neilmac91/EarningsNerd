import type { FinancialMetric } from '@/features/summaries/components/FinancialMetricsTable'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
import type { ChangeReport } from '@/features/summaries/api/summaries-api'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import demo from '@/features/analysis/demo/demo-analysis.json'
import example from '@/features/marketing/lib/landing-example.json'

/**
 * STATIC sample props for the product screens on the marketing landing page.
 *
 * None of this is fetched at request time. The product components (FinancialMetricsTable, SourceTrace,
 * CitationChip, KpiStrip, MetricsTable, WhatChanged) render these exactly as they render real payloads.
 * The evidence row's Financial Highlights rows, and its Trace-to-Source demo, are the product's real
 * output for the live example (Apple's FY2025 10-K, accession 0000320193-25-000079, filed 2025-10-31),
 * snapshotted from the API by scripts/snapshot-landing-example.mjs into landing-example.json and never
 * edited by hand (the founder's call, 2026-10-22). Every other figure is from the same filing, verified
 * against the SEC companyfacts XBRL on 2026-10-11 (docs/brand/00-audit.md §4); the excerpts are verbatim
 * from that filing's Item 7. The Multi-Period demo below is the pipeline's FY2020–FY2025 run of
 * 2026-10-22: its FY2025 and FY2024 revenue, net income, diluted EPS and operating cash flow are the same
 * verified values, and each source link opens the primary document of the filing it cites
 * (tests/unit/landingSamplesVerified.spec.ts). Regenerate it through the pipeline, never by hand, with
 * the company's filings listed first.
 */

// The primary 10-K document, not its accession directory: every sample receipt opens the filing.
export const AAPL_FY25_EDGAR_URL =
  'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm'

/** A fiscal year by the year its period ends ("2025-09-27" is FY2025), as Apple names it. */
const fiscalYear = (periodEnd: string) => `FY${periodEnd.slice(0, 4)}`

export const SAMPLE_FILING = {
  ticker: example.filing.ticker,
  companyName: example.filing.company,
  filingType: example.filing.form,
  fiscalYear: fiscalYear(example.filing.period_end),
  priorFiscalYear: fiscalYear(example.filing.prior_period_end),
  periodEnd: example.filing.period_end,
  priorPeriodEnd: example.filing.prior_period_end,
  filed: example.filing.filed,
  accession: example.filing.accession,
  secUrl: example.filing.document_url,
} as const

/** Financial Highlights rows (FinancialMetricsTable): four of the live example's rows, verbatim, chosen by the
 *  snapshot script so that each figure label appears on a real row: Total net sales and Net income match the
 *  filing, while Services net sales (a segment line) and Diluted earnings per share are linked, not checked. */
export const SAMPLE_FINANCIAL_METRICS = example.rows as FinancialMetric[]

const services = SAMPLE_FINANCIAL_METRICS.find((row) => row.metric === 'Services net sales')

/** Trace-to-Source demo: the Services row's takeaway and the passage the server located for it. */
/** Where a cited passage sits in the 10-K, read from the document (docs/brand/00-audit.md §4). The server names a
 *  takeaway passage's section only when its excerpt carries one (provenance_service._excerpt_section_ref), and this
 *  one does not, so the demo's panel names the filing's own heading, as the plan's §3.6 asks. Keyed by the exact
 *  passage: a snapshot that cites another names none until its heading is read from the filing (E172), and
 *  landingSamplesVerified.spec.ts holds each to the audit. */
const PASSAGE_SECTIONS: Record<string, string> = {
  'Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services.':
    'Item 7 · Products and Services Performance',
}

export const SAMPLE_TRACE = {
  metric: services?.metric ?? '',
  claim: services?.commentary ?? '',
  sectionRef: services?.commentary_evidence?.section_ref ?? PASSAGE_SECTIONS[services?.commentary_evidence?.excerpt ?? ''] ?? null,
  excerpt: services?.commentary_evidence?.excerpt ?? '',
  url: services?.commentary_evidence?.fragment_url ?? AAPL_FY25_EDGAR_URL,
}

/** "Follow one figure to the filing": the Total net sales row traced to the line the 10-K prints. Read from
 *  the filing on 2026-10-22 (docs/brand/00-audit.md §4): the statement and its page from the document, the
 *  tagged amount and its tag from its inline XBRL. landingSamplesVerified.spec.ts holds it to the snapshot's
 *  filing, so a snapshot of another filing fails until these are read from that filing. */
export const SAMPLE_RECEIPT = {
  metric: 'Total net sales',
  accession: '0000320193-25-000079',
  filed: '$416,161 million',
  statement: 'Consolidated Statements of Operations',
  page: 29,
  tagged: '416,161,000,000',
  currency: 'USD',
  periodEnd: '2025-09-27',
  tag: 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
  url: AAPL_FY25_EDGAR_URL,
} as const

/** Ask this Filing demo: one answer as a live run returns it. Two XBRL figure chips in
 *  fact_to_citation's own format (backend/app/services/copilot_tools.py: total net sales, a fact the
 *  tool can fetch, and its year-over-year growth, which compute_metric derives from the same fact) and
 *  one passage chip. Each figure chip carries `fact`, as parseCompletion admits it for a citation that
 *  brings the fact's own payload. The server renumbers every marker in first-appearance order
 *  (copilot/resolution.py), so the answer carries [1] [2] [3], never [F1]. Figures: 416,161M vs
 *  391,035M (docs/brand/00-audit.md §4); tests/unit/landingSamplesVerified.spec.ts holds it. */
export const SAMPLE_ASK = {
  question: 'How much did net sales grow, and what drove Services?',
  // Markers are injected as CitationChips by lib/citationMarkers, exactly as CopilotMessage does.
  answer:
    'Total net sales were $416.2B [1], up 6.4% on the prior year [2]. Management attributes the Services increase to advertising, the App Store and cloud services [3].',
  citations: [
    {
      n: 1,
      excerpt: 'Revenue = $416.16B USD (FY2025/FY)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      verified: true,
      fragment_url: AAPL_FY25_EDGAR_URL,
      fact: true,
    },
    {
      n: 2,
      excerpt: 'Revenue YoY growth = 6.4% (FY2025/FY)',
      section_ref: 'XBRL · us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
      verified: true,
      fragment_url: AAPL_FY25_EDGAR_URL,
      // compute_metric's growth (value_kind "yoy_growth"): the 10-K rounds it to 6%, so it is calculated, not filed.
      calculated: true,
    },
    {
      n: 3,
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
 * renders (Apple, annual, FY2020–FY2025, the pipeline's own run), narrowed to the three series the
 * landing screen shows. KpiStrip and MetricsTable render it unchanged. The run's data notes count
 * every series it holds, so they leave with the other series and the three shown count their own,
 * as any dataset without notes does (resolveDataNotes in features/analysis/lib/dataNotes.ts).
 */
const DEMO_DATASET = demo.dataset as unknown as AnalysisDataset
const LANDING_SERIES = new Set(['revenue', 'net_income', 'net_margin'])
const { data_notes: _everySeriesNotes, ...DEMO_WITHOUT_NOTES } = DEMO_DATASET

export const SAMPLE_ANALYSIS_DATASET: AnalysisDataset = {
  ...DEMO_WITHOUT_NOTES,
  series: DEMO_DATASET.series.filter((series) => LANDING_SERIES.has(series.concept)),
}
