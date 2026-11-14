import { test, expect, type Page } from '@playwright/test'
import type { Theme } from './fixtures/companyPeersApi'
import { BETA_READER, COMPLETE, INSIDERS_PATH, openInsiders, SCANNING, TICKER } from './fixtures/companyInsidersApi'

/**
 * Insider activity's two mounts (ADR 0009; founder direction of 2026-11-14): a card in the company page's side
 * column, so the filings keep the page, and the company's insider page (/company/{ticker}/insiders), which holds the
 * full panel. Both show themselves to a beta account only, so no render test can see either go missing from its
 * route: a fixture answers their reads here, and this browser gate can
 * (lessons/frontend-route-redesign-needs-a-mount-gate.md). CI's e2e job builds them (its build has
 * NEXT_PUBLIC_ENABLE_INSIDER_ACTIVITY on, as production's has), so on a build without the flag, or without a mount,
 * the cases that draw it fail.
 *
 * On /company/INSX (fixtures/companyInsidersApi.ts's TICKER), in both themes at 390 and 1280px: the card sits after
 * the filings, beside them from 64rem and under them below, says the window in three lines and links to the insider
 * page; the page draws no insider table of its own and does not scroll sideways. Following the link opens the insider
 * page. There, with a scan part-way through (16 of 60 filings read, three trades stored): the company in the lead
 * with the way back, the scan's words in a status region, the bar named "Form 4 filings read" at 16 of 60 with its
 * count and the date the scan reaches outside that region, the signal and the trades. Under 200% text at 390 and
 * 320px neither page scrolls sideways. A guest and an account that is not a beta tester see no card on the company
 * page and ask nothing of the insider endpoint, and on the insider page are told it is in beta. CI runs e2e with no
 * backend (lessons/test-e2e-runs-without-backend.md).
 */

const VIEWPORTS = [
  { width: 390, height: 844, isMobile: true, hasTouch: true },
  { width: 1280, height: 900, isMobile: false, hasTouch: false },
]
const THEMES: Theme[] = ['light', 'dark']

/** The company page's card. */
const card = (page: Page) => page.getByRole('complementary', { name: 'Insider activity' })
/** The insider page's panel: the nearest section around its heading. */
const panel = (page: Page) =>
  page.getByRole('heading', { level: 2, name: 'Insider activity', exact: true }).locator('xpath=ancestor::section[1]')

const overflow = (page: Page) =>
  page.evaluate(() => {
    const root = document.documentElement
    return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth }
  })

for (const theme of THEMES) {
  for (const viewport of VIEWPORTS) {
    const context = { viewport: { width: viewport.width, height: viewport.height }, isMobile: viewport.isMobile, hasTouch: viewport.hasTouch }

    test(`the company page shows a beta account the card, after the filings: ${theme}, ${viewport.width}px`, async ({ browser, baseURL }) => {
      const ctx = await browser.newContext(context)
      const page = await ctx.newPage()
      await openInsiders(page, baseURL!, theme, { insiders: COMPLETE })

      const aside = card(page)
      await expect(aside).toBeVisible()
      await expect(aside.getByText('Form 4 · last 90 days', { exact: true })).toBeVisible()
      await expect(aside.getByRole('listitem')).toHaveText([/^Net selling\s*▼\s*\$297\.9M$/, /^Buys\s*None$/, /^Sells\s*\$297\.9M\s*41 trades$/])
      await expect(aside.getByRole('link', { name: 'Open insider activity' })).toHaveAttribute('href', INSIDERS_PATH)

      // The filings keep the page: they come before the card, beside it from 64rem and above it below, and the
      // company page draws no insider table or window control of its own.
      const filings = await page.getByRole('region', { name: 'SEC filings' }).boundingBox()
      const box = await aside.boundingBox()
      if (viewport.width >= 1024) {
        expect(box!.x).toBeGreaterThanOrEqual(filings!.x + filings!.width)
        expect(Math.abs(box!.y - filings!.y)).toBeLessThan(2)
      } else {
        expect(box!.y).toBeGreaterThanOrEqual(filings!.y + filings!.height)
      }
      await expect(page.getByRole('group', { name: 'Time window' })).toHaveCount(0)
      await expect(page.getByRole('table')).toHaveCount(0)

      const { scrollWidth, clientWidth } = await overflow(page)
      expect(scrollWidth, 'the page scrolls sideways').toBeLessThanOrEqual(clientWidth)
      await ctx.close()
    })

    test(`the insider page shows a beta account a scan part-way through: ${theme}, ${viewport.width}px`, async ({ browser, baseURL }) => {
      const ctx = await browser.newContext(context)
      const page = await ctx.newPage()
      await openInsiders(page, baseURL!, theme, { path: INSIDERS_PATH })

      await expect(page.getByRole('heading', { level: 1 })).toContainText('Insider Example Corp')
      await expect(page.getByRole('navigation', { name: 'Breadcrumb' }).getByRole('link', { name: 'Insider Example Corp' })).toHaveAttribute('href', `/company/${TICKER}`)

      const section = panel(page)
      await expect(section).toBeVisible()
      const words = section.getByText('Reading this company’s recent Form 4 filings.', { exact: true })
      await expect(words).toBeVisible()
      const region = section.locator('[role="status"]').filter({ hasText: 'Reading this company’s recent Form 4 filings.' })
      await expect(region).toHaveCount(1)

      const bar = section.getByRole('progressbar', { name: 'Form 4 filings read' })
      await expect(bar).toHaveAttribute('aria-valuenow', '16')
      await expect(bar).toHaveAttribute('aria-valuemax', '60')
      const count = section.getByText('16 of 60 filings read, back to Sep 4, 2026', { exact: true })
      await expect(count).toBeVisible()
      await expect(region).toHaveText('Reading this company’s recent Form 4 filings.')   // no count, no date: neither is read out with each answer
      const fill = await bar.locator('div').first().boundingBox()
      const track = await bar.boundingBox()
      expect(fill!.width / track!.width).toBeGreaterThan(0.24)
      expect(fill!.width / track!.width).toBeLessThan(0.3)   // 16 of 60 is 27%

      await expect(section.getByText(/Net insider buying/)).toBeVisible()
      await expect(section.getByText('Jane Doe')).toBeVisible()
      await expect(section.getByText('Alexandria Montgomery-Fitzgerald')).toBeVisible()
      await expect(section.getByRole('group', { name: 'Time window' })).toBeVisible()

      const { scrollWidth, clientWidth } = await overflow(page)
      expect(scrollWidth, 'the page scrolls sideways').toBeLessThanOrEqual(clientWidth)
      await ctx.close()
    })
  }
}

test('the card’s link opens the insider page, which shows every trade the answer carries and says how many the window holds', async ({ page, baseURL }) => {
  await openInsiders(page, baseURL!, 'light', { insiders: COMPLETE })
  await card(page).getByRole('link', { name: 'Open insider activity' }).click()
  await expect(page).toHaveURL(new RegExp(`${INSIDERS_PATH}$`))

  const section = panel(page)
  await expect(section.getByText(/Net insider selling/)).toBeVisible()
  await expect(section.getByRole('row')).toHaveCount(31)   // the header and all thirty
  await expect(section.getByText(/^The 30 most recent of 41 trades in this window\./)).toBeVisible()
  // And back: the lead's link returns to the filings.
  await page.getByRole('banner').getByRole('link', { name: 'View filings' }).click()
  await expect(page).toHaveURL(new RegExp(`/company/${TICKER}$`))
  await expect(page.getByRole('region', { name: 'SEC filings' })).toBeVisible()
})

for (const width of [390, 320]) {
  test(`under 200% text at ${width}px neither page scrolls sideways, and the card and the panel keep inside it`, async ({ browser, baseURL }) => {
    const ctx = await browser.newContext({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true })
    for (const [path, target] of [[`/company/${TICKER}`, card], [INSIDERS_PATH, panel]] as const) {
      const page = await ctx.newPage()
      await openInsiders(page, baseURL!, 'light', { doubled: true, path })

      const surface = target(page)
      await expect(surface).toBeVisible()
      if (path === INSIDERS_PATH) {
        await expect(surface.getByRole('progressbar', { name: 'Form 4 filings read' })).toBeVisible()
        await expect(surface.getByText('16 of 60 filings read, back to Sep 4, 2026', { exact: true })).toBeVisible()
      } else {
        await expect(surface.getByRole('link', { name: 'Open insider activity' })).toBeVisible()
      }
      const { scrollWidth, clientWidth } = await overflow(page)
      expect(scrollWidth, `${path} scrolls sideways`).toBeLessThanOrEqual(clientWidth)
      const box = await surface.boundingBox()
      expect(box!.x).toBeGreaterThanOrEqual(0)
      expect(box!.x + box!.width).toBeLessThanOrEqual(clientWidth + 0.5)
      await page.close()
    }
    await ctx.close()
  })
}

for (const [who, reader] of [['a guest', null], ['an account that is not a beta tester', { ...BETA_READER, is_beta: false }]] as const) {
  test(`${who} sees no insider card on the company page and asks nothing of its endpoint`, async ({ page, baseURL }) => {
    const asked = await openInsiders(page, baseURL!, 'light', { reader })

    await expect(page.getByRole('heading', { level: 1 })).toContainText('Insider Example Corp')
    await expect(page.getByText('10-K').first()).toBeVisible()   // the page's own content is there
    await page.waitForLoadState('networkidle')
    await expect(page.getByRole('heading', { name: 'Insider activity' })).toHaveCount(0)
    expect(asked.insiders).toBe(0)
  })

  test(`${who} is told on the insider page that it is in beta, with the way back, and asks nothing of its endpoint`, async ({ page, baseURL }) => {
    const asked = await openInsiders(page, baseURL!, 'light', { reader, path: INSIDERS_PATH })

    await expect(page.getByRole('heading', { level: 2, name: 'Insider activity is in beta' })).toBeVisible()
    await expect(page.getByRole('main').getByRole('link', { name: 'View filings' })).toHaveAttribute('href', `/company/${TICKER}`)
    await expect(page.getByRole('main').getByRole('link', { name: 'Log in' })).toHaveCount(reader ? 0 : 1)
    await page.waitForLoadState('networkidle')
    expect(asked.insiders).toBe(0)
  })
}

test('a first visit shows the words alone on the insider page, with no bar to count against', async ({ page, baseURL }) => {
  await openInsiders(page, baseURL!, 'light', {
    path: INSIDERS_PATH,
    insiders: { ...SCANNING, transactions: [], total_transactions: 0, scan: { ...SCANNING.scan, filings_listed: 0, filings_read: 0, oldest_filed_date: null } },
  })
  const section = panel(page)
  await expect(section.getByText('Reading this company’s recent Form 4 filings.', { exact: true })).toBeVisible()
  await expect(section.getByRole('progressbar')).toHaveCount(0)
})
