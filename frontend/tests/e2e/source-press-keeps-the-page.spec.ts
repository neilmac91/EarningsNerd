import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, PANE, SUMMARY, answerApi } from './fixtures/filing3Api'

/**
 * A press on Source never moves the page under the reader (chief design on #1813; E248). Opening the pane on Ask
 * focuses the rail's composer a frame later, or once the plan or usage loads, and a focus's own scroll moves every
 * scrolling ancestor, the page included. The desktop pane's height follows its top a frame late, so after the page
 * above it moves its lower part can sit below the fold, and that scroll brought the composer up: in #1813's e2e run
 * 41053542799 the page sat at 495px after the press. The composer now takes focus with preventScroll and is brought
 * into view inside the rail's column only (CopilotComposer's revealInScrollBox).
 *
 * Here the pane's cell is held taller than the screen, so the composer stays below the fold whatever the timing: the
 * press opens the pane, the composer takes focus there, and the page stays at 0. With the page scrolled, ⌘K's focus
 * keeps it where it was too, and so do the two other ways the rail hands focus to its composer: an "Ask about this"
 * pre-fill and a starter pressed from the keyboard. Then the cell is held shorter than the column's content, as the
 * pane settles at a large text size: the focused composer keeps to the column's foot, and once the reader scrolls the
 * column away from it, the column stays where they put it. Last, a pre-fill into a column that ends above the composer:
 * the field grows after it takes focus, and the column follows the grown shell to its foot.
 */

// A completed answer with no citations, in the wire shape copilot-api.ts admits (copilot-status-line.spec.ts).
const ANSWER = { type: 'complete', kind: 'answer', answer: 'Revenue grew.', grounded: 0, citations: [], followups: [] }
/** The summary's lead paragraph, near the top of the page: the passage a reader selects to ask about. */
const LEAD = (SUMMARY.rendered_sections as { blocks: { text: string }[] }[])[0].blocks[0].text

/** The filing page for a Pro reader, its Ask stream answered, the pane's cell (mounted while the pane is closed) held
 *  at `cellHeight`, and the page at its top. */
async function openFiling(page: Page, baseURL: string, cellHeight: number) {
  await page.addInitScript(() => {
    localStorage.setItem('theme', 'light')
    localStorage.setItem('en_session_active', '1')
    localStorage.setItem('en:copilot-coachmark-v1', '1')
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
  })
  await answerApi(page, baseURL, 'pro')
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
            body: `data: ${JSON.stringify(ANSWER)}\n\n`,
          }),
  )
  await page.goto('/filing/3')
  await expect(page.getByRole('button', { name: 'Source', exact: true })).toBeVisible()
  await holdCell(page, cellHeight)
  await page.evaluate(() => window.scrollTo(0, 0))
  expect(await scrollY(page), 'the page starts at its top').toBe(0)
}

const holdCell = (page: Page, height: number) =>
  page.locator(PANE).evaluate((shell, h) => {
    shell.parentElement!.style.height = `${h}px`
  }, height)
const scrollY = (page: Page) => page.evaluate(() => window.scrollY)
/** Two frames, for any scroll a focus or a resize brought to land. */
const twoFrames = (page: Page) =>
  page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))
const composerIn = (page: Page) => page.locator(PANE).getByRole('textbox', { name: 'Ask about this filing' })

/** The rail's column (the composer form's parent, the box that scrolls it) and the composer's shell, the box that draws
 *  its focus ring: the shell's foot against the column's, and the column's scroll. */
const column = (page: Page) =>
  composerIn(page).evaluate((field) => {
    const form = field.closest('form')!
    const box = form.parentElement!
    const shell = form.firstElementChild!.getBoundingClientRect()
    const b = box.getBoundingClientRect()
    return {
      scrollTop: box.scrollTop,
      shellFoot: shell.bottom,
      foot: b.top + box.clientTop + box.clientHeight,
    }
  })

test.describe('a press on Source keeps the page / 1100x800, a Pro reader on /filing/3', () => {
  test.use({ viewport: { width: 1100, height: 800 }, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })

  test('the composer takes focus below the fold and the page stays where it was', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, 2400)
    await page.getByRole('button', { name: 'Source', exact: true }).click()
    const composer = composerIn(page)
    await expect(composer, 'the composer takes focus as the pane opens on Ask').toBeFocused()
    await twoFrames(page)
    expect(await scrollY(page), 'a press on Source leaves the page at its top').toBe(0)
    const box = (await composer.boundingBox())!
    expect(box.y, 'the composer is below the fold, where a focus with its own scroll would have moved the page').toBeGreaterThan(800)

    // ⌘K with the page scrolled: the open rail's composer takes focus again, and the page stays where the reader put it.
    await page.evaluate(() => window.scrollTo(0, 300))
    await composer.evaluate((el: HTMLElement) => el.blur())
    await page.keyboard.press('ControlOrMeta+k')
    await expect(composer, '⌘K focuses the open rail\'s composer').toBeFocused()
    await twoFrames(page)
    expect(await scrollY(page), '⌘K leaves the page where it was').toBe(300)
  })

  test('an "Ask about this" pre-fill and a starter pressed from the keyboard keep the page too', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, 2400)
    // The summary's lead paragraph selected, as a reader's drag leaves it.
    const passage = page.getByRole('main', { name: 'Filing research' }).getByText(LEAD, { exact: true })
    await expect(passage, 'the passage is on screen').toBeInViewport()
    await passage.evaluate((p) => {
      const range = document.createRange()
      range.selectNodeContents(p)
      window.getSelection()!.removeAllRanges()
      window.getSelection()!.addRange(range)
      document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })
    // A click at the action's box, as a pointer presses it (Playwright's own click first scrolls its target into view).
    const ask = page.getByRole('button', { name: 'Ask about this', exact: true })
    await expect(ask).toBeVisible()
    const action = (await ask.boundingBox())!
    await page.mouse.click(action.x + action.width / 2, action.y + action.height / 2)
    const composer = composerIn(page)
    await expect(composer, 'the pre-fill focuses the composer').toBeFocused()
    await expect(composer).toHaveValue(/^Explain this excerpt: "/)
    await twoFrames(page)
    expect(await scrollY(page), 'a pre-fill leaves the page at its top').toBe(0)
    expect((await composer.boundingBox())!.y, 'the composer is below the fold').toBeGreaterThan(800)

    // Shift+Tab from the field reaches the last starter, on screen; Enter asks it, and the rail hands focus back to the
    // composer, below the fold, with the page where it was.
    await page.keyboard.press('Shift+Tab')
    const starter = page.locator(PANE).locator(':focus')
    await expect(starter).toHaveText(/\?$/)
    await expect(starter, 'the starter is on screen').toBeInViewport()
    await page.keyboard.press('Enter')
    await expect(composer, 'the starter hands focus to the composer').toBeFocused()
    await expect(page.locator(PANE).getByText(ANSWER.answer)).toBeVisible()
    await twoFrames(page)
    expect(await scrollY(page), 'a starter leaves the page at its top').toBe(0)
  })

  test('the focused composer keeps to the foot of a column that settles shorter, unless the reader scrolled it away', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!, 2400)
    await page.getByRole('button', { name: 'Source', exact: true }).click()
    await expect(composerIn(page)).toBeFocused()
    await twoFrames(page)

    // The cell settles shorter, as the pane can at a large text size: at 320px the column (92px less, under the pane's
    // header) ends above the composer's shell, 263px into its content with its ring's margin. The column scrolls, and
    // the shell comes to its foot, the least distance.
    await holdCell(page, 320)
    await twoFrames(page)
    const settled = await column(page)
    expect(settled.scrollTop, 'the column brought the composer up').toBeGreaterThan(0)
    expect(settled.shellFoot, "the composer's shell ends inside the column").toBeLessThanOrEqual(settled.foot)
    expect(settled.shellFoot, '... at its foot').toBeGreaterThan(settled.foot - 8)

    // Settling further keeps it there.
    await holdCell(page, 300)
    await twoFrames(page)
    const further = await column(page)
    expect(further.scrollTop).toBeGreaterThan(settled.scrollTop)
    expect(further.shellFoot).toBeLessThanOrEqual(further.foot)
    expect(further.shellFoot).toBeGreaterThan(further.foot - 8)

    // The reader scrolls the column back up to read, focus still in the composer: the shell below its foot. The next
    // settle leaves the column where they put it.
    await composerIn(page).evaluate((field) => {
      field.closest('form')!.parentElement!.scrollTop = 0
    })
    await twoFrames(page)
    await holdCell(page, 290)
    await twoFrames(page)
    const kept = await column(page)
    expect(kept.scrollTop, "the reader's place in the column").toBe(0)
    expect(kept.shellFoot, 'the composer is still below the column, where the reader left it').toBeGreaterThan(kept.foot)

    // The pane grows until the composer shows again, as a page scroll can grow an unstuck pane, then shrinks back: a
    // resize never puts the column back on the composer the reader scrolled away from.
    await holdCell(page, 2400)
    await twoFrames(page)
    const uncovered = await column(page)
    expect(uncovered.shellFoot, 'the grown column shows the composer').toBeLessThanOrEqual(uncovered.foot)
    await holdCell(page, 290)
    await twoFrames(page)
    expect((await column(page)).scrollTop, "the reader's place again").toBe(0)
    await expect(composerIn(page)).toBeFocused()
    expect(await scrollY(page), 'the page never moved').toBe(0)
  })

  test("a pre-fill into a short column keeps the grown field's foot in view", async ({ page, baseURL }) => {
    // The column ends above the composer from the start. The pre-fill reveals the one-line field, then the field grows
    // to fit the excerpt a task later, before the column reports the reveal's own scroll: that scroll is not the
    // reader's, and the column follows the grown shell to its foot.
    await openFiling(page, baseURL!, 320)
    const passage = page.getByRole('main', { name: 'Filing research' }).getByText(LEAD, { exact: true })
    await expect(passage).toBeInViewport()
    await passage.evaluate((p) => {
      const range = document.createRange()
      range.selectNodeContents(p)
      window.getSelection()!.removeAllRanges()
      window.getSelection()!.addRange(range)
      document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    })
    const ask = page.getByRole('button', { name: 'Ask about this', exact: true })
    await expect(ask).toBeVisible()
    const action = (await ask.boundingBox())!
    await page.mouse.click(action.x + action.width / 2, action.y + action.height / 2)
    const composer = composerIn(page)
    await expect(composer).toBeFocused()
    await expect(composer).toHaveValue(/^Explain this excerpt: "/)
    await twoFrames(page)
    await twoFrames(page)
    const grown = await composer.evaluate((field) => field.getBoundingClientRect().height)
    expect(grown, 'the field grew past one line').toBeGreaterThan(40)
    const settled = await column(page)
    expect(settled.shellFoot, "the grown shell ends inside the column").toBeLessThanOrEqual(settled.foot)
    expect(settled.shellFoot, '... at its foot').toBeGreaterThan(settled.foot - 8)
    expect(await scrollY(page), 'the page never moved').toBe(0)
  })
})
