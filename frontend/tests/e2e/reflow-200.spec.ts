import { test, expect, type Locator, type Page } from '@playwright/test'
import { calendarWeekReady, pinCalendarWeek } from './fixtures/calendarWeek'
import { answerApi, API_ORIGIN } from './fixtures/filing3Api'
import { answerSearch, runSearch, SEARCH_QUERY } from './fixtures/searchApi'
import { ACCESS_COPY } from '../../features/marketing/lib/access'

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
 * live example", "Ask this filing") and one long heading word on /waitlist were next. /security and
 * /privacy measured 469px: each mailto address (security@, privacy@ and hello@earningsnerd.io) was one
 * word that could not break, and now breaks anywhere ([overflow-wrap:anywhere], since E131 the rule on
 * each legal page's <main>, which every word there inherits). Each case checks that chrome is on the
 * page, so a route that fails to render cannot pass empty. On a failure the message lists the widest
 * elements and text runs past the viewport edge, outside any clipping box.
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
 * ran onto three lines below its segment). Every form code in the landing's rows and its close paints on one line
 * at 320 and 390px under 200% text and at 320px at the default size, where the plan table broke "10-Q" at its
 * hyphen before each code became one nowrap run; the hero's do at 320, 390 and 1440px under 200% text, where its
 * figures keep apart and whole too, no line of its example starts with a middot and, at both text sizes, its strip's
 * rules stand only between two figures (E81). The landing's Trace to Source demo keeps its quote and its section
 * reference inside its panel, no word of either broken inside it, at 320, 360 and 390px under 200% text (E143).
 * Below a 12rem viewport the auth shell's wordmark yields to the mark.
 * At 320x640 with the text doubled every route passes the same checks (E81): /pricing's billing switch's row wraps,
 * the yearly label on a line of its own, where on one line it took "Monthly" 13px past the screen's left edge and the
 * page to 333px; / reached 329px (the hero example's identity line and figures) and /search 344px (its date fields).
 * There a legal page's gutter gives way before a word breaks, and a word still wider than its column breaks inside it
 * (E131), where /security reached 348px on its headings' "Authentication" and "Infrastructure" and /terms 362px on
 * "Indemnification"; at 390px under 200% text no word on the legal pages breaks inside it, an address aside, and at
 * 320px each one's h1 holds whole, read a character at a time.
 * The open menu scrolls inside the viewport: at 390x664 and 360x640 and 200%, guest and signed in, a
 * wheel over the menu and focus each bring its last item into view inside it, the page unmoved, and neither
 * the page nor the menu scrolls sideways (before, the sticky header showed it only at the page's very end).
 * On a 768px and an 834px tablet at 200% every route passes the same checks too: the footer's columns and
 * the final CTA card's opened at md at the reader's text size (48rem), where at md's 768px they took pages to
 * 812-886px; the card is the landing's one-line close since D-045, and the landing's rows open their label
 * column at 64rem the same way. At 1440x900 at the default size the site header's bar spans its container and
 * the logo keeps its top-left place, which the bar's w-full holds. At 390, 360 and 320px under 200% text a dialog's
 * header keeps its title inside the panel and clear of its close button, and a title on a line of its own, under its
 * icon or under the close button alone, takes the header's full width, under the close button too, with no word
 * broken inside it (E158 and E165; the last cases in this file).
 *
 * An auth page's "Request an invite" link draws its focus ring closed at 320, 360 and 390px, at both text sizes.
 * As an inline link it broke inside its label at 320px and, under 200% text, at 390 and 320px, and drew an open
 * piece of its ring on each line. The login page's, which ends its line, is one box (`inline-block`), its label
 * wrapping inside that box where the line is too narrow. The register notice's sits inside a sentence, so it stays
 * inline, wraps with it and draws its ring round each line (`box-decoration-clone`): one box there took the whole line
 * under 200% text and pushed the sentence's comma to the start of the next, so its case fails one box.
 *
 * Consent is seeded, so the consent bar stays closed, except where the dialog header case opens the consent
 * dialog from it on a first visit: the bar is fixed, adds nothing to the document's scroll width, and its own
 * reflow is not measured here. Light theme only, since a theme changes no
 * geometry, except a dialog's header, which is held in both themes, as
 * lessons/frontend-check-brand-layouts-at-200-percent-text.md asks: a dark: utility on ModalHeader would move it
 * in one theme alone. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API origin is
 * answered in the browser, as a guest, and the filing page from fixtures/filing3Api.ts (for a guest, and
 * for its Pro reader in the signed-in menu case and the feedback dialog's). CI's e2e build turns /calendar and /search on, so both
 * join the route loop with their rows painted: the calendar on its own fixtures with the clock pinned to one
 * week (fixtures/calendarWeek.ts), the search answered and run (fixtures/searchApi.ts).
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
  { name: 'security', path: '/security', open: answerGuest, ready: (p) => h1(p, 'Security'), ...siteHeader },
  { name: 'privacy', path: '/privacy', open: answerGuest, ready: (p) => h1(p, 'Privacy Policy'), ...siteHeader },
  { name: 'terms', path: '/terms', open: answerGuest, ready: (p) => h1(p, 'Terms of Service'), ...siteHeader },
  {
    name: 'filing',
    path: '/filing/3',
    open: (p, b) => answerApi(p, b, 'anon'),
    // Only a rendered summary has sections to jump to.
    ready: (p) => expect(p.getByRole('navigation', { name: 'Jump to section' })).toBeVisible(),
    ...siteHeader,
  },
  {
    // The fixtures' week with the clock pinned (fixtures/calendarWeek.ts); at every width here the week is its day list.
    name: 'calendar',
    path: '/calendar',
    open: async (p, b) => {
      await pinCalendarWeek(p)
      await answerGuest(p, b)
    },
    ready: calendarWeekReady,
    ...siteHeader,
  },
  {
    // A search answered and run (fixtures/searchApi.ts), so the page is measured with its result rows painted, a long
    // filer name included. The list clips its rows (`relative overflow-hidden`), so this check cannot see a row or its
    // sr-only commas overrun the list; full-text-search.spec.tsx pins the list's classes.
    name: 'search',
    path: '/search',
    open: async (p, b) => {
      await answerGuest(p, b)
      await answerSearch(p, b)
    },
    ready: runSearch,
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
    the dashboard the header changes while the account read is in flight). The full-text search alert on /search, fixed
    the same way (Codex on #1380 measured its Retry taking the page to 472px at 390px, and to 848px with a long token),
    has the homepage alert's cases, now that CI's e2e build turns /search on; full-text-search.spec.tsx pins its layout.
    CI has no backend: the API is answered in the browser.

    A Notice inside a card is held to its own border as well: its Retry and every text run lie inside the Notice, at
    rest and busy. Its text column used to be what the row left after the glyph, so under 200% text the comparison
    card's Retry ran 39px past the Notice's border at 320px and its title's "comparison" 62px (22px at 360px), and at
    360px the billing and ticker filings cards' Retry ran 15px past it (billing's "information" 33px). The Notice's
    row now wraps, its text column going under the glyph where it cannot keep 9rem beside it (components/ui/Notice.tsx).
    At 320px under 200% text those two cards' p-6 took 48px a side and left the Notice a 92px content box, narrower than
    the Retry's narrowest state (138px), so the Retry ran past the Notice's border there, inside the card. A surface's
    inset now stops growing at narrow widths (E120): the cards' p-cap-6 is 19.2px a side there, the Notice keeps 150px,
    and both cards hold the Retry and every text run inside the Notice at 320px as at 360px. */
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
/** The full-text search's failure: the router's 502 sentence (routers/search.py), or a detail holding a long token. */
const FULL_TEXT_DOWN = 'SEC full-text search is temporarily unavailable.'
const FULL_TEXT_DOWN_TOKEN = 'SEC full-text search failed: EFTS_UPSTREAM_TIMEOUT_EXCEEDED'
const guestFullText = (detail: string) => async (page: Page, baseURL: string, hold: () => boolean) => {
  await answerGuest(page, baseURL)
  const cors = { 'access-control-allow-origin': new URL(baseURL).origin, 'access-control-allow-credentials': 'true' }
  await page.route(
    (url) => url.origin === API_ORIGIN && url.pathname === '/api/search/full-text',
    (route) => (hold() ? undefined : route.fulfill({ status: 502, headers: cors, json: { detail } })),
  )
}
const fullTextFor = (page: Page) => page.getByRole('textbox', { name: 'Search the full text of SEC filings' }).fill(SEARCH_QUERY)
const fullTextAlert = (page: Page) => page.getByRole('alert').filter({ hasText: 'SEC full-text search' })
/** The three Notices inside a card, each an error Notice with a RetryButton. */
const comparisonNotice = (page: Page) => page.getByRole('alert').filter({ hasText: 'Couldn’t load the comparison' })
const billingNotice = (page: Page) => page.getByRole('alert').filter({ hasText: 'Failed to load billing information' })
const tickerFilingsNotice = (page: Page) => page.getByRole('alert').filter({ hasText: 'Couldn’t load the filings' })
const FAILURES: Failure[] = [
  { name: 'the homepage search alert', path: '/', open: guestSearch(SEARCH_DOWN), act: searchFor, card: searchAlert, retry: 'RetryButton', widths: [320, 360, 390] },
  { name: 'the homepage search alert, a long token in its message', path: '/', open: guestSearch(SEARCH_DOWN_TOKEN), act: searchFor, card: searchAlert, retry: 'RetryButton', widths: [320] },
  { name: 'the full-text search alert', path: '/search', open: guestFullText(FULL_TEXT_DOWN), act: fullTextFor, card: fullTextAlert, retry: 'RetryButton', widths: [320, 360, 390] },
  { name: 'the full-text search alert, a long token in its message', path: '/search', open: guestFullText(FULL_TEXT_DOWN_TOKEN), act: fullTextFor, card: fullTextAlert, retry: 'RetryButton', widths: [320] },
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
    // The settings page's billing card, a p-cap-6 Card with the Notice as its child.
    name: "the settings page's billing card (a Notice inside a p-cap-6 card)",
    path: '/dashboard/settings',
    open: (p, b, hold) => answerSite(p, b, true, { path: '/api/subscriptions/subscription', status: 503, body: { detail: 'Service temporarily unavailable.' } }, hold),
    card: (p) => billingNotice(p).locator('xpath=..'),
    notice: { at: billingNotice, widths: [320, 360] },
    retry: 'RetryButton',
    widths: [320, 360],
  },
  {
    // /filing/AAPL: the "Recent filings" card (p-cap-6) of a loaded company, its filings read failing.
    name: "the ticker filings card (a Notice inside a p-cap-6 card)",
    path: '/filing/AAPL',
    open: (p, b, hold) => answerSite(p, b, false, { path: '/api/filings/company/AAPL', status: 503, body: { detail: SEARCH_DOWN } }, hold),
    card: (p) => tickerFilingsNotice(p).locator('xpath=../..'),
    notice: { at: tickerFilingsNotice, widths: [320, 360] },
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

/** The cookie settings dialog's category rows at 200% text (components/CookieConsent.tsx), opened from the footer's
    "Cookie settings" on a page whose visitor has already chosen. Each row takes the Notice's recipe: it wraps, its text
    column keeps 9rem beside the box or takes the card's width with the box under it, and a word too long for the column
    breaks inside it. Before, a row could not wrap and its text column never went narrower than its longest word, so the
    boxes ended 32 to 73px past their cards at 390px, 62 to 103px at 360px and 89 to 130px at 320px, and the text ran
    past the cards too. At 320, 360 and 390px each box and every run of text in its card lie inside the card. With
    ModalBody's px-6 and the cards' p-4 doubled, the text column was 92, 132 and 162px there and the longest words broke
    at all three widths ("Essen" over "tial", "authenticatio" over "n,"). The body's and the cards' insets now stop
    growing at narrow widths (px-cap-6 and p-cap-4, E120): the column is 188, 220 and 244px, and no word in a card
    breaks inside it, read a character at a time. The panel's own sideways scroll is held by the dialog header case
    below, since its title wraps under its icon (#1432) and these rows stay inside their cards. */
/** The three category cards: inside the open dialog, each box that draws a border and a radius. */
const COOKIE_CATEGORY_CARDS = '[role="dialog"][aria-modal="true"] div.rounded-lg.border'
const categoryRows = (dialog: Locator) =>
  dialog.evaluate((root) => {
    const px = (a: number, b: number) => `${Math.round(a)}-${Math.round(b)}px`
    return [...root.querySelectorAll('input[type="checkbox"]')].map((box) => {
      // The box's card: the nearest box around it that draws a border.
      let card = box.parentElement as HTMLElement
      while (card !== root && getComputedStyle(card).borderTopWidth === '0px') card = card.parentElement as HTMLElement
      const c = card.getBoundingClientRect()
      const b = box.getBoundingClientRect()
      // Each run of text in the card, as painted, that reaches past the card's sides.
      const pastCard: string[] = []
      const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.textContent?.trim()) continue
        const range = document.createRange()
        range.selectNodeContents(node)
        const r = range.getBoundingClientRect()
        if (r.left < c.left - 0.5 || r.right > c.right + 0.5) pastCard.push(`"${node.textContent.replace(/\s+/g, ' ').trim().slice(0, 30)}" ${px(r.left, r.right)}`)
      }
      return {
        title: document.getElementById(box.getAttribute('aria-labelledby') ?? '')?.textContent?.trim() ?? '',
        boxInCard: b.left >= c.left - 0.5 && b.right <= c.right + 0.5 && b.top >= c.top - 0.5 && b.bottom <= c.bottom + 0.5,
        pastCard,
        where: `box ${px(b.left, b.right)} by ${px(b.top, b.bottom)}, card ${px(c.left, c.right)} by ${px(c.top, c.bottom)}`,
      }
    })
  })

test.describe("the cookie settings dialog's boxes and text stay inside their cards at 200% text", () => {
  for (const width of [320, 360, 390]) {
    test.describe(`a ${width}px phone`, () => {
      test.use({ viewport: { width, height: 780 }, isMobile: true, hasTouch: true })
      test(`opened from the footer at ${width}px, each box and its text inside its card`, async ({ page, baseURL }) => {
        await page.addInitScript(() => {
          try {
            localStorage.setItem('theme', 'light')
            localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
          } catch {}
        })
        await answerGuest(page, baseURL!)
        await page.goto('/pricing')
        await h1(page, 'Pricing')
        await page.evaluate(() => document.fonts.ready)
        await doubleText(page)
        await page.getByRole('contentinfo').getByRole('button', { name: 'Cookie settings' }).click()
        const dialog = page.getByRole('dialog', { name: 'Cookie preferences' })
        await expect(dialog).toBeVisible()
        await settle(page)

        const rows = await categoryRows(dialog)
        expect(rows.map((row) => row.title)).toEqual(['Essential cookies', 'Analytics cookies', 'Session recording'])
        for (const row of rows) {
          const at = `"${row.title}" at ${width}px and 200% text (${row.where})`
          expect(row.boxInCard, `${at}: the box lies inside its card`).toBe(true)
          expect(row.pastCard, `${at}: every run of text in the card lies inside it`).toEqual([])
        }
        // The body's and the cards' insets stop growing under enlarged text (E120), so no word in a card breaks inside it.
        const { words, found } = await brokenWords(page, COOKIE_CATEGORY_CARDS)
        // Anti-vacuity: the read reaches the three cards' titles and descriptions.
        expect(words, `the cookie dialog's cards at ${width}px: words read`).toBeGreaterThan(30)
        expect(found, `the cookie dialog's cards at ${width}px and 200% text, a word broken inside it: ${found.join('; ')}`).toEqual([])
      })
    })
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

/** At 360x780 and at 320x640 with the browser's text doubled, every route in the loop passes the width, bar and
    clear-space checks too. The header's wrap at 360px is its named fallback, so the one-row check stays at 390px. At
    320px /pricing's billing switch's row wraps (#1395). There / reached 329px: the hero example's identity line held
    "filed Oct 31, 2025" in one run, and its three figures ran past their equal thirds (HeroExample.tsx). /search reached
    344px: Chrome keeps blank room in a date field for a six-digit year, so each of its two fields was 312px in a 256px
    row (FullTextSearch.tsx). Both fit since E81.

    The legal pages fit at both widths since E131: each page's gutter gives way under enlarged text, and a word still
    wider than its column breaks inside it, the rule on its <main> (`[overflow-wrap:anywhere]`, lib/legalPageLayout.ts)
    inherited by every heading, paragraph and address (the words, after this loop). Before, at 320px /security
    reached 348px on its headings' "Authentication" and "Infrastructure", which this loop allowed by name
    (E131_AT_320) until the fix, and /terms, then outside the loop, 362px on "Indemnification" (362px at 360px too),
    with "MERCHANTABILITY,", "Subscriptions," and "EarningsNerd" past the edge. /privacy fitted at 320px in the site's
    own Inter, as CI's runner and a reader paint it; the agents' sandbox paints its body text in an installed static
    Inter (56-prefer-inter.conf), where "communications," reached 338px
    (lessons/test-layout-numbers-are-one-environments-run.md). */
for (const { width, height } of [
  { width: 360, height: 780 },
  { width: 320, height: 640 },
]) test.describe(`a ${width}px phone at 200% text`, () => {
  test.use({ viewport: { width, height }, isMobile: true, hasTouch: true })
  for (const route of ROUTES) {
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

/** A legal page's gutter gives way before a word breaks, and the wrap is the last resort (E131; chief design's review
    of #1475). Each page's <main> sits in a query container, and narrower than 13em of its text size (a phone under
    200% text) its gutter is 16px, where px-4 had doubled to 32px (lib/legalPageLayout.ts). So at 390px under 200% text
    no word on /security, /terms or /privacy breaks inside it, and at 320px each page's h1 holds whole. A word is read a
    character at a time: one whose characters sit on more than one line is broken. A break after a hyphen is a line
    break between two parts, not a word broken, and an address breaks anywhere by design (#1397), so both are left out.
    Before, at 390px /terms broke "Indemnification" ("Indemnificatio" over "n") in a 326px column, and at 320px
    /security its title ("Securit" over "y") in a 256px one. At 320px a word wider than the 288px column still breaks
    inside it, which is what the wrap is for; the width checks above hold every legal page at each width. */
const LEGAL_ROUTES = ROUTES.filter((route) => ['/security', '/terms', '/privacy'].includes(route.path))

/** The words under `selector` that a line breaks inside, each with the pieces its lines hold and the element it sits
    in, and how many words were read, so a page that rendered nothing cannot pass. */
const brokenWords = (page: Page, selector: string) =>
  page.evaluate((selector) => {
    const found: string[] = []
    let words = 0
    for (const root of document.querySelectorAll(selector)) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
        const el = node.parentElement
        // A visually hidden run is 1px wide, so its every character would read as a line of its own.
        if (!el || el.closest('.sr-only') || el.closest('a[href^="mailto:"]')) continue
        for (const match of node.data.matchAll(/\S+/g)) {
          words += 1
          const start = match.index ?? 0
          const pieces: string[] = []
          let top: number | null = null
          for (let i = 0; i < match[0].length; i++) {
            const char = document.createRange()
            char.setStart(node, start + i)
            char.setEnd(node, start + i + 1)
            const at = Math.round(char.getBoundingClientRect().top)
            if (top === null || at !== top) pieces.push('')
            pieces[pieces.length - 1] += match[0][i]
            top = at
          }
          // A piece but the last that ends on a hyphen (or a non-breaking one) is a break after it, not inside a word.
          if (pieces.slice(0, -1).some((piece) => !/[-‑]$/.test(piece))) {
            const where = `${el.tagName.toLowerCase()} "${(el.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 40)}"`
            found.push(`"${match[0]}" ("${pieces.join('" over "')}") in ${where}`)
          }
        }
      }
    }
    return { words, found }
  }, selector)

for (const state of [
  { width: 390, height: 844, scope: 'main', what: 'every word' },
  { width: 320, height: 640, scope: 'main h1', what: 'its title' },
]) test.describe(`a ${state.width}px phone at 200% text, a legal page's ${state.scope === 'main' ? 'words' : 'title'}`, () => {
  test.use({ viewport: { width: state.width, height: state.height }, isMobile: true, hasTouch: true })
  for (const route of LEGAL_ROUTES) {
    test(`${route.name} (${route.path}) keeps ${state.what} whole at ${state.width}px and 200% text`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        try {
          localStorage.setItem('theme', 'light')
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        } catch {}
      })
      await route.open(page, baseURL!)
      await page.goto(route.path)
      await route.ready(page)
      await page.evaluate(() => document.fonts.ready)
      await doubleText(page)

      const { words, found } = await brokenWords(page, state.scope)
      // Anti-vacuity: the read reaches the page's text (each page holds about 800 words or more) or its title.
      expect(words, `${route.path}: words read in ${state.scope}`).toBeGreaterThan(state.scope === 'main' ? 500 : 0)
      expect(found, `${route.path} at ${state.width}px and 200% text, a word broken inside it: ${found.join('; ')}`).toEqual([])
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

/** A form code is one unbroken run (lessons/frontend-check-brand-layouts-at-200-percent-text.md), so a line that wraps
    never breaks it at its hyphen. Before, the plan table's Filings cells painted "10-K and 10-" over "Q filings" at
    320px, at the default size and under 200% text, and at 390px under 200% text, and the claims row and How it works
    split "10-Q" the same way at 320px under 200% text. FormCodeText now sets each code in a whitespace-nowrap span, as
    the close and the Pro extras' file kinds already were. Each code painted in the landing's rows and its close (the
    hero's are E81's), a plural or possessive included ("8-Ks"), is read with a Range over its own characters and must
    paint on one line; the read must reach the table, the claims, How it works, the Pro row and the close. This read
    keeps its own pattern rather than the component's, so a narrower one there cannot narrow it. */
const FORM_CODE = /\b\d+-[A-Z]+(?:s|['’]s)?\b/
const formCodes = (page: Page, roots = 'main section[data-landing-row], main [data-landing-close]') =>
  page.evaluate(({ source, roots }) => {
    const pattern = new RegExp(source, 'g')
    const found: { where: string; code: string; lines: number; text: string }[] = []
    for (const root of document.querySelectorAll(roots)) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
        const el = node.parentElement
        if (!el || el.closest('.sr-only')) continue
        for (const match of node.data.matchAll(pattern)) {
          const range = document.createRange()
          range.setStart(node, match.index ?? 0)
          range.setEnd(node, (match.index ?? 0) + match[0].length)
          const tops: number[] = []
          for (const rect of range.getClientRects()) {
            if (rect.width > 0 && !tops.some((top) => Math.abs(top - rect.top) < 2)) tops.push(rect.top)
          }
          // A code no layout paints (inside a display:none twin) has no line to break.
          if (tops.length === 0) continue
          found.push({
            where: `${root.id || 'close'}${el.closest('table') ? ' table' : ''}`,
            code: match[0],
            lines: tops.length,
            text: (el.closest('h1, td, dd, p, li, a') ?? el).textContent?.replace(/\s+/g, ' ').trim().slice(0, 60) ?? '',
          })
        }
      }
    }
    return found
  }, { source: FORM_CODE.source, roots })

for (const state of [
  { width: 320, height: 640, doubled: true },
  { width: 390, height: 844, doubled: true },
  { width: 320, height: 640, doubled: false },
]) {
  const at = `${state.width}px${state.doubled ? ' and 200% text' : ' at the default text size'}`
  test.describe(`a ${state.width}px phone${state.doubled ? ' at 200% text' : ''}, the landing's form codes`, () => {
    test.use({ viewport: { width: state.width, height: state.height }, isMobile: true, hasTouch: true })
    test(`home (/) paints every form code in its rows and its close on one line at ${at}`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        try {
          localStorage.setItem('theme', 'light')
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        } catch {}
      })
      await answerGuest(page, baseURL!)
      await page.goto('/')
      await h1(page)
      await expect(page.locator('#pricing table')).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      if (state.doubled) await doubleText(page)

      const codes = await formCodes(page)
      // Anti-vacuity: the read reaches every place on the landing that names a form.
      for (const where of ['pricing table', 'claims', 'contents', 'pro', 'close']) {
        expect(codes.filter((code) => code.where === where).length, `form codes read in ${where} at ${at}`).toBeGreaterThan(0)
      }
      const broken = codes.filter((code) => code.lines !== 1).map((code) => `${code.where}: "${code.code}" on ${code.lines} lines in "${code.text}"`)
      expect(broken, `${at}: each form code paints on one line`).toEqual([])
    })
  })
}

// E142: the waitlist's heading and pick-a-filing step broke their codes at the hyphen at 320px.
// Read every code on the page, including the lead and problem card, rather than only those three.
for (const width of [320, 390]) {
  test.describe(`the waitlist's form codes at ${width}px and 200% text`, () => {
    test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true })
    test(`waitlist (/waitlist) paints every form code on one line at ${width}px and 200% text`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
      })
      await answerGuest(page, baseURL!)
      await page.goto('/waitlist')
      await h1(page)
      await doubleText(page)

      const codes = await formCodes(page, 'main')
      expect(codes.filter((code) => code.text.startsWith('The 10-K,')).map((code) => code.code)).toEqual(['10-K'])
      expect(codes.filter((code) => code.text.startsWith('Pick a 10-K')).map((code) => code.code)).toEqual(['10-K', '10-Q'])
      expect(codes.filter((code) => code.text.startsWith('AI summaries of')).map((code) => code.code)).toEqual(['10-Ks', '10-Qs'])
      const broken = codes.filter((code) => code.lines !== 1).map((code) => `"${code.code}" on ${code.lines} lines in "${code.text}"`)
      expect(broken, `${width}px and 200% text: each waitlist form code paints on one line`).toEqual([])
    })
  })
}

/** The hero under 200% text, read from its rendered boxes at 320, 390 and 1440px (E81). The example's three figures sat
    in equal thirds (HeroExample.tsx), so at 390px each value ran across its 81px cell into the next ("$416.2B", 119px of
    28px data face, met "$112.0B") with every label cut short, and the subhead (LandingHero.tsx) broke "10-Ks" at its
    hyphen there and "10-Qs" at 1440px. Each figure now takes its own width in a row that wraps, and each form code is
    one unbroken run (FormCodeText; the identity line's form a run of its own). The identity line's middots each sit in
    one item with the fact before it, so at 320px, where "AAPL · 10-K ·" does not fit on one line, no middot stands
    alone, and the EDGAR receipt holds its middot to the word before it, whose second line began "·" at 1440px. So,
    from the boxes: three figures, each label whole, each value and change on one painted line inside its own
    figure's content box (its box less its hairline and padding) and inside the example, and no two figures' text
    meeting; every form code the hero paints, in its lead and in the example's identity line, on one line; and no
    painted line in the example starting with a middot, read a character at a time. */
const heroFit = (page: Page) =>
  page.evaluate((source) => {
    const pattern = new RegExp(source, 'g')
    const px = (a: number, b: number) => `${Math.round(a)}-${Math.round(b)}px`
    const hero = document.querySelector('main section[aria-labelledby="hero-h"]')
    const example = hero?.querySelector('section[aria-label="Example summary"]')
    if (!hero || !example) return { figures: [] as string[], problems: ['the page has no hero with its example'], codes: [] as { where: string; code: string; lines: number }[], middots: 0, starts: [] as string[] }
    const card = example.getBoundingClientRect()
    const runOf = (el: Element) => {
      const range = document.createRange()
      range.selectNodeContents(el)
      const tops: number[] = []
      for (const r of range.getClientRects()) if (r.width > 0 && !tops.some((t) => Math.abs(t - r.top) < 2)) tops.push(r.top)
      return { text: (el.textContent ?? '').trim(), rect: range.getBoundingClientRect(), lines: tops.length }
    }
    const figures = [...example.querySelectorAll('dl > div')].map((cell) => {
      const box = cell.getBoundingClientRect()
      const style = getComputedStyle(cell)
      const left = box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft)
      const right = box.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight)
      const dt = cell.querySelector('dt')
      return {
        label: dt?.firstChild?.textContent?.trim() ?? '',
        cut: !dt || dt.scrollWidth > dt.clientWidth + 0.5,
        term: dt?.getBoundingClientRect() ?? box,
        left,
        right,
        runs: [...cell.querySelectorAll('dd')].map(runOf),
      }
    })
    const problems: string[] = []
    const meets = (a: DOMRect, b: DOMRect) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5
    for (const f of figures) {
      if (f.cut) problems.push(`"${f.label}" is cut short in its ${Math.round(f.term.width)}px term`)
      for (const run of f.runs) {
        const at = `"${f.label}": "${run.text}" at ${px(run.rect.left, run.rect.right)}`
        if (run.lines !== 1) problems.push(`${at} paints on ${run.lines} lines`)
        if (run.rect.left < f.left - 0.5 || run.rect.right > f.right + 0.5) problems.push(`${at} passes its figure's content box ${px(f.left, f.right)}`)
        if (run.rect.left < card.left - 0.5 || run.rect.right > card.right + 0.5) problems.push(`${at} passes the example ${px(card.left, card.right)}`)
      }
    }
    for (let i = 0; i < figures.length; i++) {
      for (let j = i + 1; j < figures.length; j++) {
        const a = [figures[i].term, ...figures[i].runs.map((r) => r.rect)]
        const b = [figures[j].term, ...figures[j].runs.map((r) => r.rect)]
        if (a.some((x) => b.some((y) => meets(x, y)))) problems.push(`"${figures[i].label}" and "${figures[j].label}" meet`)
      }
    }
    const codes: { where: string; code: string; lines: number }[] = []
    const walker = document.createTreeWalker(hero, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
      const el = node.parentElement
      if (!el || el.closest('.sr-only')) continue
      for (const match of node.data.matchAll(pattern)) {
        const range = document.createRange()
        range.setStart(node, match.index ?? 0)
        range.setEnd(node, (match.index ?? 0) + match[0].length)
        const tops: number[] = []
        for (const rect of range.getClientRects()) {
          if (rect.width > 0 && !tops.some((top) => Math.abs(top - rect.top) < 2)) tops.push(rect.top)
        }
        if (tops.length === 0) continue
        codes.push({ where: example.contains(node) ? 'example' : 'lead', code: match[0], lines: tops.length })
      }
    }
    // Each painted character of the example, outside the sr-only receipts and commas; a middot is the first on its
    // line when no other character sharing its line box lies to its left.
    const chars: { ch: string; rect: DOMRect }[] = []
    const glyphs = document.createTreeWalker(example, NodeFilter.SHOW_TEXT)
    for (let node = glyphs.nextNode() as Text | null; node; node = glyphs.nextNode() as Text | null) {
      if (!node.parentElement || node.parentElement.closest('.sr-only')) continue
      for (let i = 0; i < node.length; i++) {
        if (!node.data[i].trim()) continue
        const range = document.createRange()
        range.setStart(node, i)
        range.setEnd(node, i + 1)
        const rect = range.getBoundingClientRect()
        if (rect.width > 0) chars.push({ ch: node.data[i], rect })
      }
    }
    const sameLine = (a: DOMRect, b: DOMRect) => Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) < Math.min(a.height, b.height) / 2
    const middots = chars.filter((c) => c.ch === '·')
    const starts: string[] = []
    for (const dot of middots) {
      const before = chars.filter((c) => c !== dot && sameLine(c.rect, dot.rect) && c.rect.right <= dot.rect.left + 0.5)
      const line = chars.filter((c) => sameLine(c.rect, dot.rect)).sort((a, b) => a.rect.left - b.rect.left).map((c) => c.ch).join('')
      if (before.length === 0) starts.push(`the line "${line}" starts with its middot at ${px(dot.rect.left, dot.rect.right)}`)
    }
    return { figures: figures.map((f) => `${f.label}: ${f.runs.map((r) => r.text).join(', ')}`), problems, codes, middots: middots.length, starts }
  }, FORM_CODE.source)

/** The hero strip's rules as painted, at either text size (E81; #1462's review). The strip draws its own rule above
    and below and clips its list (HeroExample.tsx), whose negative margins put a row's leading rule and padding, and
    the first row's top rule, outside the clip, so a figure's own left and top rules stand only between two figures.
    Three coupled values hold that (the list's -ml-[calc(0.75rem_+_1px)] and -mt-px, a figure's pl-3 and its 1px
    rules), and dropping the margins showed a rule at every row start and doubled the top rule with every other check
    green, so the boxes are read: the strip clips and draws its two rules; a figure that starts a row has its left
    rule at or left of the clip's left edge, and one on the first row its top rule at or above the clip's top edge;
    every other figure draws its left rule, and every figure below the first row its top rule, inside the clip; and
    the first figure's label starts flush with the card's content edge, within 0.5px. */
const stripRules = (page: Page) =>
  page.evaluate(() => {
    const px = (n: number) => `${Math.round(n * 10) / 10}px`
    const ruleOf = (style: CSSStyleDeclaration, side: 'Top' | 'Right' | 'Bottom' | 'Left') => parseFloat(style[`border${side}Width`])
    const example = document.querySelector('main section[aria-labelledby="hero-h"] section[aria-label="Example summary"]')
    const list = example?.querySelector('dl')
    const clip = list?.parentElement
    const column = example?.firstElementChild
    if (!example || !list || !clip || !column) return { figures: 0, problems: ['the hero has no figure strip'] }
    const problems: string[] = []
    const clipStyle = getComputedStyle(clip)
    if (clipStyle.overflowX === 'visible' || clipStyle.overflowY === 'visible') problems.push(`the strip does not clip its list (overflow ${clipStyle.overflowX} ${clipStyle.overflowY})`)
    if (ruleOf(clipStyle, 'Top') < 1 || ruleOf(clipStyle, 'Bottom') < 1) problems.push(`the strip draws no rule of its own above or below (${clipStyle.borderTopWidth}, ${clipStyle.borderBottomWidth})`)
    const box = clip.getBoundingClientRect()
    const edge = { left: box.left + ruleOf(clipStyle, 'Left'), right: box.right - ruleOf(clipStyle, 'Right'), top: box.top + ruleOf(clipStyle, 'Top'), bottom: box.bottom - ruleOf(clipStyle, 'Bottom') }
    const cells = [...list.children].map((cell) => {
      const style = getComputedStyle(cell)
      return { label: cell.querySelector('dt')?.firstChild?.textContent?.trim() ?? '', box: cell.getBoundingClientRect(), left: ruleOf(style, 'Left'), top: ruleOf(style, 'Top') }
    })
    cells.forEach((cell, i) => {
      const startsRow = i === 0 || Math.abs(cell.box.top - cells[i - 1].box.top) > 0.5
      const onFirstRow = Math.abs(cell.box.top - cells[0].box.top) <= 0.5
      const leftRule = `${px(cell.box.left)}-${px(cell.box.left + cell.left)}`
      const topRule = `${px(cell.box.top)}-${px(cell.box.top + cell.top)}`
      if (startsRow) {
        if (cell.box.left + cell.left > edge.left + 0.5) problems.push(`"${cell.label}" starts a row with its left rule at ${leftRule}, inside the clip from ${px(edge.left)}`)
      } else if (cell.left < 1) {
        problems.push(`"${cell.label}" draws no rule after the figure before it`)
      } else if (cell.box.left < edge.left - 0.5 || cell.box.left + cell.left > edge.right + 0.5) {
        problems.push(`"${cell.label}" has its left rule at ${leftRule}, outside the clip ${px(edge.left)}-${px(edge.right)}`)
      }
      if (onFirstRow) {
        if (cell.box.top + cell.top > edge.top + 0.5) problems.push(`"${cell.label}" on the first row has its top rule at ${topRule}, inside the clip from ${px(edge.top)}, under the strip's own`)
      } else if (cell.top < 1) {
        problems.push(`"${cell.label}" draws no rule under the row before it`)
      } else if (cell.box.top < edge.top - 0.5 || cell.box.top + cell.top > edge.bottom + 0.5) {
        problems.push(`"${cell.label}" has its top rule at ${topRule}, outside the clip ${px(edge.top)}-${px(edge.bottom)}`)
      }
    })
    const columnStyle = getComputedStyle(column)
    const content = column.getBoundingClientRect().left + ruleOf(columnStyle, 'Left') + parseFloat(columnStyle.paddingLeft)
    const label = list.querySelector('dt')?.firstChild
    if (!label) problems.push('the first figure has no label')
    else {
      const range = document.createRange()
      range.selectNodeContents(label)
      const start = range.getBoundingClientRect().left
      if (Math.abs(start - content) > 0.5) problems.push(`"${cells[0]?.label}" starts at ${px(start)}, not flush with the card's content edge at ${px(content)}`)
    }
    return { figures: cells.length, problems }
  })

for (const viewport of [{ width: 320, height: 640 }, { width: 390, height: 844 }, { width: 1440, height: 900 }]) {
  const at = `${viewport.width}px and 200% text`
  test.describe(`a ${viewport.width}px ${viewport.width < 1024 ? 'phone' : 'desktop'} at 200% text, the hero`, () => {
    test.use({ viewport, isMobile: viewport.width < 1024, hasTouch: viewport.width < 1024 })
    test(`home (/) keeps the hero's figures whole and apart, its form codes on one line and no line starting with a middot at ${at}, and the strip's rules only between two figures at both sizes`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        try {
          localStorage.setItem('theme', 'light')
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        } catch {}
      })
      await answerGuest(page, baseURL!)
      await page.goto('/')
      await h1(page)
      await expect(page.getByRole('region', { name: 'Example summary' }).getByRole('term')).toHaveCount(3)
      await page.evaluate(() => document.fonts.ready)
      // The strip's rules at the default size first, then again with the text doubled.
      const rulesAtDefault = await stripRules(page)
      // The tablet pass's confirmation holds at every width here: the root at 32px, the 48rem query (1536px) not matching.
      await doubleTextOnATablet(page)

      const fit = await heroFit(page)
      const rules = await stripRules(page)
      // Anti-vacuity: three figures, each with its value and its change; codes read in the lead and in the example; the
      // identity line's two middots and the receipt's one read; the strip's three figures read at both sizes.
      expect(fit.figures, `the hero's figures at ${at}`).toHaveLength(3)
      expect(rulesAtDefault.figures, `the strip's figures at ${viewport.width}px and the default size`).toBe(3)
      expect(rules.figures, `the strip's figures at ${at}`).toBe(3)
      expect(fit.middots, `middots read in the example at ${at}`).toBeGreaterThanOrEqual(3)
      for (const figure of fit.figures) expect(figure, `a figure with its value and change at ${at}`).toMatch(/^[^:]+: \S+, \S+$/)
      expect(fit.codes.filter((code) => code.where === 'lead').length, `form codes read in the hero's lead at ${at}`).toBeGreaterThanOrEqual(2)
      expect(fit.codes.filter((code) => code.where === 'example').length, `form codes read in the example at ${at}`).toBeGreaterThanOrEqual(1)
      // Soft, so one run reports the figures, the codes, the middots and the rules together; any of them fails the test.
      expect.soft(fit.problems, `the hero's figures at ${at} (${fit.figures.join('; ')})`).toEqual([])
      const broken = fit.codes.filter((code) => code.lines !== 1).map((code) => `${code.where}: "${code.code}" on ${code.lines} lines`)
      expect.soft(broken, `${at}: each form code in the hero paints on one line`).toEqual([])
      expect.soft(fit.starts, `${at}: no painted line in the example starts with a middot`).toEqual([])
      expect.soft(rulesAtDefault.problems, `${viewport.width}px at the default size: the strip's rules stand only between two figures`).toEqual([])
      expect.soft(rules.problems, `${at}: the strip's rules stand only between two figures`).toEqual([])
    })
  })
}

/** The landing's Trace to Source demo at 200% text (features/marketing/components/TraceToSourceDemo.tsx; E143, chief
    design's rule on #1462): its nested boxes give way from the outside in. Below a 24rem viewport the claim box gives up
    its frame (border, fill and side padding) and sits on the card; the panel keeps its frame and shadow with the capped
    inset (p-cap-3), the card's p-5 is capped too (p-cap-5, E120), and the quote keeps its rule and its pl-2. Before, at
    320px the quote kept a 40px column inside four nested insets, so "advertising," ran 32px past its card, and the
    section reference broke inside its words ("Disc" over "ussi" over "on"); with E120's cap alone the quote kept 88px and
    its words still ran past the panel. At 320, 360 and 390px each painted line of the quote and of the section reference
    lies inside the panel's content box, and no word of either breaks inside it, read a character at a time. */
const TRACE_PANEL = '[role="group"][aria-label="Source detail"]'
const TRACE_TEXT = `${TRACE_PANEL} blockquote, ${TRACE_PANEL} > span:first-child`
const traceFit = (page: Page) =>
  page.locator(TRACE_PANEL).evaluate((panel) => {
    const box = panel.getBoundingClientRect()
    const style = getComputedStyle(panel)
    const left = box.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft)
    const right = box.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight)
    const read: string[] = []
    const outside: string[] = []
    for (const [name, el] of [['quote', panel.querySelector('blockquote')], ['section reference', panel.querySelector(':scope > span:first-child')]] as const) {
      if (!el?.textContent?.trim()) continue
      read.push(name)
      const range = document.createRange()
      range.selectNodeContents(el)
      for (const line of range.getClientRects()) {
        if (line.width === 0) continue
        if (line.left < left - 0.5 || line.right > right + 0.5) {
          outside.push(`${name}: a line at ${Math.round(line.left)}-${Math.round(line.right)}px, the panel's content ${Math.round(left)}-${Math.round(right)}px`)
        }
      }
    }
    return { read, outside }
  })

for (const viewport of [{ width: 320, height: 640 }, { width: 360, height: 780 }, { width: 390, height: 844 }]) {
  const at = `${viewport.width}px and 200% text`
  test.describe(`a ${viewport.width}px phone at 200% text, the Trace to Source demo`, () => {
    test.use({ viewport, isMobile: true, hasTouch: true })
    test(`home (/) keeps the demo's quote and section reference inside the panel with no word broken at ${at}`, async ({ page, baseURL }) => {
      await page.addInitScript(() => {
        try {
          localStorage.setItem('theme', 'light')
          localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
        } catch {}
      })
      await answerGuest(page, baseURL!)
      await page.goto('/')
      await h1(page)
      await expect(page.locator(TRACE_PANEL)).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      await doubleText(page)

      const fit = await traceFit(page)
      // Anti-vacuity: the quote and the section reference are read, each word of both.
      expect(fit.read, `the demo's quote and section reference at ${at}`).toEqual(['quote', 'section reference'])
      const { words, found } = await brokenWords(page, TRACE_TEXT)
      expect(words, `words read in the demo's quote and section reference at ${at}`).toBeGreaterThan(25)
      // Soft, so one run reports both.
      expect.soft(fit.outside, `${at}: every line of the quote and the section reference paints inside the panel`).toEqual([])
      expect.soft(found, `${at}: a word of the quote or the section reference broken inside it`).toEqual([])
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
    CTA card's two columns ran its one-line "See a live example" past its half, taking / to 886px. The footer opens its
    columns at md at the reader's text size, 48rem: 768px at the default size, 1536px with the text doubled; the card
    is the landing's one-line close since D-045, and the landing's rows open their columns at 64rem. At 768 and
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

/** The site header's two menus where the full bar shows at 200% text, signed in (E160). Before E173 and E175 the full
    bar showed from lg, and with the text doubled it wrapped at 1024 to 1440px, its controls (theme toggle, notification
    bell, account menu) on a line of their own below the logo. Under the bar's justify-between a line's only block sat at
    its start, so the bell's menu, 20rem wide and anchored at the bell's right edge (right-0), spanned -408 to 232px and
    the account menu -108 to 372px, every item losing its first letters; the logo's mr-auto and the controls' ml-auto
    keep the controls at the right of their line. The full bar now shows from 72rem, 2304px with the text doubled, where
    it keeps one line (below), so the margins guard a wrap no supported font makes: at 2304 and 2560px a copy fixture
    lengthens the nav's last link until the bar wraps, as a longer nav or a font wider than the switch allows for would,
    and each open menu's box, and every painted line of its text, lies inside the viewport. The full bar's nav and the
    controls' own line below the logo are checked first, so a bar that shows the compact form or stops wrapping cannot
    pass unread. */
const HEADER_MENUS = [
  { menu: 'Notifications', button: /^Notifications/ },
  { menu: 'Account', button: 'Account menu' },
] as const
const headerMenuFit = (page: Page, menu: string) =>
  page.getByRole('menu', { name: menu }).evaluate((el) => {
    const px = (a: number, b: number) => `${Math.round(a)}-${Math.round(b)}px`
    const viewport = document.documentElement.clientWidth
    const problems: string[] = []
    const box = el.getBoundingClientRect()
    if (box.left < -0.5 || box.right > viewport + 0.5) problems.push(`the menu spans ${px(box.left, box.right)}, the viewport 0-${viewport}px`)
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    let lines = 0
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      if (!node.textContent?.trim()) continue
      const range = document.createRange()
      range.selectNodeContents(node)
      for (const line of range.getClientRects()) {
        if (line.width === 0) continue
        lines += 1
        if (line.left < -0.5 || line.right > viewport + 0.5) problems.push(`"${node.textContent.trim().slice(0, 24)}" paints at ${px(line.left, line.right)}`)
      }
    }
    return { lines, problems }
  })

/** Chromium's text setting doubled on a desktop, confirmed taken: the root computes to 32px, and the full bar's 72rem
    query (2304px with the text doubled) matches or not as the width expects. */
async function doubleTextOnADesktop(page: Page, fullBar: boolean) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => ({ root: getComputedStyle(document.documentElement).fontSize, fullBar: matchMedia('(min-width: 72rem)').matches })), {
      message: `the 200% text setting took: the root computes to 32px and the 72rem query ${fullBar ? 'matches' : 'does not match'}`,
    })
    .toEqual({ root: '32px', fullBar })
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
  await page.evaluate(() => document.fonts.ready)
}

for (const viewport of [{ width: 2304, height: 1296 }, { width: 2560, height: 1440 }]) {
  test.describe(`a ${viewport.width}px desktop at 200% text, signed in, the header's menus`, () => {
    test.use({ viewport, isMobile: false, hasTouch: false })
    for (const { menu, button } of HEADER_MENUS) {
      test(`the ${menu} menu opens inside the screen at ${viewport.width}px and 200% text`, async ({ page, baseURL }) => {
        await page.addInitScript(() => {
          try {
            localStorage.setItem('theme', 'light')
            localStorage.setItem('en_session_active', '1')
            localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
          } catch {}
        })
        await answerApi(page, baseURL!, 'pro')
        await page.goto('/pricing')
        await h1(page)
        const trigger = page.getByRole('button', { name: button })
        await expect(trigger).toBeVisible()
        await page.evaluate(() => document.fonts.ready)
        await doubleTextOnADesktop(page, true)

        const nav = page.getByRole('banner').getByRole('navigation', { name: 'Main navigation' })
        await expect(nav, `${viewport.width}px and 200% text: the full bar shows`).toBeVisible()
        await nav.getByRole('link').last().evaluate((link) => {
          link.textContent = `${link.textContent}${' and everything else we have to say on the matter'.repeat(2)}`
        })
        await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
        const wrapped = await trigger.evaluate((el) => {
          const logo = document.querySelector('header[data-site-header] a[aria-label="EarningsNerd home"]')!.getBoundingClientRect()
          return el.getBoundingClientRect().top >= logo.bottom
        })
        expect(wrapped, `${viewport.width}px and 200% text, the nav lengthened: the bar wraps, the controls on a line below the logo`).toBe(true)
        await trigger.click()
        await expect(page.getByRole('menu', { name: menu })).toBeVisible()
        const fit = await headerMenuFit(page, menu)
        expect(fit.lines, `the ${menu} menu's text lines read at ${viewport.width}px`).toBeGreaterThanOrEqual(2)
        expect(fit.problems, `the ${menu} menu at ${viewport.width}px and 200% text`).toEqual([])
      })
    }
  })
}

/** The site header's two bars switch at one width, 72rem (components/Header.tsx; E173 and E175, chief design on #1544,
    comment 6375980005): 1152px at the default size and 2304px with the text doubled. Below it the compact bar shows,
    its menu button and, opened, its menu, while the full bar's nav and controls are display:none; from it, the other way
    round, a menu left open included. A signed-in reader's notification bell shows once in either bar, the compact bar's
    from lg, where the full bar showed it before, and its menu opens inside the screen. At the threshold the full bar
    keeps one line with its widest settled controls: a signed-in reader's, and a guest's with either access mode's
    account link (ACCESS_COPY's cta, set into the link as a copy fixture, since the build answers one mode). So the
    auth check never changes the bar's lines. Before, the full
    bar showed from lg, 1024px at any text size: a guest's row, about 1030px, wrapped at 1024 to 1031px (E173), and with
    the text doubled the bar wrapped at 1024 to 1440px, where the placeholder could share a line the settled controls
    could not (E175). */
const ACCOUNT_FULL = new RegExp(`^(${ACCESS_COPY.invite.cta}|${ACCESS_COPY.public.cta})$`)
/** The full bar's line: its three blocks (the logo, the nav and the desktop controls) are on one line when their middles
    lie within a pixel of each other, as items-center lays out one line; a wrapped bar sets a block a row lower. */
const fullBarLine = (page: Page) =>
  page.locator('header[data-site-header]').evaluate((header) => {
    const blocks = [...header.firstElementChild!.children].filter((el) => getComputedStyle(el).display !== 'none')
    const middles = blocks.map((el) => {
      const box = el.getBoundingClientRect()
      return box.top + box.height / 2
    })
    return { blocks: blocks.length, spread: Math.round(Math.max(...middles) - Math.min(...middles)) }
  })

for (const { below, at, doubled } of [
  { below: 1151, at: 1152, doubled: false },
  { below: 2303, at: 2304, doubled: true },
] as const) {
  const size = doubled ? '200% text' : 'the default text size'
  test.describe(`the site header's two bars at ${size}`, () => {
    test.use({ viewport: { width: below, height: 900 }, isMobile: false, hasTouch: false })
    for (const who of ['guest', 'reader'] as const) {
      test(`${who === 'guest' ? 'a guest' : 'a signed-in reader'} gets the compact bar at ${below}px and the full bar, on one line, at ${at}px`, async ({ page, baseURL }) => {
        await page.addInitScript((reader) => {
          try {
            localStorage.setItem('theme', 'light')
            if (reader) localStorage.setItem('en_session_active', '1')
            localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
          } catch {}
        }, who === 'reader')
        if (who === 'reader') await answerApi(page, baseURL!, 'pro')
        else await answerGuest(page, baseURL!)
        await page.goto('/')
        await h1(page)
        await expect(page.getByRole('status', { name: 'Checking whether you are logged in', includeHidden: true })).toHaveCount(0)
        await page.evaluate(() => document.fonts.ready)
        if (doubled) await doubleTextOnADesktop(page, false)
        const banner = page.getByRole('banner')
        const nav = banner.getByRole('navigation', { name: 'Main navigation' })
        const controls = who === 'guest' ? banner.getByRole('link', { name: 'Log in' }) : banner.getByRole('button', { name: 'Account menu' })

        await expect(nav, `${below}px at ${size}: the full bar's nav is hidden`).toBeHidden()
        await expect(controls, `${below}px at ${size}: the full bar's controls are hidden`).toBeHidden()
        const bell = banner.getByRole('button', { name: /^Notifications/ })
        if (who === 'reader') {
          await expect(bell, `${below}px at ${size}: the compact bar's bell, the one bell shown`).toHaveCount(1)
          await bell.click()
          await expect(page.getByRole('menu', { name: 'Notifications' })).toBeVisible()
          const fit = await headerMenuFit(page, 'Notifications')
          expect(fit.problems, `${below}px at ${size}: the compact bar's notification menu`).toEqual([])
          await page.keyboard.press('Escape')
          await expect(page.getByRole('menu', { name: 'Notifications' })).toBeHidden()
        }
        await banner.getByRole('button', { name: 'Open menu' }).click()
        const menu = page.getByRole('navigation', { name: 'Mobile navigation' })
        await expect(menu, `${below}px at ${size}: the compact bar's menu opens`).toBeVisible()

        await page.setViewportSize({ width: at, height: 900 })
        await expect(nav, `${at}px at ${size}: the full bar's nav shows`).toBeVisible()
        await expect(controls, `${at}px at ${size}: the full bar's controls show`).toBeVisible()
        await expect(banner.getByRole('button', { name: 'Close menu' }), `${at}px at ${size}: the compact bar's menu button is hidden`).toBeHidden()
        await expect(menu, `${at}px at ${size}: the menu left open is hidden with the compact bar`).toBeHidden()
        if (who === 'reader') await expect(bell, `${at}px at ${size}: the full bar's bell, the one bell shown`).toHaveCount(1)

        const link = banner.getByRole('link', { name: ACCOUNT_FULL })
        for (const label of who === 'guest' ? [ACCESS_COPY.invite.cta, ACCESS_COPY.public.cta] : [null]) {
          if (label) {
            await link.evaluate((el, text) => {
              const node = [...el.childNodes].find((child) => child.nodeType === Node.TEXT_NODE && child.textContent?.trim())
              if (!node) throw new Error('the account link has no text of its own')
              node.textContent = text
            }, label)
            await expect(link).toHaveText(label)
          }
          await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
          const line = await fullBarLine(page)
          const what = label ? `a guest's "${label}"` : "a signed-in reader's controls"
          expect(line.blocks, `${at}px at ${size}, ${what}: the logo, the nav and the controls show`).toBe(3)
          expect(line.spread, `${at}px at ${size}, ${what}: the full bar keeps one line (its blocks' middles ${line.spread}px apart)`).toBeLessThanOrEqual(1)
        }
      })
    }
  })
}

/** The site header's bar is a column's child with auto side margins (components/Header.tsx), which a column does not
    stretch: without its w-full the bar shrank to its content at 1440px, from 80-1360px to 291-1149px, and the logo left
    its top-left place (x=112 to x=323). At 1440x900 at the default size the bar spans its container (its max-width,
    centred in the header) and the logo starts at the container's left padding, both read against the header's own box,
    not the bar's, which a shrunken bar would carry with it. Since E160 the one-line bar's free space is shared by the
    logo's mr-auto and the controls' ml-auto rather than by justify-between, so the nav keeps justify-between's place,
    as far from the logo as from the controls, and the controls end at the bar's content edge: without either margin the
    nav would sit against the logo or against the controls. */
test.describe('a 1440px desktop at the default text size', () => {
  test.use({ viewport: { width: 1440, height: 900 }, isMobile: false, hasTouch: false })
  test('home (/) keeps the site header bar across its container, the logo in its top-left place and the nav midway between the logo and the controls', async ({ page, baseURL }) => {
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
    const row = await logo.evaluate((link) => {
      const bar = link.closest('header')!.firstElementChild!
      const [mark, nav, controls] = [...bar.children].map((el) => el.getBoundingClientRect())
      return {
        before: Math.round(nav.left - mark.right),
        after: Math.round(controls.left - nav.right),
        end: Math.round(controls.right),
        edge: Math.round(bar.getBoundingClientRect().right - parseFloat(getComputedStyle(bar).paddingRight)),
      }
    })
    expect(Math.abs(row.before - row.after), `the nav sits as far from the logo (${row.before}px) as from the controls (${row.after}px)`).toBeLessThanOrEqual(1)
    expect(row.end, `the controls end at the bar's content edge (x=${row.edge})`).toBe(row.edge)
  })
})

/** A dialog's header (components/ui/Modal.tsx, ModalHeader) on a phone at 200% text, at 390, 360 and 320px. The icon, the
    title and the close button share a row while the title can keep 9rem beside what shares it, as a Notice's glyph and
    text do; where it cannot, the title goes to a line of its own at the header's full width, under the icon and the close
    button or under the close button alone, and the close button keeps the top right (E158 and E165, chief design on
    #1495 and #1519). Every painted line of the title stays inside the title's box, clear of the close button and inside
    the panel, and no word of it breaks inside itself. Before E158 the stacked title kept the group's width beside the
    close button's column, 64px narrower than the header, so "preferences" (197px) broke in a 152px title at 320px and a
    187px one at 360px; before E165 a title with no icon kept that column too, so "feedback" (153px) broke in a 152px one
    at 320px. Before the title wrapped at all, at 390px under 200% text the icon and the close button left it 60px, and
    its words painted past it, under the close button: "Cookie preferences" to 383px, 26px past the panel's edge, and each
    word of "Verify your email to continue" (Chrome 156). The scrim is fixed, so a dialog adds
    nothing to the page's scroll width: the title's painted lines are read, a character at a time, against the panel and
    the close button, with the page's width checked as well, and the panel's own sideways scroll. The feedback dialog's
    type row widened its panel under 200% text until it took the SegmentedControl, whose segments wrap whole onto
    another row (E169). Three dialogs from three surfaces, all over /pricing: the consent dialog (Customize on a first
    visit) and checkout's email verification prompt, opened by its event as email-verification-resend.spec.ts opens it,
    each with an icon and a close button; and the feedback dialog, with a close button and no icon, opened from its
    launcher by a signed-in reader, as consent-bar-yields.spec.ts signs one in. At the default size the title sits beside
    the icon, or beside the close button, as it always has. */
type HeaderFit = { problems: string[]; panelScroll: string | null; hasIcon: boolean; beside: boolean; stacked: boolean; full: boolean; where: string }

const headerFit = (dialog: Locator): Promise<HeaderFit> =>
  dialog.evaluate((panel) => {
    const px = (a: number, b: number) => `${Math.round(a)}-${Math.round(b)}px`
    const title = panel.querySelector('h2')
    const closeButton = panel.querySelector('button[aria-label="Close"]')
    if (!title || !closeButton) return { problems: ['the header has no title or close button'], panelScroll: null, hasIcon: false, beside: false, stacked: false, full: false, where: '' }
    // A header with no icon has no tile: its title shares the first row with the close button alone (E165).
    const iconTile = title.parentElement?.querySelector(':scope > [aria-hidden="true"]')
    const close = closeButton.getBoundingClientRect()
    const icon = iconTile?.getBoundingClientRect() ?? null
    const box = title.getBoundingClientRect()
    const outer = panel.getBoundingClientRect()
    const inner = { left: outer.left + panel.clientLeft, right: outer.left + panel.clientLeft + panel.clientWidth }
    // The header's content box (the close button's parent): a title on a line of its own takes all of it, under the
    // close button too (E158, E165).
    const header = closeButton.parentElement!
    const headerBox = header.getBoundingClientRect()
    const headerStyle = getComputedStyle(header)
    const content = {
      left: headerBox.left + parseFloat(headerStyle.paddingLeft),
      right: headerBox.right - parseFloat(headerStyle.paddingRight),
      top: headerBox.top + parseFloat(headerStyle.paddingTop),
    }
    const overlaps = (r: { left: number; right: number; top: number; bottom: number }) =>
      r.left < close.right - 0.5 && r.right > close.left + 0.5 && r.top < close.bottom - 0.5 && r.bottom > close.top + 0.5

    // The title's characters as painted: each one's line (its top), its sides and its foot.
    const chars: { ch: string; top: number | null; left: number; right: number; bottom: number }[] = []
    const walker = document.createTreeWalker(title, NodeFilter.SHOW_TEXT)
    for (let node = walker.nextNode() as Text | null; node; node = walker.nextNode() as Text | null) {
      for (let i = 0; i < node.length; i++) {
        const range = document.createRange()
        range.setStart(node, i)
        range.setEnd(node, i + 1)
        const r = range.getBoundingClientRect()
        chars.push({ ch: node.data[i], top: r.width || r.height ? Math.round(r.top) : null, left: r.left, right: r.right, bottom: r.bottom })
      }
    }
    const lines = new Map<number, { text: string; left: number; right: number; top: number; bottom: number }>()
    for (const c of chars) {
      if (c.top === null) continue
      const line = lines.get(c.top) ?? { text: '', left: Infinity, right: -Infinity, top: c.top, bottom: -Infinity }
      line.text += c.ch
      if (c.ch.trim()) [line.left, line.right, line.bottom] = [Math.min(line.left, c.left), Math.max(line.right, c.right), Math.max(line.bottom, c.bottom)]
      lines.set(c.top, line)
    }
    const painted = [...lines.entries()].sort((a, b) => a[0] - b[0]).map(([, line]) => ({ ...line, text: line.text.trim() }))

    const problems: string[] = []
    for (const line of painted) {
      if (line.left < inner.left - 0.5 || line.right > inner.right + 0.5) problems.push(`"${line.text}" paints at ${px(line.left, line.right)}, past the panel's ${px(inner.left, inner.right)}`)
      if (line.left < box.left - 0.5 || line.right > box.right + 0.5) problems.push(`"${line.text}" paints at ${px(line.left, line.right)}, past the title's box at ${px(box.left, box.right)}`)
      if (overlaps(line)) problems.push(`"${line.text}" at ${px(line.left, line.right)} by ${px(line.top, line.bottom)} overlaps the close button at ${px(close.left, close.right)} by ${px(close.top, close.bottom)}`)
    }
    if (box.left < inner.left - 0.5 || box.right > inner.right + 0.5) problems.push(`the title's box at ${px(box.left, box.right)} passes the panel's ${px(inner.left, inner.right)}`)
    if (overlaps(box)) problems.push(`the title's box at ${px(box.left, box.right)} by ${px(box.top, box.bottom)} overlaps the close button at ${px(close.left, close.right)} by ${px(close.top, close.bottom)}`)
    // The close button keeps the header's top right: its margin box (its padded box less the negative margin that
    // lets the padding overhang) sits in the corner of the header's content box, and its padded box inside the panel.
    const closeStyle = getComputedStyle(closeButton)
    const corner = { right: close.right + parseFloat(closeStyle.marginRight), top: close.top - parseFloat(closeStyle.marginTop) }
    if (Math.abs(corner.right - content.right) > 0.5 || Math.abs(corner.top - content.top) > 0.5 || close.right > inner.right + 0.5) problems.push(`the close button at ${px(close.left, close.right)}, top ${Math.round(close.top)}px (its margin box's corner at ${Math.round(corner.right)}px, top ${Math.round(corner.top)}px), is not at the header's top right (the header's content ${px(content.left, content.right)} from ${Math.round(content.top)}px, the panel's right edge ${Math.round(inner.right)}px)`)

    // A word on two lines was broken inside itself: none may be (E158).
    const words: { text: string; tops: Set<number> }[] = []
    let word: { text: string; tops: Set<number> } | null = null
    for (const c of chars) {
      if (!c.ch.trim()) {
        word = null
        continue
      }
      if (!word) words.push((word = { text: '', tops: new Set() }))
      word.text += c.ch
      if (c.top !== null) word.tops.add(c.top)
    }
    const probe = document.createElement('span')
    probe.style.cssText = 'position:absolute;visibility:hidden;white-space:nowrap'
    title.appendChild(probe)
    for (const w of words) {
      if (w.tops.size < 2) continue
      probe.textContent = w.text
      const width = probe.getBoundingClientRect().width
      problems.push(`"${w.text}" (${Math.round(width)}px) breaks across lines in a ${Math.round(box.width)}px title`)
    }
    probe.remove()

    return {
      problems,
      panelScroll: panel.scrollWidth > panel.clientWidth ? `the panel scrolls sideways: ${panel.scrollWidth}px of content in ${panel.clientWidth}px` : null,
      hasIcon: !!icon,
      // Beside: on the first row, after the icon, or before the close button where there is no icon. Stacked: below the
      // first row (the icon and the close button's padded box), from the header content's left edge.
      beside: icon ? box.left >= icon.right - 0.5 && box.top < icon.bottom : box.right <= close.left + 0.5 && box.top < close.bottom,
      stacked: box.top >= Math.max(close.bottom, icon?.bottom ?? close.bottom) - 0.5 && Math.abs(box.left - content.left) <= 0.5,
      full: Math.abs(box.left - content.left) <= 0.5 && Math.abs(box.right - content.right) <= 0.5 && box.right > close.left,
      where: `panel ${px(inner.left, inner.right)}, header content ${px(content.left, content.right)}, ${icon ? `icon ${px(icon.left, icon.right)} by ${px(icon.top, icon.bottom)}` : 'no icon'}, title ${px(box.left, box.right)} by ${px(box.top, box.bottom)} painting ${painted.map((l) => `"${l.text}" ${px(l.left, l.right)}`).join(', ')}, close button ${px(close.left, close.right)} by ${px(close.top, close.bottom)}`,
    }
  })

const DIALOG_HEADERS = [
  {
    name: 'the consent dialog',
    firstVisit: true,
    signedIn: false,
    icon: true,
    title: 'Cookie preferences',
    open: async (p: Page, dialog: Locator) => {
      await p.getByRole('button', { name: 'Customize' }).click()
      await expect(dialog).toBeVisible()
    },
  },
  {
    name: 'the email verification prompt',
    firstVisit: false,
    signedIn: false,
    icon: true,
    title: 'Verify your email to continue',
    // The prompt listens once the page has hydrated; a second event while it is open is the same prompt.
    open: (p: Page, dialog: Locator) =>
      expect(async () => {
        await p.evaluate(() => window.dispatchEvent(new Event('email-verification-required')))
        await expect(dialog).toBeVisible({ timeout: 1000 })
      }).toPass(),
  },
  {
    name: 'the feedback dialog',
    firstVisit: false,
    /** Its launcher shows for a session (FeedbackWidget): a signed-in reader. */
    signedIn: true,
    icon: false,
    title: 'Send feedback',
    open: async (p: Page, dialog: Locator) => {
      await p.getByRole('button', { name: 'Send feedback', exact: true }).click()
      await expect(dialog).toBeVisible()
    },
  },
]

for (const width of [390, 360, 320]) {
  test.describe(`a ${width}px phone at 200% text, a dialog's header`, () => {
    test.use({ viewport: { width, height: 844 }, isMobile: true, hasTouch: true })
    for (const d of DIALOG_HEADERS) {
      const lead = d.icon ? 'the icon' : 'the close button'
      for (const theme of ['light', 'dark'] as const) {
        test(`${d.name} keeps its title beside ${lead} at the default size and under it at 200% text, at the header's full width with no word broken, clear of the close button and inside the panel, at ${width}px in the ${theme} theme`, async ({ page, baseURL }) => {
          await page.addInitScript(([firstVisit, signedIn, chosen]) => {
            try {
              localStorage.setItem('theme', chosen)
              if (!firstVisit) localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
              if (signedIn) localStorage.setItem('en_session_active', '1')
            } catch {}
          }, [d.firstVisit, d.signedIn, theme] as const)
          if (d.signedIn) await answerApi(page, baseURL!, 'pro')
          else await answerGuest(page, baseURL!)
          await page.goto('/pricing')
          await h1(page, 'Pricing')
          expect(await page.evaluate(() => document.documentElement.classList.contains('dark')), `/pricing in the ${theme} theme`).toBe(theme === 'dark')
          const dialog = page.getByRole('dialog', { name: d.title })
          await d.open(page, dialog)
          await page.evaluate(() => document.fonts.ready)
          const at = `${d.name} at ${width}px in the ${theme} theme`

          const atDefault = await headerFit(dialog)
          expect(atDefault.hasIcon, `${at}: the header ${d.icon ? 'has' : 'has no'} icon tile`).toBe(d.icon)
          expect(atDefault.problems, `${at} at the default text size (${atDefault.where})`).toEqual([])
          expect(atDefault.beside, `${at} at the default text size: the title sits beside ${lead} (${atDefault.where})`).toBe(true)
          expect(atDefault.panelScroll, `${at} at the default text size`).toBeNull()

          await doubleText(page)

          const enlarged = await headerFit(dialog)
          expect(enlarged.problems, `${at} and 200% text (${enlarged.where})`).toEqual([])
          expect(enlarged.stacked, `${at} and 200% text: the title goes under ${lead} (${enlarged.where})`).toBe(true)
          expect(enlarged.full, `${at} and 200% text: the title takes the header's full width, under the close button too (${enlarged.where})`).toBe(true)
          expect(enlarged.panelScroll, `${at} and 200% text`).toBeNull()
          const widths = await measure(page)
          expect(widths.scrollWidth, `/pricing with ${d.name} open at ${width}px in the ${theme} theme and 200% text: ${why(widths)}`).toBeLessThanOrEqual(widths.clientWidth)
        })
      }
    }
  })
}
