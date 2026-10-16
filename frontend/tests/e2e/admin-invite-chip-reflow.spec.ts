import { test, expect, type Page } from '@playwright/test'

/**
 * An email chip on /admin/invites (features/admin/components/EmailChipsInput.tsx) keeps its "already invited" marker
 * clear of its remove button at any width and text size. The founder's recheck of PR #1344 found the marker painting
 * through the button at 320px under a 32px root: the address-and-marker group had shrunk to 52px, and the unbreakable
 * "· already" run (the dot held to its word by a no-break space) ran across the button. Below 8em of the chips row's
 * own text size the chip now gives the marker a line of its own, under the address and the button.
 *
 * Each case types an already-invited address and a long valid one into the field and reads what Chromium paints (the
 * marker's text through a Range, so text spilling out of its own box still counts), in both themes: the marker never
 * intersects the remove button, its dot sits on the line of "already", the marker stays inside its chip, every chip
 * and its button end inside the card, and the chips never widen the page. At the default size the chip stays a
 * one-line pill where it fits (390px and 1440px). A sweep of widths under a 200% root crosses the 8em threshold, so a
 * threshold set too low fails here even where 320px and 390px pass.
 *
 * The 200% cases set the root element's font size, as catch-card-reflow does. The container query's em is the row's
 * own text size, so the threshold follows the text however it is enlarged.
 *
 * The feedback list (/admin/feedback) shares the cards and their header rows, so its cases sit here too: at 320px its
 * page never scrolls sideways, at the default size or under a 200% root (its filter row, a flex item without min-w-0,
 * grew to the 255px status select inside a 158px header and took the page to 336px).
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API origin is answered inside the
 * browser with page.route fixtures (an admin with one pending invite, and one feedback report), and the middleware's
 * session gate is satisfied by its non-credential presence cookie.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const INVITED = 'alice@example.com'
const LONG = 'maximilian.featherstonehaugh@example-enterprise.com'

type Theme = 'light' | 'dark'
type Box = { left: number; right: number; top: number; bottom: number }

/**
 * At 320px under a 200% root the page is wider than the viewport before any chip is added: "Send invites" (a Button's
 * padding, icon and one-line label, 278px against the card's 158px) widens it, an overflow the founder's recheck sets
 * apart from this finding. There the chips are held to adding nothing, and the case fails once the page fits, so the
 * exception is dropped with the overflow.
 */
const SCROLLS_BEFORE_ANY_CHIP = new Set(['320px, 200% text'])

/** Opens an admin page as an admin, the API answered in the browser. */
async function openAdmin(page: Page, baseURL: string, theme: Theme, path: string) {
  const origin = new URL(baseURL).origin
  await page.context().addCookies([{ name: 'en_session', value: '1', url: origin }])
  await page.addInitScript((theme: Theme) => {
    try {
      localStorage.setItem('theme', theme)
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  // Credentialed cross-origin responses need these two; Playwright answers any preflight itself.
  const cors = { 'access-control-allow-origin': origin, 'access-control-allow-credentials': 'true' }
  await page.route((url) => url.origin === API_ORIGIN, (route) => {
    const json = (status: number, body: unknown) => route.fulfill({ status, headers: cors, json: body })
    switch (new URL(route.request().url()).pathname) {
      case '/api/auth/me':
        return json(200, { id: 1, email: 'ada@example.com', full_name: 'Ada', is_pro: false, is_beta: false, is_admin: true, email_verified: true })
      case '/api/admin/invites':
        return json(200, { invites: [{ id: 1, email: INVITED, status: 'pending', cohort: 'beta', expires_at: '2026-11-01T00:00:00Z', used_at: null, user_id: null, created_at: '2026-10-14T00:00:00Z' }] })
      case '/api/admin/feedback':
        return json(200, { feedback: [{ id: 1, user_id: 42, user_email: INVITED, type: 'bug', message: 'The summary export button does nothing on Safari.', page_url: '/filing/123', status: 'new', created_at: '2026-10-14T00:00:00Z' }] })
      default:
        return json(404, { detail: 'Not found' })
    }
  })
  await page.goto(path)
}

async function openInvites(page: Page, baseURL: string, theme: Theme) {
  await openAdmin(page, baseURL, theme, '/admin/invites')
  // The field marks an address as invited only once the list has loaded.
  await expect(page.getByRole('table').getByText(INVITED)).toBeVisible()
  const field = page.getByLabel('Email addresses')
  await field.fill(`${INVITED}, ${LONG}`)
  await field.press('Enter')
  await expect(page.getByRole('button', { name: `Remove ${LONG}` })).toBeVisible()
  await expect(page.getByText('· already invited')).toBeVisible()
  await page.evaluate(() => document.fonts.ready)
}

const inviteCard = (page: Page) => page.locator('section', { has: page.getByRole('heading', { name: 'Invite people' }) })

async function measure(page: Page, rootFont: string) {
  await page.evaluate((size) => {
    document.documentElement.style.fontSize = size
  }, rootFont)
  return inviteCard(page).evaluate((card, invited) => {
    const box = (r: DOMRect): Box => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom })
    const style = getComputedStyle(card)
    const outer = card.getBoundingClientRect()
    const content = {
      left: outer.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
      right: outer.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight),
    }
    const removes = [...card.querySelectorAll<HTMLButtonElement>('button[aria-label^="Remove "]')]
    const chips = removes.map((button) => ({
      name: button.getAttribute('aria-label')!.slice('Remove '.length),
      chip: box(button.parentElement!.getBoundingClientRect()),
      button: box(button.getBoundingClientRect()),
    }))
    const remove = removes.find((button) => button.getAttribute('aria-label') === `Remove ${invited}`)!
    const chip = remove.parentElement!
    const spans = [...chip.querySelectorAll('span')]
    const marker = spans.find((span) => span.textContent!.startsWith('·'))!
    const address = spans.find((span) => span.textContent === invited)!
    // Where the marker's text is painted: the whole run, the dot, and the word the no-break space holds it to.
    const text = marker.firstChild as Text
    const painted = (start: number, end: number) => {
      const range = document.createRange()
      range.setStart(text, start)
      range.setEnd(text, end)
      return range
    }
    const already = text.data.indexOf('already')
    const whole = painted(0, text.data.length)
    // The chips' share of any sideways scroll: the document's width with the chip row shown and with it taken out.
    const doc = document.documentElement
    const row = chip.parentElement!
    const withChips = doc.scrollWidth
    row.style.display = 'none'
    const withoutChips = doc.scrollWidth
    row.style.display = ''
    return {
      content,
      chips,
      chip: box(chip.getBoundingClientRect()),
      button: box(remove.getBoundingClientRect()),
      address: box(address.getBoundingClientRect()),
      marker: box(whole.getBoundingClientRect()),
      markerLines: [...whole.getClientRects()].map(box),
      dot: box(painted(0, 1).getBoundingClientRect()),
      already: box(painted(already, already + 'already'.length).getBoundingClientRect()),
      page: { clientWidth: doc.clientWidth, withChips, withoutChips },
    }
  }, INVITED)
}

type Measure = Awaited<ReturnType<typeof measure>>

const overlaps = (a: Box, b: Box) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5

/** What holds at every width and text size. */
function expectClear(m: Measure, label: string) {
  expect(overlaps(m.marker, m.button), `${label}: the "already invited" marker paints over its remove button`).toBe(false)
  expect(Math.abs(m.dot.top - m.already.top), `${label}: the marker's dot and "already" sit on different lines`).toBeLessThan(1)
  expect(m.marker.left, `${label}: the marker starts outside its chip`).toBeGreaterThanOrEqual(m.chip.left - 0.5)
  expect(m.marker.right, `${label}: the marker ends outside its chip`).toBeLessThanOrEqual(m.chip.right + 0.5)
  for (const { name, chip, button } of m.chips) {
    expect(chip.left, `${label}: the chip of ${name} starts outside the card`).toBeGreaterThanOrEqual(m.content.left - 0.5)
    expect(chip.right, `${label}: the chip of ${name} ends outside the card`).toBeLessThanOrEqual(m.content.right + 0.5)
    expect(button.right, `${label}: the remove button of ${name} ends outside its chip`).toBeLessThanOrEqual(chip.right + 0.5)
  }
  expect(m.page.withChips, `${label}: the chips widen the page`).toBe(m.page.withoutChips)
}

/** The page does not scroll sideways (see SCROLLS_BEFORE_ANY_CHIP for the one case where it does without the chips). */
function expectNoSidewaysScroll(m: Measure, label: string) {
  if (SCROLLS_BEFORE_ANY_CHIP.has(label)) {
    expect(m.page.withoutChips, `${label}: the page now fits before any chip is added; drop it from SCROLLS_BEFORE_ANY_CHIP`).toBeGreaterThan(m.page.clientWidth)
  } else {
    expect(m.page.withChips, `${label}: the page scrolls sideways`).toBe(m.page.clientWidth)
  }
}

/** The document's width and the viewport's once the root font is set (catch-card-reflow's 200% method). */
async function pageWidth(page: Page, rootFont: string) {
  return page.evaluate((size) => {
    document.documentElement.style.fontSize = size
    return { scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }
  }, rootFont)
}

/** The address, the whole marker and the remove button share one line. */
function expectOneLine(m: Measure, label: string) {
  expect(m.markerLines.every((line) => Math.abs(line.top - m.marker.top) < 1), `${label}: the marker wraps`).toBe(true)
  expect(Math.abs(m.address.top - m.marker.top), `${label}: the marker is not on the address's line`).toBeLessThan(1)
  const middle = (m.marker.top + m.marker.bottom) / 2
  expect(m.button.top < middle && middle < m.button.bottom, `${label}: the remove button is not on the marker's line`).toBe(true)
}

for (const theme of ['light', 'dark'] as const) {
  test.describe(`an already-invited chip, ${theme} theme`, () => {
    test('at 320px the marker clears the remove button at the default size and under a 200% root font', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 320, height: 900 })
      await openInvites(page, baseURL!, theme)
      for (const [rootFont, text] of [['', 'default text'], ['32px', '200% text']] as const) {
        const label = `320px, ${text}`
        const m = await measure(page, rootFont)
        expectClear(m, label)
        expectNoSidewaysScroll(m, label)
      }
    })

    test('at 390px the marker clears the remove button under a 200% root font, and the chip is one line at the default size', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 390, height: 900 })
      await openInvites(page, baseURL!, theme)
      const normal = await measure(page, '')
      expectClear(normal, '390px, default text')
      expectNoSidewaysScroll(normal, '390px, default text')
      expectOneLine(normal, '390px, default text')
      const enlarged = await measure(page, '32px')
      expectClear(enlarged, '390px, 200% text')
      expectNoSidewaysScroll(enlarged, '390px, 200% text')
    })

    test('under a 200% root font the marker clears the remove button at every width from 320px to 480px', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 320, height: 900 })
      await openInvites(page, baseURL!, theme)
      for (let width = 320; width <= 480; width += 10) {
        await page.setViewportSize({ width, height: 900 })
        expectClear(await measure(page, '32px'), `${width}px, 200% text`)
      }
    })

    test('at 1440px the chip is one line at the default size', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 1440, height: 900 })
      await openInvites(page, baseURL!, theme)
      const m = await measure(page, '')
      expectClear(m, '1440px, default text')
      expectNoSidewaysScroll(m, '1440px, default text')
      expectOneLine(m, '1440px, default text')
    })
  })

  test.describe(`the feedback list, ${theme} theme`, () => {
    test('at 320px the page does not scroll sideways at the default size and under a 200% root font', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 320, height: 900 })
      await openAdmin(page, baseURL!, theme, '/admin/feedback')
      await expect(page.getByRole('table').getByText(INVITED)).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      for (const [rootFont, text] of [['', 'default text'], ['32px', '200% text']] as const) {
        const { scrollWidth, clientWidth } = await pageWidth(page, rootFont)
        expect(clientWidth, `320px, ${text}: the viewport`).toBe(320)
        expect(scrollWidth, `320px, ${text}: /admin/feedback scrolls sideways`).toBe(clientWidth)
      }
    })
  })
}
