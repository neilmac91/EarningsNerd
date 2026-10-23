import { test, expect, type Page } from '@playwright/test'

/**
 * E139: on /analysis a guest (or a Free reader) gets the sample run inside PeekLocked's locked preview, and its
 * "Upgrade to Pro" action sits on the teaser's first screen. Before, the preview held the whole blurred results tree
 * and the action was centred on all of it: at 390px it sat about 2,600px below the teaser's start. Chief design took
 * the bounded preview (PR #1457, comment 6309710108): the teaser's preview shows about one screen, fades out at its
 * foot and centres the action in that window, so the reader sees the KPI strip and the top of the results
 * (`preview="screen"` in features/analysis/components/AnalysisTeaser.tsx; the window in
 * features/subscriptions/components/PeekLocked.tsx; the recipe in frontend/DESIGN_SYSTEM.md, Locked preview).
 *
 * At 390x844 and 1440x900 at the default text size, and at 390x844 and 320x640 under a 200% text setting, in both
 * themes, it holds:
 *   - the action's bottom edge within one viewport height of the teaser's top (the todo's done line);
 *   - the window no taller than the viewport, so no inert scroll is left under the blur, and holding no scroll of its
 *     own: the preview is cut at the window (overflow-clip), not scrollable under it;
 *   - the pill and the action centred in the window (a pixel of rounding);
 *   - the fade on the preview alone: the preview's mask runs from opaque to transparent over its last quarter, top to
 *     bottom, and nothing around the action carries a mask, so the action is never faded;
 *   - no sideways scroll.
 * 200% text is Chromium's own text setting (`Page.setFontSizes`, as tests/e2e/reflow-200.spec.ts doubles it), not an
 * inline style on <html>: only the setting reaches a media query, and under the inline style the site header keeps
 * its theme toggle in the bar (the 24rem query stays at 384px), widening /analysis to 472px at 390px, a state no
 * reader is in.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md), and the build may name a production API
 * host, so every API request is answered here in the browser whatever its host: the session check 401 (a guest), any
 * other API path 404 and recorded; every other request but the frontend's own GET and HEAD is aborted.
 */

const THEMES = ['light', 'dark'] as const
const PROFILES = [
  { name: '390px', width: 390, height: 844, doubleText: false },
  { name: '1440px', width: 1440, height: 900, doubleText: false },
  { name: '390px under 200% text', width: 390, height: 844, doubleText: true },
  { name: '320px under 200% text', width: 320, height: 640, doubleText: true },
]

/** A guest on /analysis, answered in the browser. Returns the API paths the page read. */
async function answerGuest(page: Page, baseURL: string) {
  const origin = new URL(baseURL).origin
  const traffic = { me: 0, unexpectedApi: [] as string[] }
  await page.route('**/*', (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const headers = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS' }
    // Sentry's ingestion URLs also begin /api, but are telemetry, not this app's API.
    if (url.hostname.endsWith('.sentry.io')) return route.abort()
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/internal/')) {
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
      if (url.pathname === '/api/auth/me') {
        traffic.me++
        return route.fulfill({ status: 401, headers, json: { detail: 'Not authenticated' } })
      }
      traffic.unexpectedApi.push(`${request.method()} ${url.pathname}`)
      return route.fulfill({ status: 404, headers, json: { detail: 'No backend is available: unexpected API request in the teaser case' } })
    }
    if (url.origin === origin && ['GET', 'HEAD'].includes(request.method())) return route.continue()
    return route.abort()
  })
  return traffic
}

/** Chromium's own text setting doubled (standard 32, fixed 26), confirmed taken: the root computes to 32px and the
    24rem query matches. */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => ({ root: getComputedStyle(document.documentElement).fontSize, narrow: matchMedia('(max-width: 24rem)').matches })), {
      message: 'the 200% text setting took: the root computes to 32px and the 24rem query matches',
    })
    .toEqual({ root: '32px', narrow: true })
}

for (const theme of THEMES) for (const profile of PROFILES) {
  test.describe(`analysis teaser window / ${theme} / ${profile.name}`, () => {
    const mobile = profile.width <= 390
    test.use({ viewport: { width: profile.width, height: profile.height }, isMobile: mobile, hasTouch: mobile, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block' })

    test("the upgrade action sits on the teaser's first screen", async ({ page, baseURL }) => {
      await page.addInitScript((theme) => {
        localStorage.setItem('theme', theme)
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
      }, theme)
      const traffic = await answerGuest(page, baseURL!)
      await page.goto('/analysis')
      const teaser = page.locator('[data-analysis-teaser]')
      await expect(teaser).toBeVisible()
      await expect(teaser.getByRole('button', { name: 'Upgrade to Pro', exact: true })).toBeVisible()
      await expect(page.locator('html')).toHaveClass(theme === 'dark' ? /\bdark\b/ : /^(?!.*\bdark\b)/)
      if (profile.doubleText) await doubleText(page)
      await page.evaluate(() => document.fonts.ready)
      await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))

      const g = await teaser.evaluate((root) => {
        const box = (el: Element) => el.getBoundingClientRect()
        const win = root.querySelector('[data-peek-locked]')!
        const preview = win.querySelector(':scope > [inert]')!
        const button = [...win.querySelectorAll('button')].find((el) => el.textContent?.trim() === 'Upgrade to Pro')!
        const pill = button.previousElementSibling!
        const masked: string[] = []
        for (let node: Element | null = button; node; node = node.parentElement) {
          if (getComputedStyle(node).maskImage !== 'none') masked.push(`${node.tagName.toLowerCase()}.${node.className}`)
        }
        return {
          teaserTop: box(root).top,
          windowTop: box(win).top,
          windowBottom: box(win).bottom,
          windowHeight: box(win).height,
          windowScrollHeight: win.scrollHeight,
          windowClientHeight: win.clientHeight,
          pillTop: box(pill).top,
          buttonBottom: box(button).bottom,
          previewMask: getComputedStyle(preview).maskImage,
          masked,
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
        }
      })
      const at = `${theme}, ${profile.name}`
      const offset = g.buttonBottom - g.teaserTop
      expect(offset, `${at}: the upgrade action's bottom edge is ${offset.toFixed(1)}px below the teaser's top, past one ${profile.height}px screen`).toBeLessThanOrEqual(profile.height)
      expect(g.windowHeight, `${at}: the locked preview is ${g.windowHeight.toFixed(1)}px tall, taller than the ${profile.height}px screen`).toBeLessThanOrEqual(profile.height)
      expect(g.windowScrollHeight, `${at}: the window holds no scroll of its own (${g.windowScrollHeight}px of content in a ${g.windowClientHeight}px window): the preview is cut at it`).toBeLessThanOrEqual(g.windowClientHeight + 1)
      const above = g.pillTop - g.windowTop
      const below = g.windowBottom - g.buttonBottom
      expect(Math.abs(above - below), `${at}: the pill and the action are centred in the window (${above.toFixed(1)}px above, ${below.toFixed(1)}px below)`).toBeLessThanOrEqual(1)
      expect(g.previewMask, `${at}: the preview fades out at its foot, opaque to transparent over its last quarter, top to bottom`).toMatch(/^linear-gradient\((?:to bottom, |180deg, )?rgb\(0, 0, 0\) 75%, rgba\(0, 0, 0, 0\)\)$/)
      expect(g.masked, `${at}: nothing around the upgrade action carries a mask, so the action is never faded`).toEqual([])
      expect(g.scrollWidth, `${at}: /analysis does not scroll sideways (scrollWidth ${g.scrollWidth}px, clientWidth ${g.clientWidth}px)`).toBeLessThanOrEqual(g.clientWidth)
      expect(traffic.me, 'the page read the session as a guest').toBeGreaterThan(0)
      expect(traffic.unexpectedApi, 'a guest on /analysis reads only the session').toEqual([])
    })
  })
}
