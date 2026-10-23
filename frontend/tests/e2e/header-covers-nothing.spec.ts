import { test, expect, type Page } from '@playwright/test'

/**
 * The site header (components/Header.tsx) is the one bar that sticks at the top of the viewport, and it covers
 * nothing a reader scrolls or tabs to: chief design's rulings E162 and E163 (PR #1515, comment 6362491933).
 *
 * E162: a page's own header (components/SecondaryHeader.tsx) scrolls with the page. It stuck at `top-0` under the
 * site header: once /pricing scrolled, its title showed through the bar's translucent ground beside a second logo
 * mark, its last pixels hung below the bar as a blurred band, and a click at its back link's centre landed on the
 * site header. At 390x844 and 1440x900, in both themes, once the page has scrolled past the page header, the page
 * header is off the screen, and it sits on an opaque ground with no blur, since nothing passes under it.
 *
 * E163: the document's `scroll-padding-top` reads the header's height (app/globals.css), so a focused control is
 * scrolled clear of the bar (WCAG 2.2 SC 2.4.11, Focus Not Obscured). Without it Chromium treats a control behind
 * the sticky bar as already in view and leaves it there: on main a Shift+Tab walk found the landing's Trace to
 * Source chip wholly under the bar at the default text size, and under 200% text the footer's links, the search
 * field, "Upgrade to Pro" and "Request an invite". The walk runs Shift+Tab from each page's last stop to its first
 * on /, /pricing and /analysis, at 390x844 and 1440x900, at the default text size and under a 200% text setting,
 * and finds no stop wholly under the bar. The bar's own controls are its own, and fixed chrome (the skip link, the
 * launchers) does not scroll, so neither is a page stop here. The walk runs in the light theme: a theme changes no
 * geometry the walk reads.
 *
 * 200% text is Chromium's own text setting (`Page.setFontSizes`, as tests/e2e/reflow-200.spec.ts doubles it), not
 * an inline style on <html>, which no media query reads. CI runs e2e with no backend
 * (lessons/test-e2e-runs-without-backend.md), and the build may name a production API host, so every API request is
 * answered here in the browser whatever its host: the session check 401 (a guest), any other API path 404; every
 * other request but the frontend's own GET and HEAD is aborted. The consent bar is answered before load, so its
 * bottom inset is not in play.
 */

const VIEWPORTS = [
  { name: '390px', width: 390, height: 844 },
  { name: '1440px', width: 1440, height: 900 },
]
const WALK_ROUTES = ['/', '/pricing', '/analysis']
/** More stops than any walked page holds; a walk that reaches it never came back round. */
const MAX_STOPS = 600

/** A guest, answered in the browser. */
async function answerGuest(page: Page, baseURL: string) {
  const origin = new URL(baseURL).origin
  await page.route('**/*', (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const headers = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS' }
    // Sentry's ingestion URLs also begin /api, but are telemetry, not this app's API.
    if (url.hostname.endsWith('.sentry.io')) return route.abort()
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/internal/')) {
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
      if (url.pathname === '/api/auth/me') return route.fulfill({ status: 401, headers, json: { detail: 'Not authenticated' } })
      return route.fulfill({ status: 404, headers, json: { detail: 'No backend is available in the header case' } })
    }
    if (url.origin === origin && ['GET', 'HEAD'].includes(request.method())) return route.continue()
    return route.abort()
  })
}

async function open(page: Page, baseURL: string, route: string, theme: 'light' | 'dark') {
  await page.addInitScript((theme) => {
    localStorage.setItem('theme', theme)
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
  }, theme)
  await answerGuest(page, baseURL)
  await page.goto(route)
  await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
}

/** Chromium's own text setting doubled (standard 32, fixed 26), confirmed taken: the root computes to 32px. */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize), { message: 'the 200% text setting took: the root computes to 32px' })
    .toBe('32px')
}

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready)
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
}

interface Stop {
  label: string
  top: number
  bottom: number
  barBottom: number
  scrollY: number
}

/**
 * Walks Shift+Tab from the page's last stop to its first and returns each page stop wholly under the bar. A
 * sentinel button, fixed so it moves nothing, is appended last and focused, so the first Shift+Tab lands on the
 * page's last stop; the walk ends when focus leaves the page or comes back round to the sentinel.
 */
async function walkBack(page: Page): Promise<{ stops: number; hidden: Stop[] }> {
  await page.evaluate(() => {
    const sentinel = document.createElement('button')
    sentinel.dataset.walkSentinel = ''
    sentinel.textContent = 'walk sentinel'
    sentinel.style.cssText = 'position:fixed;left:0;bottom:0;width:1px;height:1px;opacity:0'
    document.body.append(sentinel)
    sentinel.focus({ preventScroll: true })
  })
  const hidden: Stop[] = []
  let stops = 0
  for (;;) {
    await page.keyboard.press('Shift+Tab')
    const stop = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null
      if (!el || el === document.body || 'walkSentinel' in el.dataset) return { done: true as const }
      const bar = [...document.querySelectorAll('header')].find((h) => getComputedStyle(h).position === 'sticky')
      if (!bar) throw new Error('no sticky site header on the page')
      let fixed = false
      for (let node: Element | null = el; node; node = node.parentElement) if (getComputedStyle(node).position === 'fixed') fixed = true
      const r = el.getBoundingClientRect()
      const b = bar.getBoundingClientRect()
      const label = (el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || el.tagName).replace(/\s+/g, ' ').trim().slice(0, 60)
      const own = bar.contains(el) || fixed || r.width === 0 || r.height === 0
      return { done: false as const, own, label: `${el.tagName.toLowerCase()} "${label}"`, top: r.top, bottom: r.bottom, barTop: b.top, barBottom: b.bottom, scrollY: window.scrollY }
    })
    if (stop.done) break
    stops++
    if (stops > MAX_STOPS) throw new Error(`the walk passed ${MAX_STOPS} stops without coming back round`)
    if (!stop.own && stop.top >= stop.barTop - 0.5 && stop.bottom <= stop.barBottom + 0.5) {
      hidden.push({ label: stop.label, top: stop.top, bottom: stop.bottom, barBottom: stop.barBottom, scrollY: stop.scrollY })
    }
  }
  return { stops, hidden }
}

for (const viewport of VIEWPORTS) {
  const mobile = viewport.width <= 390
  const device = { viewport: { width: viewport.width, height: viewport.height }, isMobile: mobile, hasTouch: mobile, reducedMotion: 'reduce' as const, serviceWorkers: 'block' as const }

  for (const theme of ['light', 'dark'] as const) {
    test.describe(`the page header scrolls away / ${theme} / ${viewport.name}`, () => {
      test.use({ ...device, colorScheme: theme })
      test("once /pricing has scrolled past its page header, the page header is off the screen", async ({ page, baseURL }) => {
        await open(page, baseURL!, '/pricing', theme)
        const pageHeader = page.locator('header', { has: page.getByRole('heading', { level: 1, name: 'Pricing' }) })
        await expect(pageHeader).toBeVisible()
        await settle(page)
        const ground = await pageHeader.evaluate((el) => ({ background: getComputedStyle(el).backgroundColor, blur: getComputedStyle(el).backdropFilter }))
        expect(ground.background, `${theme}, ${viewport.name}: the page header sits on an opaque ground`).toMatch(/^rgb\(\d+, \d+, \d+\)$/)
        expect(ground.blur, `${theme}, ${viewport.name}: nothing passes under the page header, so it blurs nothing`).toBe('none')
        const past = await pageHeader.evaluate((el) => Math.ceil(el.getBoundingClientRect().bottom + window.scrollY) + 200)
        await page.evaluate((y) => window.scrollTo(0, y), past)
        await settle(page)
        const at = await pageHeader.evaluate((el) => ({ top: el.getBoundingClientRect().top, bottom: el.getBoundingClientRect().bottom, scrollY: window.scrollY }))
        expect(at.scrollY, `${theme}, ${viewport.name}: /pricing scrolled to ${past}px`).toBe(past)
        expect(
          at.bottom,
          `${theme}, ${viewport.name}: scrolled ${past}px, the page header's box runs ${at.top.toFixed(1)}px to ${at.bottom.toFixed(1)}px, still on the screen (stuck under the site header)`,
        ).toBeLessThanOrEqual(0)
      })
    })
  }

  for (const doubled of [false, true]) {
    for (const route of WALK_ROUTES) {
      const name = `${viewport.name}${doubled ? ' under 200% text' : ''}`
      test.describe(`a keyboard focus clears the site header / ${route} / ${name}`, () => {
        test.use({ ...device, colorScheme: 'light' })
        test(`a Shift+Tab walk of ${route} finds no stop wholly under the bar`, async ({ page, baseURL }) => {
          await open(page, baseURL!, route, 'light')
          await expect(page.locator('main').first()).toBeVisible()
          if (doubled) await doubleText(page)
          await settle(page)
          const walk = await walkBack(page)
          expect(walk.stops, `${route}, ${name}: the walk reached the page's stops`).toBeGreaterThan(3)
          expect(
            walk.hidden.map((s) => `${s.label} at ${s.top.toFixed(0)} to ${s.bottom.toFixed(0)}px, under a bar ending at ${s.barBottom.toFixed(0)}px (scrollY ${s.scrollY.toFixed(0)})`),
            `${route}, ${name}: a focused control wholly behind the site header`,
          ).toEqual([])
        })
      })
    }
  }
}
