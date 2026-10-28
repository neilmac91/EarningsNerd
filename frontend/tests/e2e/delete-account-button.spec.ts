import { test, expect, type Page } from '@playwright/test'

/**
 * /delete-account's destructive button fits its card under 200% text (E231). Before, the signed-in card's "Permanently
 * delete my account" kept 275px where the card's content box was 216px at 320px, so the page scrolled 8px sideways,
 * and at 340 and 360px it ran 21 and 2px past the card's border while the page held; from 320 to 390px the row
 * squeezed the trash icon from 32px to 14px wide beside a label that wanted the room. Chief design's answer on #1750,
 * both moves, since neither alone fits at 320px:
 *  - the page's gutter gives way under 200% text as the legal pages' does: <main> narrows px-4 (32px a side there) to
 *    px-2 below 13em of its layout's query container, so the gutter is 16px at every phone width and text size;
 *  - the button lays its label out in Button's wrapping row (`reserveLoadingText`), so where the label's longest word
 *    cannot sit beside the icon, the icon goes above the label and keeps its 32px.
 * At each width the button lies inside its card's content box, the icon keeps its own size, the gutter is 16px and
 * the page does not scroll sideways.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the reader is signed in by the middleware's
 * presence cookie and the session read, answered inside the browser.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const LABEL = 'Permanently delete my account'

async function signedIn(page: Page, baseURL: string) {
  const origin = new URL(baseURL).origin
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.addInitScript(() => {
    localStorage.setItem('theme', 'light')
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-23T00:00:00Z' }))
  })
  // Credentialed cross-origin responses need these two; Playwright answers any preflight itself.
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname === '/api/auth/me')
      return route.fulfill({ status: 200, headers: cors, json: { id: 1, email: 'reader@example.com', full_name: 'Ada', is_pro: false, is_beta: false, is_admin: false, email_verified: true } })
    return route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } })
  })
}

for (const [width, doubled] of [
  [414, true],
  [390, true],
  [375, true],
  [360, true],
  [340, true],
  [320, true],
  [390, false],
  [320, false],
] as const) {
  const at = `${width}px${doubled ? ' under 200% text' : ' at the default size'}`
  test(`/delete-account's destructive button fits its card, its icon at its own size, at ${at}`, async ({ page, baseURL }) => {
    await page.setViewportSize({ width, height: 844 })
    if (doubled) {
      const cdp = await page.context().newCDPSession(page)
      await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
    }
    await signedIn(page, baseURL!)
    await page.goto('/delete-account')
    const button = page.getByRole('button', { name: LABEL })
    await expect(button).toBeVisible()
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize), `${at}: the text setting took`).toBe(doubled ? '32px' : '16px')
    await page.evaluate(() => document.fonts.ready)

    const read = await button.evaluate((el) => {
      const card = el.closest('section')!
      const cardBox = card.getBoundingClientRect()
      const cs = getComputedStyle(card)
      const contentLeft = cardBox.left + parseFloat(cs.borderLeftWidth) + parseFloat(cs.paddingLeft)
      const contentRight = cardBox.right - parseFloat(cs.borderRightWidth) - parseFloat(cs.paddingRight)
      const box = el.getBoundingClientRect()
      const icon = el.querySelector('svg')!.getBoundingClientRect()
      const main = getComputedStyle(el.closest('main')!)
      const doc = document.documentElement
      return {
        pastLeft: Math.round((contentLeft - box.left) * 10) / 10,
        pastRight: Math.round((box.right - contentRight) * 10) / 10,
        icon: `${Math.round(icon.width * 10) / 10}x${Math.round(icon.height * 10) / 10}`,
        gutter: `${main.paddingLeft} ${main.paddingRight}`,
        page: doc.scrollWidth > doc.clientWidth + 1 ? `${doc.scrollWidth}px in ${doc.clientWidth}px` : null,
      }
    })
    const side = doubled ? 32 : 16
    expect(read.pastRight, `${at}: the button's right edge runs ${read.pastRight}px past its card's content box`).toBeLessThanOrEqual(0.5)
    expect(read.pastLeft, `${at}: the button's left edge runs ${read.pastLeft}px past its card's content box`).toBeLessThanOrEqual(0.5)
    expect(read.icon, `${at}: the trash icon keeps its own size`).toBe(`${side}x${side}`)
    expect(read.gutter, `${at}: <main>'s gutter is 16px a side`).toBe('16px 16px')
    expect(read.page, `${at}: the page does not scroll sideways`).toBeNull()
  })
}
