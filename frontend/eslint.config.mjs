import next from 'eslint-config-next'

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
// Those sites are enumerated here; adding one is a reviewed decision, not a
// disable comment. Rule-12 gate for the audit's "never raw fetch again".
const RAW_FETCH_ALLOWLIST = [
  'app/sitemap.ts',
  'lib/serverApi.ts',
  'features/summaries/api/summaries-api.ts',
  'features/filings/api/copilot-api.ts',
  'features/analysis/api/analysis-api.ts',
]
const RAW_FETCH_MESSAGE =
  'Raw fetch() is forbidden — route HTTP through the shared axios client (lib/api/client.ts). ' +
  'SSE readers and Next server/ISR fetches are the only exceptions, allow-listed in eslint.config.mjs (RAW_FETCH_ALLOWLIST).'
const RAW_FETCH_RULES = [
  { selector: "CallExpression[callee.name='fetch']", message: RAW_FETCH_MESSAGE },
  {
    // window.fetch(...) / globalThis.fetch(...) / self.fetch(...)
    selector: "CallExpression[callee.type='MemberExpression'][callee.property.name='fetch']",
    message: RAW_FETCH_MESSAGE,
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
    ignores: [...TEST_FILES, 'lib/queryKeys.ts', ...RAW_FETCH_ALLOWLIST],
    rules: { 'no-restricted-syntax': ['error', ...QUERY_KEY_RULES, ...RAW_FETCH_RULES] },
  },
  // The query-key registry defines keys as literals, so only the fetch gate applies to it.
  {
    files: ['lib/queryKeys.ts'],
    rules: { 'no-restricted-syntax': ['error', ...RAW_FETCH_RULES] },
  },
  // The sanctioned raw-fetch sites still get the query-key gate.
  {
    files: RAW_FETCH_ALLOWLIST,
    rules: { 'no-restricted-syntax': ['error', ...QUERY_KEY_RULES] },
  },
]

export default config
