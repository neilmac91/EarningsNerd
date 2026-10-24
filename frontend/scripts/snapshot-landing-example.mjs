#!/usr/bin/env node
/**
 * Snapshot the live example's Financial Highlights for the landing page's evidence row.
 *
 * The evidence row shows the product's real output for its example filing (the founder's call, 2026-10-22): the
 * rows, figures, changes, labels, takeaways and takeaway evidence as GET /api/summaries/filing/{id} serves them,
 * never written by hand. The script reads three public endpoints (the filing, its summary, and its Change Report for
 * the prior period's end) and writes features/marketing/lib/landing-example.json. One rule is applied on top: a
 * takeaway's passage that carries the table's own section label (where the figures come from) loses it, as the
 * backend's read-time enrichment now does (provenance_service._excerpt_section_ref); against an API that already
 * serves that rule it changes nothing.
 *
 * Rerun it when the example moves to another filing (NEXT_PUBLIC_EXAMPLE_FILING_ID) and after a deploy that changes
 * what the summary endpoint serves. tests/unit/landingSamplesVerified.spec.ts then holds every figure in the
 * snapshot to the filing facts docs/brand/00-audit.md §4 records.
 *
 * Usage, from frontend/: node scripts/snapshot-landing-example.mjs [filingId] [apiOrigin]
 *   filingId   the example filing, default 3 (Apple's FY2025 10-K)
 *   apiOrigin  default https://api.earningsnerd.io
 */
import { writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// The rows the evidence row shows, by the summary's own labels: two figures the server matches to the filing, a
// segment line and a per-share figure it never checks, so each figure label in the legend appears on a real row.
const ROWS = ['Total net sales', 'Services net sales', 'Net income', 'Diluted earnings per share']
// The fields the table reads (FinancialMetric); anything else the payload carries stays out of the snapshot.
const FIELDS = [
  'metric', 'current_period', 'prior_period', 'change_display', 'change_direction', 'change_tone', 'commentary',
  'commentary_evidence', 'commentary_withheld', 'source_url', 'source_verified', 'source_checkable',
  'source_section_ref', 'source_filed', 'source_replaced', 'xbrl_concept', 'per_ads',
]
const TARGET = path.join(path.dirname(fileURLToPath(import.meta.url)), '../features/marketing/lib/landing-example.json')

const [filingId = '3', origin = 'https://api.earningsnerd.io'] = process.argv.slice(2)

async function get(route) {
  const response = await fetch(`${origin}${route}`, { headers: { accept: 'application/json' } })
  if (!response.ok) throw new Error(`${route}: HTTP ${response.status}`)
  return response.json()
}

/** "2025-09-27T00:00:00+00:00" -> "2025-09-27" */
const day = (value) => (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : null)

const [filing, summary, changes] = await Promise.all([
  get(`/api/filings/${filingId}`),
  get(`/api/summaries/filing/${filingId}`),
  get(`/api/summaries/filing/${filingId}/what-changed`),
])

const served = (summary.rendered_sections ?? [])
  .flatMap((section) => section.blocks ?? [])
  .filter((block) => block.kind === 'metrics')
  .flatMap((block) => block.metric_rows ?? [])

const rows = ROWS.map((label) => {
  const row = served.find((candidate) => candidate?.metric === label)
  if (!row) throw new Error(`the summary for filing ${filingId} has no "${label}" row`)
  const picked = Object.fromEntries(FIELDS.filter((field) => row[field] !== undefined).map((field) => [field, row[field]]))
  const evidence = picked.commentary_evidence
  if (evidence?.section_ref && evidence.section_ref === row.source_section_ref) {
    picked.commentary_evidence = { ...evidence, section_ref: null }
  }
  return picked
})

const snapshot = {
  note: 'Written by frontend/scripts/snapshot-landing-example.mjs from the live example. Never edit by hand.',
  source: `${origin}/api/summaries/filing/${filingId}`,
  fetched: new Date().toISOString().slice(0, 10),
  filing: {
    id: filing.id,
    ticker: filing.company?.ticker ?? null,
    company: filing.company?.name ?? null,
    form: filing.filing_type,
    accession: filing.accession_number,
    document_url: filing.document_url,
    period_end: day(filing.report_date),
    prior_period_end: day(changes.prior_filing?.period_end_date),
    filed: day(filing.filing_date),
  },
  rows,
}

writeFileSync(TARGET, `${JSON.stringify(snapshot, null, 2)}\n`)
console.log(`wrote ${path.relative(process.cwd(), TARGET)}: ${rows.length} rows from filing ${filingId} (${snapshot.filing.ticker} ${snapshot.filing.form}, period ${snapshot.filing.period_end})`)
