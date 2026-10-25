import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { formatCompanyName } from '@/lib/formatCompanyName'

// The one casing rule (lib/formatCompanyName.ts): ALL-CAPS EDGAR names are title-cased per token
// with a small exceptions list; punctuation is never added or removed; already-cased names are
// returned untouched.
//
// The cases live in backend/tests/fixtures/company_display_names.json, the one table both copies of
// the rule run: this module and backend/app/utils/company_names.py, which the analysis PDF and
// workbook print through (backend/tests/unit/test_company_names.py runs the same table and holds the
// two modules' word lists equal). A case added for either copy runs on both.
interface CaseTable {
  groups: { rule: string; why?: string; cases: [string, string][] }[]
}
const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const table: CaseTable = JSON.parse(
  readFileSync(path.resolve(frontendDir, '../backend/tests/fixtures/company_display_names.json'), 'utf8'),
)
const cases = table.groups.flatMap(({ rule, cases: pairs }) => pairs.map(([served, shown]) => [rule, served, shown] as const))

describe('formatCompanyName', () => {
  it('reads a case table that reaches every part of the rule', () => {
    expect(table.groups.length).toBeGreaterThanOrEqual(12)
    expect(table.groups.every((group) => group.cases.length > 0)).toBe(true)
    // Rule 5's decomposed accent: a served name holding a combining mark, written in the fixture as a JSON escape.
    expect(cases.some(([, served]) => /\p{M}/u.test(served))).toBe(true)
  })

  it.each(cases)('%s: %j -> %j', (_rule, served, shown) => {
    expect(formatCompanyName(served)).toBe(shown)
  })

  it('never adds punctuation: CORP stays CORP-shaped, INC. keeps its period', () => {
    expect(formatCompanyName('MICROSOFT CORP')).not.toContain('.')
    expect(formatCompanyName('APPLE INC.')).toMatch(/Inc\.$/)
  })

  it('treats null and undefined as an empty string', () => {
    expect(formatCompanyName(null)).toBe('')
    expect(formatCompanyName(undefined)).toBe('')
  })
})
