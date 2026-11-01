import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import type { GrowthValue } from '@/features/analysis/api/analysis-api'
import { formatGrowth } from '@/features/analysis/lib/growth'

// The growth as first reported (MPA WP5a): the evidence dialog prints it through formatGrowth, and the analysis PDF and
// workbook print it after "As first reported:" through their own copy of the rule
// (backend/app/services/analysis_export_metadata.py growth_text). The cases live in
// backend/tests/fixtures/analysis_growth_text.json, the one table both copies run
// (backend/tests/unit/test_export_later_filings.py runs it on the backend's), so a change to the page's rule fails here
// until the table, and with it the files' copy, follows.
interface CaseTable {
  groups: { rule: string; why?: string; cases: [number | string, boolean, string][] }[]
}
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const table: CaseTable = JSON.parse(
  readFileSync(path.resolve(frontendDir, '../backend/tests/fixtures/analysis_growth_text.json'), 'utf8'),
)
const cases = table.groups.flatMap(({ rule, cases: rows }) => rows.map(([value, percent, text]) => [rule, value, percent, text] as const))

describe('the growth as first reported, as the page prints it', () => {
  it('reads a table with cases for each part of the rule, and collects a test for every case', ({ task }) => {
    // backend/tests/unit/test_export_later_filings.py holds the files' copy to the same counts.
    expect(table.groups).toHaveLength(9)
    expect(table.groups.every((group) => group.cases.length > 0)).toBe(true)
    expect(cases).toHaveLength(34)
    // The runner's count, not the list's: the tests this suite collected, one for each case of the table.
    const collected = task.suite?.tasks.filter((test) => test.type === 'test' && test.name.includes(': formatGrowth('))
    expect(collected).toHaveLength(table.groups.reduce((total, group) => total + group.cases.length, 0))
  })

  it.each(cases)('%s: formatGrowth(%j, %j) prints %j', (_rule, value, percent, text) => {
    expect(formatGrowth(value as GrowthValue, percent).text).toBe(text)
  })
})
