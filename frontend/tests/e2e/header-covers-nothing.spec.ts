import { test, expect, type Page } from '@playwright/test'
import { answerApi } from './fixtures/filing3Api'

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
 * Both bars on the filing page: below lg its section nav sticks under the site header, a second bar, and the
 * document's padding reserves it too (E164, chief design's ruling on #1521). The walk counts a stop hidden when it
 * lies wholly under the site header, or under the nav while the nav is stuck at the bar's foot; the nav's own chips
 * are measured against the site header alone. /filing/3 is walked at 390x844 at both text sizes, its API answered
 * from the filing fixtures (tests/e2e/fixtures/filing3Api.ts).
 *
 * The header's own stops: the padding steps aside while focus is inside the site header
 * (`html:has([data-site-header]:focus-within)`). The header is stuck in view, and the padding, which counts its
 * open mobile menu, scrolled the page behind the menu at every Tab through it (from 2,350px to the top in five
 * Tabs at 390px), and a control in the bar that took focus while the page was scrolled moved the page by half a
 * screen. With the page scrolled, the menu opened at 390x844 at both text sizes keeps the page where it is through
 * every Tab in it, and a Tab out of it lands on a control the open menu does not wholly cover, at the default size
 * inside the screen and below the menu (under 200% text the open menu fills the screen: E167); at 1440x900 a focus
 * on the bar's logo or theme toggle leaves the page where it is.
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
  // The header's auth check settles before a test scrolls: where the check changes the bar's lines (E173, E175) the
  // header still grows when it settles, and scroll anchoring then moves a page already scrolled by the difference,
  // which a test of the page holding still would read as a focus moving it; the held-check case below holds the
  // states where the header must keep its height (E174). Hidden
  // included: below lg the placeholder sits in the desktop block, display:none, until the check settles.
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
      // The filing page's section nav, while it reaches the bar's foot (stuck there, or leaving with its column), covers
      // what passes beneath it as the bar does; a chip of its own can only lie under the bar.
      const nav = document.querySelector('nav[aria-label="Jump to section"]')
      const n = nav?.getBoundingClientRect()
      const inNav = !!nav && nav.contains(el)
      const navCovers = !!n && n.height > 0 && n.top <= b.bottom + 1 && !inNav
      return { done: false as const, own, inBar, label: `${el.tagName.toLowerCase()} "${label}"`, top: r.top, bottom: r.bottom, barTop: b.top, barBottom: navCovers ? Math.max(b.bottom, n.bottom) : b.bottom, scrollY: window.scrollY }
    })
    if (stop.done) break
    stops++
    if (stops > MAX_STOPS) throw new Error(`the walk passed ${MAX_STOPS} stops without coming back round`)
    if (stop.inBar) reachedBar = true
    // The bar (and a stuck section nav below it) sits at the top of the viewport, so a stop that ends above its bottom
    // edge is wholly behind it (or above the screen altogether).
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

test.describe('a keyboard focus clears both bars / /filing/3 / 390px', () => {
  test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
  for (const doubled of [false, true]) {
    const name = `390px${doubled ? ' under 200% text' : ''}`
    test(`a Shift+Tab walk of /filing/3 finds no stop wholly under the bar or the section nav, ${name}`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('en:copilot-coachmark-v1', '1')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
      })
      await answerApi(page, baseURL!, 'anon')
      await page.goto('/filing/3')
      // Only a rendered summary has its section nav.
      await expect(page.getByRole('navigation', { name: 'Jump to section' })).toBeVisible()
      if (doubled) await doubleText(page)
      await settle(page)
      const walk = await walkBack(page)
      expect(walk.stops, `/filing/3, ${name}: the walk reached the page's stops`).toBeGreaterThan(3)
      expect(walk.reachedBar, `/filing/3, ${name}: the walk came back round to the site header`).toBe(true)
      expect(
        walk.hidden.map((s) => `${s.label} at ${s.top.toFixed(0)} to ${s.bottom.toFixed(0)}px, under bars ending at ${s.barBottom.toFixed(0)}px (scrollY ${s.scrollY.toFixed(0)})`),
        `/filing/3, ${name}: a focused control wholly behind the site header or the section nav`,
      ).toEqual([])
    })

    // The fixture's stops lie far apart, so the walk scrolls to each before it can settle under the nav. This puts one
    // there: the summary's first control, scrolled until it sits wholly under the stuck nav, then reached by a Shift+Tab
    // from the control after it. With the header's height alone in the padding, the browser left it there (at 73 to
    // 93px under a nav ending at 122px; 155 to 223px under 256px under 200% text).
    test(`a Shift+Tab onto a control the page scrolled under the section nav lands below both bars, ${name}`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('en:copilot-coachmark-v1', '1')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
      })
      await answerApi(page, baseURL!, 'anon')
      await page.goto('/filing/3')
      await expect(page.getByRole('navigation', { name: 'Jump to section' })).toBeVisible()
      if (doubled) await doubleText(page)
      await settle(page)
      const before = await page.evaluate(async () => {
        const nav = document.querySelector('nav[aria-label="Jump to section"]')!
        const stops = [...document.querySelectorAll<HTMLElement>('section[id] a[href], section[id] button')].filter((el) => el.getClientRects().length && !nav.contains(el))
        const [target, next] = stops
        const headerBottom = document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom
        window.scrollBy(0, target.getBoundingClientRect().top - headerBottom - 4)
        await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))
        target.dataset.underNav = ''
        next.focus({ preventScroll: true })
        const t = target.getBoundingClientRect()
        const n = nav.getBoundingClientRect()
        return { label: (target.getAttribute('aria-label') || target.textContent || '').trim(), top: t.top, bottom: t.bottom, navTop: n.top, navBottom: n.bottom, headerBottom }
      })
      expect(
        [Math.abs(before.navTop - before.headerBottom) <= 1, before.top >= before.headerBottom - 0.5, before.bottom <= before.navBottom + 0.5],
        `${name}: ${before.label} set wholly under the stuck section nav (${before.top.toFixed(0)} to ${before.bottom.toFixed(0)}px, the nav ${before.navTop.toFixed(0)} to ${before.navBottom.toFixed(0)}px)`,
      ).toEqual([true, true, true])
      await page.keyboard.press('Shift+Tab')
      const after = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement
        const r = el.getBoundingClientRect()
        return { onTarget: 'underNav' in el.dataset, top: r.top, bottom: r.bottom, navBottom: document.querySelector('nav[aria-label="Jump to section"]')!.getBoundingClientRect().bottom }
      })
      expect(after.onTarget, `${name}: the Shift+Tab reached ${before.label}`).toBe(true)
      expect(
        [after.top >= after.navBottom - 0.5, after.bottom <= 844.5],
        `${name}: ${before.label} lands at ${after.top.toFixed(0)} to ${after.bottom.toFixed(0)}px, below the section nav ending at ${after.navBottom.toFixed(0)}px and inside the screen`,
      ).toEqual([true, true])
    })

    // A focus inside the stuck nav drops the nav's share of the padding, or each chip would lie inside the reserved
    // strip and every Tab through them would scroll the page.
    test(`a Tab through the stuck section nav's chips leaves the page where it is, ${name}`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('en:copilot-coachmark-v1', '1')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
      })
      await answerApi(page, baseURL!, 'anon')
      await page.goto('/filing/3')
      const nav = page.getByRole('navigation', { name: 'Jump to section' })
      await expect(nav).toBeVisible()
      if (doubled) await doubleText(page)
      await settle(page)
      // Into the summary's second section, so the nav is stuck under the bar.
      const scrolled = await page.evaluate(async () => {
        const sections = [...document.querySelectorAll<HTMLElement>('section[id]')]
        window.scrollBy(0, sections[1].getBoundingClientRect().top - 300)
        await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))
        const n = document.querySelector('nav[aria-label="Jump to section"]')!.getBoundingClientRect()
        return { scrollY: window.scrollY, stuck: Math.abs(n.top - document.querySelector('[data-site-header]')!.getBoundingClientRect().bottom) <= 1 }
      })
      expect(scrolled.stuck, `${name}: the section nav is stuck under the bar`).toBe(true)
      const chips = nav.getByRole('link')
      const count = await chips.count()
      expect(count, `${name}: the nav has chips to walk`).toBeGreaterThan(1)
      await chips.first().evaluate((el: HTMLElement) => el.focus({ preventScroll: true }))
      for (let i = 1; i < count; i++) {
        await page.keyboard.press('Tab')
        const now = await page.evaluate(() => ({ scrollY: window.scrollY, inNav: !!document.querySelector('nav[aria-label="Jump to section"]')!.contains(document.activeElement) }))
        expect(now.inNav, `${name}: Tab ${i} stays in the nav`).toBe(true)
        expect(now.scrollY, `${name}: Tab ${i} through the section nav's chips moved the page from ${scrolled.scrollY}px`).toBe(scrolled.scrollY)
      }
    })
  }
})

test.describe("the site header's own stops hold the page in place", () => {
  for (const doubled of [false, true]) {
    const name = `390px${doubled ? ' under 200% text' : ''}`
    test.describe(name, () => {
      test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
      test('a Tab through the open menu keeps the page where it is, and a Tab out of it lands on a control the menu does not cover', async ({ page, baseURL }) => {
        await open(page, baseURL!, '/', 'light')
        if (doubled) await doubleText(page)
        await settle(page)
        await page.evaluate(() => window.scrollTo(0, 2000))
        await settle(page)
        // Opened from the keyboard, its toggle focused without a scroll, as a reader who had tabbed there would have it.
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
            expect(now.bottom, `${name}: a Tab out of the open menu lands on ${now.label} at ${now.top.toFixed(0)} to ${now.bottom.toFixed(0)}px, wholly under a header ending at ${now.barBottom.toFixed(0)}px`).toBeGreaterThan(now.barBottom + 0.5)
            // At the default size the open menu leaves room below it, and the control lands there, inside the screen. Under
            // 200% text the menu fills the screen and stays open, so the control lands past its foot: E167 closes the menu
            // when focus leaves it, and then holds this at both sizes.
            if (!doubled) {
              expect(
                [now.top >= now.barBottom - 0.5, now.bottom <= 844.5],
                `${name}: a Tab out of the open menu lands on ${now.label} at ${now.top.toFixed(0)} to ${now.bottom.toFixed(0)}px, inside the screen and below the open menu ending at ${now.barBottom.toFixed(0)}px`,
              ).toEqual([true, true])
            }
            break
          }
          tabs++
          expect(now.scrollY, `${name}: Tab ${tabs}, onto ${now.label} in the open menu, moved the page from ${opened.scrollY}px`).toBe(opened.scrollY)
          expect(tabs, `${name}: the walk through the open menu ends`).toBeLessThan(40)
        }
        expect(tabs, `${name}: the walk went through the menu's stops`).toBeGreaterThan(3)
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

/**
 * The header holds one height as its auth check settles (E174; chief design on #1538, comment 6375148655). The check
 * shows a 36px placeholder, then a guest's Log in and account links (the md button, 40px) or a signed-in reader's
 * 36px avatar, so the header was 61px while the check ran and for a reader, and 65px for a guest: when the check
 * settled for a guest the header grew 4px, and scroll anchoring moved a page already scrolled by those 4px. The
 * desktop controls block takes min-h-10, the md button's height, so every state gives the 65px header (217px at 1440px
 * and 313px at 1024px under 200% text, where it grew 8px). With the check held open the page is scrolled, then the
 * check is answered (a guest's 401, or a reader), and the header keeps its height and the page its place. The bar
 * must keep its lines in every state for the height to hold, so the states are 1280 and 1440px at the default size
 * and 1024 and 1440px under 200% text. Where the check changes the bar's lines it does not hold yet: at 1024 to
 * 1031px a guest's bar wraps where a reader's does not (E173), and under 200% text at 1280px the placeholder fits
 * beside the nav where the settled controls do not, and at 390px a guest's account link wraps (E175). At 1440px under
 * 200% text the logo and the nav share the first line in CI's fonts; in fonts where they miss it by a few pixels a
 * guest's bar gains a line as the check settles too (E175, chief design on #1544).
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

const headerAt = (page: Page) =>
  page.evaluate(() => ({ height: document.querySelector('header[data-site-header]')!.getBoundingClientRect().height, scrollY: window.scrollY }))

const HELD_STATES = [
  { width: 1280, doubled: false },
  { width: 1440, doubled: false },
  { width: 1024, doubled: true },
  { width: 1440, doubled: true },
]

test.describe('the site header holds one height as its auth check settles (E174)', () => {
  for (const { width, doubled } of HELD_STATES) {
    for (const who of ['guest', 'reader'] as const) {
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
          const settled = page.getByRole('banner').getByRole(who === 'guest' ? 'link' : 'button', { name: who === 'guest' ? 'Log in' : 'Account menu' })
          await expect(settled, `the bar shows ${who === 'guest' ? "a guest's Log in" : "a reader's account menu"} once the check settles`).toBeVisible()
          await settle(page)
          const after = await headerAt(page)
          expect(after.height, `the header while the check ran (${pending.height}px) and after (${after.height}px)`).toBe(pending.height)
          expect(after.scrollY, `the page scrolled to ${pending.scrollY}px while the check ran`).toBe(pending.scrollY)
        })
      })
    }
  }
})
