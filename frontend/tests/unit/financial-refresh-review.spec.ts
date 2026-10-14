import { describe, expect, it } from 'vitest'
import { FICTIONAL_ROWS } from '@/features/financial-refresh-review/data/fictionalExample'
import { buildReceipt, compareRow, csvCell, currentValuesCsv, reviewRows, type RefreshRow, type SampleFact } from '@/features/financial-refresh-review/lib/refreshReview'

const revenue = FICTIONAL_ROWS[0]
const withCandidate = (patch: Partial<SampleFact>): RefreshRow => ({ ...revenue, candidate: { ...revenue.candidate, ...patch } })

describe('Financial refresh comparison and immutable decisions', () => {
  it('distinguishes revisions, source-only updates, missing figures and zero', () => {
    expect(compareRow(revenue, 'existing-periods').kind).toBe('revised-comparative')
    expect(compareRow(FICTIONAL_ROWS[1], 'existing-periods').kind).toBe('source-only')
    expect(compareRow(FICTIONAL_ROWS[3], 'existing-periods')).toMatchObject({ kind: 'missing', eligible: false })
    expect(compareRow(FICTIONAL_ROWS[5], 'existing-periods')).toMatchObject({ kind: 'revised-comparative', eligible: true })
    expect(compareRow({ ...revenue, candidate: revenue.baseline }, 'existing-periods').kind).toBe('unchanged')
  })
  it.each([
    { company: 'another-issuer' }, { metric: 'gross_profit' }, { context: 'segment-only' }, { unit: 'EUR' },
    { sourceId: '' }, { sourceId: revenue.baseline.sourceId }, { filedOn: '2025-01-01' }, { filedOn: revenue.baseline.filedOn },
    { value: 1.25 }, { value: Number.MAX_SAFE_INTEGER + 1 }, { value: Number.NaN }, { value: Infinity },
    { periodStart: '2024-02-01' }, { periodStart: null }, { periodEnd: '2024-09-30' },
    { periodStart: '2024-06-01', periodEnd: '2025-05-31' },
  ])('refuses incompatible candidate %j', (patch) => {
    expect(compareRow(withCandidate(patch), 'include-new-periods')).toMatchObject({ kind: 'incomparable', eligible: false })
  })
  it('requires explicit new-period scope and appends without overwriting', () => {
    const row = FICTIONAL_ROWS[2]
    expect(compareRow(row, 'existing-periods').eligible).toBe(false)
    expect(compareRow(row, 'include-new-periods')).toMatchObject({ kind: 'new-period', eligible: true })
    expect(reviewRows([row], 'include-new-periods', { [row.id]: 'accept' })[0].values).toEqual([row.baseline, row.candidate])
    expect(reviewRows([row], 'existing-periods', { [row.id]: 'accept' })[0]).toMatchObject({ decision: null, values: [row.baseline] })
  })
  it('rechecks eligibility for stale accept decisions', () => {
    const decisions = Object.fromEntries(FICTIONAL_ROWS.map((row) => [row.id, 'accept' as const]))
    const result = reviewRows(FICTIONAL_ROWS, 'existing-periods', decisions)
    for (const index of [2, 3, 4]) {
      expect(result[index].decision).toBeNull()
      expect(result[index].values).toEqual([FICTIONAL_ROWS[index].baseline])
    }
  })
  it('preserves frozen inputs and distinguishes conscious keep from unresolved', () => {
    const row = { ...revenue, baseline: Object.freeze({ ...revenue.baseline }), candidate: Object.freeze({ ...revenue.candidate }) }
    const rows = Object.freeze([Object.freeze(row)])
    const before = JSON.stringify(rows)
    expect(reviewRows(rows, 'existing-periods', {})[0]).toMatchObject({ decision: null, values: [row.baseline] })
    expect(reviewRows(rows, 'existing-periods', { revenue: 'keep' })[0]).toMatchObject({ decision: 'keep', values: [row.baseline] })
    expect(reviewRows(rows, 'existing-periods', { revenue: 'accept' })[0]).toMatchObject({ decision: 'accept', values: [row.candidate] })
    expect(JSON.stringify(rows)).toBe(before)
  })
  it('exports decided values and both-source receipts with missing/blocked decisions intact', () => {
    const decisions = { revenue: 'accept', capex: 'accept', 'net-income': 'accept', cash: 'keep', charges: 'accept' } as const
    const receipt = buildReceipt(FICTIONAL_ROWS, 'include-new-periods', decisions)
    const csv = currentValuesCsv(FICTIONAL_ROWS, 'include-new-periods', decisions)
    expect(receipt).toMatchObject({ sampleData: true, schemaVersion: 1, mode: 'include-new-periods' })
    expect(receipt.rows[0]).toMatchObject({ baseline: revenue.baseline, candidate: revenue.candidate, decision: 'accept', values: [revenue.candidate] })
    expect(receipt.rows[4]).toMatchObject({ decision: null, comparison: { kind: 'incomparable' } })
    expect(receipt.rows[1].comparison.kind).toBe('source-only')
    expect(csv).toContain('"123000000","SAMPLE-2025-ANNUAL","2026-02-12","accept","revised-comparative"')
    expect(csv).toContain('"19000000","SAMPLE-2024-ANNUAL","2025-02-10","keep","missing"')
    expect(csv).toContain('"42000000","SAMPLE-2024-ANNUAL","2025-02-10","unresolved","incomparable"')
    expect(csv).toContain('"0","SAMPLE-2025-ANNUAL"')
    expect(csv.trim().split('\r\n')).toHaveLength(8)
    expect(csv.split('\r\n')[0]).toContain('"source_id","filed_on","decision","comparison"')
  })
})

describe('Inert spreadsheet export text', () => {
  it.each(['=1+1', '+cmd', '-1+2', '@SUM(A1)', ' \t=1', '\n=1', '\r+1', '\tplain', '\u0000plain', '\uFEFF=1'])('neutralizes formula/control-leading label %j', (value) => {
    expect(csvCell(value)).toBe(`"'${value}"`)
  })
  it('quotes delimiters/newlines/quotes and preserves numeric negatives, null and zero', () => {
    expect(csvCell('A,"B"\nC')).toBe('"A,""B""\nC"')
    expect(csvCell(-12)).toBe('"-12"')
    expect(csvCell(null)).toBe('""')
    expect(csvCell(0)).toBe('"0"')
  })
})
