// The filed day has to survive a zone behind UTC, so this file pins one, as filing-date-local-day.spec.tsx does (Node
// re-reads process.env.TZ on assignment), and its first case checks that the pin applies.
process.env.TZ = 'America/New_York'

import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { Filing } from '@/features/filings/api/filings-api'
import { buildFilename } from '@/features/summaries/hooks/useSummaryExports'

// The summary's download name (E305). The cases live in backend/tests/fixtures/summary_export_filenames.json, the one
// table this builder and the backend's summary_export_filename (backend/tests/unit/test_export_service.py) both run, so
// the name the page gives a download and the name the export routes send cannot drift apart.
interface FilenameCase {
  ticker: string | null
  filing_type: string | null
  filing_date: string | null
  kind: 'pdf' | 'csv'
  name: string
}
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const table: { cases: FilenameCase[] } = JSON.parse(
  readFileSync(path.resolve(frontendDir, '../backend/tests/fixtures/summary_export_filenames.json'), 'utf8'),
)

describe('the summary download name', () => {
  it('runs in a zone where a UTC-shifted day would show', () => {
    expect(new Date('2026-02-06T00:00:00+00:00').getDate()).toBe(5)
  })

  it.each(table.cases)('$ticker $filing_type $filing_date $kind -> $name', (row) => {
    const filing = {
      filing_type: row.filing_type,
      filing_date: row.filing_date,
      ...(row.ticker === null ? {} : { company: { id: 1, ticker: row.ticker, name: 'Fixture Inc.' } }),
    } as unknown as Filing
    expect(buildFilename(filing, row.kind)).toBe(row.name)
  })
})
