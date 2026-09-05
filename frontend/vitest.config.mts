import { defineConfig, configDefaults } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'
import { createRequire } from 'node:module'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const sentryBrowserEntry = path.join(
  path.dirname(require.resolve('@sentry/nextjs/package.json')),
  'build/cjs/index.client.js',
)

export default defineConfig({
  plugins: [react()],
  // Feature flags for tests.
  define: {
    'process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS': JSON.stringify('true'),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: path.resolve(__dirname, 'vitest.setup.ts'),
    css: false,
    // ONE test home (tests/unit) + ONE suffix (.spec) after the F3 __tests__ merge.
    include: ['tests/unit/**/*.spec.ts?(x)'],
    exclude: [...configDefaults.exclude, 'tests/e2e/**'],
  },
  resolve: {
    alias: [
      // jsdom exercises the browser SDK. The Node entry loads build-time orchestrion tooling
      // whose import.meta.url is not a file URL under Vitest. Keep production resolution intact
      // and use the real SDK (including capture behavior), not a global test mock.
      { find: /^@sentry\/nextjs$/, replacement: sentryBrowserEntry },
      { find: '@', replacement: path.resolve(__dirname, './') },
    ],
  },
})
