import next from 'eslint-config-next'

// Flat config (ESLint 9). Replaces the legacy .eslintrc.json:
//   extends ["next/core-web-vitals", "next/typescript"]  ->  ...next
// eslint-config-next's default export already bundles both core-web-vitals
// and the TypeScript config (which registers the @typescript-eslint plugin).
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
    files: [
      '**/*.spec.ts',
      '**/*.spec.tsx',
      '**/*.test.ts',
      '**/*.test.tsx',
      '__tests__/**',
      'tests/**',
      'vitest.setup.ts',
    ],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/ban-ts-comment': 'off',
    },
  },
  // F1 invariant, enforced (not just reviewed): every React Query key is built by
  // the lib/queryKeys.ts registry — never as an inline array literal at a call
  // site — so a key and the code that invalidates it can't drift. This makes the
  // former PR-body grep-gate structural. Two shapes are forbidden: the object form
  // `queryKey: [...]` (useQuery / useQueries / invalidate/cancel/refetch/remove/
  // prefetch/fetch/ensure/setQueriesData all take `{ queryKey }`) and the
  // positional getter/setter `getQueryData([...])` / `setQueryData([...], …)`.
  // Scope mirrors the grep-gate: prod code only — the registry defines the keys,
  // and tests may still poke the cache with raw keys.
  {
    files: ['**/*.ts', '**/*.tsx'],
    ignores: [
      'lib/queryKeys.ts',
      '**/*.spec.ts',
      '**/*.spec.tsx',
      '**/*.test.ts',
      '**/*.test.tsx',
      '__tests__/**',
      'tests/**',
      'vitest.setup.ts',
    ],
    rules: {
      'no-restricted-syntax': [
        'error',
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
      ],
    },
  },
]

export default config
