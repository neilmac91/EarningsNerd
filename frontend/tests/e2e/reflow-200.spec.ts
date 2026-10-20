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
 * the auth bar no two controls overlap, and no control's text paints beyond its own box sideways. Nor
 * does a control enter the logo's clear space (frontend/public/assets/LOGO_README.md: one E-bar, 11.6%
 * of the mark's width), which a bar full at one row broke with nothing overlapping.
 *
 * The site header also keeps one row at 390px and 200% for a guest: below a 24rem viewport its theme
 * toggle moves into the mobile menu's first row, so the bar is the logo, the account link and the menu
 * button, and the link's label wraps before the bar does. Before that the bar wrapped to two rows, 239px
 * of an 844px viewport (28%), sticky on every scroll. One row is asserted from the bar's own boxes: the
 * header is no taller than its tallest item plus the bar's vertical padding and the header's border
 * (one row's worth, 151px here with the label on two lines), where a second row adds that row and the
 * row gap; at 200% it is also held to 151px, the founder's measure, with 2px of tolerance, since a row
 * that grows raises its own limit. At 360px and 200% the "Request invite" label's longest word and the
 * two controls do not fit beside the logo, so the bar wraps there, the fallback, and this check is not
 * made at that width. The open menu's toggle is in view on a 390x664 phone at 200%, guest or signed in.
 *
 * At 360x780 with the text doubled every route passes the same width, bar and clear-space checks, all but
 * the one-row check. There / reached 368px, the pricing section's billing toggle, and /login and /register
 * 369px, the auth shell's lockup. The toggle's segments now wrap whole inside its one shell, and each label
 * stays inside its segment with no line starting at its middot (at 360 and 390px; at both, the Annual label
 * ran onto three lines below its segment). Below a 12rem viewport the auth shell's wordmark yields to the
 * mark. At 320x640 with the text doubled /pricing passes the same checks: its billing switch's row wraps, the
 * yearly label on a line of its own, where on one line it took "Monthly" 13px past the screen's left edge and
 * the page to 333px. The other routes join it at 320px with E81 (/ reaches 356px there). The open menu scrolls
 * inside the viewport: at 390x664 and 360x640 and 200%, guest and signed in, a
 * wheel over the menu and focus each bring its last item into view inside it, the page unmoved, and neither
 * the page nor the menu scrolls sideways (before, the sticky header showed it only at the page's very end).
 * On a 768px and an 834px tablet at 200% every route passes the same checks too: the footer's columns and
 * the final CTA card's open at md at the reader's text size (48rem), where at md's 768px they took pages to
 * 812-886px. At 1440x900 at the default size the site header's bar spans its container and the logo keeps
 * its top-left place, which the bar's w-full holds.
 *
 * An auth page's "Request an invite" link draws its focus ring closed at 320, 360 and 390px, at both text sizes.
 * As an inline link it broke inside its label at 320px and, under 200% text, at 390 and 320px, and drew an open
 * piece of its ring on each line. The login page's, which ends its line, is one box (`inline-block`), its label
 * wrapping inside that box where the line is too narrow. The register notice's sits inside a sentence, so it stays
 * inline, wraps with it and draws its ring round each line (`box-decoration-clone`): one box there took the whole line
 * under 200% text and pushed the sentence's comma to the start of the next, so its case fails one box.
 *
 * Consent is seeded, so the consent bar stays closed: it is fixed, adds nothing to the document's
 * scroll width, and its own reflow is not measured here. Light theme only, since a theme changes no
 * geometry. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API origin is
 * answered in the browser, as a guest, and the filing page from fixtures/filing3Api.ts (for a guest, and
 * for its Pro reader in the signed-in menu case).
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
  /** The site header for a guest: one row at 390px, at both text sizes. */
  oneRow?: boolean
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
  oneRow: true,
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
        `own` counts the element's own overflow too: a text run is clipped by its parent. An absolutely
        positioned box escapes the overflow of every ancestor below its containing block (the nearest
        positioned one), so those do not hold it: an sr-only span in a truncated label is past the edge. */
    const clipped = (el: Element, own: boolean) => {
      let escaping = false
      for (let n: Element | null = el; n && n !== document.body; n = n.parentElement) {
        const style = getComputedStyle(n)
        if (style.position === 'fixed') return true
        if (escaping && style.position !== 'static') escaping = false
        if (!escaping && (own || n !== el) && style.overflowX !== 'visible') return true
        if (style.position === 'absolute') escaping = true
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

/** The logo's clear space (frontend/public/assets/LOGO_README.md): one E-bar, 11.6% of the mark's width, on every
    side of the logo (the bare mark, or the lockup), which no other control in the bar enters. A bar that squeezes
    its controls against the logo to keep one row would break it with nothing overlapping. Nor does the bar's own edge
    enter it ("no edge of a panel"): a lockup that runs to the viewport's edge has no clear space there. */
const logoClearSpace = (bar: Locator): Promise<string[]> =>
  bar.evaluate((root) => {
    const home = root.querySelector('a[href="/"]')
    const mark = home?.querySelector('svg, img')
    if (!home || !mark) return ['the bar has no home link with the mark']
    const logo = home.getBoundingClientRect()
    const space = mark.getBoundingClientRect().width * 0.116
    const found: string[] = []
    const edge = root.getBoundingClientRect()
    if (logo.left - space < edge.left - 0.5 || logo.right + space > edge.right + 0.5 || logo.top - space < edge.top - 0.5 || logo.bottom + space > edge.bottom + 0.5) {
      found.push(`the logo (${Math.round(logo.left)}-${Math.round(logo.right)}px) with its ${space.toFixed(1)}px clear space passes the bar's edge (${Math.round(edge.left)}-${Math.round(edge.right)}px)`)
    }
    for (const el of root.querySelectorAll('a, button')) {
      if (el === home || !el.checkVisibility()) continue
      const b = el.getBoundingClientRect()
      if (b.left < logo.right + space - 0.5 && b.right > logo.left - space + 0.5 && b.top < logo.bottom + space - 0.5 && b.bottom > logo.top - space + 0.5) {
        const name = (el.textContent?.trim() || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').slice(0, 30)
        found.push(`${el.tagName.toLowerCase()} "${name}" from ${Math.round(b.left)}px enters the logo's ${space.toFixed(1)}px clear space (logo ${Math.round(logo.left)}-${Math.round(logo.right)}px)`)
      }
    }
    return found
  })

/** The header against one row's worth: its tallest item (the logo, or the action group) plus the bar's
    vertical padding and the header's bottom border. A second row adds that row and the row gap. */
const rows = (header: Locator) =>
  header.evaluate((el) => {
    const bar = el.firstElementChild as HTMLElement
    const style = getComputedStyle(bar)
    const items = [...bar.children].filter((c) => c.checkVisibility()).map((c) => c.getBoundingClientRect())
    const tallest = Math.max(...items.map((r) => r.height))
    const oneRow = tallest + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) + parseFloat(getComputedStyle(el).borderBottomWidth)
    const tops = items.map((r) => Math.round(r.top))
    return { height: Math.round(el.getBoundingClientRect().height), oneRow: Math.ceil(oneRow), tallest: Math.round(tallest), tops }
  })

/** The one-row threshold: the header's measured height at most one row's worth (above), with a pixel
    for rounding. A second row adds at least a 44px control and the bar's 0.5rem row gap, so the margin
    cannot hide one. That limit rises with whatever grows inside the row (a label on a third line, a
    taller mark, more padding), so where a ceiling is given the header is also held to it. */
async function expectOneRow(header: Locator, at: string, ceiling?: number) {
  const r = await rows(header)
  expect(r.height, `${at}: the site header is one row, ${r.height}px against one row's worth ${r.oneRow}px (its tallest item ${r.tallest}px; item tops ${r.tops.join(', ')}px)`).toBeLessThanOrEqual(r.oneRow + 1)
  if (ceiling !== undefined) {
    expect(r.height, `${at}: the site header is at most ${ceiling}px, the founder's one-row measure with its tolerance (its tallest item ${r.tallest}px)`).toBeLessThanOrEqual(ceiling)
  }
}

/** The founder's measure is the header's share of the viewport: one row at 390px and 200% text is 151px
    (the bar's 24px padding above and below, the 102px account link with its label on two lines, the 1px
    border), 18% of 844px. The ceiling allows 2px over it, a pixel for rounding the measured height and a
    pixel for a fractional line box: a third line of the label adds 35px at 200%, so the tolerance cannot
    hide one. */
const HEADER_AT_200 = 151 + 2

const why = ({ scrollWidth, clientWidth, widest }: Overflow) =>
  `scrollWidth ${scrollWidth}px against clientWidth ${clientWidth}px; past the edge: ${widest.join('; ') || 'nothing outside a clipping box'}`

/** Chromium's own text setting doubled (standard 32, fixed 26), confirmed taken, then a beat for
    anything that re-measures on resize (the header publishes its new height) before the layout is read. */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => ({ root: getComputedStyle(document.documentElement).fontSize, narrow: matchMedia('(max-width: 24rem)').matches })), {
      message: 'the 200% text setting took: the root computes to 32px and the 24rem query matches',
    })
    .toEqual({ root: '32px', narrow: true })
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
  await page.evaluate(() => document.fonts.ready)
}

test.use({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true })

/** Below 24rem at the default text size (a 360px phone) the Button's narrow state is already on; a
    caller's own min-h must still win there, so the header's account link keeps its 44px target. */
test.describe('a 360px phone at the default text size', () => {
  test.use({ viewport: { width: 360, height: 780 }, isMobile: true, hasTouch: true })
  test('home (/) keeps the header account link a 44px target and does not scroll sideways', async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      } catch {}
    })
    await answerGuest(page, baseURL!)
    await page.goto('/')
    await h1(page)
    const link = siteHeader.chrome(page)
    await expect(link).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    expect(await page.evaluate(() => matchMedia('(max-width: 24rem)').matches), 'the narrow state is on at 360px').toBe(true)
    const box = await link.boundingBox()
    expect(box?.height ?? 0, 'the account link keeps its 44px target (min-h-11) inside the narrow state').toBeGreaterThanOrEqual(44)
    const at360 = await measure(page)
    expect(at360.scrollWidth, `/ at 360px: ${why(at360)}`).toBeLessThanOrEqual(at360.clientWidth)
    expect(await collisions(siteHeader.bar(page)), '/ at 360px: the bar\'s controls').toEqual([])
    expect(await logoClearSpace(siteHeader.bar(page)), '/ at 360px: the logo\'s clear space').toEqual([])
  })
})

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
    expect(await logoClearSpace(route.bar(page)), `${route.path} at the default text size: the logo's clear space`).toEqual([])
    if (route.oneRow) await expectOneRow(route.bar(page), `${route.path} at the default text size`)

    await doubleText(page)

    const enlarged = await measure(page)
    expect(enlarged.scrollWidth, `${route.path} at 200% text: ${why(enlarged)}`).toBeLessThanOrEqual(enlarged.clientWidth)
    expect(await collisions(route.bar(page)), `${route.path} at 200% text: the bar's controls`).toEqual([])
    expect(await logoClearSpace(route.bar(page)), `${route.path} at 200% text: the logo's clear space`).toEqual([])
    if (route.oneRow) await expectOneRow(route.bar(page), `${route.path} at 200% text`, HEADER_AT_200)
  })
}

/** How a link's ring is drawn, read from the browser's own line boxes (a link that breaks across lines has a client rect
    per line): one box (an atomic box, such as `inline-block`), one inline piece, or a piece per line, each closed only
    where the link clones its decoration onto every line. */
const ring = (link: Locator) =>
  link.evaluate((el) => {
    const style = getComputedStyle(el)
    const clone = [style.getPropertyValue('box-decoration-break'), style.getPropertyValue('-webkit-box-decoration-break')].includes('clone')
    const pieces = el.getClientRects().length
    if (pieces > 1) return `${pieces} ${clone ? 'closed' : 'open'} pieces`
    return style.display === 'inline' ? 'one inline piece' : 'one box'
  })
/** The login page's link ends its line and stays one box; the register notice's stays inline in its sentence and wraps
    with it, its pieces closed (as one box it took the whole line under 200% text and pushed the comma to the next). */
const INVITE_RING: Record<string, RegExp> = { '/login': /^one box$/, '/register': /^(?:one inline piece|\d+ closed pieces)$/ }

for (const width of [320, 360, 390]) {
  test.describe(`a ${width}px phone: the auth pages' invite link draws its ring closed`, () => {
    test.use({ viewport: { width, height: 780 }, isMobile: true, hasTouch: true })
    for (const route of ROUTES.filter((r) => r.path === '/login' || r.path === '/register')) {
      test(`${route.name} (${route.path}) at the default text size and at 200%`, async ({ page, baseURL }) => {
        await page.addInitScript(() => {
          try {
            localStorage.setItem('theme', 'light')
            localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
          } catch {}
        })
        await route.open(page, baseURL!)
        await page.goto(route.path)
        await route.ready(page)
        const link = page.getByRole('link', { name: 'Request an invite' })
        await expect(link).toBeVisible()
        await page.evaluate(() => document.fonts.ready)
        expect(await ring(link), `${route.path} at ${width}px: the ring round "Request an invite"`).toMatch(INVITE_RING[route.path])
        await doubleText(page)
        expect(await ring(link), `${route.path} at ${width}px and 200% text: the ring round "Request an invite"`).toMatch(INVITE_RING[route.path])
      })
    }
  })
}

/** Below 24rem the theme toggle is a menu item, not a bar control: at 390px and 200% the bar shows none,
    and the open menu shows one, which still switches the theme. */
test('home (/) moves the theme toggle into the mobile menu at 200% text', async ({ page, baseURL }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  })
  await answerGuest(page, baseURL!)
  await page.goto('/')
  await h1(page)
  await expect(siteHeader.chrome(page)).toBeVisible()
  const toggle = siteHeader.bar(page).getByRole('button', { name: /^Switch to (dark|light) mode$/ })
  await expect(toggle, 'at the default text size the bar carries the toggle').toBeVisible()
  await doubleText(page)
  await expect(toggle, 'at 200% text the bar carries no toggle').toBeHidden()
  await siteHeader.bar(page).getByRole('button', { name: 'Open menu' }).click()
  const inMenu = page.getByRole('navigation', { name: 'Mobile navigation' }).getByRole('button', { name: 'Switch to dark mode' })
  await expect(inMenu).toBeVisible()
  await inMenu.click()
  await expect(page.locator('html')).toHaveClass(/(^|\s)dark(\s|$)/)
})

/** Below 24rem the menu's Theme row is its first row, directly under the bar, so it opens in view before the
    menu is scrolled. With the row at the menu's end, a guest's toggle sat at 713-801px and a signed-in reader's
    at 979-1067px, below the fold of a phone whose toolbars leave 664px, and the menu did not scroll then (its
    own case is further down this file). Opened there at 200% text, the menu's toggle lies wholly inside the
    viewport and switches the theme, for a guest and for a signed-in reader. */
test.describe('a 390x664 phone at 200% text', () => {
  test.use({ viewport: { width: 390, height: 664 }, isMobile: true, hasTouch: true })
  const READERS = [
    {
      who: 'a guest',
      path: '/',
      open: answerGuest,
      ready: (p: Page) => h1(p),
      /** The menu's account items have settled: a guest's Log in link. */
      settled: (menu: Locator) => menu.getByRole('link', { name: 'Log in' }),
    },
    {
      who: 'a signed-in reader',
      path: '/filing/3',
      open: (p: Page, b: string) => answerApi(p, b, 'pro'),
      ready: (p: Page) => expect(p.getByRole('navigation', { name: 'Jump to section' })).toBeVisible(),
      settled: (menu: Locator) => menu.getByRole('button', { name: 'Log out' }),
    },
  ]
  for (const reader of READERS) {
    test(`${reader.path} for ${reader.who}: the open menu's theme toggle is in view and switches the theme`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        try {
          localStorage.setItem('theme', 'light')
          localStorage.setItem('en:copilot-coachmark-v1', '1')
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        } catch {}
      })
      await reader.open(page, baseURL!)
      await page.goto(reader.path)
      await reader.ready(page)
      await page.evaluate(() => document.fonts.ready)
      await doubleText(page)

      await page.getByRole('button', { name: 'Open menu' }).click()
      const menu = page.getByRole('navigation', { name: 'Mobile navigation' })
      await expect(reader.settled(menu)).toBeVisible()
      const toggle = menu.getByRole('button', { name: 'Switch to dark mode' })
      await expect(toggle).toBeVisible()
      const box = (await toggle.boundingBox())!
      const { height } = page.viewportSize()!
      const at = `the menu's theme toggle (${Math.round(box.y)}-${Math.round(box.y + box.height)}px)`
      expect(box.y, `${at} starts inside the viewport`).toBeGreaterThanOrEqual(0)
      expect(box.y + box.height, `${at} ends inside the ${height}px viewport`).toBeLessThanOrEqual(height)
      await toggle.click()
      await expect(page.locator('html')).toHaveClass(/(^|\s)dark(\s|$)/)
    })
  }
})

/** A failure's controls stay inside their card at 200% text on a phone (the reserve's condition, D-032: the room of
    "Trying again…" that RetryButton keeps at rest must never cost reflow). That room makes a Retry wider than its
    label; where it shared a row it could not leave, it pushed itself or its neighbour past the card and the screen:
    the homepage search alert's Retry beside its message (at 390px the page scrolled to 445px, the Retry 87px past the
    alert, cut to "Try aga"), the dashboard's account card with Try again beside Go to login (the Retry's left edge
    off the screen at 320px), the route error boundaries' two actions at 320px, and a long token in the search
    alert's message (the page 598px wide). Now a Retry takes its own row under its message, a card's two actions
    wrap, a message breaks a long token, and a cramped Retry sets its spinner above its label (Button's reserve), so
    in the company page's comparison card, a Notice inside a card, the Retry stays inside the card at 320px (it ran
    to 326px). Each case, at rest and, for a RetryButton, with the press's request held open (busy): nothing in the
    card reaches past the screen, the card adds nothing to the page's own width (measured before the failure), every
    control lies inside the card, no control's text paints past its box or onto another's, and the press neither resizes the
    card nor moves a control in it (read from the card's own corner: focusing the Retry scrolls it into view, and on
    the dashboard the header changes while the account read is in flight). The full-text search alert, fixed the same way, is
    behind a flag CI's build leaves off, so its browser case waits on E39 and full-text-search.spec.tsx pins its
    layout. CI has no backend: the API is answered in the browser.

    A Notice inside a card is held to its own border as well: its Retry and every text run lie inside the Notice, at
    rest and busy. Its text column used to be what the row left after the glyph, so under 200% text the comparison
    card's Retry ran 39px past the Notice's border at 320px and its title's "comparison" 62px (22px at 360px), and at
    360px the billing and ticker filings cards' Retry ran 15px past it (billing's "information" 33px). The Notice's
    row now wraps, its text column going under the glyph where it cannot keep 9rem beside it (components/ui/Notice.tsx).
    At 320px those two cards keep only the card's checks: their p-6 (48px a side at 200% text) leaves the Notice a 92px
    content box, narrower than the Retry's narrowest state (138px), which sits 13px past the Notice's border there,
    inside the card (tasks/todo.md E120). */
const SEARCH_DOWN = 'SEC EDGAR is temporarily unavailable. Please retry shortly.'
/** A backend detail with a long token in it, which no line break may split. */
const SEARCH_DOWN_TOKEN = 'SEC EDGAR is unavailable: EDGAR_COMPANY_TICKERS_UPSTREAM_TIMEOUT'
const COMPANY = { id: 1, cik: '320193', ticker: 'AAPL', name: 'Apple Inc.', exchange: 'NASDAQ' }
const FOLDER = 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/'
const companyFiling = (id: number, filing_type: string, filing_date: string, report_date: string) => ({
  id, filing_type, filing_date: `${filing_date}T00:00:00+00:00`, report_date,
  accession_number: `0000320193-25-0000${id}`, document_url: `${FOLDER}doc-${id}.htm`, sec_url: FOLDER,
})
/** The company page and the signed-in dashboard, as text-floors.spec.ts answers them, with one path answered as a
    failure (or a malformed body), and the next request on it held open once `hold` says so. */
async function answerSite(page: Page, baseURL: string, signedIn: boolean, answer: { path: string; status: number; body: unknown }, hold = () => false) {
  const origin = new URL(baseURL).origin
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  if (signedIn) await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const { pathname } = new URL(route.request().url())
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    if (pathname === answer.path) return hold() ? undefined : json(answer.status, answer.body)
    switch (pathname) {
      case '/api/companies/AAPL':
        return json(200, COMPANY)
      case '/api/filings/company/AAPL':
        return json(200, [companyFiling(11, '10-K', '2025-10-31', '2025-09-27'), companyFiling(12, '10-Q', '2025-08-01', '2025-06-28'), companyFiling(14, '10-K', '2024-11-01', '2024-09-28')])
      case '/api/auth/me':
        return signedIn
          ? json(200, { id: 1, email: 'jordan@example.com', full_name: 'Jordan Whitaker', is_pro: false, is_beta: false, is_admin: false, email_verified: true })
          : json(401, { detail: 'Not authenticated' })
      case '/api/subscriptions/usage':
        return json(200, { summaries_used: 2, summaries_limit: 5, is_pro: false, month: '2026-10', qa_used: 0, qa_limit: 0, copilot_free_taste_used: 0, copilot_free_taste_total: 3, analysis_used: 0, analysis_limit: 0 })
      case '/api/subscriptions/subscription':
        return json(200, { is_pro: false, stripe_customer_id: null, stripe_subscription_id: null, subscription_status: null, plan: 'free', status: null, trial_end: null, current_period_end: null, cancel_at_period_end: false })
      case '/api/watchlist/insights':
        return json(200, [])
      case '/api/dashboard/feed':
        return json(200, { items: [] })
      case '/api/saved-summaries/':
      case '/api/watchlist/':
        return json(200, [])
      default:
        return json(404, { detail: 'Not found' })
    }
  })
}
/** The card's box and each visible control's, in page coordinates, the card's footprint (its size, and each control's
    box from its corner), and the controls not wholly inside the card. */
const controlBoxes = (card: Locator) =>
  card.evaluate((el) => {
    const px = (r: DOMRect) => `${Math.round(r.left + scrollX)}-${Math.round(r.right + scrollX)} x ${Math.round(r.top + scrollY)}-${Math.round(r.bottom + scrollY)}px`
    const c = el.getBoundingClientRect()
    const name = (n: Element) => (n.textContent?.trim() || n.getAttribute('aria-label') || '').replace(/\s+/g, ' ').slice(0, 30)
    const controls = [...el.querySelectorAll('a, button')].filter((n) => n.checkVisibility())
    // Each control's box from the card's own corner, and the card's size: what the press must not change, wherever
    // the page above it moves (the dashboard's header changes while the account read is in flight).
    const own = (r: DOMRect) => `${Math.round(r.left - c.left)},${Math.round(r.top - c.top)} ${Math.round(r.width)}x${Math.round(r.height)}`
    return {
      card: px(c),
      footprint: [`${Math.round(c.width)}x${Math.round(c.height)}`, ...controls.map((n) => own(n.getBoundingClientRect()))],
      controls: controls.map((n) => `"${name(n)}" ${px(n.getBoundingClientRect())}`),
      outside: controls
        .filter((n) => {
          const b = n.getBoundingClientRect()
          return b.left < c.left - 0.5 || b.right > c.right + 0.5 || b.top < c.top - 0.5 || b.bottom > c.bottom + 0.5
        })
        .map(name),
    }
  })
/** The right-most edge of the card, of any box in it and of any text run in it, against the viewport's width. */
const reach = (card: Locator) =>
  card.evaluate((el) => {
    let right = el.getBoundingClientRect().right
    let what = 'the card'
    for (const box of el.querySelectorAll('*')) {
      const r = box.getBoundingClientRect().right
      if (r > right) [right, what] = [r, `${box.tagName.toLowerCase()} "${(box.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 30)}"`]
    }
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent?.trim()) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      const r = range.getBoundingClientRect().right
      if (r > right) [right, what] = [r, `text "${node.textContent.replace(/\s+/g, ' ').trim().slice(0, 30)}"`]
    }
    return { right: Math.round(right * 10) / 10, what, viewport: document.documentElement.clientWidth }
  })
/** What crosses a Notice's border: each visible control's box and each text run, against the Notice's own box. */
const pastNotice = (notice: Locator) =>
  notice.evaluate((el) => {
    const n = el.getBoundingClientRect()
    const past = (r: DOMRect) => r.left < n.left - 0.5 || r.right > n.right + 0.5 || r.top < n.top - 0.5 || r.bottom > n.bottom + 0.5
    const edges = (r: DOMRect) => `${Math.round(r.left)}-${Math.round(r.right)}px`
    const said = (text: string | null) => (text ?? '').replace(/\s+/g, ' ').trim().slice(0, 30)
    const found: string[] = []
    for (const control of el.querySelectorAll('a, button')) {
      const r = control.getBoundingClientRect()
      if (control.checkVisibility() && past(r)) found.push(`${control.tagName.toLowerCase()} "${said(control.textContent)}" ${edges(r)}`)
    }
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent?.trim()) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      const r = range.getBoundingClientRect()
      if (past(r)) found.push(`text "${said(node.textContent)}" ${edges(r)}`)
    }
    return { notice: edges(n), found }
  })
const settle = (page: Page) => page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))

type Failure = {
  /** The surface, as a case names it. */
  name: string
  path: string
  /** Routes the API; `hold` says when the press's request stays open. */
  open: (page: Page, baseURL: string, hold: () => boolean) => Promise<void>
  /** What the visitor does to bring the failure up, after the text is doubled. */
  act?: (page: Page) => Promise<void>
  /** The card the controls must stay inside. */
  card: (page: Page) => Locator
  /** A Notice inside the card, and the widths at which its own border holds the Retry and every text run too. */
  notice?: { at: (page: Page) => Locator; widths: number[] }
  /** The first control's name; a RetryButton is pressed and its request held open for the busy state. */
  retry: 'RetryButton' | 'reset'
  widths: number[]
}
const guestSearch = (detail: string) => async (page: Page, baseURL: string, hold: () => boolean) => {
  await answerGuest(page, baseURL)
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  // Registered last, so it answers the search before answerGuest's catch-all.
  await page.route(
    (url) => url.origin === API_ORIGIN && url.pathname === '/api/companies/search',
    (route) => (hold() ? undefined : route.fulfill({ status: 503, headers: cors, json: { detail } })),
  )
}
const searchFor = (page: Page) => page.getByRole('combobox', { name: 'Or start with a company' }).fill('apple')
const searchAlert = (page: Page) => page.getByRole('alert').filter({ hasText: 'Error searching companies' })
/** The three Notices inside a card, each an error Notice with a RetryButton. */
const comparisonNotice = (page: Page) => page.getByRole('alert').filter({ hasText: 'Couldn’t load the comparison' })
const billingNotice = (page: Page) => page.getByRole('alert').filter({ hasText: 'Failed to load billing information' })
const tickerFilingsNotice = (page: Page) => page.getByRole('alert').filter({ hasText: 'Couldn’t load the filings' })
const FAILURES: Failure[] = [
  { name: 'the homepage search alert', path: '/', open: guestSearch(SEARCH_DOWN), act: searchFor, card: searchAlert, retry: 'RetryButton', widths: [320, 360, 390] },
  { name: 'the homepage search alert, a long token in its message', path: '/', open: guestSearch(SEARCH_DOWN_TOKEN), act: searchFor, card: searchAlert, retry: 'RetryButton', widths: [320] },
  {
    name: "the dashboard's account card (Try again beside Go to login)",
    path: '/dashboard',
    open: (p, b, hold) => answerSite(p, b, true, { path: '/api/auth/me', status: 503, body: { detail: 'The account service is temporarily unavailable.' } }, hold),
    card: (p) => p.getByRole('alert').filter({ hasText: 'Unable to load your dashboard' }),
    retry: 'RetryButton',
    widths: [320, 360, 390],
  },
  {
    // app/error.tsx, forced as text-floors.spec.ts forces it: a numeric name on the coverage-unavailable state makes
    // formatCompanyName throw while the page renders.
    name: 'the route error boundary (Try again beside Go home)',
    path: '/company/AAPL',
    open: (p, b) => answerSite(p, b, false, { path: '/api/companies/AAPL', status: 200, body: { ...COMPANY, name: 42, coverage_status: 'unsupported_foreign' } }),
    card: (p) => p.getByRole('alert').filter({ hasText: 'Something went wrong' }),
    retry: 'reset',
    widths: [320],
  },
  {
    // app/dashboard/error.tsx: the same numeric name, in Your companies.
    name: 'the dashboard error boundary (Try again beside Go home)',
    path: '/dashboard',
    open: (p, b) => answerSite(p, b, true, { path: '/api/watchlist/insights', status: 200, body: [{ company: { id: 1, ticker: 'AAPL', name: 42 }, latest_filing: null, total_filings: 0 }] }),
    card: (p) => p.getByRole('alert').filter({ hasText: 'Something went wrong' }),
    retry: 'reset',
    widths: [320],
  },
  {
    // A Notice inside a card: a cramped Retry sets its spinner above its label, and where the Notice's text column
    // cannot keep 9rem beside the glyph it goes under it.
    name: "the company page's comparison card (a Notice inside a card)",
    path: '/company/AAPL',
    open: (p, b, hold) => answerSite(p, b, false, { path: '/api/summaries/filing/11/what-changed', status: 503, body: { detail: 'Service temporarily unavailable.' } }, hold),
    card: (p) => comparisonNotice(p).locator('xpath=../..'),
    notice: { at: comparisonNotice, widths: [320, 360] },
    retry: 'RetryButton',
    widths: [320, 360],
  },
  {
    // The settings page's billing card, a p-6 Card with the Notice as its child.
    name: "the settings page's billing card (a Notice inside a p-6 card)",
    path: '/dashboard/settings',
    open: (p, b, hold) => answerSite(p, b, true, { path: '/api/subscriptions/subscription', status: 503, body: { detail: 'Service temporarily unavailable.' } }, hold),
    card: (p) => billingNotice(p).locator('xpath=..'),
    notice: { at: billingNotice, widths: [360] },
    retry: 'RetryButton',
    widths: [320, 360],
  },
  {
    // /filing/AAPL: the "Recent filings" card (p-6) of a loaded company, its filings read failing.
    name: "the ticker filings card (a Notice inside a p-6 card)",
    path: '/filing/AAPL',
    open: (p, b, hold) => answerSite(p, b, false, { path: '/api/filings/company/AAPL', status: 503, body: { detail: SEARCH_DOWN } }, hold),
    card: (p) => tickerFilingsNotice(p).locator('xpath=../..'),
    notice: { at: tickerFilingsNotice, widths: [360] },
    retry: 'RetryButton',
    widths: [320, 360],
  },
]

test.describe("a failure's controls stay inside their card at 200% text", () => {
  for (const failure of FAILURES) {
    for (const width of failure.widths) {
      test.describe(`a ${width}px phone`, () => {
        test.use({ viewport: { width, height: 780 }, isMobile: true, hasTouch: true })
        test(`${failure.name} at ${width}px`, async ({ page, baseURL }) => {
          await page.addInitScript(() => {
            try {
              localStorage.setItem('theme', 'light')
              localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
            } catch {}
          })
          let holding = false
          await failure.open(page, baseURL!, () => holding)
          await page.goto(failure.path)
          await page.evaluate(() => document.fonts.ready)
          await doubleText(page)
          // Its own width before the failure shows; an error boundary replaces the page, so it has none apart.
          const without = await measure(page)
          const pageWidth = Math.max(without.clientWidth, without.scrollWidth)
          await failure.act?.(page)
          const card = failure.card(page)
          // The client retries a 503 three times (1, 2 and 4 seconds apart) before a query's failure shows.
          await expect(card).toBeVisible({ timeout: 20_000 })
          await settle(page)

          const at = `${failure.name} at ${width}px and 200% text`
          const check = async (state: string) => {
            const r = await reach(card)
            expect(r.right, `${at}, ${state}: nothing in it reaches past the ${r.viewport}px viewport; the furthest is ${r.what} at ${r.right}px`).toBeLessThanOrEqual(r.viewport + 0.5)
            const m = await measure(page)
            expect(m.scrollWidth, `${at}, ${state}: it widens the page past its own ${pageWidth}px; ${why(m)}`).toBeLessThanOrEqual(pageWidth)
            const b = await controlBoxes(card)
            expect(b.outside, `${at}, ${state}: every control lies inside the card (${b.card}): ${b.controls.join('; ')}`).toEqual([])
            if (failure.notice?.widths.includes(width)) {
              const n = await pastNotice(failure.notice.at(page))
              expect(n.found, `${at}, ${state}: the Retry and every text run lie inside the Notice (${n.notice})`).toEqual([])
            }
            expect(await collisions(card), `${at}, ${state}: its controls`).toEqual([])
            return b
          }
          const rest = await check('at rest')
          if (failure.retry === 'reset') return

          holding = true
          await card.getByRole('button', { name: 'Try again', exact: true }).focus()
          await page.keyboard.press('Enter')
          await expect(card.getByRole('button', { name: 'Trying again…', exact: true })).toBeVisible()
          await settle(page)
          const busy = await check('busy')
          expect(busy.footprint, `${at}: the press resizes nothing in the card and moves nothing in it`).toEqual(rest.footprint)
        })
      })
    }
  }
})

/** The header must not cover what is pinned under it. At 200% text the site header is about 151px
    (one row; 239px when it wrapped to two); the filing page's section nav, once stuck, sits below the
    header's measured height (`--site-header-h`, components/Header.tsx), not below a fixed 4rem (128px
    here), which left its chips under the header and sent a tap on the first one to a header control.
    Scrolled well past the nav's own place, its first link lies wholly below the header's bottom edge,
    a hit at its centre reaches it, and focusing it leaves it so. */
test('filing (/filing/3) keeps the stuck section nav below the header at 200% text', async ({ page, baseURL }) => {
  await page.addInitScript(() => {
    try {
      localStorage.setItem('theme', 'light')
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  })
  await answerApi(page, baseURL!, 'anon')
  await page.goto('/filing/3')
  const nav = page.getByRole('navigation', { name: 'Jump to section' })
  await expect(nav).toBeVisible()
  await expect(siteHeader.chrome(page)).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
  await doubleText(page)

  // Scroll well past the nav's own place and stay inside its column, so it is stuck (the founder's
  // report scrolled to about 2500px).
  const scrolled = await nav.evaluate((el) => {
    const natural = el.getBoundingClientRect().top + window.scrollY
    const columnEnd = el.parentElement!.getBoundingClientRect().bottom + window.scrollY
    window.scrollTo({ top: Math.min(natural + 2000, columnEnd - window.innerHeight), behavior: 'instant' })
    return { natural, at: window.scrollY }
  })
  expect(scrolled.at, 'the page scrolls past the section nav, so the nav is stuck').toBeGreaterThan(scrolled.natural)
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))

  const first = nav.getByRole('link').first()
  const header = await siteHeader.bar(page).elementHandle()
  /** The first link's box against the header's bottom edge, and what a hit at the link's centre reaches. */
  const read = () =>
    first.evaluate((link, banner) => {
      const box = link.getBoundingClientRect()
      const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
      const name = (el: Element | null) => (el ? `${el.tagName.toLowerCase()} "${(el.textContent?.trim() || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').slice(0, 30)}"` : 'nothing')
      return {
        headerBottom: Math.round(banner!.getBoundingClientRect().bottom),
        linkTop: Math.round(box.top),
        linkBottom: Math.round(box.bottom),
        hitsLink: !!hit && link.contains(hit),
        hit: name(hit),
      }
    }, header)

  const stuck = await read()
  expect(stuck.linkTop, `the first section link (${stuck.linkTop}-${stuck.linkBottom}px) lies below the header's bottom edge (${stuck.headerBottom}px)`).toBeGreaterThanOrEqual(stuck.headerBottom)
  expect(stuck.hitsLink, `a hit at the first section link's centre reaches it, not ${stuck.hit}`).toBe(true)

  await first.focus()
  await expect(first).toBeFocused()
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
  const focused = await read()
  expect(focused.linkTop, `focused, the first section link (${focused.linkTop}-${focused.linkBottom}px) lies below the header's bottom edge (${focused.headerBottom}px)`).toBeGreaterThanOrEqual(focused.headerBottom)
  expect(focused.hitsLink, `focused, a hit at the first section link's centre reaches it, not ${focused.hit}`).toBe(true)
})

/** At 360x780 with the browser's text doubled, every route in the loop passes the width, bar and clear-space checks
    too. The header's wrap at 360px is its named fallback, so the one-row check stays at 390px. At 320x640 /pricing
    does too, its billing switch's row wrapped; the rest of the loop joins it there with E81. */
for (const { width, height, routes } of [
  { width: 360, height: 780, routes: ROUTES },
  { width: 320, height: 640, routes: ROUTES.filter(({ path }) => path === '/pricing') },
]) test.describe(`a ${width}px phone at 200% text`, () => {
  test.use({ viewport: { width, height }, isMobile: true, hasTouch: true })
  for (const route of routes) {
    test(`${route.name} (${route.path}) does not scroll sideways at ${width}px and 200% text`, async ({ page, baseURL }) => {
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
      await doubleText(page)

      const enlarged = await measure(page)
      expect(enlarged.scrollWidth, `${route.path} at ${width}px and 200% text: ${why(enlarged)}`).toBeLessThanOrEqual(enlarged.clientWidth)
      expect(await collisions(route.bar(page)), `${route.path} at ${width}px and 200% text: the bar's controls`).toEqual([])
      expect(await logoClearSpace(route.bar(page)), `${route.path} at ${width}px and 200% text: the logo's clear space`).toEqual([])
    })
  }
})

/** The pricing section's billing toggle (a radio group of two segments) at 200% text: one control whose segments wrap
    whole onto a second row inside its shell when they do not fit side by side, each label inside its segment, broken
    only between words and only after its middot, every line but the last ending with it, so never on a line that
    starts with it ("Annual ·" over "save 20%"; the no-break spaces in PricingSection.tsx hold that, and with plain
    spaces the label paints "Annual · save" over "20%" at 360px). Before, at 360 and at 390px, the group was 336px wide
    and its Annual label ran onto three lines, "Annual", "· save" and "20%", the last painted below its 72px segment.
    Each label's lines are read as painted, a character at a time. */
const segments = (group: Locator) =>
  group.evaluate((root) => {
    const shell = root.getBoundingClientRect()
    const px = (a: number, b: number) => `${Math.round(a)}-${Math.round(b)}px`
    return [...root.querySelectorAll('[role="radio"]')].map((radio) => {
      const box = radio.getBoundingClientRect()
      const all = document.createRange()
      all.selectNodeContents(radio)
      const text = all.getBoundingClientRect()
      const lines = new Map<number, string>()
      const walker = document.createTreeWalker(radio, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
        for (let i = 0; i < node.length; i++) {
          const char = document.createRange()
          char.setStart(node, i)
          char.setEnd(node, i + 1)
          const r = char.getBoundingClientRect()
          if (!r.width && !r.height) continue
          lines.set(Math.round(r.top), (lines.get(Math.round(r.top)) ?? '') + node.data[i])
        }
      }
      return {
        name: (radio.textContent ?? '').replace(/\s+/g, ' ').trim(),
        lines: [...lines.entries()].sort((a, b) => a[0] - b[0]).map(([, line]) => line.trim()),
        inShell: box.left >= shell.left - 0.5 && box.right <= shell.right + 0.5 && box.top >= shell.top - 0.5 && box.bottom <= shell.bottom + 0.5,
        inSegment: text.left >= box.left - 0.5 && text.right <= box.right + 0.5 && text.top >= box.top - 0.5 && text.bottom <= box.bottom + 0.5,
        where: `segment ${px(box.left, box.right)} by ${px(box.top, box.bottom)}, label ${px(text.left, text.right)} by ${px(text.top, text.bottom)}, shell ${px(shell.left, shell.right)}`,
      }
    })
  })

for (const viewport of [{ width: 360, height: 780 }, { width: 390, height: 844 }]) {
  test.describe(`a ${viewport.width}px phone at 200% text, the billing toggle`, () => {
    test.use({ viewport, isMobile: true, hasTouch: true })
    test(`home (/) keeps both billing segments in one control at ${viewport.width}px, each label whole inside its segment`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        try {
          localStorage.setItem('theme', 'light')
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        } catch {}
      })
      await answerGuest(page, baseURL!)
      await page.goto('/')
      await h1(page)
      const group = page.getByRole('radiogroup', { name: 'Billing period' })
      await expect(group.getByRole('radio')).toHaveCount(2)
      await page.evaluate(() => document.fonts.ready)
      await doubleText(page)

      for (const segment of await segments(group)) {
        const at = `"${segment.name}" at ${viewport.width}px and 200% text (lines ${JSON.stringify(segment.lines)}; ${segment.where})`
        const words = segment.name.split(/\s+/)
        expect(segment.inShell, `${at}: the segment sits inside the one control`).toBe(true)
        expect(segment.inSegment, `${at}: the label stays inside its segment`).toBe(true)
        expect(segment.lines.some((line) => line.startsWith('·')), `${at}: no line starts with the middot`).toBe(false)
        expect(segment.lines.every((line) => line.split(/\s+/).every((token) => words.includes(token))), `${at}: the label breaks only between words`).toBe(true)
        expect(segment.lines.slice(0, -1).every((line) => line.endsWith('·')), `${at}: the label breaks only after its middot`).toBe(true)
      }
    })
  })
}

/** The open menu scrolls inside the viewport. The header is a column no taller than the viewport, its bar keeps its own
    height and the menu panel takes the rest and scrolls (components/Header.tsx). Before, a sticky header taller than
    the viewport stayed stuck to its top until the page's very end, so the menu's last item (the account CTA for a
    guest, Log out for a signed-in reader) came into view only there: under the fold at 713-801px and 987-1067px on a
    390x664 phone. At 390x664 and 360x640 at 200% text, for a guest and for a signed-in reader, a wheel over the menu
    brings its last item wholly into view inside it with the page unmoved, and a second wheel at the menu's end leaves
    the page behind it unmoved too; scrolled back to its top, the menu brings the item into view again as focus lands
    on it, the item's 3px ring clear of the menu's edge; and neither the page nor the menu scrolls sideways, the menu
    read on its own, since what it clips adds nothing to the page's width. */
const MENU_ENDS = [
  {
    who: 'a guest',
    path: '/',
    open: answerGuest,
    ready: (p: Page) => h1(p),
    last: (menu: Locator) => menu.getByRole('link', { name: /^(Create a free account|Request an invite)$/ }),
  },
  {
    who: 'a signed-in reader',
    path: '/filing/3',
    open: (p: Page, b: string) => answerApi(p, b, 'pro'),
    ready: (p: Page) => expect(p.getByRole('navigation', { name: 'Jump to section' })).toBeVisible(),
    last: (menu: Locator) => menu.getByRole('button', { name: 'Log out' }),
  },
]

/** The item against the part of the menu the reader sees (the menu panel's box within the viewport), with `ring`
    pixels around it, and whether a hit at its centre reaches it. 'in view' when it lies wholly inside. */
const inMenuView = (item: Locator, ring = 0) =>
  item.evaluate((el, ring) => {
    const panel = el.closest('nav')!.parentElement!.getBoundingClientRect()
    const box = el.getBoundingClientRect()
    const top = Math.max(panel.top, 0)
    const bottom = Math.min(panel.bottom, window.innerHeight)
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
    const inside = box.top - ring >= top - 0.5 && box.bottom + ring <= bottom + 0.5 && !!hit && el.contains(hit)
    return inside ? 'in view' : `the item at ${Math.round(box.top)}-${Math.round(box.bottom)}px, the menu seen at ${Math.round(top)}-${Math.round(bottom)}px, a hit at its centre reaching ${hit ? hit.tagName.toLowerCase() : 'nothing'}`
  }, ring)

/** The menu panel's own widths and, for a failure message, what reaches past its inner right edge outside any clipping
    box inside it, read from its start. The panel scrolls, and a non-visible overflow-y makes overflow-x auto too, so a
    row wider than the menu scrolls sideways inside it and adds nothing to the page's scroll width: `measure` cannot see
    it, since it skips what a clipping box holds. */
const menuWidths = (panel: Locator): Promise<Overflow> =>
  panel.evaluate((root) => {
    root.scrollTo({ left: 0 })
    const edge = root.getBoundingClientRect().left + root.clientLeft + root.clientWidth
    const clipped = (el: Element, own: boolean) => {
      for (let n: Element | null = el; n && n !== root; n = n.parentElement) {
        if ((own || n !== el) && getComputedStyle(n).overflowX !== 'visible') return true
      }
      return false
    }
    const label = (el: Element, text: string) => `${el.tagName.toLowerCase()} "${text.replace(/\s+/g, ' ').trim().slice(0, 40)}"`
    const past: { right: number; what: string }[] = []
    for (const el of root.querySelectorAll('*')) {
      const right = el.getBoundingClientRect().right
      if (right > edge + 0.5 && !clipped(el, false)) past.push({ right, what: label(el, el.textContent ?? '') })
    }
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const el = node.parentElement
      if (!el || !node.textContent?.trim() || clipped(el, true)) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      const right = range.getBoundingClientRect().right
      if (right > edge + 0.5) past.push({ right, what: `text in ${label(el, node.textContent)}` })
    }
    past.sort((a, b) => b.right - a.right)
    return { scrollWidth: root.scrollWidth, clientWidth: root.clientWidth, widest: past.slice(0, 6).map((p) => `${Math.round(p.right)}px ${p.what}`) }
  })

for (const viewport of [{ width: 390, height: 664 }, { width: 360, height: 640 }]) {
  test.describe(`a ${viewport.width}x${viewport.height} phone at 200% text, the menu open`, () => {
    test.use({ viewport, isMobile: true, hasTouch: true })
    for (const reader of MENU_ENDS) {
      test(`${reader.path} for ${reader.who}: the menu scrolls inside the viewport to its last item, and neither the page nor the menu scrolls sideways`, async ({ page, baseURL }) => {
        await page.addInitScript(() => {
          try {
            localStorage.setItem('theme', 'light')
            localStorage.setItem('en:copilot-coachmark-v1', '1')
            localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
          } catch {}
        })
        await reader.open(page, baseURL!)
        await page.goto(reader.path)
        await reader.ready(page)
        await page.evaluate(() => document.fonts.ready)
        await doubleText(page)
        await page.getByRole('button', { name: 'Open menu' }).click()
        const menu = page.getByRole('navigation', { name: 'Mobile navigation' })
        const last = reader.last(menu)
        await expect(last).toBeVisible()
        const at = `${reader.path} at ${viewport.width}x${viewport.height}, the menu's last item "${(await last.textContent())?.trim()}"`

        // A pointer: a wheel over the part of the menu in view, far past its end. The menu scrolls, not the page, and
        // at its end it holds: a second wheel after a pause, a new sequence that could chain, moves nothing behind it
        // (without overscroll-contain it scrolled the page 1000px under the open menu).
        const scrollY = await page.evaluate(() => window.scrollY)
        const panel = (await menu.locator('xpath=..').boundingBox())!
        await page.mouse.move(panel.x + panel.width / 2, (Math.max(panel.y, 0) + Math.min(panel.y + panel.height, viewport.height)) / 2)
        await page.mouse.wheel(0, 4000)
        await expect.poll(() => inMenuView(last), { message: `${at}, after a wheel over the menu` }).toBe('in view')
        await page.waitForTimeout(700)
        await page.mouse.wheel(0, 1000)
        await page.waitForTimeout(700)
        expect(await page.evaluate(() => window.scrollY), `${at}: the menu scrolled and holds its end, the page behind it unmoved`).toBe(scrollY)

        // A keyboard: the menu back at its top, focus on the item scrolls it into view with its ring.
        await menu.locator('xpath=..').evaluate((el) => el.scrollTo({ top: 0 }))
        await last.focus()
        await expect.poll(() => inMenuView(last, 3), { message: `${at}, focused, with its 3px ring` }).toBe('in view')

        const widths = await measure(page)
        expect(widths.scrollWidth, `${reader.path} at ${viewport.width}x${viewport.height} with the menu open: ${why(widths)}`).toBeLessThanOrEqual(widths.clientWidth)
        const inside = await menuWidths(menu.locator('xpath=..'))
        expect(inside.scrollWidth, `${reader.path} at ${viewport.width}x${viewport.height}, inside the open menu: ${why(inside)}`).toBeLessThanOrEqual(inside.clientWidth)
      })
    }
  })
}

/** A tablet at 200% text. At 768px with the text doubled, the footer's four columns took every route with the footer to
    812px (an fr column never shrinks below its longest word, here the Legal column's), and from 780 to 880px the final
    CTA card's two columns ran its one-line "See a live example" past its half, taking / to 886px. Both now open their
    columns at md at the reader's text size, 48rem: 768px at the default size, 1536px with the text doubled. At 768 and
    834px every route in the loop passes the width, bar and clear-space checks; the 200% setting is confirmed by the
    root's 32px and by the 48rem query not matching. */
async function doubleTextOnATablet(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => ({ root: getComputedStyle(document.documentElement).fontSize, md: matchMedia('(min-width: 48rem)').matches })), {
      message: 'the 200% text setting took: the root computes to 32px and the 48rem query does not match',
    })
    .toEqual({ root: '32px', md: false })
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
  await page.evaluate(() => document.fonts.ready)
}

for (const viewport of [{ width: 768, height: 1024 }, { width: 834, height: 1194 }]) {
  test.describe(`a ${viewport.width}px tablet at 200% text`, () => {
    test.use({ viewport, isMobile: true, hasTouch: true })
    for (const route of ROUTES) {
      test(`${route.name} (${route.path}) does not scroll sideways at ${viewport.width}px and 200% text`, async ({ page, baseURL }) => {
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
        await doubleTextOnATablet(page)

        const enlarged = await measure(page)
        expect(enlarged.scrollWidth, `${route.path} at ${viewport.width}px and 200% text: ${why(enlarged)}`).toBeLessThanOrEqual(enlarged.clientWidth)
        expect(await collisions(route.bar(page)), `${route.path} at ${viewport.width}px and 200% text: the bar's controls`).toEqual([])
        expect(await logoClearSpace(route.bar(page)), `${route.path} at ${viewport.width}px and 200% text: the logo's clear space`).toEqual([])
      })
    }
  })
}

/** The site header's bar is a column's child with auto side margins (components/Header.tsx), which a column does not
    stretch: without its w-full the bar shrank to its content at 1440px, from 80-1360px to 291-1149px, and the logo left
    its top-left place (x=112 to x=323). At 1440x900 at the default size the bar spans its container (its max-width,
    centred in the header) and the logo starts at the container's left padding, both read against the header's own box,
    not the bar's, which a shrunken bar would carry with it. */
test.describe('a 1440px desktop at the default text size', () => {
  test.use({ viewport: { width: 1440, height: 900 }, isMobile: false, hasTouch: false })
  test('home (/) keeps the site header bar across its container and the logo in its top-left place', async ({ page, baseURL }) => {
    await page.addInitScript(() => {
      try {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      } catch {}
    })
    await answerGuest(page, baseURL!)
    await page.goto('/')
    await h1(page)
    const logo = page.getByRole('banner').getByRole('link', { name: 'EarningsNerd home' })
    await expect(logo).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    const place = await logo.evaluate((link) => {
      const header = link.closest('header')!
      const bar = header.firstElementChild!
      const style = getComputedStyle(bar)
      const width = Math.min(header.clientWidth, parseFloat(style.maxWidth))
      const left = header.getBoundingClientRect().left + header.clientLeft + (header.clientWidth - width) / 2
      const box = bar.getBoundingClientRect()
      return {
        bar: `${Math.round(box.left)}-${Math.round(box.right)}px`,
        container: `${Math.round(left)}-${Math.round(left + width)}px`,
        logo: Math.round(link.getBoundingClientRect().left),
        place: Math.round(left + parseFloat(style.paddingLeft)),
      }
    })
    expect(place.bar, `the header's bar spans its container, centred in the header (the bar at ${place.bar}, its container at ${place.container})`).toBe(place.container)
    expect(place.logo, `the logo starts at the container's left padding (the logo at x=${place.logo}, its place at x=${place.place})`).toBe(place.place)
  })
})
