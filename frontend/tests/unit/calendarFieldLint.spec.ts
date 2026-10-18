import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

/**
 * The calendar-field lint (eslint.config.mjs, CALENDAR_FIELD_RULES) through the repository config. A Date, a
 * parseISO or a formatInstant built from an API calendar-date field is an error: each renders a UTC-midnight
 * instant as the day before for a reader behind UTC. formatInstant runs parseISO inside lib/format.ts, where no
 * selector at the call site sees it, so it is a constructor in the rule's list, and the call-case selector names
 * each callee (a hardcoded parseISO root would list its selectors twice, and ESLint rejects such a config, so
 * building the instance here also proves the config loads). A genuine instant through formatInstant and a
 * calendar date through formatLocalDate pass. The rendered day is pinned behaviourally in
 * filing-date-local-day.spec.tsx; this case pins the lint's reach.
 */
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

/** Building ESLint from the real config takes 2-3.5s warm and over 7s cold or on a loaded runner; 5s is too tight. */
const SLOW = { timeout: 30_000 }

describe('the calendar-field lint', SLOW, () => {
  it('errors on a calendar-date field through new Date, parseISO and formatInstant, and passes an instant and formatLocalDate', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { parseISO } from 'date-fns'",
        "import { formatInstant, formatLocalDate } from '@/lib/format'",
        'export function probe(filing: { filing_date: string }, sub: { trial_end: string }) {',
        '  const built = new Date(filing.filing_date)',
        '  const parsed = parseISO(filing.filing_date)',
        "  const wrapped = formatInstant(filing.filing_date, 'MMM d, yyyy')",
        "  const instant = formatInstant(sub.trial_end, 'MMM d, yyyy')",
        "  const day = formatLocalDate(filing.filing_date, 'MMM d, yyyy')",
        '  return [built, parsed, wrapped, instant, day]',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/calendar-field-probe.ts') },
    )
    const calendar = result.messages.filter((m) => m.ruleId === 'no-restricted-syntax' && /calendar-date field/.test(m.message))
    expect(calendar.map((m) => m.line)).toEqual([4, 5, 6])
    expect(calendar.every((m) => m.severity === 2)).toBe(true)
  })
})
