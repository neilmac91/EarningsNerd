import { test, expect, type Locator, type Page } from '@playwright/test'

/**
 * The receipt card's amounts (features/marketing/components/FigureReceipt.tsx), "Follow one figure to the filing",
 * which replaced the catch card on the founder's review of 2026-10-22: each step reads down, its label, its amount and
 * a note, in any column and at any text size, and an amount breaks inside only when it is wider than the card on its
 * own. Each case reads the real card on the landing page, in both themes, and checks the painted text: no amount
 * overlaps its step's label or note, each stays inside the card, the card never scrolls sideways,
 * and nothing in the evidence row is struck through (the catch card's strike-through marked a correct filed figure
 * as wrong).
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md); the card is static sample content, so the
 * landing page needs no answered API here.
 */
type Theme = 'light' | 'dark'
type Box = { left: number; right: number; top: number; bottom: number }

const AMOUNTS = ['$416.2B', '$416,161 million', '416,161,000,000 USD'] as const

async function openLanding(page: Page, theme: Theme) {
  await page.addInitScript((theme: Theme) => {
    try {
      localStorage.setItem('theme', theme)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto('/')
  await expect(page.locator('#evidence')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

/** The card is the nearest panel around its title. */
const receiptCard = (page: Page) =>
  page.locator('#evidence').getByRole('heading', { name: 'Follow one figure to the filing' }).locator('xpath=ancestor::*[contains(@class,"p-5")][1]')

/** Where the text itself is painted (a Range), so an amount spilling out of its own box still counts. */
const paintedBox = (loc: Locator): Promise<Box> =>
  loc.evaluate((el) => {
    const range = document.createRange()
    range.selectNodeContents(el)
    const r = range.getBoundingClientRect()
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom }
  })

const overlaps = (a: Box, b: Box) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5

async function measure(page: Page, rootFont: string) {
  await page.evaluate((size) => {
    document.documentElement.style.fontSize = size
  }, rootFont)
  const card = receiptCard(page)
  await card.scrollIntoViewIfNeeded()
  const steps = []
  for (const amount of AMOUNTS) {
    const figure = card.getByText(amount, { exact: true })
    const label = figure.locator('xpath=preceding-sibling::p[1]')
    const note = figure.locator('xpath=following-sibling::p[1]')
    steps.push({ amount, figure: await paintedBox(figure), words: [await paintedBox(label), await paintedBox(note)] })
  }
  const cardBox = await card.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, scrolls: el.scrollWidth > el.clientWidth + 1 }
  })
  return { steps, cardBox }
}

function expectReadable({ steps, cardBox }: Awaited<ReturnType<typeof measure>>, label: string) {
  for (const { amount, figure, words } of steps) {
    for (const box of words) expect(overlaps(figure, box), `${label}: ${amount} overlaps its step's words`).toBe(false)
    expect(figure.left, `${label}: ${amount} starts outside the card`).toBeGreaterThanOrEqual(cardBox.left - 0.5)
    expect(figure.right, `${label}: ${amount} ends outside the card`).toBeLessThanOrEqual(cardBox.right + 0.5)
  }
  expect(cardBox.scrolls, `${label}: the card scrolls sideways`).toBe(false)
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`the receipt card, ${theme} theme`, () => {
    test('at 390px each amount stays readable at the default size and under a 200% root font', async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 })
      await openLanding(page, theme)
      expectReadable(await measure(page, ''), '390px, default text')
      expectReadable(await measure(page, '32px'), '390px, 200% text')
    })

    test('in the desktop column under a 200% root font no amount collides with its words', async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 })
      await openLanding(page, theme)
      expectReadable(await measure(page, ''), '1280px, default text')
      expectReadable(await measure(page, '32px'), '1280px, 200% text')
    })

    test('at 320px under a 200% root font each amount stays inside the card', async ({ page }) => {
      await page.setViewportSize({ width: 320, height: 568 })
      await openLanding(page, theme)
      expectReadable(await measure(page, '32px'), '320px, 200% text')
    })

    test('nothing in the evidence row is struck through', async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 })
      await openLanding(page, theme)
      const struck = await page.locator('#evidence').evaluate((root) =>
        [root, ...root.querySelectorAll('*')]
          .filter((el) => getComputedStyle(el).textDecorationLine.includes('line-through'))
          .map((el) => (el.textContent ?? '').trim().slice(0, 40)),
      )
      expect(struck).toEqual([])
    })
  })
}
