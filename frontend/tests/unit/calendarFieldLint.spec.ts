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
 * UTC day, not the reader's. Each helper is read by its own name and as a namespace member, its key dotted,
 * bracketed or a template (`fmt.formatInstant(…)`, `fmt['formatInstant'](…)`, `new globalThis['Date'](…)`), and
 * going by another name is an error of its own: an import or an export alias (either name quoted or not), a
 * destructuring that renames it (its key in any spelling, with or without a default, Date's from globalThis
 * included), a const that holds it. A field is read in each spelling too (`f.filing_date`, `f['filing_date']`, a
 * template with no substitution); a template with one names no field the lint can be sure of. A genuine instant
 * through formatInstant, a calendar date through formatLocalDate, a destructuring that keeps the name (a default
 * added or not), a nested pattern of a helper's members and an export that keeps the name as a string pass,
 * bracketed or not. Every negated attribute in the rules has its node's type pinned first, so a node that lacks the
 * attribute is not read as a rename. A field key held in a const
 * (`filing[KEY]`) is the residual eslint.config.mjs names, planted as a gap the lint does not see. The rendered day is
 * pinned behaviourally in filing-date-local-day.spec.tsx, TrialBanner.spec.tsx and BillingPanel.spec.tsx; this case
 * pins the lint's reach. Each probe line names what the lint must say of it.
 */
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')

/** Building ESLint from the real config takes 2-3.5s warm and over 7s cold or on a loaded runner; 5s is too tight. */
const SLOW = { timeout: 30_000 }

/** What the lint must say of a line: one of its three messages, nothing (null), or nothing though the line breaks the
    rule, out of the lint's reach as eslint.config.mjs's residual note says ('gap'). */
type Said = 'calendar' | 'billing' | 'alias' | 'gap' | null
const PROBE: Array<[string, Said]> = [
  ["import { parseISO } from 'date-fns'", null],
  ["import * as dateFns from 'date-fns'", null],
  ["import { formatInstant, formatLocalDate } from '@/lib/format'", null],
  ["import * as fmt from '@/lib/format'", null],
  ["import { formatInstant as formatDay } from '@/lib/format'", 'alias'],
  [
    'export function probe(filing: { filing_date: string }, sub: { trial_end: string; current_period_end: string }, row: Record<string, string>, prefix: string, suffix: string) {',
    null,
  ],
  // A calendar-date field through each constructor: by its name, as a member, its key bracketed or a template.
  ['  const built = new Date(filing.filing_date)', 'calendar'],
  ['  const parsed = parseISO(filing.filing_date)', 'calendar'],
  ["  const wrapped = formatInstant(filing.filing_date, 'MMM d, yyyy')", 'calendar'],
  ["  const namespaced = fmt.formatInstant(filing.filing_date, 'MMM d, yyyy')", 'calendar'],
  ["  const bracketed = fmt['formatInstant'](filing.filing_date, 'MMM d, yyyy')", 'calendar'],
  ["  const parsedBracketed = dateFns['parseISO'](filing.filing_date)", 'calendar'],
  ["  const builtBracketed = new globalThis['Date'](filing.filing_date)", 'calendar'],
  ["  const templated = fmt[`formatInstant`](filing.filing_date, 'MMM d, yyyy')", 'calendar'],
  // A field's key in each spelling (the re-review of 8fb22fbe): a template with no substitution names it; one with a
  // substitution names no field the lint can be sure of; a key held in a const is the residual.
  ['  const templatedField = new Date(filing[`filing_date`])', 'calendar'],
  ['  const prefixed = new Date(row[`${prefix}filing_date`])', null],
  ['  const suffixed = new Date(row[`filing_date${suffix}`])', null],
  ["  const FIELD = 'filing_date'", null],
  ['  const heldKey = new Date(row[FIELD])', 'gap'],
  // A billing instant through formatLocalDate, the same ways.
  ["  const renews = formatLocalDate(sub.current_period_end, 'MMM d, yyyy')", 'billing'],
  ["  const ends = fmt.formatLocalDate(sub['trial_end'], 'MMM d, yyyy')", 'billing'],
  ["  const renewsBracketed = fmt['formatLocalDate'](sub.current_period_end, 'MMM d, yyyy')", 'billing'],
  ["  const endsTemplated = fmt[`formatLocalDate`](sub.trial_end, 'MMM d, yyyy')", 'billing'],
  ["  const endsTemplatedField = formatLocalDate(sub[`trial_end`], 'MMM d, yyyy')", 'billing'],
  // Each the right way round passes, bracketed or not.
  ["  const instant = formatInstant(sub.trial_end, 'MMM d, yyyy')", null],
  ["  const day = formatLocalDate(filing.filing_date, 'MMM d, yyyy')", null],
  ["  const instantBracketed = fmt['formatInstant'](sub.trial_end, 'MMM d, yyyy')", null],
  ["  const dayBracketed = fmt['formatLocalDate'](filing.filing_date, 'MMM d, yyyy')", null],
  // A helper under another name: destructured with its key in each spelling, Date's included, or held in a const.
  ['  const { formatInstant: held } = fmt', 'alias'],
  ["  const { ['formatInstant']: heldInstant } = fmt", 'alias'],
  ["  const { ['formatLocalDate']: heldLocal } = fmt", 'alias'],
  ["  const { 'parseISO': heldParse } = dateFns", 'alias'],
  ['  const { Date: HeldDate } = globalThis', 'alias'],
  ["  const { ['Date']: HeldDateComputed } = globalThis", 'alias'],
  ['  const local = formatLocalDate', 'alias'],
  ["  const picked = fmt['formatInstant']", 'alias'],
  ['  const { formatInstant: heldWithDefault = formatLocalDate } = fmt', 'alias'],
  ['  return [built, parsed, wrapped, namespaced, bracketed, parsedBracketed, builtBracketed, templated, templatedField, prefixed,', null],
  ['    suffixed, heldKey, renews, ends, renewsBracketed, endsTemplated, endsTemplatedField, instant, day, instantBracketed,', null],
  ['    dayBracketed, formatDay, held, heldInstant, heldLocal, heldParse, HeldDate, HeldDateComputed, local, picked, heldWithDefault]', null],
  ['}', null],
  // A destructuring that keeps the name renames nothing.
  ['export function ownNames() {', null],
  ['  const { formatInstant } = fmt', null],
  ["  const { ['parseISO']: parseISO } = dateFns", null],
  ['  const { Date } = globalThis', null],
  ['  return [formatInstant, parseISO, Date]', null],
  ['}', null],
  // Keeping the name and adding a default renames nothing (the re-review of 8fb22fbe).
  ['export function ownNamesWithDefaults(fallback: typeof formatInstant) {', null],
  ['  const { formatInstant = fallback } = fmt', null],
  ['  const { Date = globalThis.Date } = globalThis', null],
  ['  return [formatInstant, Date]', null],
  ['}', null],
  // A nested pattern binds no alias of the helper, with a default or not (the re-review of 77b306f6: each negated
  // attribute's node type is pinned first).
  ['export function nestedPatterns() {', null],
  ['  const { formatInstant: { length } = fmt.formatInstant } = fmt', null],
  ['  const { formatLocalDate: [first] = [] } = fmt', null],
  ['  return [length, first]', null],
  ['}', null],
  // An export named by a string keeps the name, or renames it.
  ["export { formatInstant as 'formatInstant' }", null],
  ["export { formatLocalDate as 'heldExport' }", 'alias'],
  ['', null],
]

describe('the calendar-field lint', SLOW, () => {
  it('errors on a calendar-date field through new Date, parseISO and formatInstant, a billing instant through formatLocalDate, and a renamed helper, each key in any spelling, and passes an instant and formatLocalDate', async () => {
    const eslint = new ESLint({ cwd: frontendRoot })
    const [result] = await eslint.lintText(PROBE.map(([code]) => code).join('\n'), {
      filePath: path.join(frontendRoot, 'app/calendar-field-probe.ts'),
    })
    const lines = (pattern: RegExp) =>
      result.messages.filter((m) => m.ruleId === 'no-restricted-syntax' && pattern.test(m.message)).map((m) => m.line)
    const said = (what: Said) => PROBE.flatMap(([, line], index) => (line === what ? [index + 1] : []))
    expect(lines(/calendar-date field/), 'a calendar-date field through a Date constructor').toEqual(said('calendar'))
    expect(lines(/Stripe billing date/), 'a billing instant through formatLocalDate').toEqual(said('billing'))
    expect(lines(/by their own names/), 'a helper under another name').toEqual(said('alias'))
    expect(result.messages.filter((m) => m.ruleId === 'no-restricted-syntax').every((m) => m.severity === 2)).toBe(true)
  })
})
