import { test, expect, type Page } from '@playwright/test'
import { PANE, answerApi } from './fixtures/filing3Api'

/**
 * A press on Source never moves the page under the reader (E248; chief design on #1813). The Ask rail focuses its
 * composer a frame after the pane opens, and a plain focus() scrolls every box around the field to it, the page
 * included. On /filing/3 at 1100x600 under 200% text the pane opens 54px tall, below its own tabs, so the field lies
 * under the window's foot, and the press scrolled the page 394px down to it (with motion reduced). The composer now
 * takes focus without scrolling and brings its shell (the field and Send, inside one focus ring) to the nearest edge
 * of the rail's column, the one box it moves; that field waits under the window's foot until the reader scrolls, or
 * types, since Chromium brings a field into view as text goes in. The sheet below lg relies on the column under 200%
 * text, where the column scrolls and the focus was what showed the field: there the shell sits whole inside the
 * column, its 3px ring included, where the plain focus left it 23px under the column's foot at 390x844. A Pro reader
 * at the top of the page, the coachmark seen and consent stored, presses Source as a pointer does, at the launcher's
 * box.
 */

const CASES = [
  // The pane opens shorter than its tabs: the field lies under the window's foot, where it stays.
  { width: 1100, height: 600, doubled: true, fieldShows: false },
  { width: 1100, height: 800, doubled: false, fieldShows: true },
  // The sheet, whose column scrolls under 200% text.
  { width: 390, height: 844, doubled: true, fieldShows: true },
  { width: 320, height: 568, doubled: true, fieldShows: true },
]

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

test.describe('a press on Source keeps the page where it was / a Pro reader on /filing/3', () => {
  test.use({ reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })
  for (const { width, height, doubled, fieldShows } of CASES) {
    const where = `${width}x${height}, ${doubled ? '200% text' : 'the default text size'}`
    test(`at ${where}, the composer takes focus and the page stays at its top`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height })
      await page.addInitScript(() => {
        localStorage.setItem('theme', 'light')
        localStorage.setItem('en_session_active', '1')
        localStorage.setItem('en:copilot-coachmark-v1', '1')
        localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
      })
      await answerApi(page, baseURL!, 'pro')
      await page.goto('/filing/3')
      const source = page.getByRole('button', { name: 'Source', exact: true })
      await expect(source).toBeVisible()
      if (doubled) await doubleText(page)
      await settle(page)
      expect(await page.evaluate(() => window.scrollY), `${where}: the press comes at the top of the page`).toBe(0)

      // A click at the launcher's box, as a pointer presses it: Playwright's own click may scroll first.
      const box = (await source.boundingBox())!
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
      const field = page.locator(PANE).getByPlaceholder('Ask about this filing…')
      await expect(field, `${where}: the press focuses the composer`).toBeFocused()
      await settle(page)

      const at = await field.evaluate((el) => {
        const shell = el.closest('.scroll-mb-1')!.getBoundingClientRect()
        const column = el.closest('form')!.parentElement!
        const top = column.getBoundingClientRect().top + column.clientTop
        return { scrollY: window.scrollY, foot: window.innerHeight, shell: { top: shell.top, bottom: shell.bottom }, column: { top, bottom: top + column.clientHeight } }
      })
      expect(at.scrollY, `${where}: the page stays at its top`).toBe(0)
      if (fieldShows) {
        // The shell and its 3px ring lie whole inside the column, and the column inside the window.
        const r = (n: number) => Math.round(n)
        const inside = `${where}: the composer's shell, ${r(at.shell.top)} to ${r(at.shell.bottom)}px, and its ring lie inside the column, ${r(at.column.top)} to ${r(at.column.bottom)}px`
        expect(at.shell.top - 3, inside).toBeGreaterThanOrEqual(at.column.top - 0.5)
        expect(at.shell.bottom + 3, inside).toBeLessThanOrEqual(at.column.bottom + 0.5)
        expect(at.column.bottom, `${where}: the column ends inside the ${at.foot}px window`).toBeLessThanOrEqual(at.foot + 0.5)
      } else {
        // The case's premise: the field lies under the window's foot, where a plain focus scrolled the page.
        expect(at.shell.top, `${where}: the field lies under the ${at.foot}px window's foot`).toBeGreaterThan(at.foot)
      }
    })
  }
})
