import { test, expect, type Page } from '@playwright/test'
import { EXCERPT, PANE, answerApi, type Theme } from './fixtures/filing3Api'

/**
 * EN-04: a wide filing table never breaks the in-app filing reader, in a real Chromium.
 *
 * The reader is a flex item whose auto inline margins turn off stretch, so it used to size itself to
 * its widest table (the 9-column segment table, about 770px): on a desktop it spilled out of its
 * 420px pane and the whole page scrolled sideways, and a citation's scrollIntoView slid the page too;
 * on a phone the bottom sheet (position: fixed, so the document never got wider) simply clipped the
 * paragraphs and the table. Now the reader fills its pane and stops there, each table scrolls in its
 * own box (a named, focusable region whenever it does scroll), and a citation jump scrolls the reader
 * and that box only.
 *
 * The measurements are the ones that can fail with the bug: the document's scroll width at 1440x900,
 * the reader's edges against its pane's, each text block's right edge against the sheet's at 390x844
 * (document-level scroll width, and the reader's own scrollWidth === clientWidth, both pass there with
 * the bug), the table box's own scroll width, and window.scrollX plus the cited passage's rectangle
 * after the jump.
 *
 * Filing text: no production filing is known to have any, so the reader gets the synthetic, labelled
 * fixture fixtures/filing-3-content.md (see its header) through answerApi's `tables` content, for a
 * Pro visitor. CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the API is
 * answered in the browser. DOM measurements only: no screen reader ran.
 */

const CHIP = 'Source: Verified in filing'
const READER = `${PANE} .filing-reader`

async function openPage(page: Page, baseURL: string, theme: Theme) {
  await answerApi(page, baseURL, 'pro', 'tables')
  // Consent answered and the first-run coachmark seen: neither is this spec's subject.
  await page.addInitScript((t: string) => {
    try {
      localStorage.setItem('theme', t)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      // components/CookieConsent.tsx reads STORAGE_KEY 'cookie_consent' (its own preference shape).
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
  await page.goto('/filing/3')
  const chip = page.getByRole('button', { name: CHIP }).first()
  await expect(chip).toBeVisible()
  return chip
}

/** The reader rendered the fixture: its widest table (9 header cells) is in the DOM. */
async function readerReady(page: Page) {
  await expect(page.locator(`${READER} table`).filter({ hasText: 'Reportable since' })).toHaveCount(1)
}

/** The cited passage is highlighted (CSS Custom Highlight API: one Range registered). */
async function highlighted(page: Page) {
  await expect
    .poll(() => page.evaluate(() => (CSS as unknown as { highlights: Map<string, { size: number }> }).highlights.get('copilot-citation')?.size ?? 0))
    .toBe(1)
}

/** Wait until the citation's smooth scroll has stopped: nothing scrolled for three samples running. */
async function settled(page: Page) {
  let previous = ''
  let stable = 0
  for (let i = 0; i < 60 && stable < 3; i++) {
    const now = await page.evaluate((reader) => {
      const scrollers = [document.querySelector(reader), ...Array.from(document.querySelectorAll(`${reader} table`)).map((t) => t.parentElement)]
      return JSON.stringify([window.scrollX, window.scrollY, ...scrollers.map((el) => [el?.scrollTop, el?.scrollLeft])])
    }, READER)
    stable = now === previous ? stable + 1 : 0
    previous = now
    await page.waitForTimeout(100)
  }
}

interface Box {
  left: number
  right: number
  top: number
  bottom: number
}

interface TableBox {
  scrollWidth: number
  clientWidth: number
  right: number
  role: string | null
  name: string | null
  tabIndex: number
}

interface Layout {
  doc: { scrollWidth: number; clientWidth: number; scrollX: number }
  /** The part of the reader the user can see: its scrollport, within the pane and the viewport. */
  visible: Box
  pane: Box
  reader: Box & { width: number; parentClientWidth: number; maxWidth: number; paragraphMaxWidth: number }
  /** Text blocks reaching past the visible right edge (clipped, or reachable only by scrolling the reader sideways). */
  clipped: string[]
  /** Each table's own scroll box: its nearest ancestor below the reader that scrolls sideways (null if none). */
  tables: { columns: number; box: TableBox | null }[]
  /** The cited passage's rectangle (the highlight's Range), if a citation is highlighted. */
  cited: Box | null
}

const layout = (page: Page): Promise<Layout> =>
  page.evaluate(
    ({ pane, reader }) => {
      const shell = document.querySelector<HTMLElement>(pane)!
      const r = document.querySelector<HTMLElement>(reader)!
      const box = (el: Element): Box => {
        const b = el.getBoundingClientRect()
        return { left: b.left, right: b.right, top: b.top, bottom: b.bottom }
      }
      // Inner (padding-box, scrollbar excluded) edges of a scroll container or the pane.
      const inner = (el: HTMLElement): Box => {
        const b = el.getBoundingClientRect()
        const left = b.left + el.clientLeft
        const top = b.top + el.clientTop
        return { left, right: left + el.clientWidth, top, bottom: top + el.clientHeight }
      }
      const p = inner(shell)
      const rd = inner(r)
      const visible: Box = {
        left: Math.max(p.left, rd.left, 0),
        right: Math.min(p.right, rd.right, window.innerWidth),
        top: Math.max(p.top, rd.top, 0),
        bottom: Math.min(p.bottom, rd.bottom, window.innerHeight),
      }
      // A prose child of the reader (the fixture opens with a blockquote, whose own p has no measure).
      const paragraph = r.querySelector(':scope > p')!
      const tables = Array.from(r.querySelectorAll('table')).map((t) => {
        let el: HTMLElement | null = t.parentElement
        while (el && el !== r && !['auto', 'scroll'].includes(getComputedStyle(el).overflowX)) el = el.parentElement
        const scroller = el && el !== r ? el : null
        return {
          columns: t.querySelectorAll('thead th').length,
          box: scroller
            ? {
                scrollWidth: scroller.scrollWidth,
                clientWidth: scroller.clientWidth,
                right: scroller.getBoundingClientRect().right,
                role: scroller.getAttribute('role'),
                name: scroller.getAttribute('aria-label'),
                tabIndex: scroller.tabIndex,
              }
            : null,
        }
      })
      const highlight = (CSS as unknown as { highlights: Map<string, Set<Range>> }).highlights.get('copilot-citation')
      const range = highlight ? Array.from(highlight)[0] : undefined
      return {
        doc: {
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          scrollX: window.scrollX,
        },
        visible,
        pane: p,
        reader: {
          ...box(r),
          width: r.getBoundingClientRect().width,
          parentClientWidth: r.parentElement!.clientWidth,
          maxWidth: parseFloat(getComputedStyle(r).maxWidth),
          paragraphMaxWidth: parseFloat(getComputedStyle(paragraph).maxWidth),
        },
        clipped: Array.from(r.querySelectorAll('p, h1, h2, h3, h4, li, blockquote'))
          .filter((el) => el.getBoundingClientRect().right > visible.right + 0.5)
          .map((el) => (el.textContent ?? '').trim().slice(0, 48)),
        tables,
        cited: range ? box(range) : null,
      }
    },
    { pane: PANE, reader: READER },
  )

const within = (inner: Box, outer: Box) =>
  inner.left >= outer.left - 0.5 && inner.right <= outer.right + 0.5 && inner.top >= outer.top - 0.5 && inner.bottom <= outer.bottom + 0.5

/** The reader fits its pane and each wide table scrolls in a box of its own. */
function expectContained(l: Layout) {
  expect.soft(l.reader.width, 'the reader is no wider than its parent').toBeLessThanOrEqual(l.reader.parentClientWidth + 0.5)
  expect.soft(l.reader.right, "the reader's right edge is within the pane's").toBeLessThanOrEqual(l.pane.right + 0.5)
  expect.soft(l.clipped, 'no text block reaches past the visible right edge').toEqual([])
  const segment = l.tables.find((t) => t.columns === 9)
  expect.soft(segment?.box, 'the 9-column segment table has a scroll box of its own').not.toBeNull()
  if (segment?.box) {
    expect.soft(segment.box.scrollWidth, 'the segment table scrolls inside its box').toBeGreaterThan(segment.box.clientWidth)
    expect.soft(segment.box.right, "the table box's right edge is within the pane's").toBeLessThanOrEqual(l.pane.right + 0.5)
  }
}

test.describe('desktop 1440x900: the reader stays in its pane', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const theme of ['light', 'dark'] as const) {
    test(`${theme}: the Filing tab with wide tables leaves the page without a sideways scroll`, async ({ page, baseURL }) => {
      await openPage(page, baseURL!, theme)
      await page.locator('button[aria-label="Ask this Filing"]').click()
      await page.locator(PANE).getByRole('tab', { name: 'Filing' }).click()
      await readerReady(page)

      const l = await layout(page)
      expect.soft(l.doc.scrollWidth, 'the page has no sideways scroll').toBe(l.doc.clientWidth)
      expectContained(l)
      // The reading measure is unchanged: the 88ch rail on the reader, 68ch on its prose children.
      expect.soft(l.reader.maxWidth / l.reader.paragraphMaxWidth).toBeCloseTo(88 / 68, 2)

      // Scrolled down to the statements, the page still has no sideways scroll.
      await page.locator(READER).evaluate((r) => {
        r.scrollTop = r.scrollHeight
      })
      const bottom = await layout(page)
      expect.soft(bottom.doc.scrollWidth, 'no sideways scroll at the statements').toBe(bottom.doc.clientWidth)
    })

    test(`${theme}: a citation jump scrolls the reader only, never the page sideways`, async ({ page, baseURL }) => {
      const chip = await openPage(page, baseURL!, theme)
      expect(await page.evaluate(() => window.scrollX)).toBe(0)
      await chip.click()
      await readerReady(page)
      await highlighted(page)
      await settled(page)

      const l = await layout(page)
      expect.soft(l.doc.scrollX, 'the page did not scroll sideways').toBe(0)
      expect.soft(l.doc.scrollWidth, 'the page has no sideways scroll').toBe(l.doc.clientWidth)
      expect.soft(l.cited, 'the cited passage is highlighted').not.toBeNull()
      if (l.cited) expect.soft(within(l.cited, l.visible), `the cited passage ${JSON.stringify(l.cited)} is visible inside the reader ${JSON.stringify(l.visible)}`).toBe(true)
      expect.soft(await page.locator(READER).evaluate((r) => r.scrollTop), 'the reader scrolled to the passage').toBeGreaterThan(0)
      expectContained(l)
    })

    test(`${theme}: a table that scrolls is a named region the keyboard reaches and scrolls; one that fits is not`, async ({ page, baseURL }) => {
      await openPage(page, baseURL!, theme)
      await page.locator('button[aria-label="Ask this Filing"]').click()
      const filingTab = page.locator(PANE).getByRole('tab', { name: 'Filing' })
      await filingTab.click()
      await readerReady(page)

      // Every box: a named, focusable region exactly when its table is wider than it.
      const check = async () => {
        const { tables } = await layout(page)
        expect(tables.every((t) => t.box)).toBe(true)
        for (const { box } of tables) {
          const scrolls = box!.scrollWidth > box!.clientWidth
          expect({ scrolls, role: box!.role, focusable: box!.tabIndex === 0, named: !!box!.name }).toEqual(
            scrolls ? { scrolls, role: 'region', focusable: true, named: true } : { scrolls, role: null, focusable: false, named: false },
          )
        }
        // The fixture at the default 420px pane has both kinds: the segment table scrolls, the balance sheet fits.
        expect(tables.find((t) => t.columns === 9)?.box?.role).toBe('region')
        expect(tables.some((t) => t.box && t.box.scrollWidth <= t.box.clientWidth)).toBe(true)
      }
      await check()
      // Hidden behind the Answer tab and shown again, the boxes re-measure.
      await page.locator(PANE).getByRole('tab', { name: 'Answer' }).click()
      await filingTab.click()
      await readerReady(page)
      await check()

      // After the pane's Close, Tab reaches the reader itself, still at its top (Chromium made the scroller
      // a tab stop on its own only while nothing in it was focusable; a table's region is), then the first
      // scrolling table's region. Both show the brand ring (the reader's inset), in both themes.
      const brand = theme === 'light' ? 'rgba(79, 122, 99' : 'rgba(127, 178, 149'
      const reader = page.locator(PANE).getByRole('region', { name: 'AAPL 10-K · filing text' })
      const region = page.locator(PANE).getByRole('region', { name: 'Scrollable table: Segment Operating Performance' })
      await expect(region).toHaveCount(1)
      await page.locator(PANE).getByRole('button', { name: 'Close' }).focus()
      await page.keyboard.press('Tab')
      await expect(reader).toBeFocused()
      expect(await reader.evaluate((el) => el.scrollTop)).toBe(0)
      expect(await reader.evaluate((el) => getComputedStyle(el).boxShadow)).toContain(brand)
      await page.keyboard.press('Tab')
      await expect(region).toBeFocused()
      expect(await region.evaluate((el) => getComputedStyle(el).boxShadow)).toContain(brand)
      // The arrow keys scroll it sideways, both ways; the page stays put.
      expect(await region.evaluate((el) => el.scrollLeft)).toBe(0)
      await page.keyboard.press('ArrowRight')
      await expect.poll(() => region.evaluate((el) => el.scrollLeft)).toBeGreaterThan(0)
      await page.keyboard.press('ArrowLeft')
      await expect.poll(() => region.evaluate((el) => el.scrollLeft)).toBe(0)
      expect(await page.evaluate(() => window.scrollX)).toBe(0)
    })
  }
})

test.describe('phone 390x844 (touch): the sheet shows the whole reader', () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true })

  for (const theme of ['light', 'dark'] as const) {
    test(`${theme}: "Show in filing" reaches the cited passage; no text is clipped; the table scrolls in its own box`, async ({ page, baseURL }) => {
      const chip = await openPage(page, baseURL!, theme)
      await chip.tap()
      const sheet = page.getByRole('dialog', { name: 'Source detail' })
      await expect(sheet).toBeVisible()
      await sheet.getByRole('button', { name: 'Show in filing' }).tap()
      await expect(page.locator(PANE)).toBeVisible()
      await readerReady(page)
      await highlighted(page)
      await settled(page)

      const l = await layout(page)
      expectContained(l)
      expect.soft(l.cited, 'the cited passage is highlighted').not.toBeNull()
      if (l.cited) expect.soft(within(l.cited, l.visible), `the cited passage ${JSON.stringify(l.cited)} is visible inside the sheet's reader ${JSON.stringify(l.visible)}`).toBe(true)
      expect.soft(l.doc.scrollX).toBe(0)

      // The segment table's own box scrolls sideways (a swipe's effect, set directly) and the reader does not.
      const moved = await page.locator(`${READER} table`).filter({ hasText: 'Reportable since' }).evaluate((t) => {
        const box = t.parentElement!
        box.scrollLeft = box.scrollWidth
        const reader = t.closest('.filing-reader')!
        return { box: box.scrollLeft, reader: reader.scrollLeft, boxIsReader: box === reader }
      })
      expect.soft(moved.boxIsReader, 'the table has a box of its own').toBe(false)
      expect.soft(moved.box, 'the table box scrolled').toBeGreaterThan(0)
      expect.soft(moved.reader, 'the reader did not scroll sideways').toBe(0)
    })
  }
})
