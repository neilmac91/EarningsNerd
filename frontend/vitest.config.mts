import { defineConfig, configDefaults } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

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
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
})


