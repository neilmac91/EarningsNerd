import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

/**
 * The live example's quality badge under 200% text (E156). Production's landing renders the live example, whose header
 * row holds "Example summary" and a "Full summary" badge. CI's e2e build serves no live example, only the fallback,
 * whose row holds the label alone. So this spec lays the live badge, as the hero renders it, into the built fallback's
 * row and reads the boxes. The badge is fixtures/hero-example-live-badge.html, which
 * tests/unit/hero-example-surface.spec.tsx holds to the component's render, and holds the fallback's row with it laid
 * in to the live row.
 *
 * On one line at 390px under 200% text the badge took the page to 422px. On a line of its own at 320px it was still
 * 236px, wider than the card's 222px content box. The row wraps, so the badge goes under the label where the two do
 * not fit side by side, and below a 24rem viewport the badge's label wraps inside it, the badge then a rounded box
 * (the 16px step), never a capsule whose curve crosses its text. Where the two fit (390px at the
 * default text size, 1440px under 200% text) the badge keeps the row's right, beside the label. The label's painted
 * text is read with a Range (lessons/frontend-check-brand-layouts-at-200-percent-text.md).
 */
const BADGE = readFileSync(path.join(__dirname, 'fixtures', 'hero-example-live-badge.html'), 'utf8').trim()

const CASES = [
  { width: 320, height: 844, doubled: true, fits: false },
  { width: 390, height: 844, doubled: true, fits: false },
  { width: 390, height: 844, doubled: false, fits: true },
  { width: 1440, height: 900, doubled: true, fits: true },
] as const

/** Chromium's own text setting doubled (standard 32, fixed 26), as reflow-200.spec.ts doubles it, confirmed taken. */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect.poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize)).toBe('32px')
}

for (const c of CASES) {
  const at = `${c.width}px, ${c.doubled ? '200%' : 'default'} text`
  test.describe(`the live example's quality badge at ${at}`, () => {
    test.use({ viewport: { width: c.width, height: c.height }, isMobile: c.width < 1024, hasTouch: c.width < 1024 })

    for (const theme of ['light', 'dark'] as const) {
      test(`${theme}: ${c.fits ? 'beside the label at the row’s right' : 'under the label'}, inside the card, the page not scrolling sideways`, async ({ page, baseURL }) => {
        // A settled guest header: a retrying session check otherwise moves the hero while it is read.
        await page.route('**/api/auth/me', (route) => route.fulfill({
          status: 401,
          headers: { 'access-control-allow-origin': new URL(baseURL!).origin, 'access-control-allow-credentials': 'true' },
          json: { detail: 'Not authenticated' },
        }))
        await page.addInitScript((mode) => {
          localStorage.setItem('theme', mode)
          localStorage.setItem('cookie_consent', JSON.stringify({
            essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString(),
          }))
        }, theme)
        await page.goto('/')
        const label = page.getByRole('region', { name: 'Example summary' }).getByText('Example summary', { exact: true })
        await expect(label).toBeVisible()
        // The row is server-rendered; lay the badge in once React has hydrated it, so hydration cannot replace it.
        await expect.poll(() => label.evaluate((el) => Object.keys(el).some((key) => key.startsWith('__reactFiber$')))).toBe(true)
        if (c.doubled) await doubleText(page)
        await page.evaluate(() => document.fonts.ready)
        await label.evaluate((el, badge) => {
          if (el.parentElement!.children.length !== 1) throw new Error('the fallback row already holds more than its label')
          el.parentElement!.insertAdjacentHTML('beforeend', badge)
        }, BADGE)
        await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))

        const m = await label.evaluate((el) => {
          const box = (r: DOMRect) => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom })
          const row = el.parentElement!
          const badge = row.lastElementChild as HTMLElement
          const text = document.createRange()
          text.selectNodeContents(el)
          const words = [...badge.childNodes].filter((node) => node.nodeType === Node.TEXT_NODE)
          const lines = words.flatMap((node) => {
            const range = document.createRange()
            range.selectNodeContents(node)
            return [...range.getClientRects()].map(box)
          })
          return {
            label: box(text.getBoundingClientRect()),
            row: box(row.getBoundingClientRect()),
            badge: box(badge.getBoundingClientRect()),
            badgeText: badge.textContent,
            lines,
            radius: parseFloat(getComputedStyle(badge).borderTopLeftRadius),
            scrollWidth: document.documentElement.scrollWidth,
            // A phone view's innerWidth grows with an overflow; the root's clientWidth is the screen's.
            clientWidth: document.documentElement.clientWidth,
            dark: document.documentElement.classList.contains('dark'),
          }
        })
        const where = `${at}, ${theme}: label ${JSON.stringify(m.label)}, badge ${JSON.stringify(m.badge)}, row ${JSON.stringify(m.row)}`
        expect(m.badgeText, 'the laid badge is the live one').toBe('Full summary')
        expect(m.dark, `${at}: the ${theme} theme is the one on the page`).toBe(theme === 'dark')
        expect(m.scrollWidth, `${at}, ${theme}: the page does not scroll sideways`).toBeLessThanOrEqual(m.clientWidth)
        expect(m.badge.left, `${where}: the badge starts inside the card's content box`).toBeGreaterThanOrEqual(m.row.left - 0.5)
        expect(m.badge.right, `${where}: the badge ends inside the card's content box`).toBeLessThanOrEqual(m.row.right + 0.5)
        expect(m.lines.length, `${where}: the badge paints its label`).toBeGreaterThan(0)
        for (const line of m.lines) {
          expect(line.left >= m.badge.left - 0.5 && line.right <= m.badge.right + 0.5, `${where}: each line of the badge's label inside the badge (${JSON.stringify(line)})`).toBe(true)
        }
        if (c.fits) {
          expect(m.badge.top, `${where}: the badge sits beside the label, on its line`).toBeLessThan(m.label.bottom)
          expect(Math.abs(m.badge.right - m.row.right), `${where}: the badge keeps the row's right`).toBeLessThanOrEqual(0.5)
        } else {
          expect(m.badge.top, `${where}: the badge sits wholly under the label`).toBeGreaterThanOrEqual(m.label.bottom - 0.5)
        }
        const lineCount = new Set(m.lines.map((line) => Math.round(line.top))).size
        if (c.width >= 390) {
          // The badge's label breaks only where the badge cannot fit on a line of its own.
          expect(lineCount, `${where}: the badge's label on one line`).toBe(1)
        }
        if (lineCount > 1) {
          // A chip whose label wraps is a rounded box, never a capsule whose curve crosses its text (DESIGN.md's radius scale).
          expect(m.radius, `${where}: the wrapped badge's corners are a rounded box's`).toBeLessThan((m.badge.bottom - m.badge.top) / 2)
        }
      })
    }
  })
}
