import next from 'eslint-config-next'
import { RAW_FETCH_ALLOWLIST_FILES } from './eslint.rawFetchAllowlist.mjs'
import gridBaseTrackPlugin from './eslint.gridBaseTrack.mjs'
import designRulesPlugin, { LANDING_GRID_FILES } from './eslint.designRules.mjs'

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
  '(A genuine timestamp, such as created_at or Stripe\'s trial_end, goes through formatInstant from ' +
  'lib/format.ts, which renders the day it falls on in the viewer\'s zone.)'
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
 *  (`const { filing_date: fd } = filing; new Date(fd)`), or a key held in a const (`filing[KEY]`),
 *  defeats any selector, because tracking that rename is data-flow analysis and ESLint selectors are
 *  syntactic. No further widening fixes it. The
 *  same holds for a same-file wrapper (`const day = (iso) => formatLocalDate(iso, …)`, as FilingIndex
 *  and ComparePeriodsCard write): the rules read the call inside it, not the field a caller hands it.
 *  A helper reached through something other than its name or a written member key (held in a binding
 *  under another name, a branch of a condition or a logical operand, handed on as an argument, returned,
 *  held in an object, behind a cast, called through call, apply or bind, or taken off a date module's
 *  namespace or the global object by a key held in a name: `fmt[key]`) is refused where it stands, by
 *  earningsnerd/date-helpers-called-directly (eslint.designRules.mjs), so a call the rules cannot read
 *  never ships. A helper's key is never resolved: its member fails closed (chief design). A FIELD's key
 *  held in a const stays the residual above. The behavioural spec and review cover what this cannot; do
 *  not read the rule as exhaustive. */
const CALENDAR_DATE_FIELDS =
  'filing_date|filed_date|period_end_date|earnings_date|event_date|transaction_date|last_transaction_date|report_date'
const CALENDAR_FIELD_MESSAGE =
  'Do not build a Date from an API calendar-date field, directly or through formatInstant — it is a ' +
  'UTC-midnight instant, so any later render shows the previous day for viewers behind UTC. Pass the ' +
  'raw string to formatLocalDate from lib/format.ts instead. (Comparing two of them as instants is fine; ' +
  'features/filings/lib/recommendedFiling.ts is allow-listed for exactly that.)'
/** Four access shapes, because one selector cannot see all of them (fieldSelectors):
 *   - `f.filing_date`      -> the property is an Identifier
 *   - `f['filing_date']`   -> computed, so the name lives on Literal.value, not Identifier.name
 *   - f[`filing_date`]     -> a template with no substitution, so the name lives on its TemplateElement's
 *                             cooked value (a template with one names no field the rule can be sure of)
 *   - `const { filing_date } = f` then `new Date(filing_date)` -> a bare Identifier, no member at all
 *  The Identifier selector covers the first and fourth together.
 *  formatInstant (lib/format.ts) is a constructor here too: it runs parseISO inside the helper, where
 *  no selector at the call site sees it, so `formatInstant(filing.filing_date, …)` would render the
 *  previous day behind UTC while passing every rule above. Its gate is this list.
 *  Each constructor is read by its own name and as a namespace member, its key in each spelling
 *  (KEY_NAME_PATHS: `fmt.formatInstant(…)`, `fmt['formatInstant'](…)`, `new globalThis['Date'](…)`);
 *  DATE_HELPER_RULES, below, keeps it from going by another name. */
/** Where a member's or a key's name lives, in each spelling: `fmt.formatInstant` (Identifier.name),
 *  `fmt['formatInstant']` (computed: Literal.value) and fmt[`formatInstant`] (a template's text). */
const KEY_NAME_PATHS = ['name', 'value', 'quasis.0.value.cooked']
const callsTo = (name) => {
  const call = name === 'Date' ? 'NewExpression' : 'CallExpression'
  return [`${call}[callee.name='${name}']`, ...KEY_NAME_PATHS.map((at) => `${call}[callee.property.${at}='${name}']`)]
}
/** A field named anywhere inside a constructor's call, in each access shape above. */
const fieldSelectors = (root, fields, message) => [
  { selector: `${root} Identifier[name=/^(${fields})$/]`, message },
  { selector: `${root} Literal[value=/^(${fields})$/]`, message },
  { selector: `${root} TemplateLiteral[expressions.length=0] > TemplateElement[value.cooked=/^(${fields})$/]`, message },
]
const CALENDAR_FIELD_RULES = ['Date', 'parseISO', 'formatInstant']
  .flatMap(callsTo)
  .flatMap((root) => fieldSelectors(root, CALENDAR_DATE_FIELDS, CALENDAR_FIELD_MESSAGE))

/** The other direction (D-033): a Stripe billing date is an INSTANT with its offset, so the day it
 *  falls on depends on where the reader is. formatLocalDate reads only its first ten characters, the
 *  UTC day, which is the wrong day for part of every day anywhere but UTC: the defect BillingPanel
 *  shipped (`formatLocalDate(sub.current_period_end, …)`) before formatInstant. Every lint block reads
 *  these, the calendar-sort allow-list's included, since sorting dates gives no reason for either. */
const BILLING_INSTANT_FIELDS = 'trial_end|current_period_end'
const BILLING_INSTANT_MESSAGE =
  'Do not pass a Stripe billing date (trial_end, current_period_end) to formatLocalDate: it is an instant, ' +
  'and formatLocalDate names its UTC day, not the day it falls on where the reader is. Use formatInstant ' +
  'from lib/format.ts (D-033).'
/** The rules read a constructor by its callee's name, so it must keep that name: an import under
 *  another name (`formatInstant as formatDay`), a re-export or a destructuring that renames it (its key
 *  in any spelling, with or without a default, `{ ['formatInstant']: held }`, and Date's from globalThis
 *  among them) would hide every call from them. A destructuring that keeps the name and adds a default
 *  (`{ formatInstant = fallback }`) renames nothing: its calls keep the name. Date's destructured renames
 *  are keyed to no holder, so a data row's key named Date taken out by a pattern (`const { Date: first } =
 *  rows[0]`) draws the message too: a false positive no live code meets, planted in
 *  tests/unit/calendarFieldLint.spec.ts. A helper held as a value, in a const or anywhere else, is
 *  earningsnerd/date-helpers-called-directly's, which reads DATE_HELPERS and DATE_HELPER_MODULES as its
 *  options, and so is a namespace of a date module used other than through a member with a written key. */
const DATE_HELPERS = ['Date', 'parseISO', 'formatInstant', 'formatLocalDate']
/** The modules a date helper comes from, as an import names them: date-fns's barrels and parseISO's own
 *  entry in each (the package's exports map opens no other path to it), and lib/format by its `@/` alias
 *  (the rule reads a path relative to the importing file as the same module). A namespace of each is read
 *  only through members with a written key. A helper from another module means adding that module here. */
const DATE_HELPER_MODULES = ['date-fns', 'date-fns/fp', 'date-fns/parseISO', 'date-fns/fp/parseISO', '@/lib/format']
const DATE_HELPER_ALIAS_MESSAGE =
  'Call Date, parseISO, formatInstant and formatLocalDate by their own names: the calendar-date and ' +
  'billing-instant rules (eslint.config.mjs) read a call by its callee, so a renamed one hides it.'
const DATE_HELPER_RULES = [
  ...callsTo('formatLocalDate').flatMap((root) => fieldSelectors(root, BILLING_INSTANT_FIELDS, BILLING_INSTANT_MESSAGE)),
  // An import or a re-export under another name, either name quoted or not (Date, a global, travels by neither). Each
  // negated attribute has its node's type pinned first: a negation holds for every node that lacks the attribute, so an
  // export named by a string (`export { formatInstant as 'formatInstant' }`) would otherwise read as a rename.
  ...DATE_HELPERS.filter((name) => name !== 'Date').flatMap((name) => [
    ...['name', 'value'].map((at) => ({
      selector: `ImportSpecifier[imported.${at}='${name}'][local.type='Identifier'][local.name!='${name}']`,
      message: DATE_HELPER_ALIAS_MESSAGE,
    })),
    ...['name', 'value'].flatMap((at) => [
      {
        selector: `ExportSpecifier[local.${at}='${name}'][exported.type='Identifier'][exported.name!='${name}']`,
        message: DATE_HELPER_ALIAS_MESSAGE,
      },
      {
        selector: `ExportSpecifier[local.${at}='${name}'][exported.type='Literal'][exported.value!='${name}']`,
        message: DATE_HELPER_ALIAS_MESSAGE,
      },
    ]),
  ]),
  // A destructuring that renames it, its key in each spelling, with or without a default: `{ formatInstant: held }`,
  // `{ ['formatInstant']: held }`, `{ formatInstant: held = fallback }`, `const { Date: D } = globalThis`. A nested
  // pattern (`{ formatInstant: { length } = … }`) binds no alias of the helper, so the value's type is pinned first.
  ...DATE_HELPERS.flatMap((name) =>
    KEY_NAME_PATHS.flatMap((at) => [
      {
        selector: `ObjectPattern > Property[key.${at}='${name}'][value.type='Identifier'][value.name!='${name}']`,
        message: DATE_HELPER_ALIAS_MESSAGE,
      },
      {
        selector: `ObjectPattern > Property[key.${at}='${name}'][value.type='AssignmentPattern'][value.left.type='Identifier'][value.left.name!='${name}']`,
        message: DATE_HELPER_ALIAS_MESSAGE,
      },
    ]),
  ),
]

// MIGRATION-v3 §c — design-token guardrails (CLAUDE.md rule 12: a "never do X again" rule lands as
// a machine gate in the same PR as the sweep). Tokens only: no raw hex, no raw palette classes, no
// arbitrary z / radius / duration / sub-scale text, no off-ramp tracking, no window.alert.
// Exemptions, each pinned to its own block below:
//   - the sanctioned JS color mirrors (lib/motion.ts, lib/financialTone.ts, ui/Chart.tsx,
//     features/analysis/lib/chartExport.ts) and the brand-mandated GoogleSignInButton skip the two
//     color rules (tests/unit/designTokenParity.spec.ts checks the mirrors use only token hexes);
//   - app/manifest.ts + app/layout.tsx declare the OS-facing theme colors (PWA manifest, <meta
//     theme-color>), which have no Tailwind form, so they skip the hex rule only (the parity spec
//     checks those hexes too) — added beyond §c's list, recorded in the PR;
//   - components/ui/DataTable.tsx keeps its internal z-[5] sticky-cell layering (the one z exemption).
// Every class-string rule also runs on template-literal chunks (withTemplates), so a className built
// with `${…}` is held to the same rules. A class name assembled from fragments at runtime is not.
// aria-hidden glyphs below the type scale (Badge ▲▼, DataTable ▲▼) and the 40px pricing display
// figure (its own tracking-[…]) carry an eslint-disable with a reason.
// The raw-colour rule reads a 6-digit hex (8-digit included) and an rgb(), rgba(), hsl() or hsla()
// call in either case (`RGB(` is the same colour to a browser), in a string, a template chunk or an
// arbitrary utility (`shadow-[0_20px_50px_rgba(…)]`), since each is a colour no token governs (BG-19).
// A 3- or 4-digit hex is read only where it can be nothing but a colour: inside an arbitrary utility or
// property, at its start or after a colon, an underscore, a parenthesis or a comma (`bg-[#fff]`,
// `[color:#fff]`, `shadow-[0_0_0_1px_#abc]`), or as the whole literal (`'#000a'`); inside copy
// ("PR #619") it is not. The mirrors above keep their exemption.
const DESIGN_HEX_RULE = {
  selector: 'Literal[value=/#[0-9a-f]{6}|(?:rgba?|hsla?)\\(|\\[(?:[^\\]\\s]*[:_(,])?#[0-9a-f]{3,4}(?![0-9a-f])[^\\]\\s]*\\]|^#[0-9a-f]{3,4}$/i]',
  message: 'Raw colour (hex, rgb[a]() or hsl[a]()): use a token (mirrors: motion.ts, financialTone, Chart, chartExport).',
}
const DESIGN_PALETTE_RULE = {
  selector:
    'Literal[value=/\\b(bg|text|border|ring|from|to)-(slate|gray|zinc|neutral|stone|blue|green|red|amber|emerald|teal|sky|mint)-[0-9]/]',
  message: 'Raw palette class — semantic tokens only.',
}
const DESIGN_Z_RULE = {
  selector: 'Literal[value=/\\bz-\\[/]',
  message: 'Arbitrary z — use the zIndex ladder (sticky/header/overlay/modal/toast).',
}
const DESIGN_SHARED_RULES = [
  { selector: 'Literal[value=/\\bduration-[0-9]/]', message: 'Raw duration — duration-fast|base|slow|ambient.' },
  {
    selector: 'Literal[value=/\\btracking-((wide|wider|widest|tight|tighter)\\b|\\[)/]',
    message: 'Off-ramp tracking — tracking-eyebrow for labels; the fontSize ramp tracks headings.',
  },
  {
    selector: 'Literal[value=/\\btext-\\[(?:[0-9]|1[0-3])(?:\\.5)?px\\]/]',
    message: 'Below-scale type — data-xs(11)/xs(12)/sm(14). Glyphs: eslint-disable with a reason.',
  },
  { selector: 'Literal[value=/\\brounded-\\[/]', message: 'Off-scale radius — 4/8/12/16/24.' },
  { selector: "CallExpression[callee.name='alert']", message: 'window.alert — render a Notice or toast.' },
  {
    selector: "CallExpression[callee.type='MemberExpression'][callee.property.name='alert']",
    message: 'window.alert — render a Notice or toast.',
  },
]
/** Each class-string rule gets a twin on template-literal chunks (`… ${x} …` is not a Literal). */
const withTemplates = (rules) =>
  rules.flatMap((rule) =>
    rule.selector.startsWith('Literal[value=')
      ? [rule, { ...rule, selector: rule.selector.replace('Literal[value=', 'TemplateElement[value.raw=') }]
      : [rule],
  )
const DESIGN_RULES = withTemplates([DESIGN_HEX_RULE, DESIGN_PALETTE_RULE, DESIGN_Z_RULE, ...DESIGN_SHARED_RULES])
const DESIGN_COLOR_EXEMPT = [
  'lib/motion.ts',
  'lib/financialTone.ts',
  'components/ui/Chart.tsx',
  'features/analysis/lib/chartExport.ts',
  'features/auth/components/GoogleSignInButton.tsx',
]
const DESIGN_HEX_EXEMPT = ['app/manifest.ts', 'app/layout.tsx']
const DESIGN_Z_EXEMPT = ['components/ui/DataTable.tsx']

/** The repository's own rules as one object: two config blocks name it, and flat config refuses a plugin redefined. */
const EARNINGSNERD_PLUGIN = { rules: { ...gridBaseTrackPlugin.rules, ...designRulesPlugin.rules } }

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
    ignores: [
      ...TEST_FILES,
      'lib/queryKeys.ts',
      ...RAW_FETCH_ALLOWLIST,
      ...CALENDAR_SORT_ALLOWLIST,
      ...DESIGN_COLOR_EXEMPT,
      ...DESIGN_Z_EXEMPT,
    ],
    rules: {
      'no-restricted-syntax': [
        'error',
        ...QUERY_KEY_RULES,
        ...RAW_FETCH_RULES,
        ...DATE_RULES,
        ...CALENDAR_FIELD_RULES,
        ...DATE_HELPER_RULES,
        ...DESIGN_RULES,
      ],
    },
  },
  // Every grid that sets its columns under a variant also sets its base track
  // (lessons/frontend-variable-text-must-not-size-a-wrapping-row.md). A custom rule, not a selector:
  // it evaluates a whole class string (the text that always renders together, each conditional
  // branch with that text only) and parses variant prefixes. It is its own rule, so it covers the
  // design-exempt files too. The 2026-10 critique's gates ride the same plugin and the same class-
  // string walker (eslint.designRules.mjs): no side-tab stripe on a rounded container (P-08), no
  // form code inside a Badge (P-04), no animation utility that keeps moving under reduced motion
  // (P-09), and no hand-rolled single-choice toggle group outside the SegmentedControl (CO-15).
  // direction-text-tokens holds direction text to the 700-level gain/loss inks, never the 600
  // level or sage (D-030). elements-built-with-jsx refuses React's element factories, so every
  // element the app renders is JSX the gates that read elements can see. date-helpers-called-directly
  // refuses a date helper held as a value, and a namespace or object that holds one read other than by a
  // written key, so every call the date rules above read is written by name or by a written key.
  {
    files: ['**/*.ts', '**/*.tsx'],
    ignores: TEST_FILES,
    plugins: { earningsnerd: EARNINGSNERD_PLUGIN },
    rules: {
      'earningsnerd/responsive-grid-base-track': 'error',
      'earningsnerd/direction-text-tokens': 'error',
      'earningsnerd/no-side-stripe': 'error',
      'earningsnerd/no-form-code-badge': 'error',
      'earningsnerd/no-unguarded-animation': 'error',
      'earningsnerd/locale-pinned-numbers': 'error',
      'earningsnerd/no-hand-rolled-toggle-group': 'error',
      'earningsnerd/elements-built-with-jsx': 'error',
      'earningsnerd/date-helpers-called-directly': ['error', { helpers: DATE_HELPERS, modules: DATE_HELPER_MODULES }],
      'earningsnerd/surface-padding-cap': 'error',
    },
  },
  // The password scan parses every script it finds (passwordRulesLockstep.spec.tsx), JavaScript included, so the rule
  // that leaves an element built by a factory to lint reads JavaScript too. The other design rules read TypeScript.
  {
    files: ['**/*.js', '**/*.jsx', '**/*.mjs', '**/*.cjs', '**/*.mts', '**/*.cts'],
    ignores: TEST_FILES,
    plugins: { earningsnerd: EARNINGSNERD_PLUGIN },
    rules: { 'earningsnerd/elements-built-with-jsx': 'error' },
  },
  // D-045: the landing page lays nothing out four across (no-four-up-grid, the same plugin and class-string walker).
  // It reads the landing's own composition, LANDING_GRID_FILES (the route, the marketing modules and the sections the
  // route mounts from other features, held to the route's imports by tests/unit/landing-sections-mounted.spec.ts);
  // the product screens the landing demos keep their own layouts.
  {
    files: LANDING_GRID_FILES,
    ignores: TEST_FILES,
    rules: {
      'earningsnerd/no-four-up-grid': 'error',
    },
  },
  // The JS color mirrors + the brand-mandated GoogleSignInButton: every gate except the two color rules.
  {
    files: DESIGN_COLOR_EXEMPT,
    rules: {
      'no-restricted-syntax': [
        'error',
        ...QUERY_KEY_RULES,
        ...RAW_FETCH_RULES,
        ...DATE_RULES,
        ...CALENDAR_FIELD_RULES,
        ...DATE_HELPER_RULES,
        ...withTemplates([DESIGN_Z_RULE, ...DESIGN_SHARED_RULES]),
      ],
    },
  },
  // OS-facing theme colors (PWA manifest, <meta theme-color>): every gate except the hex rule.
  {
    files: DESIGN_HEX_EXEMPT,
    rules: {
      'no-restricted-syntax': [
        'error',
        ...QUERY_KEY_RULES,
        ...RAW_FETCH_RULES,
        ...DATE_RULES,
        ...CALENDAR_FIELD_RULES,
        ...DATE_HELPER_RULES,
        ...withTemplates([DESIGN_PALETTE_RULE, DESIGN_Z_RULE, ...DESIGN_SHARED_RULES]),
      ],
    },
  },
  // DataTable's internal sticky-cell z-[5]: every gate except the z rule.
  {
    files: DESIGN_Z_EXEMPT,
    rules: {
      'no-restricted-syntax': [
        'error',
        ...QUERY_KEY_RULES,
        ...RAW_FETCH_RULES,
        ...DATE_RULES,
        ...CALENDAR_FIELD_RULES,
        ...DATE_HELPER_RULES,
        ...withTemplates([DESIGN_HEX_RULE, DESIGN_PALETTE_RULE, ...DESIGN_SHARED_RULES]),
      ],
    },
  },
  // Sorting compares two filing dates AS INSTANTS and never renders them, which is the one correct
  // reason to build a Date from a calendar-date field. Every other gate still applies here.
  {
    files: CALENDAR_SORT_ALLOWLIST,
    rules: { 'no-restricted-syntax': ['error', ...QUERY_KEY_RULES, ...RAW_FETCH_RULES, ...DATE_RULES, ...DATE_HELPER_RULES, ...DESIGN_RULES] },
  },
  // The query-key registry defines keys as literals, so only the fetch gate applies to it.
  {
    files: ['lib/queryKeys.ts'],
    rules: { 'no-restricted-syntax': ['error', ...RAW_FETCH_RULES, ...DATE_RULES, ...CALENDAR_FIELD_RULES, ...DATE_HELPER_RULES, ...DESIGN_RULES] },
  },
  // The sanctioned raw-fetch sites still get the query-key gate.
  {
    files: RAW_FETCH_ALLOWLIST,
    rules: { 'no-restricted-syntax': ['error', ...QUERY_KEY_RULES, ...DATE_RULES, ...CALENDAR_FIELD_RULES, ...DATE_HELPER_RULES, ...DESIGN_RULES] },
  },
]

export default config
