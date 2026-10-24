import { test, expect, type Page } from '@playwright/test'
import { PANE, answerApi } from './fixtures/filing3Api'
import { ACCESS_COPY } from '../../features/marketing/lib/access'

/**
 * The site header (components/Header.tsx) is the one bar that sticks at the top of the viewport, and it covers
 * nothing a reader scrolls or tabs to: chief design's two rulings on PR #1515 (comment 6362491933).
 *
 * The page header: a page's own header (components/SecondaryHeader.tsx) scrolls with the page. It stuck at `top-0` under the
 * site header: once /pricing scrolled, its title showed through the bar's translucent ground beside a second logo
 * mark, its last pixels hung below the bar as a blurred band, and a click at its back link's centre landed on the
 * site header. At 390x844 and 1440x900, in both themes, once the page has scrolled past the page header, the page
 * header is off the screen, and it sits on an opaque ground with no blur, since nothing passes under it.
 *
 * Keyboard focus: the document's `scroll-padding-top` reads the header's height (app/globals.css), so a focused control is
 * scrolled clear of the bar (WCAG 2.2 SC 2.4.11, Focus Not Obscured). Without it Chromium treats a control behind
 * the sticky bar as already in view and leaves it there: on main a Shift+Tab walk found the landing's Trace to
 * Source chip wholly under the bar at the default text size, and under 200% text the footer's links, the search
 * field, "Upgrade to Pro" and "Request an invite". The walk runs Shift+Tab from each page's last stop to its first
 * on /, /pricing and /analysis, at 390x844 and 1440x900, at the default text size and under a 200% text setting,
 * and finds no stop wholly under the bar. The bar's own controls are its own, and fixed chrome (the skip link, the
 * launchers) does not scroll, so neither is a page stop here, and the walk must reach the bar, so a walk cut short
 * fails. The walk runs in the light theme: a theme changes no geometry the walk reads.
 *
 * The header's own stops: the padding steps aside while focus is inside the site header
 * (`html:has([data-site-header]:focus-within)`). The header is stuck in view, and the padding, which counts its
 * open mobile menu, scrolled the page behind the menu at every Tab through it (from 2,350px to the top in five
 * Tabs at 390px), and a control in the bar that took focus while the page was scrolled moved the page by half a
 * screen. With the page scrolled, the menu opened at 390x844 at both text sizes keeps the page where it is through
 * every Tab in it, and a Tab out of it closes the menu and lands on a control inside the screen and below the bar;
 * at 1440x900 a focus on the bar's logo or theme toggle leaves the page where it is.
 *
 * The open menu is a disclosure: it closes when focus leaves the header (E167, chief design's ruling on #1521). Under
 * 200% text the open menu fills the screen, and it stayed open when a Tab left it, so the next control was scrolled
 * into view past the screen's foot (784 to 904px). It closes inside the focusout, before the browser scrolls the
 * next control into view, or that scroll would still reserve the open menu's height; a focus moved by script out
 * of the open menu, which leaves no microtask between the two, closes it and lands below the bar too.
 *
 * 200% text is Chromium's own text setting (`Page.setFontSizes`, as tests/e2e/reflow-200.spec.ts doubles it), not
 * an inline style on <html>, which no media query reads. CI runs e2e with no backend
 * (lessons/test-e2e-runs-without-backend.md), and the build may name a production API host, so every API request is
 * answered here in the browser whatever its host: the session check 401 (a guest), any other API path 404; every
 * other request but the frontend's own GET and HEAD is aborted. The filing pane's case answers the API from
 * fixtures/filing3Api.ts, for a Pro reader. The consent bar is answered before load, so its bottom inset is not in
 * play.
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
  // The header's auth check settles before a test scrolls: where the check changes the phone bar's lines (below about
  // 15rem, a band chief design accepts) the header still grows when it settles, and scroll anchoring then moves a page
  // already scrolled by the difference, which a test of the page holding still would read as a focus moving it; the
  // held-check case below holds the states where the header must keep its height (E174, E173, E175). Hidden included:
  // below 72rem the placeholder sits in the full bar's controls, display:none, until the check settles.
  await expect(page.getByRole('status', { name: 'Checking whether you are logged in', includeHidden: true })).toHaveCount(0)
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
async function walkBack(page: Page): Promise<{ stops: number; reachedBar: boolean; hidden: Stop[] }> {
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
  let reachedBar = false
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
      const inBar = bar.contains(el)
      const own = inBar || fixed || r.width === 0 || r.height === 0
      return { done: false as const, own, inBar, label: `${el.tagName.toLowerCase()} "${label}"`, top: r.top, bottom: r.bottom, barTop: b.top, barBottom: b.bottom, scrollY: window.scrollY }
    })
    if (stop.done) break
    stops++
    if (stops > MAX_STOPS) throw new Error(`the walk passed ${MAX_STOPS} stops without coming back round`)
    if (stop.inBar) reachedBar = true
    // The bar sits at the top of the viewport, so a stop that ends above its bottom edge is wholly behind it (or above
    // the screen altogether).
    if (!stop.own && stop.bottom <= stop.barBottom + 0.5) {
      hidden.push({ label: stop.label, top: stop.top, bottom: stop.bottom, barBottom: stop.barBottom, scrollY: stop.scrollY })
    }
  }
  return { stops, reachedBar, hidden }
}

/** The page's scroll, the focused control's box and whether it sits inside the site header. */
async function focusState(page: Page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null
    const bar = document.querySelector('[data-site-header]')
    if (!el || !bar) throw new Error('no focus or no site header')
    const r = el.getBoundingClientRect()
    const label = (el.getAttribute('aria-label') || el.textContent || el.tagName).replace(/\s+/g, ' ').trim().slice(0, 40)
    return { scrollY: window.scrollY, inHeader: bar.contains(el), label, top: r.top, bottom: r.bottom, barBottom: bar.getBoundingClientRect().bottom }
  })
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
          expect(walk.reachedBar, `${route}, ${name}: the walk came back round to the site header`).toBe(true)
          expect(
            walk.hidden.map((s) => `${s.label} at ${s.top.toFixed(0)} to ${s.bottom.toFixed(0)}px, under a bar ending at ${s.barBottom.toFixed(0)}px (scrollY ${s.scrollY.toFixed(0)})`),
            `${route}, ${name}: a focused control wholly behind the site header`,
          ).toEqual([])
        })
      })
    }
  }
}

/**
 * The open-menu walk: with the page scrolled to 2000px the menu is opened from the keyboard, its toggle focused without
 * a scroll, as a reader who had tabbed there would have it. A Tab through it keeps the page where it is, and a Tab out
 * of it closes the menu and lands on a control inside the screen and below the bar.
 */
async function walkTheOpenMenu(page: Page, name: string, screenHeight: number) {
  await page.evaluate(() => window.scrollTo(0, 2000))
  await settle(page)
  await page.getByRole('button', { name: 'Open menu' }).evaluate((el: HTMLElement) => el.focus({ preventScroll: true }))
  await page.keyboard.press('Enter')
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible()
  await settle(page)
  const opened = await focusState(page)
  expect(opened.scrollY, `${name}: the page is scrolled before the menu's walk`).toBeGreaterThan(1000)
  let tabs = 0
  for (;;) {
    await page.keyboard.press('Tab')
    const now = await focusState(page)
    if (!now.inHeader) {
      await expect(page.getByRole('navigation', { name: 'Mobile navigation' }), `${name}: a Tab out of the open menu, onto ${now.label}, closes it`).toHaveCount(0)
      expect(
        [now.top >= now.barBottom - 0.5, now.bottom <= screenHeight + 0.5],
        `${name}: a Tab out of the open menu lands on ${now.label} at ${now.top.toFixed(0)} to ${now.bottom.toFixed(0)}px, inside the screen and below the bar ending at ${now.barBottom.toFixed(0)}px`,
      ).toEqual([true, true])
      break
    }
    tabs++
    expect(now.scrollY, `${name}: Tab ${tabs}, onto ${now.label} in the open menu, moved the page from ${opened.scrollY}px`).toBe(opened.scrollY)
    expect(tabs, `${name}: the walk through the open menu ends`).toBeLessThan(40)
  }
  expect(tabs, `${name}: the walk went through the menu's stops`).toBeGreaterThan(3)
}

test.describe("the site header's own stops hold the page in place", () => {
  for (const doubled of [false, true]) {
    const name = `390px${doubled ? ' under 200% text' : ''}`
    test.describe(name, () => {
      test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
      test('a Tab through the open menu keeps the page where it is, and a Tab out of it closes the menu and lands below the bar', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/', 'light')
        if (doubled) await doubleText(page)
        await settle(page)
        await walkTheOpenMenu(page, name, 844)
      })

      // A tap or a click moves focus to what it presses on its mousedown, before its release. The header is in the
      // page's flow, and at the top of a page nothing anchors the scroll, so a menu that closed on that focusout moved
      // the page under the finger and the release followed nothing. A press leaves the menu open, as before (chief
      // design's ruling on #1542), and the navigation it starts closes it. Under 200% text the open menu fills the
      // screen, so no page control shows below it to press.
      if (!doubled) {
        test('a tap on a page link below the open menu, at the top of the page, follows it, and the next page opens with the menu closed', async ({ page, baseURL }) => {
          await open(page, baseURL!, '/', 'light')
          await settle(page)
          expect(await page.evaluate(() => window.scrollY), `${name}: the page is at its top`).toBe(0)
          const toggle = (await page.getByRole('button', { name: 'Open menu' }).boundingBox())!
          await page.touchscreen.tap(toggle.x + toggle.width / 2, toggle.y + toggle.height / 2)
          await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible()
          await settle(page)
          const target = await page.evaluate(() => {
            const menuEnd = document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom
            const link = [...document.querySelectorAll<HTMLAnchorElement>('main a[href^="/"]')].find((a) => {
              const r = a.getBoundingClientRect()
              return r.width > 0 && r.top > menuEnd + 8 && r.bottom < window.innerHeight - 8
            })
            if (!link) return null
            const r = link.getBoundingClientRect()
            return { href: link.getAttribute('href')!, label: link.textContent!.replace(/\s+/g, ' ').trim(), x: r.x + r.width / 2, y: r.y + r.height / 2, menuEnd }
          })
          expect(target, `${name}: a page link shows below the open menu`).not.toBeNull()
          await page.touchscreen.tap(target!.x, target!.y)
          await expect(page, `${name}: a tap on "${target!.label}" at ${target!.y.toFixed(0)}px, below the open menu ending at ${target!.menuEnd.toFixed(0)}px, follows it`).toHaveURL(
            (url) => url.pathname === target!.href,
          )
          await expect(page.getByRole('navigation', { name: 'Mobile navigation' }), `${name}: ${target!.href} opens with the menu closed`).toHaveCount(0)
        })
      }

      // A focus moved by script runs with script on the stack, so no microtask runs between the focusout and the
      // browser's scroll: only a close inside the focusout clears the open menu's height from the padding in time.
      // Without it, under 200% text, the control landed at 91 to 211px, partly under a 151px bar.
      test('a focus moved by script out of the open menu closes it and lands below the bar', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/', 'light')
        if (doubled) await doubleText(page)
        await settle(page)
        await page.evaluate(() => window.scrollTo(0, 2000))
        await settle(page)
        await page.getByRole('button', { name: 'Open menu' }).evaluate((el: HTMLElement) => el.focus({ preventScroll: true }))
        await page.keyboard.press('Enter')
        await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible()
        await settle(page)
        await page.locator('main').locator('a[href], button').first().evaluate((el: HTMLElement) => el.focus())
        await settle(page)
        const now = await focusState(page)
        await expect(page.getByRole('navigation', { name: 'Mobile navigation' }), `${name}: a focus moved by script onto ${now.label} closes the open menu`).toHaveCount(0)
        expect(
          [now.inHeader, now.top >= now.barBottom - 0.5, now.bottom <= 844.5],
          `${name}: a focus moved by script out of the open menu lands on ${now.label} at ${now.top.toFixed(0)} to ${now.bottom.toFixed(0)}px, inside the screen and below the bar ending at ${now.barBottom.toFixed(0)}px`,
        ).toEqual([false, true, true])
      })
    })
  }

  test.describe('1440px', () => {
    test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
    test("a focus on the bar's own controls leaves the page where it is", async ({ page, baseURL }) => {
      await open(page, baseURL!, '/', 'light')
      await settle(page)
      for (const control of [page.getByRole('link', { name: 'EarningsNerd home' }), page.getByRole('button', { name: /Switch to (dark|light) mode/ })]) {
        await page.evaluate(() => window.scrollTo(0, 2000))
        await settle(page)
        await control.first().evaluate((el: HTMLElement) => el.focus())
        await settle(page)
        const now = await focusState(page)
        expect(now.inHeader, `the focus is on ${now.label}, in the site header`).toBe(true)
        expect(now.scrollY, `a focus on ${now.label} in the bar moved the page from 2000px`).toBe(2000)
      }
    })
  })
})

// From lg the compact bar stands where the full bar did below 72rem, so under 200% text its menu opens on a desktop too,
// where a signed-in reader's fills the screen (chief design on #1558, comment 6377073723): the same walk at 1440x900.
test.describe("the site header's own stops hold the page in place / 1440x900 under 200% text, a signed-in reader", () => {
  test.use({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
  test('a Tab through the open menu keeps the page where it is, and a Tab out of it closes the menu and lands below the bar', async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
      localStorage.setItem('en_session_active', '1')
    })
    const release = await answerHeld(page, baseURL!, 'reader')
    release()
    await page.goto('/')
    await expect(page.getByRole('status', { name: 'Checking whether you are logged in', includeHidden: true })).toHaveCount(0)
    await doubleText(page)
    await settle(page)
    await expect(page.getByRole('button', { name: 'Open menu' }), 'the compact bar shows at 1440px under 200% text').toBeVisible()
    await expect(page.getByRole('button', { name: /^Notifications/ }), "and a signed-in reader's bell in it").toBeVisible()
    await walkTheOpenMenu(page, '1440x900 under 200% text, a signed-in reader', 900)
  })
})

/** From lg the open menu lies over the page, so a press outside the header closes it, as it closes the bar's other
    menus, and the press still lands where it was aimed (E182, chief design on #1565, comment 6380050139): the header
    keeps the bar's height, so nothing moves under the pointer. On / at 1024x768 and 1100x800, a guest's page is
    scrolled so the pricing row's billing switch, its Monthly choice unchosen (it opens on Annual), shows below where
    the open menu reaches; a click on it closes the menu and chooses it, and the page stays where it was. Below lg the
    menu sits in the header's flow, and a press leaves it open (E167, the tap case above). Under 200% text the open
    menu fills the screen, so no page control shows below it to press. */
test.describe('from lg a press on the page closes the open menu and reaches its target', () => {
  for (const viewport of [{ width: 1024, height: 768 }, { width: 1100, height: 800 }]) {
    test.describe(`${viewport.width}x${viewport.height}`, () => {
      test.use({ viewport, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
      test('a click on a control below the open menu closes the menu and reaches the control', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/', 'light')
        await settle(page)
        const label = 'Monthly'
        const target = page.getByRole('radio', { name: label, exact: true })
        await expect(target, 'the billing switch opens on Annual, Monthly unchosen').toHaveAttribute('aria-checked', 'false')
        // Its middle a quarter of the screen above the foot, below where the open menu reaches, scrolled there again
        // until it rests there: the landing's sections above it can still grow after the first scroll.
        await expect
          .poll(
            async () => {
              const off = await target.evaluate((el) => {
                const r = el.getBoundingClientRect()
                const by = r.top + r.height / 2 - window.innerHeight * 0.75
                window.scrollBy(0, by)
                return Math.abs(by)
              })
              await settle(page)
              return off
            },
            { message: `${viewport.width}px: "${label}" rests a quarter of the screen above its foot` },
          )
          .toBeLessThanOrEqual(1)
        // A click at the toggle's box, as a pointer presses it: Playwright's own click first scrolls a sticky element's
        // box into view, which moved this page 400px.
        const toggle = (await page.getByRole('button', { name: 'Open menu' }).boundingBox())!
        await page.mouse.click(toggle.x + toggle.width / 2, toggle.y + toggle.height / 2)
        const menu = page.getByRole('navigation', { name: 'Mobile navigation' })
        await expect(menu).toBeVisible()
        await settle(page)
        const at = await target.evaluate((el) => {
          const r = el.getBoundingClientRect()
          const menuEnd = document.querySelector('nav[aria-label="Mobile navigation"]')!.parentElement!.getBoundingClientRect().bottom
          return { x: r.x + r.width / 2, y: r.y + r.height / 2, menuEnd, scrollY: window.scrollY, foot: window.innerHeight }
        })
        expect(at.y, `${viewport.width}px: "${label}" sits below the open menu, which ends at ${Math.round(at.menuEnd)}px`).toBeGreaterThan(at.menuEnd + 8)
        expect(at.y, `${viewport.width}px: "${label}" sits inside the screen, whose foot is at ${at.foot}px`).toBeLessThan(at.foot - 8)
        await page.mouse.click(at.x, at.y)
        await expect(menu, `${viewport.width}px: the press on the page closes the open menu`).toHaveCount(0)
        await expect(target, `${viewport.width}px: the press reaches "${label}", which is now chosen`).toHaveAttribute('aria-checked', 'true')
        expect(await page.evaluate(() => window.scrollY), `${viewport.width}px: the page stays where it was`).toBe(at.scrollY)
      })
    })
  }
})

/**
 * From lg the open compact menu lies over the page under the bar, as the bar's other menus do, and the height the
 * header publishes leaves it out (chief design on #1558, comment 6377356358). In the header's flow the open menu
 * pushed the page down and grew --site-header-h, so the filing workspace's pane, which runs from its own top to the
 * screen's foot, shrank under it: at 1100x800 from 550 to 12px, and under 200% text from 254 to 0px. At 1100x800 on
 * /filing/3, a Pro reader with the pane open, at both text sizes, at the top of the page and with the page scrolled
 * so the pane sticks under the bar: with the menu open the pane keeps its top and its height, the page its scroll, and
 * the header publishes the bar's height; the menu lies over the pane, the header's layer above it, and ends inside the
 * screen.
 */
test.describe('from lg the open menu lies over the page / 1100x800, a Pro reader on /filing/3', () => {
  test.use({ viewport: { width: 1100, height: 800 }, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
  for (const doubled of [false, true]) {
    const size = doubled ? '200% text' : 'the default text size'
    test(`at ${size}, the open menu leaves the filing pane its top and its height`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('en_session_active', '1')
        localStorage.setItem('en:copilot-coachmark-v1', '1')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
      })
      await answerApi(page, baseURL!, 'pro')
      await page.goto('/filing/3')
      await page.getByRole('button', { name: 'Source', exact: true }).click()
      const pane = page.locator(PANE)
      await expect(pane).toBeVisible()
      if (doubled) await doubleText(page)
      await settle(page)
      await expect(page.getByRole('button', { name: 'Open menu' }), `${size}: the compact bar shows at 1100px`).toBeVisible()
      const menu = page.getByRole('navigation', { name: 'Mobile navigation' })
      const read = () =>
        pane.evaluate((el) => {
          const r = el.getBoundingClientRect()
          return { top: Math.round(r.top), height: Math.round(r.height), published: document.documentElement.style.getPropertyValue('--site-header-h'), scrollY: window.scrollY }
        })

      for (const scrolled of [false, true]) {
        const where = `${size}, ${scrolled ? 'the page scrolled' : 'the top of the page'}`
        if (scrolled) {
          await page.evaluate(() => window.scrollTo(0, 1200))
          await settle(page)
        }
        const closed = await read()
        expect(closed.height, `${where}: the pane is open with the menu closed`).toBeGreaterThan(200)
        if (scrolled) expect(closed.top, `${where}: the pane sticks under the bar`).toBe(parseInt(closed.published))
        await page.getByRole('button', { name: 'Open menu' }).click()
        await expect(menu).toBeVisible()
        await settle(page)
        const opened = await read()
        expect(opened, `${where}: with the menu open the pane keeps its top and height (${closed.top}px, ${closed.height}px), the page its scroll, and the header the bar's published height`).toEqual(closed)
        // A point 8px inside the pane's top left corner: the open menu reaches below it, and lies over it.
        const point = await pane.evaluate((el) => ({ x: el.getBoundingClientRect().left + 8, y: el.getBoundingClientRect().top + 8 }))
        const over = await menu.locator('xpath=..').evaluate((panel, { x, y }) => {
          const hit = document.elementFromPoint(x, y)
          return { bottom: panel.getBoundingClientRect().bottom, hitsMenu: hit !== null && panel.contains(hit) }
        }, point)
        expect(over.bottom, `${where}: the open menu reaches the pane's top`).toBeGreaterThan(point.y)
        expect(over.hitsMenu, `${where}: the open menu lies over the pane, the header's layer above it`).toBe(true)
        expect(over.bottom, `${where}: the open menu ends inside the 800px screen`).toBeLessThanOrEqual(800.5)
        await page.getByRole('button', { name: 'Close menu' }).click()
        await expect(menu).toHaveCount(0)
      }
    })
  }
})

/**
 * The header holds one height as its auth check settles (E174, chief design on #1538, comment 6375148655; E173 and
 * E175, on #1544, comment 6375980005). The check shows a 36px placeholder, then a guest's Log in and account links
 * (the md button, 40px) or a signed-in reader's 36px avatar: the full bar's controls take min-h-10, the md button's
 * height, so every state gives it one height. The check also changed the full bar's lines: a guest's row wrapped at
 * 1024 to 1031px (E173), and with the text doubled the placeholder shared a line the settled controls could not
 * (E175). The full bar now shows only from 72rem, where it keeps one line with its widest settled controls, and the
 * compact bar below it keeps one line from 1024px. With the check held open the page is scrolled, then the check is
 * answered (a guest's 401, or a reader), and the header keeps its height and the page its place, in the bar each width
 * shows: the compact bar at 1024px and the full bar at 1152px (72rem) and 1440px at the default size; with the text
 * doubled the compact bar at 1024 and 1440px and the full bar at 2304px.
 *
 * The nav keeps its place too (E175, chief design on #1558, comment 6377073723): the full bar's controls cell keeps a
 * guest's width whatever the check shows, a hidden copy of a guest's controls in the live ones' grid cell, so in each
 * full-bar state the nav's left edge holds as the check settles, where it moved 109px for a guest and 35px for a reader
 * at 1152px. The wordmark shows from 40rem, 1280px with the text doubled, so a guest's compact bar keeps one line at
 * 640 and 800px under 200% text as well, where it grew 14px with "Sign up" and 88px with "Request invite"; a reader's
 * holds there too, as its notification bell joins the bar (E176). A build answers one access mode, so a guest's
 * compact link then takes each mode's label in turn (a copy fixture), and the header keeps the height it had while the
 * check was held. Below about 15rem (480px under 200% text) a guest's link cannot share the logo's line, so the bar
 * still grows as it appears: chief design accepts that band, since any reservation would give every reader the extra
 * row.
 */
async function answerHeld(page: Page, baseURL: string, who: 'guest' | 'reader'): Promise<() => void> {
  const origin = new URL(baseURL).origin
  let release!: () => void
  const held = new Promise<void>((done) => (release = done))
  if (who === 'reader') await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route('**/*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const headers = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS' }
    if (url.hostname.endsWith('.sentry.io')) return route.abort()
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/internal/')) {
      if (request.method() === 'OPTIONS') return route.fulfill({ status: 204, headers })
      if (url.pathname === '/api/auth/me') {
        await held
        return who === 'reader'
          ? route.fulfill({ status: 200, headers, json: { id: 1, email: 'pro@example.com', full_name: 'Pro User', is_pro: true, is_beta: false, is_admin: false, email_verified: true } })
          : route.fulfill({ status: 401, headers, json: { detail: 'Not authenticated' } })
      }
      return route.fulfill({ status: 404, headers, json: { detail: 'No backend is available in the header case' } })
    }
    if (url.origin === origin && ['GET', 'HEAD'].includes(request.method())) return route.continue()
    return route.abort()
  })
  return release
}

/** The header's height, the page's scroll, and the full bar's nav's left edge where it shows. */
const headerAt = (page: Page) =>
  page.evaluate(() => {
    const header = document.querySelector('header[data-site-header]')!
    const nav = header.querySelector('nav[aria-label="Main navigation"]')!.getBoundingClientRect()
    return { height: header.getBoundingClientRect().height, scrollY: window.scrollY, navLeft: nav.width > 0 ? nav.left : null }
  })

const HELD_STATES = [
  { width: 1024, doubled: false, bar: 'compact' },
  { width: 1152, doubled: false, bar: 'full' },
  { width: 1440, doubled: false, bar: 'full' },
  { width: 1024, doubled: true, bar: 'compact' },
  { width: 1440, doubled: true, bar: 'compact' },
  { width: 2304, doubled: true, bar: 'full' },
  { width: 640, doubled: true, bar: 'compact' },
  { width: 800, doubled: true, bar: 'compact' },
  // A signed-in reader's phone bar, where the bell joins it as the check settles (E176): one row at 320px at the default
  // size and at 360 and 390px under 200% text. A guest's link takes a row of its own there, the band accepted on #1565,
  // and below about 10.4rem (332px under 200% text) a reader's bell does too.
  { width: 320, doubled: false, bar: 'compact', only: 'reader' },
  { width: 360, doubled: true, bar: 'compact', only: 'reader' },
  { width: 390, doubled: true, bar: 'compact', only: 'reader' },
] as const
/** The compact bar's account link (ACCESS_COPY's ctaShort, for either access mode). */
const ACCOUNT_SHORT = /^(Sign up|Request invite)$/

test.describe('the site header holds one height as its auth check settles (E174, E173, E175)', () => {
  for (const state of HELD_STATES) {
    const { width, doubled, bar } = state
    for (const who of 'only' in state ? [state.only] : (['guest', 'reader'] as const)) {
      test.describe(`${width}px${doubled ? ' and 200% text' : ''}, ${who === 'guest' ? 'a guest' : 'a signed-in reader'}`, () => {
        test.use({ viewport: { width, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
        test('the header keeps its height, and a scrolled page its place, when the check settles', async ({ page, baseURL }) => {
          await page.addInitScript((reader) => {
            localStorage.setItem('theme', 'light')
            localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
            if (reader) localStorage.setItem('en_session_active', '1')
          }, who === 'reader')
          const release = await answerHeld(page, baseURL!, who)
          await page.goto('/')
          const placeholder = page.getByRole('status', { name: 'Checking whether you are logged in', includeHidden: true })
          await expect(placeholder, 'the check is held open, its placeholder in the bar').not.toHaveCount(0)
          if (doubled) await doubleText(page)
          await settle(page)
          await page.evaluate(() => window.scrollTo(0, 2000))
          await settle(page)
          const pending = await headerAt(page)
          expect(pending.scrollY, 'the page is scrolled while the check is held').toBeGreaterThan(1000)

          release()
          await expect(placeholder).toHaveCount(0)
          const banner = page.getByRole('banner')
          const nav = banner.getByRole('navigation', { name: 'Main navigation' })
          if (bar === 'full') {
            await expect(nav, `the full bar at ${width}px`).toBeVisible()
          } else {
            await expect(banner.getByRole('button', { name: 'Open menu' }), `the compact bar at ${width}px`).toBeVisible()
            await expect(nav, `the full bar's nav hidden at ${width}px`).toBeHidden()
          }
          // The settled controls: the full bar's Log in or account menu, or the compact bar's account link for a guest and
          // its notification bell for a reader, at every width since E176, so a reader's compact bar holds its height as
          // the bell appears.
          const settled = bar === 'full'
            ? banner.getByRole(who === 'guest' ? 'link' : 'button', { name: who === 'guest' ? 'Log in' : 'Account menu' })
            : banner.getByRole(who === 'guest' ? 'link' : 'button', { name: who === 'guest' ? ACCOUNT_SHORT : /^Notifications/ })
          await expect(settled, `the ${bar} bar shows a ${who}'s controls once the check settles`).toBeVisible()
          await settle(page)
          const after = await headerAt(page)
          expect(after.height, `the header while the check ran (${pending.height}px) and after (${after.height}px)`).toBe(pending.height)
          expect(after.scrollY, `the page scrolled to ${pending.scrollY}px while the check ran`).toBe(pending.scrollY)
          if (bar === 'full') {
            expect(pending.navLeft, 'the full bar shows its nav while the check is held').not.toBeNull()
            expect(Math.abs(after.navLeft! - pending.navLeft!), `the nav's left edge while the check ran (${pending.navLeft}px) and after (${after.navLeft}px)`).toBeLessThanOrEqual(0.5)
          }
          // Each access mode's compact label in turn, as a copy fixture: the header keeps its held height with either.
          if (bar === 'compact' && who === 'guest') {
            for (const label of [ACCESS_COPY.invite.ctaShort, ACCESS_COPY.public.ctaShort]) {
              await settled.evaluate((link, text) => {
                link.textContent = text
              }, label)
              await settle(page)
              const held = await headerAt(page)
              expect(held.height, `the header with a guest's "${label}" (${held.height}px), as while the check ran (${pending.height}px)`).toBe(pending.height)
            }
          }
        })
      })
    }
  }
})
