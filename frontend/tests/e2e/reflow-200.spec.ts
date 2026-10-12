import { test, expect, type Locator, type Page } from '@playwright/test'
import { answerApi, API_ORIGIN } from './fixtures/filing3Api'

/**
 * No sideways scroll at 200% text on a phone. At 390x844, at the default text size and with the
 * browser's text size doubled, no public route and no filing page scrolls horizontally: the
 * document's scroll width never exceeds its client width.
 *
 * What is doubled is the browser's own text setting (Chromium's `Page.setFontSizes`: standard 16 to
 * 32, fixed 13 to 26), not an inline style on <html>. Both double every rem on the page, but only the
 * setting reaches a media query, whose rem is the browser's default font size and never the root
 * element's style. A Button keeps its label on one line except in a viewport narrower than 24rem
 * (components/ui/Button.tsx): 384px at the default size, 768px at 200%. An inline style would leave
 * that query at 384px and test a state no reader is in, so each case first confirms the setting took:
 * the root computes to 32px and the 24rem query matches.
 *
 * Before the fix each route with the site header measured 552px at 200% (its theme toggle and account
 * link) and each auth page 576px (the auth shell's top bar); with those wrapping, Button labels ("See a
 * live example", "Ask this filing") and one long heading word on /waitlist were next. Each case checks
 * that chrome is on the page, so a route that fails to render cannot pass empty. On a failure the
 * message lists the widest elements and text runs past the viewport edge, outside any clipping box.
 *
 * The scroll width alone cannot see a bar that squeezes instead of wrapping: its controls may shrink
 * (min-w-0) until a label spills over its neighbours, with nothing past the edge. So in the header or
 * the auth bar no two controls overlap, and no control's text paints beyond its own box sideways.
 *
 * Consent is seeded, so the consent bar stays closed: it is fixed, adds nothing to the document's
 * scroll width, and its own reflow is not measured here. Light theme only, since a theme changes no
 * geometry. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API origin is
 * answered in the browser, as a guest, and the filing page from fixtures/filing3Api.ts.
 */

type Route = {
  name: string
  path: string
  status?: number
  open: (page: Page, baseURL: string) => Promise<void>
  ready: (page: Page) => Promise<void>
  /** The control that overflowed before the fix, which must be on the page when it is measured. */
  chrome: (page: Page) => Locator
  /** The bar that holds it, whose controls must neither overlap nor spill their text. */
  bar: (page: Page) => Locator
}

/** A guest: the session check answers 401, so the header settles on its signed-out link; nothing else is served. */
async function answerGuest(page: Page, baseURL: string) {
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) =>
    new URL(route.request().url()).pathname === '/api/auth/me'
      ? route.fulfill({ status: 401, headers: cors, json: { detail: 'Not authenticated' } })
      : route.fulfill({ status: 404, headers: cors, json: { detail: 'Not found' } }),
  )
}

/** The site header: its mobile account link (ACCESS_COPY's ctaShort for either access mode). A page's
    own header (SecondaryHeader on /pricing and the filing page) is a banner too, without that link. */
const ACCOUNT = /^(Sign up|Request invite)$/
const siteHeader = {
  chrome: (page: Page) => page.getByRole('banner').getByRole('link', { name: ACCOUNT }),
  bar: (page: Page) => page.getByRole('banner').filter({ has: page.getByRole('link', { name: ACCOUNT }) }),
}
/** The auth shell has no site header; its top bar's "Back to home" link sat past the edge. */
const authShellBar = {
  chrome: (page: Page) => page.getByRole('link', { name: 'Back to home' }),
  bar: (page: Page) => page.getByRole('link', { name: 'Back to home' }).locator('xpath=../..'),
}
const h1 = (page: Page, name?: string) => expect(page.getByRole('heading', { level: 1, name })).toBeVisible()

const ROUTES: Route[] = [
  { name: 'home', path: '/', open: answerGuest, ready: (p) => h1(p), ...siteHeader },
  { name: 'pricing', path: '/pricing', open: answerGuest, ready: (p) => h1(p, 'Pricing'), ...siteHeader },
  { name: 'waitlist', path: '/waitlist', open: answerGuest, ready: (p) => h1(p), ...siteHeader },
  { name: 'login', path: '/login', open: answerGuest, ready: (p) => h1(p, 'Welcome back'), ...authShellBar },
  { name: 'register', path: '/register', open: answerGuest, ready: (p) => h1(p, 'Create your account'), ...authShellBar },
  { name: 'not found', path: '/no-such-page', status: 404, open: answerGuest, ready: (p) => h1(p, 'Page not found'), ...siteHeader },
  {
    name: 'filing',
    path: '/filing/3',
    open: (p, b) => answerApi(p, b, 'anon'),
    // Only a rendered summary has sections to jump to.
    ready: (p) => expect(p.getByRole('navigation', { name: 'Jump to section' })).toBeVisible(),
    ...siteHeader,
  },
]

type Overflow = { scrollWidth: number; clientWidth: number; widest: string[] }

/** The document's widths and, for a failure message, what reaches past the viewport's right edge. */
const measure = (page: Page): Promise<Overflow> =>
  page.evaluate(() => {
    const root = document.documentElement
    const vw = root.clientWidth
    /** Fixed boxes and anything a clipping box holds add nothing to the document's scroll width.
        `own` counts the element's own overflow too: a text run is clipped by its parent. */
    const clipped = (el: Element, own: boolean) => {
      for (let n: Element | null = el; n && n !== document.body; n = n.parentElement) {
        const style = getComputedStyle(n)
        if (style.position === 'fixed' || ((own || n !== el) && style.overflowX !== 'visible')) return true
      }
      return false
    }
    const label = (el: Element, text: string) => `${el.tagName.toLowerCase()} "${text.replace(/\s+/g, ' ').trim().slice(0, 40)}"`
    const past: { right: number; what: string }[] = []
    for (const el of document.querySelectorAll('body *')) {
      const right = el.getBoundingClientRect().right
      if (right > vw + 0.5 && !clipped(el, false)) past.push({ right, what: label(el, el.textContent ?? '') })
    }
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement
      if (!el || !node.textContent?.trim() || clipped(el, true)) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      const right = range.getBoundingClientRect().right
      if (right > vw + 0.5) past.push({ right, what: `text in ${label(el, node.textContent)}` })
    }
    past.sort((a, b) => b.right - a.right)
    return { scrollWidth: root.scrollWidth, clientWidth: vw, widest: past.slice(0, 6).map((p) => `${Math.round(p.right)}px ${p.what}`) }
  })

/** Controls in the bar that overlap one another, or whose text paints past their own box's sides. */
const collisions = (bar: Locator): Promise<string[]> =>
  bar.evaluate((root) => {
    const controls = [...root.querySelectorAll('a, button')].filter((el) => el.checkVisibility())
    const name = (el: Element) => `${el.tagName.toLowerCase()} "${(el.textContent?.trim() || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').slice(0, 30)}"`
    const boxes = controls.map((el) => ({ el, box: el.getBoundingClientRect() }))
    const found: string[] = []
    for (const { el, box } of boxes) {
      if (!el.textContent?.trim()) continue
      const range = document.createRange()
      range.selectNodeContents(el)
      const text = range.getBoundingClientRect()
      if (text.left < box.left - 0.5 || text.right > box.right + 0.5) {
        found.push(`${name(el)}: text ${Math.round(text.left)}-${Math.round(text.right)}px in a box ${Math.round(box.left)}-${Math.round(box.right)}px`)
      }
    }
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const [a, b] = [boxes[i].box, boxes[j].box]
        if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) found.push(`${name(boxes[i].el)} overlaps ${name(boxes[j].el)}`)
      }
    }
    return found
  })

const why = ({ scrollWidth, clientWidth, widest }: Overflow) =>
  `scrollWidth ${scrollWidth}px against clientWidth ${clientWidth}px; past the edge: ${widest.join('; ') || 'nothing outside a clipping box'}`

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

for (const route of ROUTES) {
  test(`${route.name} (${route.path}) does not scroll sideways at 390px, at the default text size and at 200%`, async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('en:copilot-coachmark-v1', '1')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      } catch {}
    })
    await route.open(page, baseURL!)
    const response = await page.goto(route.path)
    if (route.status) expect(response?.status()).toBe(route.status)
    await route.ready(page)
    await expect(route.chrome(page)).toBeVisible()
    await page.evaluate(() => document.fonts.ready)

    const atDefault = await measure(page)
    expect(atDefault.scrollWidth, `${route.path} at the default text size: ${why(atDefault)}`).toBeLessThanOrEqual(atDefault.clientWidth)
    expect(await collisions(route.bar(page)), `${route.path} at the default text size: the bar's controls`).toEqual([])

    const cdp = await page.context().newCDPSession(page)
    await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
    await expect
      .poll(() => page.evaluate(() => ({ root: getComputedStyle(document.documentElement).fontSize, narrow: matchMedia('(max-width: 24rem)').matches })), {
        message: 'the 200% text setting took: the root computes to 32px and the 24rem query matches',
      })
      .toEqual({ root: '32px', narrow: true })
    // A beat for anything that re-measures on resize, then the layout is read.
    await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
    await page.evaluate(() => document.fonts.ready)

    const enlarged = await measure(page)
    expect(enlarged.scrollWidth, `${route.path} at 200% text: ${why(enlarged)}`).toBeLessThanOrEqual(enlarged.clientWidth)
    expect(await collisions(route.bar(page)), `${route.path} at 200% text: the bar's controls`).toEqual([])
  })
}
