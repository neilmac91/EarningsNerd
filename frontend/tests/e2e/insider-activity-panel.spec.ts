import { test, expect, type Page } from '@playwright/test'
import type { Theme } from './fixtures/companyPeersApi'
import { BETA_READER, openInsiders, SCANNING } from './fixtures/companyInsidersApi'

/**
 * The Insider activity panel mounts on the company page for a beta account and shows nothing to anyone else (ADR 0009),
 * so no render test can see it go missing from the page: a fixture answers its reads here, and this browser gate can
 * (lessons/frontend-route-redesign-needs-a-mount-gate.md). CI's e2e job builds the panel (its build has
 * NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY on, as production's has), so on a build without the flag, or without the mount,
 * the cases that draw it fail.
 *
 * On /company/INSX (fixtures/companyInsidersApi.ts's TICKER), answered by fixtures/companyInsidersApi.ts with a scan part-way through (16 of 60 filings read,
 * three trades stored), in both themes at 390 and 1280px: the heading, the scan's words in a status region, the bar
 * named "Form 4 filings read" at 16 of 60 with its count and the date the scan reaches outside that region, the signal and the trades mount, and the
 * page does not scroll sideways; under 200% text at 390 and 320px the page still does not scroll sideways and the panel
 * keeps inside the viewport. A guest and an account that is not a beta tester see no panel and ask nothing of the
 * insider endpoint, with the page's filings rendered. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md).
 */

const VIEWPORTS = [
  { width: 390, height: 844, isMobile: true, hasTouch: true },
  { width: 1280, height: 900, isMobile: false, hasTouch: false },
]
const THEMES: Theme[] = ['light', 'dark']

/** The panel: the nearest section around its heading. */
const panel = (page: Page) =>
  page.getByRole('heading', { level: 2, name: 'Insider activity', exact: true }).locator('xpath=ancestor::section[1]')

const overflow = (page: Page) =>
  page.evaluate(() => {
    const root = document.documentElement
    return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth }
  })

for (const theme of THEMES) {
  for (const viewport of VIEWPORTS) {
    test(`a beta account sees a scan part-way through: ${theme}, ${viewport.width}px`, async ({ browser, baseURL }) => {
      const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, isMobile: viewport.isMobile, hasTouch: viewport.hasTouch })
      const page = await context.newPage()
      await openInsiders(page, baseURL!, theme)

      const card = panel(page)
      await expect(card).toBeVisible()
      const words = card.getByText('Reading this company’s recent Form 4 filings.', { exact: true })
      await expect(words).toBeVisible()
      const region = card.locator('[role="status"]').filter({ hasText: 'Reading this company’s recent Form 4 filings.' })
      await expect(region).toHaveCount(1)

      const bar = card.getByRole('progressbar', { name: 'Form 4 filings read' })
      await expect(bar).toHaveAttribute('aria-valuenow', '16')
      await expect(bar).toHaveAttribute('aria-valuemax', '60')
      const count = card.getByText('16 of 60 filings read, back to Sep 4, 2026', { exact: true })
      await expect(count).toBeVisible()
      await expect(region).toHaveText('Reading this company’s recent Form 4 filings.')   // no count, no date: neither is read out with each answer
      const fill = await bar.locator('div').first().boundingBox()
      const track = await bar.boundingBox()
      expect(fill!.width / track!.width).toBeGreaterThan(0.24)
      expect(fill!.width / track!.width).toBeLessThan(0.3)   // 16 of 60 is 27%

      await expect(card.getByText(/Net insider buying/)).toBeVisible()
      await expect(card.getByText('Jane Doe')).toBeVisible()
      await expect(card.getByText('Alexandria Montgomery-Fitzgerald')).toBeVisible()
      await expect(card.getByRole('group', { name: 'Time window' })).toBeVisible()

      const { scrollWidth, clientWidth } = await overflow(page)
      expect(scrollWidth, 'the page scrolls sideways').toBeLessThanOrEqual(clientWidth)
      await context.close()
    })
  }
}

for (const width of [390, 320]) {
  test(`under 200% text at ${width}px the page does not scroll sideways and the panel keeps inside it`, async ({ browser, baseURL }) => {
    const context = await browser.newContext({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true })
    const page = await context.newPage()
    await openInsiders(page, baseURL!, 'light', { doubled: true })

    const card = panel(page)
    await expect(card.getByRole('progressbar', { name: 'Form 4 filings read' })).toBeVisible()
    await expect(card.getByText('16 of 60 filings read, back to Sep 4, 2026', { exact: true })).toBeVisible()
    const { scrollWidth, clientWidth } = await overflow(page)
    expect(scrollWidth, 'the page scrolls sideways').toBeLessThanOrEqual(clientWidth)
    const box = await card.boundingBox()
    expect(box!.x).toBeGreaterThanOrEqual(0)
    expect(box!.x + box!.width).toBeLessThanOrEqual(clientWidth + 0.5)
    await context.close()
  })
}

for (const [who, reader] of [['a guest', null], ['an account that is not a beta tester', { ...BETA_READER, is_beta: false }]] as const) {
  test(`${who} sees no insider panel and asks nothing of its endpoint`, async ({ page, baseURL }) => {
    const asked = await openInsiders(page, baseURL!, 'light', { reader })

    await expect(page.getByRole('heading', { level: 1 })).toContainText('Insider Example Corp')
    await expect(page.getByText('10-K').first()).toBeVisible()   // the page's own content is there
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('heading', { name: 'Insider activity' })).toHaveCount(0)
    expect(asked.insiders).toBe(0)
  })
}

test('a first visit shows the words alone, with no bar to count against', async ({ page, baseURL }) => {
  await openInsiders(page, baseURL!, 'light', {
    insiders: { ...SCANNING, transactions: [], total_transactions: 0, scan: { ...SCANNING.scan, filings_listed: 0, filings_read: 0, oldest_filed_date: null } },
  })
  const card = panel(page)
  await expect(card.getByText('Reading this company’s recent Form 4 filings.', { exact: true })).toBeVisible()
  await expect(card.getByRole('progressbar')).toHaveCount(0)
})
