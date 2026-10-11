import { expect, test } from '@playwright/test'
import { readFile } from 'node:fs/promises'

// Match the local server's build/dev flag. WAITLIST_MODE=false bypasses the existing global redirect.
const enabled = process.env.NEXT_PUBLIC_ENABLE_RESEARCH_EVIDENCE_PACKS === 'true'
const route = '/labs/research-evidence-packs'

test('evidence packs direct URL returns 404 while off', async ({ page, baseURL }) => {
  test.skip(enabled, 'Use a server built with this flag unset.')
  await page.route('**/*', async (request) => {
    const url = new URL(request.request().url())
    if (url.origin === new URL(baseURL!).origin && !url.pathname.startsWith('/api/') && ['GET', 'HEAD'].includes(request.request().method())) await request.continue()
    else await request.abort()
  })
  const response = await page.goto(route)
  expect(response?.status()).toBe(404)
  await expect(page.getByRole('heading', { name: 'Evidence worth revisiting' })).toHaveCount(0)
})

for (const theme of ['light', 'dark'] as const) {
  for (const width of [390, 1440]) {
    test(`evidence capture, review, export and missing cache: ${theme} ${width}px`, async ({ page, baseURL }, testInfo) => {
      test.skip(!enabled, 'Enable the flag in both local server and test process.')
      await page.setViewportSize({ width, height: 1000 })
      await page.addInitScript((mode) => {
        localStorage.setItem('theme', mode)
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, marketing: false }))
      }, theme)
      const calls: string[] = []
      let missing = false
      let release!: () => void
      const pending = new Promise<void>((resolve) => { release = resolve })
      const literal = '<img src=x onerror="window.evidenceInjected=true"> Revenue was $10 million.'
      const headers = { 'access-control-allow-origin': new URL(baseURL!).origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,OPTIONS' }
      await page.route('**/*', async (request) => {
        const url = new URL(request.request().url())
        if (!url.pathname.startsWith('/api/')) {
          if (url.origin === new URL(baseURL!).origin && ['GET', 'HEAD'].includes(request.request().method())) await request.continue()
          else await request.abort()
          return
        }
        if (request.request().method() === 'OPTIONS') { await request.fulfill({ status: 204, headers }); return }
        const match = url.pathname.match(/^\/api\/filings\/(101|102)(\/content)?$/)
        if (!match) { await request.fulfill({ headers, json: url.pathname.endsWith('/auth/signup-config') ? { registration_enabled: false } : {} }); return }
        calls.push(url.pathname)
        const id = Number(match[1]); const earlier = id === 101
        if (match[2]) {
          await pending
          await request.fulfill({ headers, json: { filing_id: id, has_content: !missing, markdown_content: missing ? null : earlier ? `First paragraph.\n\n${literal}` : 'Revenue was $12 million.' } })
          return
        }
        const accession = earlier ? '0000000123-25-000001' : '0000000123-26-000001'
        await request.fulfill({ headers, json: { id, filing_type: '10-K', filing_date: earlier ? '2025-02-10T00:00:00+00:00' : '2026-02-10T00:00:00+00:00', report_date: earlier ? '2024-12-31T00:00:00' : '2025-12-31T00:00:00', accession_number: accession, document_url: `https://www.sec.gov/Archives/edgar/data/123/${accession.replaceAll('-', '')}/original.htm`, sec_url: '', company: { id: 123, ticker: 'FIXTURE', name: 'Local browser fixture' } } })
      })

      await page.goto(route)
      await expect(page.getByRole('heading', { name: 'Evidence worth revisiting' })).toBeVisible()
      await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/)
      await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
      expect(calls).toEqual([])
      await page.screenshot({ path: testInfo.outputPath(`example-${theme}-${width}.png`), fullPage: true })
      await page.getByRole('button', { name: 'Cached filings', exact: true }).click()
      await page.getByLabel('Filing ID').fill('101')
      const load = page.getByRole('button', { name: /Load cached filing|Loading cached text/ })
      await load.focus(); await load.press('Enter')
      await expect.poll(() => calls.filter((path) => path.endsWith('/content')).length).toBe(1)
      await expect(load).toBeFocused(); await load.press('Enter'); expect(calls).toHaveLength(2)
      release()
      await expect(page.getByLabel('Cached paragraph')).toBeVisible()
      await expect(load).toBeFocused()
      await page.getByLabel('Cached paragraph').selectOption('1')
      await page.getByRole('button', { name: 'Save as new evidence' }).click()
      const card = page.getByRole('article', { name: 'Evidence 1' })
      await expect(card.getByText(literal, { exact: true })).toBeVisible()
      expect(await page.evaluate(() => 'evidenceInjected' in window)).toBe(false)
      await card.getByLabel('My interpretation for evidence 1').fill('Compare revenue before reuse.')
      await page.getByLabel('Filing ID').fill('102'); await load.click()
      await expect(page.getByRole('region', { name: 'Source selection' }).getByText('Revenue was $12 million.', { exact: true })).toBeVisible()
      await card.getByRole('button', { name: 'Compare selected source' }).click()
      await expect(card.getByText('Review needed', { exact: true })).toBeVisible()
      await card.getByLabel('Review note for evidence 1').fill('Read both sources and updated the source revision.')
      const accept = card.getByRole('button', { name: 'Accept new revision' })
      await accept.focus(); await accept.press('Enter')
      await expect(card.getByRole('heading', { name: 'Evidence 1' })).toBeFocused()
      await expect(card.getByText('Preserved source revision 1')).toBeVisible()
      await expect(card.getByText('User reviewed', { exact: true })).toBeVisible()
      const downloading = page.waitForEvent('download')
      await page.getByRole('button', { name: 'Export JSON' }).click()
      const download = await downloading
      expect(download.suggestedFilename()).toBe('research-evidence-pack.json')
      const pack = JSON.parse(await readFile((await download.path())!, 'utf8'))
      expect(pack.entries[0].revisions.map((source: { filingId: number }) => source.filingId)).toEqual([101, 102])
      expect(pack.entries[0].revisions[0].quote).toBe(literal)
      expect(pack.entries[0].reviews[0].interpretation).toBe('Compare revenue before reuse.')
      await card.getByLabel('My interpretation for evidence 1').fill('A new interpretation needs another review.')
      await expect(card.getByText('Unreviewed', { exact: true })).toBeVisible()
      const dimensions = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }))
      expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1)
      await page.screenshot({ path: testInfo.outputPath(`review-${theme}-${width}.png`), fullPage: true })
      missing = true
      await load.click()
      await expect(page.getByRole('alert')).toContainText('Cached text is unavailable')
      await expect(page.getByRole('button', { name: 'Save as new evidence' })).toHaveCount(0)
      await expect(card.getByText(literal, { exact: true })).toBeVisible()
      await page.screenshot({ path: testInfo.outputPath(`missing-${theme}-${width}.png`), fullPage: true })
    })
  }
}
