import { test, expect, type Page } from '@playwright/test'
import { addressFit, atItsAt } from './fixtures/readerAddress'

/**
 * The pages that set the reader's own address in a sentence keep it inside its paragraph (the verify-email dialog's
 * intro, chief design's note on #1745, is in email-verification-resend.spec.ts). An address has no break opportunity,
 * so under 200% text "unverified@example.com" is longer than the line: /delete-account's "Logged in as" ran it 37, 59,
 * 85 and 120px past its paragraph at 414, 390, 360 and 320px, the page scrolling sideways from 390px, and
 * /forgot-password's sent line 4, 28, 58 and 98px, the page scrolling sideways from 360px. Each breaks after its @
 * before anywhere else (AddressText, chief design on #1750), "unverified@" over "example.com" under 200% text, and
 * inside a part only where the part is longer than the line (`break-words`, as /check-email's address does). At 320px
 * at the default size the address stays whole or breaks after its @, never inside a part. Each painted box of the
 * address lies inside its paragraph and the screen, and nothing in <main> or the page scrolls sideways. Where E231
 * holds, at 320px under 200% text, /delete-account's destructive button, below the address, is wider than its card;
 * the page is read with that button out of the layout, so anything else that takes the page wide still fails.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is answered inside the browser, and
 * /delete-account's reader is signed in by the middleware's presence cookie and the session read.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const EMAIL = 'unverified@example.com'

async function answer(page: Page, baseURL: string, signedIn: boolean) {
  const origin = new URL(baseURL).origin
  if (signedIn) await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.addInitScript(() => {
    localStorage.setItem('theme', 'light')
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-23T00:00:00Z' }))
  })
  // Credentialed cross-origin responses need these two; Playwright answers any preflight itself.
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    if (pathname === '/api/auth/me')
      return signedIn
        ? route.fulfill({ status: 200, headers: cors, json: { id: 1, email: EMAIL, full_name: 'Ada', is_pro: false, is_beta: false, is_admin: false, email_verified: true } })
        : route.fulfill({ status: 401, headers: cors, json: { detail: 'Not authenticated' } })
    if (pathname === '/api/auth/forgot-password')
      return route.fulfill({ status: 200, headers: cors, json: { message: 'If that email is registered, a reset link is on its way.' } })
    return route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } })
  })
}

const PAGES = [
  {
    name: '/delete-account, signed in,',
    // E231: the destructive button's longest word, icon and padding are wider than the card at 320px under 200% text.
    wideAt320: 'Permanently delete my account',
    open: async (page: Page, baseURL: string) => {
      await answer(page, baseURL, true)
      await page.goto('/delete-account')
      await expect(page.getByText('Logged in as')).toBeVisible()
    },
  },
  {
    name: "/forgot-password's sent line",
    wideAt320: null,
    open: async (page: Page, baseURL: string) => {
      await answer(page, baseURL, false)
      await page.goto('/forgot-password')
      await page.getByLabel('Email').fill(EMAIL)
      await page.getByRole('button', { name: 'Send reset link' }).click()
      await expect(page.getByRole('heading', { level: 1, name: 'Check your email' })).toBeVisible()
    },
  },
]

for (const surface of PAGES) {
  for (const [width, doubled] of [
    [390, true],
    [360, true],
    [320, true],
    [320, false],
  ] as const) {
    const at = `${width}px${doubled ? ' under 200% text' : ' at the default size'}`
    test(`${surface.name} keeps the reader's address inside its paragraph, and the page from scrolling sideways, at ${at}`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height: 844 })
      if (doubled) {
        const cdp = await page.context().newCDPSession(page)
        await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
      }
      await surface.open(page, baseURL!)
      expect(await page.evaluate(() => getComputedStyle(document.documentElement).fontSize), `${at}: the text setting took`).toBe(doubled ? '32px' : '16px')
      await page.evaluate(() => document.fonts.ready)
      if (surface.wideAt320 && width === 320 && doubled) {
        await page.getByRole('button', { name: surface.wideAt320 }).evaluate((button) => { button.style.display = 'none' })
      }
      const fit = await addressFit(page.getByRole('main'), EMAIL)
      expect(fit.found, `${at}: the page names the reader's address`).toBe(true)
      expect(fit.past, `${at}: the address lies inside its paragraph`).toEqual([])
      expect(fit.offscreen, `${at}: the address lies inside the screen`).toEqual([])
      expect(fit.scrolls, `${at}: nothing in <main> scrolls sideways`).toEqual([])
      expect(fit.page, `${at}: the page does not scroll sideways`).toBeNull()
      if (doubled) expect(fit.pieces, `${at}: the address breaks after its @`).toEqual(atItsAt(EMAIL)[1])
      else expect(atItsAt(EMAIL), `${at}: the address is whole, or broken only after its @`).toContainEqual(fit.pieces)
    })
  }
}
