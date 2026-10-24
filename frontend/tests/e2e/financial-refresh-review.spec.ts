import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

// Match the local build/dev flag; WAITLIST_MODE=false lets the request reach the lab.
const enabled = process.env.NEXT_PUBLIC_ENABLE_FINANCIAL_REFRESH_REVIEW === 'true'
const route = '/labs/financial-refresh-review'

test('financial refresh review is hidden by default', async ({ page }) => {
  test.skip(enabled, 'Run against a server built with the flag unset.')
  const response = await page.goto(route)
  expect(response?.status()).toBe(404)
  await expect(page.getByRole('heading', { name: 'Financial refresh review' })).toHaveCount(0)
})

for (const theme of ['light', 'dark'] as const) {
  for (const width of [390, 1440]) {
    test(`financial refresh decisions and exports: ${theme} ${width}px`, async ({ page, baseURL }, testInfo) => {
      test.skip(!enabled, 'Enable the flag in the local server and test process.')
      await page.setViewportSize({ width, height: 1000 })
      await page.addInitScript((mode) => {
        localStorage.setItem('theme', mode)
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-23T00:00:00Z' }))
      }, theme)
      await page.route('**/*', async (request) => {
        const url = new URL(request.request().url())
        if (url.pathname.startsWith('/api/')) {
          await request.fulfill({
            status: request.request().method() === 'OPTIONS' ? 204 : 200,
            headers: { 'access-control-allow-origin': new URL(baseURL!).origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,OPTIONS' },
            json: url.pathname.endsWith('/auth/signup-config') ? { registration_enabled: false } : {},
          })
        } else if (url.origin === new URL(baseURL!).origin && ['GET', 'HEAD'].includes(request.request().method())) {
          await request.continue()
        } else {
          await request.abort()
        }
      })
      await page.goto(route)
      await expect(page.getByRole('heading', { name: 'Financial refresh review' })).toBeVisible()
      await expect(page.getByText(/Harbor Components is fictional/)).toBeVisible()
      await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/)
      await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
      const accept = page.getByRole('button', { name: 'Accept value for Revenue' })
      await accept.focus()
      await accept.press('Enter')
      await expect(accept).toBeFocused()
      await expect(accept).toHaveAttribute('aria-pressed', 'true')
      await page.getByRole('button', { name: 'Keep baseline for Cash' }).click()
      const csvPromise = page.waitForEvent('download')
      await page.getByRole('button', { name: 'Export current values CSV' }).click()
      const csv = await csvPromise
      expect(csv.suggestedFilename()).toBe('fictional-financial-values.csv')
      const csvText = await readFile((await csv.path())!, 'utf8')
      expect(csvText).toContain('"123000000","SAMPLE-2025-ANNUAL"')
      expect(csvText).toContain('"19000000","SAMPLE-2024-ANNUAL","2025-02-10","keep","missing"')
      await page.getByRole('button', { name: 'Include new periods' }).click()
      await expect(page.getByText('0 accepted · 0 kept · 6 unresolved')).toBeVisible()
      await page.getByRole('button', { name: 'Add period for Net income' }).click()
      const receiptPromise = page.waitForEvent('download')
      await page.getByRole('button', { name: 'Export decision receipt JSON' }).click()
      const receipt = JSON.parse(await readFile((await (await receiptPromise).path())!, 'utf8'))
      expect(receipt.sampleData).toBe(true)
      const addition = receipt.rows.find((row: { id: string }) => row.id === 'net-income')
      expect(addition.values.map((fact: { periodEnd: string }) => fact.periodEnd)).toEqual(['2024-12-31', '2025-12-31'])
      expect(receipt.rows.find((row: { id: string }) => row.id === 'revenue').decision).toBeNull()
      await page.getByRole('button', { name: 'Existing periods' }).click()
      await expect(page.getByRole('button', { name: 'Add period for Net income' })).toHaveCount(0)
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow).toBeLessThanOrEqual(1)
      await page.screenshot({ path: testInfo.outputPath(`financial-refresh-${theme}-${width}.png`), fullPage: true })
    })
  }
}
