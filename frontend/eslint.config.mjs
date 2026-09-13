import next from 'eslint-config-next'
import { RAW_FETCH_ALLOWLIST_FILES } from './eslint.rawFetchAllowlist.mjs'

// Flat config (ESLint 9). Replaces the legacy .eslintrc.json:
//   extends ["next/core-web-vitals", "next/typescript"]  ->  ...next
// eslint-config-next's default export already bundles both core-web-vitals
// and the TypeScript config (which registers the @typescript-eslint plugin).

const TEST_FILES = ['**/*.spec.ts', '**/*.spec.tsx', 'tests/**', 'vitest.setup.ts']

// F1 invariant, enforced (not just reviewed): every React Query key is built by
// the lib/queryKeys.ts registry — never as an inline array literal at a call
// site — so a key and the code that invalidates it can't drift. This makes the
// former PR-body grep-gate structural. Two shapes are forbidden: the object form
// `queryKey: [...]` (useQuery / useQueries / invalidate/cancel/refetch/remove/
// prefetch/fetch/ensure/setQueriesData all take `{ queryKey }`) and the
// positional getter/setter `getQueryData([...])` / `setQueryData([...], …)`.
const QUERY_KEY_RULES = [
  {
    selector: "Property[key.name='queryKey'] ArrayExpression",
    message:
      'Query keys must come from lib/queryKeys.ts — call a queryKeys.* factory instead of an inline array literal (F1 invariant).',
  },
  {
    selector: "CallExpression[callee.property.name='getQueryData'] > ArrayExpression",
    message:
      'Query keys must come from lib/queryKeys.ts — pass a queryKeys.* factory to getQueryData, not an inline array literal (F1 invariant).',
  },
  {
    selector: "CallExpression[callee.property.name='setQueryData'] > ArrayExpression",
    message:
      'Query keys must come from lib/queryKeys.ts — pass a queryKeys.* factory to setQueryData, not an inline array literal (F1 invariant).',
  },
]

// CLAUDE.md "Where things live": ALL HTTP goes through the shared axios client
// (lib/api/client.ts — cookies, refresh, error normalisation, base URL). Raw
// `fetch(` is sanctioned ONLY for the SSE stream readers (axios can't stream a
// POST body) and Next's server/ISR fetches (which need `next: { revalidate }`).
// The sanctioned files live in eslint.rawFetchAllowlist.mjs (one source of
// truth, shared with tests/unit/rawFetchAllowlist.spec.ts, which pins each
// file's call count and keeps the list shrink-only); adding one is a reviewed
// decision, not a disable comment. Rule-12 gate for "never raw fetch again".
const RAW_FETCH_ALLOWLIST = RAW_FETCH_ALLOWLIST_FILES
const CALENDAR_SORT_ALLOWLIST = ['features/filings/lib/recommendedFiling.ts']
const RAW_FETCH_MESSAGE =
  'Raw fetch() is forbidden — route HTTP through the shared axios client (lib/api/client.ts). ' +
  'SSE readers and Next server/ISR fetches are the only exceptions, allow-listed in eslint.rawFetchAllowlist.mjs.'
const RAW_FETCH_RULES = [
  { selector: "CallExpression[callee.name='fetch']", message: RAW_FETCH_MESSAGE },
  {
    // window.fetch(...) / globalThis.fetch(...) / self.fetch(...)
    selector: "CallExpression[callee.type='MemberExpression'][callee.property.name='fetch']",
    message: RAW_FETCH_MESSAGE,
  },
]

// CLAUDE.md/lessons: a calendar date from the API (filing_date, period_end_date, earnings_date) is
// serialised as a UTC-midnight INSTANT ('2025-08-05T00:00:00+00:00'), so building a Date from it and
// formatting it renders the PREVIOUS day for every viewer behind UTC — which is every US user.
// lib/format.ts::formatLocalDate exists precisely for this and its docblock says so, yet the rule had
// rotted at six sites. CI cannot catch it by accident: CI runs in UTC, where the bug is invisible.
//
// SCOPE: the shape selectors below catch the mechanical forms that actually occurred. They cannot
// see the INDIRECT form (`const d = new Date(x)` on one line, `format(d, …)` on the next), which is
// the shape that recreates the production defect while a gate reports success — so
// CALENDAR_FIELD_RULES closes it from the other end, by forbidding construction of a Date (or a
// parseISO) from a known calendar-date field at all, however the result is later used. The
// load-bearing gate is the behavioural one, tests/unit/filing-date-local-day.spec.tsx, which pins the
// rendered output with TZ set to a US zone. Do not read this lint rule as more than it is.
const LOCAL_DATE_MESSAGE =
  'Do not format a Date built from an API value — an API calendar date is a UTC-midnight instant, so ' +
  'this renders the previous day for viewers behind UTC. Use formatLocalDate from lib/format.ts. ' +
  '(A genuine timestamp — created_at, updated_at — should be assigned to a variable first, which ' +
  'documents that the local-time render is intended.)'
/** The API's calendar-date fields. Each is a UTC-midnight instant on the wire, so constructing a
 *  Date from one is the root of the whole defect class — banning the construction catches the
 *  indirect form that no shape-based selector can see. Adding a new calendar-date field to the API
 *  means adding it here.
 *
 *  Descendant match, not a direct child: `new Date(filing.filing_date as string)` wraps the member
 *  in a TSAsExpression, and a parenthesised expression or a `?? ''` fallback wraps it too, so `>`
 *  silently missed exactly the shape this rule exists to catch. Measured, not assumed.
 *
 *  KNOWN RESIDUAL, and it is a property of the tool rather than a gap to patch: a RENAMED binding
 *  (`const { filing_date: fd } = filing; new Date(fd)`) defeats any selector, because tracking that
 *  rename is data-flow analysis and ESLint selectors are syntactic. No further widening fixes it.
 *  The behavioural spec and review cover what this cannot; do not read the rule as exhaustive. */
const CALENDAR_DATE_FIELDS =
  'filing_date|filed_date|period_end_date|earnings_date|event_date|transaction_date|last_transaction_date|report_date'
const CALENDAR_FIELD_MESSAGE =
  'Do not build a Date from an API calendar-date field — it is a UTC-midnight instant, so any ' +
  'later render shows the previous day for viewers behind UTC. Pass the raw string to ' +
  'formatLocalDate from lib/format.ts instead. (Comparing two of them as instants is fine; ' +
  'features/filings/lib/recommendedFiling.ts is allow-listed for exactly that.)'
/** Three access shapes, because one selector cannot see all of them:
 *   - `f.filing_date`      -> the property is an Identifier
 *   - `f['filing_date']`   -> computed, so the name lives on Literal.value, not Identifier.name
 *   - `const { filing_date } = f` then `new Date(filing_date)` -> a bare Identifier, no member at all
 *  The Identifier selector covers the first and third together. */
const CALENDAR_FIELD_RULES = ['Date', 'parseISO'].flatMap((ctor) => {
  const root = ctor === 'Date' ? `NewExpression[callee.name='Date']` : `CallExpression[callee.name='parseISO']`
  return [
    { selector: `${root} Identifier[name=/^(${CALENDAR_DATE_FIELDS})$/]`, message: CALENDAR_FIELD_MESSAGE },
    { selector: `${root} Literal[value=/^(${CALENDAR_DATE_FIELDS})$/]`, message: CALENDAR_FIELD_MESSAGE },
  ]
})

const DATE_RULES = [
  {
    // format(new Date(x), …). `new Date()` with no argument (meaning "now") is deliberately allowed.
    selector: "CallExpression[callee.name='format'] > NewExpression[callee.name='Date'][arguments.length=1]",
    message: LOCAL_DATE_MESSAGE,
  },
  {
    // format(parseISO(x), …). parseISO honours an offset, so it returns the UTC instant for a full
    // ISO datetime — the exact shape FilingsHistoryNote shipped. The indirect form
    // (const d = parseISO(x)) is still not caught; features/marketing/HeroExample.tsx uses that
    // form deliberately after slicing to a date-only string, which is safe.
    selector: "CallExpression[callee.name='format'] > CallExpression[callee.name='parseISO']",
    message: LOCAL_DATE_MESSAGE,
  },
  {
    selector: "MemberExpression[property.name='toLocaleDateString']",
    message:
      'toLocaleDateString renders in the viewer timezone, so an API calendar date shows the previous ' +
      'day for viewers behind UTC. Use formatLocalDate from lib/format.ts.',
  },
]

const config = [
  // Global ignores. Flat config does NOT skip dot-dirs like eslintrc did, so
  // the generated build output must be ignored explicitly or eslint lints it.
  {
    ignores: [
      '.next/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      'next-env.d.ts',
      // The Claude Design export (its own runtime + bundle), a spec reference, not app code.
      'design/**',
    ],
  },
  ...next,
  // Tests lean on `any` and ts-expect-error pragmas for fixtures/mocks; keep
  // the same relaxations the legacy override had.
  {
    files: TEST_FILES,
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/ban-ts-comment': 'off',
    },
  },
  // Structural invariants for prod code (tests excluded — they may poke the cache with raw keys
  // and stub `fetch`). Both invariants are `no-restricted-syntax` selectors, so they MUST be
  // declared in ONE rule config per file set: flat config REPLACES a rule's options on override
  // (it does not merge), so a second `no-restricted-syntax` block would silently switch the first
  // one off. The allow-listed files therefore get their own block re-declaring only the rules that
  // still apply to them.
  {
    files: ['**/*.ts', '**/*.tsx'],
    ignores: [...TEST_FILES, 'lib/queryKeys.ts', ...RAW_FETCH_ALLOWLIST, ...CALENDAR_SORT_ALLOWLIST],
    rules: {
      'no-restricted-syntax': [
        'error',
        ...QUERY_KEY_RULES,
        ...RAW_FETCH_RULES,
        ...DATE_RULES,
        ...CALENDAR_FIELD_RULES,
      ],
    },
  },
  // Sorting compares two filing dates AS INSTANTS and never renders them, which is the one correct
  // reason to build a Date from a calendar-date field. Every other gate still applies here.
  {
    files: CALENDAR_SORT_ALLOWLIST,
    rules: { 'no-restricted-syntax': ['error', ...QUERY_KEY_RULES, ...RAW_FETCH_RULES, ...DATE_RULES] },
  },
  // The query-key registry defines keys as literals, so only the fetch gate applies to it.
  {
    files: ['lib/queryKeys.ts'],
    rules: { 'no-restricted-syntax': ['error', ...RAW_FETCH_RULES, ...DATE_RULES, ...CALENDAR_FIELD_RULES] },
  },
  // The sanctioned raw-fetch sites still get the query-key gate.
  {
    files: RAW_FETCH_ALLOWLIST,
    rules: { 'no-restricted-syntax': ['error', ...QUERY_KEY_RULES, ...DATE_RULES, ...CALENDAR_FIELD_RULES] },
  },
]

export default config
