import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ESLint } from 'eslint'
import { describe, expect, it } from 'vitest'

/**
 * The calendar-field lint (eslint.config.mjs, CALENDAR_FIELD_RULES and DATE_HELPER_RULES) through the repository
 * config, in both directions of D-033. A Date, a parseISO or a formatInstant built from an API calendar-date field is
 * an error: each renders a UTC-midnight instant as the day before for a reader behind UTC. formatInstant runs
 * parseISO inside lib/format.ts, where no selector at the call site sees it, so it is a constructor in the rule's
 * list, and the call-case selector names each callee (a hardcoded parseISO root would list its selectors twice, and
 * ESLint rejects such a config, so building the instance here also proves the config loads). The other way, a
 * Stripe billing date (trial_end, current_period_end) through formatLocalDate is an error: it names the instant's
 * UTC day, not the reader's. Each helper is read by its own name and as a namespace member (`fmt.formatInstant(…)`),
 * and going by another name (an import alias, a renaming destructuring, a const that holds it) is an error of its
 * own. A genuine instant through formatInstant and a calendar date through formatLocalDate pass. The rendered day is
 * pinned behaviourally in filing-date-local-day.spec.tsx, TrialBanner.spec.tsx and BillingPanel.spec.tsx; this case
 * pins the lint's reach.
 */
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

/** Building ESLint from the real config takes 2-3.5s warm and over 7s cold or on a loaded runner; 5s is too tight. */
const SLOW = { timeout: 30_000 }

describe('the calendar-field lint', SLOW, () => {
  it('errors on a calendar-date field through new Date, parseISO and formatInstant, a billing instant through formatLocalDate, and a renamed helper, and passes an instant and formatLocalDate', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(
      [
        "import { parseISO } from 'date-fns'",
        "import { formatInstant, formatLocalDate } from '@/lib/format'",
        "import * as fmt from '@/lib/format'",
        "import { formatInstant as formatDay } from '@/lib/format'",
        'export function probe(filing: { filing_date: string }, sub: { trial_end: string; current_period_end: string }) {',
        '  const built = new Date(filing.filing_date)',
        '  const parsed = parseISO(filing.filing_date)',
        "  const wrapped = formatInstant(filing.filing_date, 'MMM d, yyyy')",
        "  const namespaced = fmt.formatInstant(filing.filing_date, 'MMM d, yyyy')",
        "  const renews = formatLocalDate(sub.current_period_end, 'MMM d, yyyy')",
        "  const ends = fmt.formatLocalDate(sub['trial_end'], 'MMM d, yyyy')",
        "  const instant = formatInstant(sub.trial_end, 'MMM d, yyyy')",
        "  const day = formatLocalDate(filing.filing_date, 'MMM d, yyyy')",
        '  const { formatInstant: held } = fmt',
        '  const local = formatLocalDate',
        '  return [built, parsed, wrapped, namespaced, renews, ends, instant, day, formatDay, held, local]',
        '}',
        '',
      ].join('\n'),
      { filePath: path.join(frontendRoot, 'app/calendar-field-probe.ts') },
    )
    const lines = (pattern: RegExp) =>
      result.messages.filter((m) => m.ruleId === 'no-restricted-syntax' && pattern.test(m.message)).map((m) => m.line)
    expect(lines(/calendar-date field/), 'a calendar-date field through a Date constructor').toEqual([6, 7, 8, 9])
    expect(lines(/Stripe billing date/), 'a billing instant through formatLocalDate').toEqual([10, 11])
    expect(lines(/by their own names/), 'a helper under another name').toEqual([4, 14, 15])
    expect(result.messages.filter((m) => m.ruleId === 'no-restricted-syntax').every((m) => m.severity === 2)).toBe(true)
  })
})
