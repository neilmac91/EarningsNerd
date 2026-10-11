import { expect, test } from '@playwright/test'

// Match this setting to the local server's build/dev process; see the prototype guide.
const enabled = process.env.NEXT_PUBLIC_ENABLE_FILING_REDLINES === 'true'
const route = '/labs/filing-redlines'

test('redlines direct URL returns 404 with the flag off', async ({ page }) => {
  test.skip(enabled, 'Run against a server built with the flag unset.')
  const response = await page.goto(route)
  expect(response?.status()).toBe(404)
  await expect(page.getByRole('heading', { name: 'Read what changed.' })).toHaveCount(0)
})

for (const theme of ['light', 'dark'] as const) {
  for (const width of [390, 1440]) {
    test(`redlines example, cached reads and missing text: ${theme} ${width}px`, async ({ page }, testInfo) => {
      test.skip(!enabled, 'Enable the flag in both the local server and this test process.')
      await page.setViewportSize({ width, height: 1000 })
      await page.addInitScript((mode) => {
        localStorage.setItem('theme', mode)
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, marketing: false }))
      }, theme)
      const calls: string[] = []
      let release!: () => void
      const pending = new Promise<void>((resolve) => { release = resolve })
      let missing = false
      const literal = '<img src=x onerror="window.redlineInjected=true"> Revenue was $11 million.'

      await page.route('**/api/**', async (request) => {
        const path = new URL(request.request().url()).pathname
        const match = path.match(/^\/api\/filings\/(101|102)(\/content)?$/)
        if (!match) {
          await request.fulfill({ status: 200, json: path.endsWith('/auth/signup-config') ? { registration_enabled: false } : {} })
          return
        }
        calls.push(path)
        const id = Number(match[1])
        const earlier = id === 101
        if (match[2]) {
          await pending
          await request.fulfill({ json: {
            filing_id: id,
            has_content: !missing,
            markdown_content: missing ? null : earlier ? 'Revenue was $10 million.\n\nStable text.' : `${literal}\n\nStable text.`,
          } })
          return
        }
        const accession = earlier ? '0000000123-25-000001' : '0000000123-26-000001'
        await request.fulfill({ json: {
          id, filing_type: '10-K',
          filing_date: earlier ? '2025-02-10T00:00:00+00:00' : '2026-02-10T00:00:00+00:00',
          report_date: earlier ? '2024-12-31T00:00:00' : '2025-12-31T00:00:00',
          accession_number: accession,
          document_url: `https://www.sec.gov/Archives/edgar/data/123/${accession.replaceAll('-', '')}/original.htm`,
          sec_url: `https://www.sec.gov/Archives/edgar/data/123/${accession.replaceAll('-', '')}/`,
          company: { id: 123, ticker: 'FIXTURE', name: 'Local browser fixture' },
        } })
      })

      await page.goto(route)
      await expect(page.getByRole('heading', { name: 'Fictional example comparison' })).toBeVisible()
      expect(calls).toEqual([])
      await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/)
      await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
      await expect(page.getByRole('main')).toHaveCount(1)
      await page.screenshot({ path: testInfo.outputPath(`example-${theme}-${width}.png`), fullPage: true })

      await page.getByRole('button', { name: 'Cached filings', exact: true }).click()
      await page.getByLabel('Earlier filing ID').fill('101')
      await page.getByLabel('Later filing ID').fill('102')
      const compare = page.getByRole('button', { name: /Compare cached text|Reading cached filings/ })
      await compare.focus()
      await compare.press('Enter')
      await expect.poll(() => calls.filter((path) => path.endsWith('/content')).length).toBe(2)
      await expect(compare).toBeFocused()
      await compare.press('Enter')
      expect(calls).toHaveLength(4)
      release()
      await expect(page.getByRole('heading', { name: 'Selected filing comparison' })).toBeVisible()
      await expect(compare).toBeFocused()
      await expect(page.getByText(literal, { exact: true })).toBeVisible()
      await expect(page.getByRole('link', { name: 'Open earlier original' })).toHaveAttribute('href', /000000012325000001\/original.htm$/)
      await expect(page.getByRole('link', { name: 'Open later original' })).toHaveAttribute('href', /000000012326000001\/original.htm$/)
      expect(await page.evaluate(() => 'redlineInjected' in window)).toBe(false)
      const geometry = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
      expect(geometry.scroll).toBeLessThanOrEqual(Math.min(width, geometry.width) + 1)
      await page.screenshot({ path: testInfo.outputPath(`cached-${theme}-${width}.png`), fullPage: true })

      missing = true
      await compare.press('Enter')
      await expect(page.getByText('Comparison unavailable', { exact: true })).toBeVisible()
      await expect(page.getByText(literal, { exact: true })).toHaveCount(0)
      await expect(page.getByRole('link', { name: 'Open earlier original' })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`unavailable-${theme}-${width}.png`), fullPage: true })
    })
  }
}
