import { defineConfig, configDefaults } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  // Set feature flags for tests - tests expect tabbed UI to be available
  define: {
    'process.env.NEXT_PUBLIC_ENABLE_SECTION_TABS': JSON.stringify('true'),
    'process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_CHARTS': JSON.stringify('true'),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: path.resolve(__dirname, 'vitest.setup.ts'),
    css: false,
    include: [
      '__tests__/**/*.test.ts?(x)',
      '__tests__/**/*.spec.ts?(x)',
      'tests/unit/**/*.test.ts?(x)',
      'tests/unit/**/*.spec.ts?(x)',
    ],
    exclude: [...configDefaults.exclude, 'tests/e2e/**'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
    },
  },
})


