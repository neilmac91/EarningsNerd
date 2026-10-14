import { test, expect, type Locator, type Page } from '@playwright/test'
import { API_ORIGIN, DOCUMENT, PANE, answerApi, type Theme } from './fixtures/filing3Api'

/**
 * D-030 in a real Chromium: a prose link prints words the product does not write, a figure or a date among
 * them, so it rests in its prose's own ink, underlined, and takes sage only under the pointer (app/globals.css,
 * the prose links' rule); a citation chip among the prose is no prose link and keeps its own chip.
 * brandCopyRules.spec.ts rule 2 holds the stylesheet's source; this spec holds what the cascade paints.
 *
 *  - A link in a Copilot answer (.copilot-answer), in both themes: at rest it takes the answer's ink and draws
 *    its underline; under the pointer it takes the sage of the answer's own citation chip.
 *  - The homepage's Ask demo mounts no filing viewer, so its citation chips are anchors: each keeps its chip,
 *    with no underline and its own radius.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): the filing page's API and the Ask
 * stream are answered inside the browser (fixtures/filing3Api.ts); the homepage needs neither.
 */

const LINK = 'Item 8, Note 13'
// A completed Ask answer whose prose carries a link, in the wire shape copilot-api.ts admits.
const ANSWER = {
  type: 'complete',
  kind: 'answer',
  answer: `Growth came mainly from Services [1], which the segment note in [${LINK}](${DOCUMENT}) breaks out.`,
  grounded: 1,
  citations: [
    { n: 1, excerpt: 'Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services.', section_ref: 'Item 7. MD&A – Products and Services Performance', verified: true, fragment_url: `${DOCUMENT}#:~:text=Services%20net%20sales` },
  ],
  followups: [],
}

/** Consent answered and the first-run coachmark seen, in the given theme: neither is under test here. */
async function settle(page: Page, theme: Theme) {
  await page.addInitScript((t: string) => {
    try {
      localStorage.setItem('theme', t)
      localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, theme)
}

/** Open filing 3 for a Pro visitor, ask a question and return the answer's link and its citation chip. */
async function askWithLink(page: Page, baseURL: string, theme: Theme) {
  await answerApi(page, baseURL, 'pro')
  // Registered last, so it runs first: the Ask stream and the CORS preflight its POST sends.
  const cors = {
    'access-control-allow-origin': new URL(baseURL).origin,
    'access-control-allow-credentials': 'true',
    'access-control-allow-headers': 'content-type',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
  }
  await page.route(
    (url) => url.origin === API_ORIGIN && url.pathname === '/api/summaries/filing/3/ask-stream',
    (route) =>
      route.request().method() === 'OPTIONS'
        ? route.fulfill({ status: 204, headers: cors })
        : route.fulfill({
            status: 200,
            headers: { ...cors, 'content-type': 'text/event-stream', 'cache-control': 'no-cache' },
            body: `data: ${JSON.stringify({ type: 'progress', stage: 'reading' })}\n\ndata: ${JSON.stringify(ANSWER)}\n\n`,
          }),
  )
  await settle(page, theme)
  await page.goto('/filing/3')
  await page.locator('button[aria-label="Source"]').click()
  const composer = page.locator(PANE).getByPlaceholder('Ask about this filing…')
  await composer.fill('What drove revenue?')
  await composer.press('Enter')
  const link = page.locator(PANE).locator('.copilot-answer').getByRole('link', { name: LINK })
  const chip = page.locator(PANE).getByRole('button', { name: /^Citation 1:/ })
  await expect(link).toBeVisible()
  await expect(chip).toBeVisible()
  // The pointer starts off the answer, so the first read is the link at rest.
  await page.mouse.move(2, 2)
  return { link, chip }
}

const style = (el: Locator) =>
  el.evaluate((node) => {
    const s = getComputedStyle(node)
    const prose = node.closest('.copilot-answer')
    return {
      color: s.color,
      line: s.textDecorationLine,
      decoration: s.textDecorationColor,
      radius: s.borderTopLeftRadius,
      proseInk: prose ? getComputedStyle(prose).color : null,
    }
  })

test.describe('a link in a Copilot answer rests in the ink and turns sage under the pointer', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const theme of ['light', 'dark'] as const) {
    test(theme, async ({ page, baseURL }) => {
      const { link, chip } = await askWithLink(page, baseURL!, theme)
      const sage = (await style(chip)).color
      const rest = await style(link)
      expect(rest.color, 'at rest the link takes the answer’s own ink').toBe(rest.proseInk)
      expect(rest.color, 'at rest the link is not sage').not.toBe(sage)
      expect(rest.line, 'the underline marks the link at rest').toContain('underline')
      expect(rest.decoration, 'the underline at rest is quieter than sage').not.toBe(sage)

      await link.hover()
      await expect.poll(async () => (await style(link)).color, { message: 'under the pointer the link takes sage' }).toBe(sage)
      await expect.poll(async () => (await style(link)).decoration, { message: 'and its underline with it' }).toBe(sage)
    })
  }
})

test.describe('a citation chip among prose keeps its chip', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test("the homepage's Ask demo: its chips are anchors, with no prose underline and their own radius", async ({ page }) => {
    await settle(page, 'light')
    await page.goto('/')
    const chips = page.locator('.copilot-answer a[data-citation-kind]')
    await chips.first().scrollIntoViewIfNeeded()
    await expect(chips.first()).toBeVisible()
    const count = await chips.count()
    expect(count, 'the demo renders its citation chips as anchors').toBeGreaterThan(0)
    // The chip's own radius is `rounded` (CitationChip); the prose links' rule would set `rounded-sm`. Read what
    // `rounded` resolves to on the page, so the check holds whatever the theme's scale.
    const own = await chips.first().evaluate((el) => {
      const probe = document.createElement('span')
      probe.className = 'rounded'
      el.parentElement!.appendChild(probe)
      const radius = getComputedStyle(probe).borderTopLeftRadius
      probe.remove()
      return radius
    })
    for (let i = 0; i < count; i++) {
      const { line, radius } = await style(chips.nth(i))
      expect({ line, radius }, `chip ${i + 1}: the chip's own decoration and radius`).toEqual({ line: 'none', radius: own })
    }
  })
})
