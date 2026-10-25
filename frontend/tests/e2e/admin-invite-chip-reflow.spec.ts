import { test, expect, type Page } from '@playwright/test'

/**
 * An email chip on /admin/invites (features/admin/components/EmailChipsInput.tsx) keeps its "already invited" marker
 * clear of its remove button at any width and text size. The founder's recheck of PR #1344 found the marker painting
 * through the button at 320px under a 32px root: the address-and-marker group had shrunk to 52px, and the unbreakable
 * "· already" run (the dot held to its word by a no-break space) ran across the button. Below 9.6em of the chips row's
 * own text size, where an invited chip no longer fits on one line, the chip now gives its address the first line whole, wrapped rather than truncated, with the marker
 * and the button under it: the chief designer's review of that fix found the address cut to 52px beside the button
 * ("al…", "bo…", and a bare "n" for an invalid one), so an admin could not tell the chips apart.
 *
 * Each case types two already-invited addresses (alice's and a short one), a short and a long valid one and an
 * invalid one into the field and reads what Chromium paints (the marker's text through a Range, so text spilling out
 * of its own box still counts), in both themes: the marker never intersects the remove button, its dot sits on the
 * line of "already", the marker stays inside its chip, every chip and its button end inside the card, and the chips
 * never widen the page. At 320px and 390px under a 200% root every address shows whole (each character painted inside
 * the address's own box, nothing hidden) on lines no other part of its chip shares, and the remove button keeps its
 * 48px and ends its chip on whatever line it lands, its right edge on the chip's content edge; at 390px there the
 * button sits on the marker's line. At the default size a chip stays a one-line pill where it fits: alice's at 390px and
 * 1440px, and the short one's at 320px, whose row is 15.5em, so a threshold set too high fails here (alice's row at
 * 390px alone held it only below 19.3em). A sweep of widths under a 200% root crosses the 9.6em threshold, so a
 * threshold set too low fails here even where 320px and 390px pass: with the capped card inset (E120) the row at 390px
 * under a 200% root is 8.7em, and an 8em threshold truncated alice's address there by 55px.
 *
 * The 200% cases set the root element's font size, as figure-receipt-reflow does. The container query's em is the row's
 * own text size, so the threshold follows the text however it is enlarged.
 *
 * The feedback list (/admin/feedback) shares the cards and their header rows, so its cases sit here too: at 320px its
 * page never scrolls sideways, at the default size or under a 200% root (its filter row, a flex item without min-w-0,
 * grew to the 255px status select inside a 158px header and took the page to 336px); at 1440px a 50-character reporter
 * address shows whole, wrapped inside its cell, and the table fits its box (with the cell nowrap it was 1264px in
 * 1214px), while a short address and "Anonymous" keep one line each.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API origin is answered inside the
 * browser with page.route fixtures (an admin with two pending invites, and three feedback reports), and the
 * middleware's session gate is satisfied by its non-credential presence cookie.
 */

const API_ORIGIN = new URL(process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').origin
const INVITED = 'alice@example.com'
/** Already invited too: a short address. */
const SHORT = 'bo@ex.io'
/** A short address that is not invited. */
const SHORT_VALID = 'bob@example.com'
const LONG = 'maximilian.featherstonehaugh@example-enterprise.com'
const INVALID = 'not-an-email'
/** Every address the chip cases type, one chip each. */
const CHIPS = [INVITED, SHORT, SHORT_VALID, LONG, INVALID]
/** A reporter's address of 50 characters. */
const REPORTER_50 = 'maximilian.featherstonehaugh@exampleenterprise.com'
const FEEDBACK_LINK = `https://evidence.example.test/report/${'long-filing-reference-'.repeat(12)}?quarter=1#chart`

type Theme = 'light' | 'dark'
type Box = { left: number; right: number; top: number; bottom: number }

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
        return json(200, {
          invites: [INVITED, SHORT].map((email, i) => ({ id: i + 1, email, status: 'pending', cohort: 'beta', expires_at: '2026-11-01T00:00:00Z', used_at: null, user_id: null, created_at: '2026-10-14T00:00:00Z' })),
        })
      case '/api/admin/feedback':
        // One report of each type and status, so the badge columns take their widest.
        return json(200, {
          feedback: [
            [REPORTER_50, 'feature', 'triaged'],
            [INVITED, 'bug', 'new'],
            [null, 'general', 'resolved'],
          ].map(([user_email, type, status], i) => ({ id: i + 1, user_id: user_email ? 42 + i : null, user_email, type, message: `The summary export button does nothing on Safari.\n${FEEDBACK_LINK}`, page_url: '/filing/123', status, created_at: '2026-10-14T00:00:00Z' })),
        })
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
  await field.fill(CHIPS.join(', '))
  await field.press('Enter')
  for (const email of CHIPS) await expect(page.getByRole('button', { name: `Remove ${email}` })).toBeVisible()
  await expect(page.getByText('· already invited')).toHaveCount(2)
  await page.evaluate(() => document.fonts.ready)
}

const inviteCard = (page: Page) => page.locator('section', { has: page.getByRole('heading', { name: 'Invite people' }) })

/** What Chromium paints for the chip of `invited`, an already-invited address (alice's unless another is named). */
async function measure(page: Page, rootFont: string, invited = INVITED) {
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
  }, invited)
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

/**
 * The page does not scroll sideways, at every width and text size here. At 320px under a 200% root "Send invites" once
 * widened it before any chip was added (278px in the card's 158px); since #1278 a Button's label wraps below a 24rem
 * viewport, and the page fits there too.
 */
function expectNoSidewaysScroll(m: Measure, label: string) {
  expect(m.page.withChips, `${label}: the page scrolls sideways`).toBe(m.page.clientWidth)
}

/** The document's width and the viewport's once the root font is set (figure-receipt-reflow's 200% method). */
async function pageWidth(page: Page, rootFont: string) {
  return page.evaluate((size) => {
    document.documentElement.style.fontSize = size
    return { scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth }
  }, rootFont)
}

/** Every chip's address against its own box, and the other parts of its chip. */
async function measureAddresses(page: Page, rootFont: string) {
  await page.evaluate((size) => {
    document.documentElement.style.fontSize = size
  }, rootFont)
  return inviteCard(page).evaluate((card) => {
    const box = (r: DOMRect): Box => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom })
    return [...card.querySelectorAll<HTMLButtonElement>('button[aria-label^="Remove "]')].map((button) => {
      const email = button.getAttribute('aria-label')!.slice('Remove '.length)
      const chip = button.parentElement!
      // The innermost element that holds the address alone (the group around it may hold nothing else).
      const address = [...chip.querySelectorAll('span')].filter((span) => span.textContent === email).at(-1)!
      // Where each character is painted, hidden or not: a truncated address still lays out what it hides.
      const text = address.firstChild as Text
      const range = document.createRange()
      const glyphs = Array.from({ length: text.data.length }, (_, i) => {
        range.setStart(text, i)
        range.setEnd(text, i + 1)
        return box(range.getBoundingClientRect())
      })
      const style = getComputedStyle(chip)
      const outer = chip.getBoundingClientRect()
      const marker = [...chip.querySelectorAll('span')].find((span) => span.textContent!.startsWith('·'))
      const icon = chip.querySelector(':scope > svg')
      return {
        email,
        address: box(address.getBoundingClientRect()),
        hidden: { x: address.scrollWidth - address.clientWidth, y: address.scrollHeight - address.clientHeight },
        glyphs,
        content: {
          left: outer.left + parseFloat(style.borderLeftWidth) + parseFloat(style.paddingLeft),
          right: outer.right - parseFloat(style.borderRightWidth) - parseFloat(style.paddingRight),
        },
        others: [button, marker, icon].filter((part): part is Element => part != null).map((part) => box(part.getBoundingClientRect())),
        button: box(button.getBoundingClientRect()),
        marker: marker ? box(marker.getBoundingClientRect()) : null,
      }
    })
  })
}

type Addresses = Awaited<ReturnType<typeof measureAddresses>>

/**
 * Below 9.6em every address shows whole: each character painted inside the address's own box, nothing hidden (so no
 * ellipsis), the box as wide as the chip's content and on lines of its own, above the marker, the invalid glyph and the
 * remove button, which keeps its 48px under a 200% root.
 */
function expectWholeAddresses(chips: Addresses, label: string) {
  expect(chips.map(({ email }) => email).sort(), `${label}: the chips`).toEqual([...CHIPS].sort())
  for (const { email, address, hidden, glyphs, content, others, button } of chips) {
    expect(hidden.x, `${label}: ${email} hides part of its address`).toBeLessThanOrEqual(1)
    expect(hidden.y, `${label}: ${email} hides part of its address`).toBeLessThanOrEqual(1)
    glyphs.forEach((glyph, i) => {
      const inside = glyph.left >= address.left - 0.5 && glyph.right <= address.right + 0.5 && glyph.top >= address.top - 0.5 && glyph.bottom <= address.bottom + 0.5
      expect(inside, `${label}: "${email[i]}" (character ${i + 1} of ${email}) is painted outside its address`).toBe(true)
    })
    expect(address.left, `${label}: the address ${email} does not start the chip's line`).toBeLessThan(content.left + 1)
    expect(address.right, `${label}: the address ${email} does not fill the chip's line`).toBeGreaterThan(content.right - 1)
    for (const other of others) expect(other.top, `${label}: ${email} shares its address's line`).toBeGreaterThanOrEqual(address.bottom - 0.5)
    expect(button.right - button.left, `${label}: the remove button of ${email}`).toBeCloseTo(48, 0)
    expect(button.bottom - button.top, `${label}: the remove button of ${email}`).toBeCloseTo(48, 0)
  }
}

/**
 * Below 9.6em the remove button ends its chip on whatever line it lands, as it does above: its right edge on the chip's
 * content edge, alone on a line, beside the invalid glyph or after the marker.
 */
function expectButtonsEndChips(chips: Addresses, label: string) {
  for (const { email, button, content } of chips) {
    expect(Math.abs(button.right - content.right), `${label}: the remove button of ${email} does not end its chip`).toBeLessThanOrEqual(1)
  }
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
    test('at 320px the marker clears the remove button at the default size and under a 200% root font, where every address shows whole, and a short chip is one line at the default size', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 320, height: 900 })
      await openInvites(page, baseURL!, theme)
      for (const [rootFont, text] of [['', 'default text'], ['32px', '200% text']] as const) {
        const label = `320px, ${text}`
        const m = await measure(page, rootFont)
        expectClear(m, label)
        expectNoSidewaysScroll(m, label)
      }
      // The narrow state never splits a chip that fits: at the default size this row is 14.9em and the short chip
      // fits it on one line, so a threshold above 14.9em fails here; alice's one-line pill at 390px catches one above
      // 19.3em only.
      expectOneLine(await measure(page, '', SHORT), '320px, default text, a short address')
      const addresses = await measureAddresses(page, '32px')
      expectWholeAddresses(addresses, '320px, 200% text')
      expectButtonsEndChips(addresses, '320px, 200% text')
    })

    test('at 390px the marker clears the remove button under a 200% root font, where every address shows whole, and the chip is one line at the default size', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 390, height: 900 })
      await openInvites(page, baseURL!, theme)
      const normal = await measure(page, '')
      expectClear(normal, '390px, default text')
      expectNoSidewaysScroll(normal, '390px, default text')
      expectOneLine(normal, '390px, default text')
      const enlarged = await measure(page, '32px')
      expectClear(enlarged, '390px, 200% text')
      expectNoSidewaysScroll(enlarged, '390px, 200% text')
      const addresses = await measureAddresses(page, '32px')
      expectWholeAddresses(addresses, '390px, 200% text')
      expectButtonsEndChips(addresses, '390px, 200% text')
      // Here "· already" and the button fit side by side, so the button sits on the marker's line.
      for (const { email, marker, button } of addresses) {
        if (!marker) continue
        const middle = (button.top + button.bottom) / 2
        expect(marker.top < middle && middle < marker.bottom, `390px, 200% text: the remove button of ${email} is not on its marker's line`).toBe(true)
      }
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
    test('details wrap long links at 390px and 200% text, with keyboard close and no preview fetch', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 390, height: 400 })
      const evidenceRequests: string[] = []
      page.on('request', (request) => {
        if (new URL(request.url()).hostname === 'evidence.example.test') evidenceRequests.push(request.url())
      })
      await openAdmin(page, baseURL!, theme, '/admin/feedback')
      await page.evaluate(() => { document.documentElement.style.fontSize = '32px' })
      const opener = page.getByRole('button', { name: 'View details for feedback 1' })
      await opener.focus()
      await opener.press('Enter')
      const dialog = page.getByRole('dialog', { name: 'Feedback details' })
      const close = dialog.getByRole('button', { name: 'Close' })
      await expect(close).toBeFocused()
      const link = dialog.getByRole('link', { name: FEEDBACK_LINK })
      await expect(link).toHaveAttribute('href', FEEDBACK_LINK)
      await page.keyboard.press('Tab')
      await expect(link).toBeFocused()
      await expect(link).toBeInViewport()
      const fit = await dialog.evaluate((panel) => {
        const bounds = panel.getBoundingClientRect()
        const link = panel.querySelector('a')!
        return {
          sideways: panel.scrollWidth > panel.clientWidth,
          outside: [...link.getClientRects()].some((rect) => rect.left < bounds.left || rect.right > bounds.right),
          pageSideways: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        }
      })
      expect(fit).toEqual({ sideways: false, outside: false, pageSideways: false })
      await page.keyboard.press('Tab')
      await expect(close).toBeFocused()
      await expect(close).toBeInViewport()
      await page.keyboard.press('Escape')
      await expect(dialog).toHaveCount(0)
      await expect(opener).toBeFocused()
      expect(evidenceRequests).toEqual([])
    })

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

    test('at 1440px a 50-character reporter address shows whole inside its cell, and the table fits its box', async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 1440, height: 900 })
      await openAdmin(page, baseURL!, theme, '/admin/feedback')
      await expect(page.getByRole('table').getByText(REPORTER_50)).toBeVisible()
      await page.evaluate(() => document.fonts.ready)
      const m = await page.getByRole('table').evaluate((table, reporters) => {
        const box = table.parentElement!
        const right = (el: Element) => el.getBoundingClientRect().right
        const cells = reporters.map((reporter) => {
          const cell = [...table.querySelectorAll('td')].find((td) => td.textContent === reporter)!
          const style = getComputedStyle(cell)
          const outer = cell.getBoundingClientRect()
          const text = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT).nextNode() as Text
          const range = document.createRange()
          // Where each character is painted, and on how many lines.
          const glyphs = Array.from({ length: text.data.length }, (_, i) => {
            range.setStart(text, i)
            range.setEnd(text, i + 1)
            const r = range.getBoundingClientRect()
            return { left: r.left, right: r.right }
          })
          range.selectNodeContents(text)
          return {
            reporter,
            glyphs,
            lines: new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size,
            content: { left: outer.left + parseFloat(style.paddingLeft), right: outer.right - parseFloat(style.paddingRight) },
          }
        })
        return {
          table: table.getBoundingClientRect().width,
          box: { clientWidth: box.clientWidth, scrollWidth: box.scrollWidth, right: right(box) },
          selects: [...table.querySelectorAll('select')].map(right),
          cells,
        }
      }, [REPORTER_50, INVITED, 'Anonymous'])
      const label = `1440px, ${theme}`
      expect(m.table, `${label}: the table is wider than its box`).toBeLessThanOrEqual(m.box.clientWidth + 0.5)
      expect(m.box.scrollWidth, `${label}: the table's box scrolls`).toBe(m.box.clientWidth)
      for (const select of m.selects) expect(select, `${label}: a status select ends past the box`).toBeLessThanOrEqual(m.box.right + 0.5)
      for (const { reporter, glyphs, lines, content } of m.cells) {
        glyphs.forEach((glyph, i) => {
          const inside = glyph.left >= content.left - 0.5 && glyph.right <= content.right + 0.5
          expect(inside, `${label}: "${reporter[i]}" (character ${i + 1} of ${reporter}) is painted outside its cell`).toBe(true)
        })
        if (reporter === REPORTER_50) expect(lines, `${label}: ${reporter} does not wrap inside its cell`).toBeGreaterThan(1)
        else expect(lines, `${label}: ${reporter} wraps, its column squeezed`).toBe(1)
      }
    })
  })
}
