import { test, expect, type Locator, type Page } from '@playwright/test'

/**
 * The catch card's two amounts (features/marketing/components/CatchCard.tsx) sit side by side while
 * both fit and stack when they do not, in any column and at any text size. The founder's review of
 * PR #1226 measured them overlapping by 59.6px on the production build at 390px under a 200% root
 * font, and in the narrower desktop column, because two equal grid tracks could not hold the two
 * unbreakable values. Each case reads the real card on the landing page, in both themes, and checks
 * the painted text: the amounts never overlap, each stays inside the card, and the card never
 * scrolls sideways. At the default text size on a phone the pair stays on one line, as designed.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md); the card is static
 * sample content, so the landing page needs no answered API here.
 */
type Theme = 'light' | 'dark'
type Box = { left: number; right: number; top: number; bottom: number }

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

/** The card is the nearest panel around "The number you remember". */
const catchCard = (page: Page) => page.locator('#evidence dl', { hasText: 'From memory' }).locator('xpath=..')

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
  const card = catchCard(page)
  await card.scrollIntoViewIfNeeded()
  const remembered = await paintedBox(card.getByText('$391.0B', { exact: true }))
  const inFiling = await paintedBox(card.getByText('$416.2B', { exact: true }))
  const cardBox = await card.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, scrolls: el.scrollWidth > el.clientWidth + 1 }
  })
  return { remembered, inFiling, cardBox }
}

function expectReadable({ remembered, inFiling, cardBox }: Awaited<ReturnType<typeof measure>>, label: string) {
  expect(overlaps(remembered, inFiling), `${label}: the two amounts overlap`).toBe(false)
  for (const [name, box] of [['$391.0B', remembered], ['$416.2B', inFiling]] as const) {
    expect(box.left, `${label}: ${name} starts outside the card`).toBeGreaterThanOrEqual(cardBox.left - 0.5)
    expect(box.right, `${label}: ${name} ends outside the card`).toBeLessThanOrEqual(cardBox.right + 0.5)
  }
  expect(cardBox.scrolls, `${label}: the card scrolls sideways`).toBe(false)
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`the catch card, ${theme} theme`, () => {
    test('at 390px the pair shares a line at the default size and stacks under a 200% root font', async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 })
      await openLanding(page, theme)
      const normal = await measure(page, '')
      expectReadable(normal, '390px, default text')
      expect(Math.abs(normal.remembered.top - normal.inFiling.top), 'the pair shares a line at the default size').toBeLessThan(1)
      const enlarged = await measure(page, '32px')
      expectReadable(enlarged, '390px, 200% text')
      expect(enlarged.inFiling.top, 'the pair stacks when the values cannot share a line').toBeGreaterThanOrEqual(enlarged.remembered.bottom - 0.5)
    })

    test('in the desktop column under a 200% root font the pair stacks instead of colliding', async ({ page }) => {
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
  })
}
