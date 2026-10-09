import { test, expect, type Locator, type Page } from '@playwright/test'
import { textContrast } from './fixtures/contrast'

/**
 * The company page's filing list (critique v3.1 CLEAN-R3 and CLEAN-R4), in a real Chromium.
 *
 * CLEAN-R3: each filing row was a card with a 4px type-coloured left stripe and a type tint: sage
 * for 10-K/20-F/40-F, the status-blue `info` colour for 10-Q/6-K, so an interim filing read like an
 * alert (the Impeccable detector's one real side-tab defect), and the grey filing date inside the
 * blue tint measured 4.04:1. Now every row is the same card (hairline on all four sides, one fill
 * and one hover for every type); the type Badge still names and colours the type. Checked in both
 * themes, with the pointer away from the rows.
 *
 * CLEAN-R4: each report-year header is a disclosure button: `aria-expanded` follows the panel, and
 * while the panel is open `aria-controls` names it (a collapsed panel is not rendered, so there is
 * nothing to name). DOM measurements only: this is not a screen-reader test.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the server-side fetch
 * fails, the page falls back to its client shell, and the browser's API calls are answered here.
 */

type Theme = 'light' | 'dark'
const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const FOLDER = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
const filing = (id: number, filing_type: string, filing_date: string, report_date: string) => ({
  id,
  filing_type,
  filing_date: `${filing_date}T00:00:00+00:00`,
  report_date,
  accession_number: `0000320193-25-0000${id}`,
  document_url: `${FOLDER}doc-${id}.htm`,
  sec_url: FOLDER,
})
const FILINGS = [
  filing(11, '10-K', '2025-10-31', '2025-09-27'),
  filing(12, '10-Q', '2025-08-01', '2025-06-28'),
  filing(13, '10-Q', '2025-05-02', '2025-03-29'),
  filing(14, '10-K', '2024-11-01', '2024-09-28'),
]

async function openCompany(page: Page, baseURL: string, theme: Theme) {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    if (pathname === '/api/companies/AAPL') return json(200, { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' })
    if (pathname === '/api/filings/company/AAPL') return json(200, FILINGS)
    if (pathname === '/api/auth/me') return json(401, { detail: 'Not authenticated' })
    return json(404, { detail: 'Not found' })
  })
  await page.addInitScript((t: Theme) => {
    try {
      localStorage.setItem('theme', t)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto('/company/AAPL')
  await expect(page.getByRole('link', { name: 'Generate Filing Summary' })).toHaveCount(FILINGS.length)
}

const yearButton = (page: Page, year: string) => page.getByRole('button', { name: new RegExp(`^Report year ${year}\\b`) })
/** A filing row: the card that holds a filing's "Generate Filing Summary" link. */
const rows = (page: Page) =>
  page.getByRole('link', { name: 'Generate Filing Summary' }).locator('xpath=ancestor::div[contains(concat(" ", @class, " "), " rounded-xl ")][1]')

const boxOf = (row: Locator) =>
  row.evaluate((el) => {
    const s = getComputedStyle(el)
    return {
      borderWidths: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth],
      borderColors: [s.borderTopColor, s.borderRightColor, s.borderBottomColor, s.borderLeftColor],
      background: s.backgroundColor,
    }
  })

for (const theme of ['light', 'dark'] as const) {
  test(`filing rows carry no type stripe or type tint in ${theme} theme`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await openCompany(page, baseURL!, theme)
    await page.mouse.move(0, 0)

    const all = rows(page)
    await expect(all).toHaveCount(FILINGS.length)
    const boxes = await Promise.all(FILINGS.map((_, i) => boxOf(all.nth(i))))
    for (const [i, box] of boxes.entries()) {
      const type = FILINGS[i].filing_type
      expect(new Set(box.borderWidths).size, `${type} row: one border width on all four sides`).toBe(1)
      expect(new Set(box.borderColors).size, `${type} row: one border colour on all four sides`).toBe(1)
      // The type is still named, by the Badge.
      await expect(all.nth(i).getByText(type, { exact: true })).toBeVisible()
    }
    // One resting fill for every filing type: 10-Q rows are no longer tinted with the status blue.
    expect(new Set(boxes.map((b) => b.background)).size, 'one fill for 10-K and 10-Q rows').toBe(1)
    expect(new Set(boxes.map((b) => b.borderColors[0])).size, 'one hairline for 10-K and 10-Q rows').toBe(1)

    // The filing date inside each row clears AA against what is painted behind it.
    for (let i = 0; i < FILINGS.length; i++) {
      const date = all.nth(i).getByText(/^[A-Z][a-z]{2} \d{1,2}, \d{4}$/)
      expect(await textContrast(date), `${FILINGS[i].filing_type} row date`).toBeGreaterThanOrEqual(4.5)
    }
  })
}

test('report-year headers are disclosure buttons that expose their state and panel', async ({ page, baseURL }) => {
  await openCompany(page, baseURL!, 'light')
  for (const year of ['2025', '2024']) {
    const button = yearButton(page, year)
    await expect(button).toHaveAttribute('type', 'button')
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    const panelId = await button.getAttribute('aria-controls')
    expect(panelId, `${year} names its open panel`).toBeTruthy()
    const panel = page.locator(`[id="${panelId}"]`)
    await expect(panel).toHaveCount(1)
    await expect(panel.getByRole('link', { name: 'Generate Filing Summary' })).toHaveCount(year === '2025' ? 3 : 1)
  }

  // Pointer: collapse 2025.
  await yearButton(page, '2025').click()
  await expect(yearButton(page, '2025')).toHaveAttribute('aria-expanded', 'false')
  await expect(yearButton(page, '2025')).not.toHaveAttribute('aria-controls', /.+/)
  await expect(page.getByRole('link', { name: 'Generate Filing Summary' })).toHaveCount(1)

  // Keyboard: Enter and Space on the focused header toggle it back and forth.
  await yearButton(page, '2025').focus()
  await page.keyboard.press('Enter')
  await expect(yearButton(page, '2025')).toHaveAttribute('aria-expanded', 'true')
  await expect(yearButton(page, '2025')).toBeFocused()
  await page.keyboard.press('Space')
  await expect(yearButton(page, '2025')).toHaveAttribute('aria-expanded', 'false')
})
