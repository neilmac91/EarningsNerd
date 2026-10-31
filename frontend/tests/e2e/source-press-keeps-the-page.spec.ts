import { test, expect, type Page } from '@playwright/test'
import { API_ORIGIN, PANE, SUMMARY, answerApi } from './fixtures/filing3Api'

/**
 * A press on Source never moves the page under the reader while the pane settles (chief design on #1813; E248), and
 * moves it once, after, when the composer it focused is still out of view (chief design's rule A on #1845; E252).
 * Opening the pane on Ask focuses the rail's composer a frame later, or once the plan or usage loads, and a focus's own
 * scroll moves every scrolling ancestor, the page included. The desktop pane's height follows its top a frame late, so
 * after the page above it moves its lower part can sit below the fold, and that scroll brought the composer up: in
 * #1813's e2e run 41053542799 the page sat at 495px after the press. The composer now takes focus with preventScroll and
 * its column alone brings it into the column's part on screen (CopilotComposer's revealInScrollBox). Once the pane has
 * settled, a press whose composer is still not wholly in view below the site header moves the page by the least
 * distance, once (revealOnPage).
 *
 * First, the press with the pane's cell held taller than the screen until a frame after the composer takes focus, as
 * the pane's own frame-late height does: the composer takes focus below the fold, the page stays at 0, and the composer
 * ends in view. ⌘K with the page scrolled, an "Ask about this" pre-fill and a starter pressed from the keyboard keep the
 * page the same way. Then the cell is held shorter than the column's content, as the pane settles at a large text size:
 * the focused composer keeps to the column's foot, and once the reader scrolls the column away from it, the column
 * stays where they put it. A pre-fill into a column that ends above the composer: the field grows after it takes focus,
 * and the column follows the grown shell to its foot.
 *
 * Then the pane itself out of view under 200% text, with no cell held (E252). At the page's foot the pane's sticky cell
 * has scrolled up with the workspace's end, so the pane opens above the screen: Source and ⌘K move the page up once, by
 * the least distance, and the composer's shell lands below the site header, its ring included. At 100% text the pane
 * shows there and the page holds. At the page's top in a short window the pane opens below the fold, or too short for
 * the composer: the page moves down once, and the shell lands at the window's foot (#1847's cases, with the 38px
 * column at 1100x800). The phone's sheet, a fixed layer, never moves the page: its column alone shows the composer,
 * its ring inside the column (#1847's 390x844 and 320x568).
 *
 * Opening the pane reflows the page (the summary's column narrows), and where Chrome's scroll anchoring then leaves the
 * reader varies from run to run on main too, so the cases read where the composer lands and how far the reveal moved the
 * page (a wrapped window.scrollBy, the composer's one page move), not one scroll position.
 */

// A completed answer with no citations, in the wire shape copilot-api.ts admits (copilot-status-line.spec.ts).
const ANSWER = { type: 'complete', kind: 'answer', answer: 'Revenue grew.', grounded: 0, citations: [], followups: [] }
/** The summary's lead paragraph, near the top of the page: the passage a reader selects to ask about. */
const LEAD = (SUMMARY.rendered_sections as { blocks: { text: string }[] }[])[0].blocks[0].text
/** The focus ring's width: the shell's scroll margins keep it in view. */
const RING = 3

interface PageMove {
  /** The call's options: `top` is the distance asked for. */
  options: { top: number; behavior?: string }
  /** The page's scroll before and after the call, and the composer's shell, in the window, as it was called. */
  before: number
  after: number
  shell: { top: number; bottom: number } | null
}

/** The filing page for a Pro reader, its Ask stream answered, each page move the code makes through window.scrollBy
 *  recorded, at the default text size or twice it, and the page at its top. */
async function openFiling(page: Page, baseURL: string, { doubled = false } = {}) {
  await page.addInitScript((pane) => {
    localStorage.setItem('theme', 'light')
    localStorage.setItem('en_session_active', '1')
    localStorage.setItem('en:copilot-coachmark-v1', '1')
    localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: '2026-10-10T00:00:00Z', version: 2 }))
    const moves: PageMove[] = []
    ;(window as unknown as { __pageMoves: PageMove[] }).__pageMoves = moves
    const scrollBy = window.scrollBy.bind(window) as (options: ScrollToOptions) => void
    window.scrollBy = ((options: ScrollToOptions) => {
      const shell = document.querySelector(`${pane} form`)?.firstElementChild?.getBoundingClientRect()
      const before = window.scrollY
      scrollBy(options)
      moves.push({
        options: { top: options.top ?? 0, behavior: options.behavior },
        before,
        after: window.scrollY,
        shell: shell ? { top: shell.top, bottom: shell.bottom } : null,
      })
    }) as typeof window.scrollBy
  }, PANE)
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
  if (doubled) await doubleText(page)
  await page.evaluate(() => document.fonts.ready)
  await frames(page, 2)
  await page.evaluate(() => window.scrollTo(0, 0))
  expect(await scrollY(page), 'the page starts at its top').toBe(0)
}

/** Chromium's own text setting doubled (standard 32, fixed 26), confirmed taken: the root computes to 32px (#1847). */
async function doubleText(page: Page) {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Page.setFontSizes', { fontSizes: { standard: 32, fixed: 26 } })
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.documentElement).fontSize), { message: 'the 200% text setting took: the root computes to 32px' })
    .toBe('32px')
}

const holdCell = (page: Page, height: number) =>
  page.locator(PANE).evaluate((shell, h) => {
    shell.parentElement!.style.height = `${h}px`
  }, height)
/** Hold the pane's cell three screens tall until a frame after the composer's field takes focus, then let it take its
 *  own height, as the pane's height catches up with its top a frame late. Records the shell's place as the field took
 *  focus, before its column moved it. */
const holdCellUntilFocus = (page: Page) =>
  page.locator(PANE).evaluate((pane) => {
    const cell = pane.parentElement!
    cell.style.height = '2400px'
    const onFocus = (event: FocusEvent) => {
      const field = event.target
      if (!(field instanceof HTMLTextAreaElement) || !pane.contains(field)) return
      document.removeEventListener('focusin', onFocus, true)
      const r = field.closest('form')!.firstElementChild!.getBoundingClientRect()
      ;(window as unknown as { __atFocus: { top: number; bottom: number } }).__atFocus = { top: r.top, bottom: r.bottom }
      requestAnimationFrame(() => {
        cell.style.height = ''
      })
    }
    document.addEventListener('focusin', onFocus, true)
  })
const atFocus = (page: Page) => page.evaluate(() => (window as unknown as { __atFocus: { top: number; bottom: number } }).__atFocus)
const pageMoves = (page: Page) => page.evaluate(() => (window as unknown as { __pageMoves: PageMove[] }).__pageMoves)
const scrollY = (page: Page) => page.evaluate(() => window.scrollY)
const frames = (page: Page, count: number) =>
  page.evaluate(
    (n) =>
      new Promise<void>((done) => {
        let left = n
        const step = () => (--left <= 0 ? done() : requestAnimationFrame(step))
        requestAnimationFrame(step)
      }),
    count,
  )
/** Two frames, for any scroll a focus or a resize brought to land. */
const twoFrames = (page: Page) => frames(page, 2)
/** Past the composer's wait for the pane to settle (at most 12 frames), and the page still. */
async function settled(page: Page) {
  await frames(page, 16)
  let last = await scrollY(page)
  for (let i = 0; i < 20; i++) {
    await frames(page, 4)
    const now = await scrollY(page)
    if (now === last) return now
    last = now
  }
  return last
}
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

/** Where the composer's shell is, with its scroll margins, against the band a reveal lands in (below the bars the page's
 *  scroll padding holds, the site header, and above the window's foot), its column, and the pane. */
const where = (page: Page) =>
  composerIn(page).evaluate((field, pane) => {
    const form = field.closest('form')!
    const box = form.parentElement!
    const shellEl = form.firstElementChild!
    const shell = shellEl.getBoundingClientRect()
    const style = getComputedStyle(shellEl)
    const b = box.getBoundingClientRect()
    const page = getComputedStyle(document.documentElement)
    return {
      focused: document.activeElement === field,
      scrollY: window.scrollY,
      bandTop: parseFloat(page.scrollPaddingTop) || 0,
      bandBottom: window.innerHeight - (parseFloat(page.scrollPaddingBottom) || 0),
      shell: { top: shell.top, bottom: shell.bottom, marginTop: parseFloat(style.scrollMarginTop), marginBottom: parseFloat(style.scrollMarginBottom) },
      column: { top: b.top + box.clientTop, bottom: b.top + box.clientTop + box.clientHeight },
      paneTop: document.querySelector(pane)!.getBoundingClientRect().top,
    }
  }, PANE)
type Where = Awaited<ReturnType<typeof where>>

const r = (n: number) => Math.round(n)
/** Within a pixel: scroll offsets and boxes land on fractions of one. */
const expectNear = (actual: number, expected: number, message: string) =>
  expect(Math.abs(actual - expected), `${message} (${actual.toFixed(1)}px against ${expected.toFixed(1)}px)`).toBeLessThanOrEqual(1)
/** The composer's shell, its scroll margins and ring included, wholly in view: inside the band (in a fixed layer, the
 *  window), and inside its column. */
function expectInView(at: Where, label: string, { fixedLayer = false } = {}) {
  const shell = `${label}: the composer's shell, ${r(at.shell.top)} to ${r(at.shell.bottom)}px`
  const [top, bottom] = fixedLayer ? [0, at.bandBottom] : [at.bandTop, at.bandBottom]
  expect(at.focused, `${label}: focus is in the composer`).toBe(true)
  expect(at.shell.top - at.shell.marginTop, `${shell}, with its margin, below the ${r(top)}px band's top`).toBeGreaterThanOrEqual(top - 0.5)
  expect(at.shell.bottom + at.shell.marginBottom, `${shell}, with its margin, above the ${r(bottom)}px band's foot`).toBeLessThanOrEqual(bottom + 0.5)
  const inColumn = `${shell}, and its ring inside its column, ${r(at.column.top)} to ${r(at.column.bottom)}px`
  expect(at.shell.top - RING, inColumn).toBeGreaterThanOrEqual(at.column.top - 0.5)
  expect(at.shell.bottom + RING, inColumn).toBeLessThanOrEqual(at.column.bottom + 0.5)
}

async function selectLeadAndAsk(page: Page) {
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
}

/** A press on the floating launcher at its box, as a pointer presses it (Playwright's own click may scroll first). */
async function pressSource(page: Page) {
  const box = (await page.getByRole('button', { name: 'Source', exact: true }).boundingBox())!
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
}

test.describe('a press on Source keeps the page while the pane settles / 1100x800, a Pro reader on /filing/3', () => {
  test.use({ viewport: { width: 1100, height: 800 }, reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })

  test('the composer takes focus below the fold, the page stays where it was, and the composer ends in view', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await holdCellUntilFocus(page)
    await pressSource(page)
    const composer = composerIn(page)
    await expect(composer, 'the composer takes focus as the pane opens on Ask').toBeFocused()
    expect((await atFocus(page)).top, 'the composer took focus below the fold, where its own scroll would have moved the page').toBeGreaterThan(800)
    expect(await settled(page), 'a press on Source leaves the page at its top').toBe(0)
    expectInView(await where(page), 'once the pane settles')
    expect(await pageMoves(page), 'the composer never moved the page').toEqual([])

    // ⌘K with the page scrolled: the open rail's composer takes focus again, and the page stays where the reader put it.
    await page.evaluate(() => window.scrollTo(0, 300))
    await composer.evaluate((el: HTMLElement) => el.blur())
    await holdCellUntilFocus(page)
    await page.keyboard.press('ControlOrMeta+k')
    await expect(composer, "⌘K focuses the open rail's composer").toBeFocused()
    expect((await atFocus(page)).top, '... below the fold').toBeGreaterThan(800)
    expect(await settled(page), '⌘K leaves the page where it was').toBe(300)
    expectInView(await where(page), 'after ⌘K')
    expect(await pageMoves(page)).toEqual([])
  })

  test('an "Ask about this" pre-fill and a starter pressed from the keyboard keep the page too', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await holdCellUntilFocus(page)
    await selectLeadAndAsk(page)
    const composer = composerIn(page)
    await expect(composer, 'the pre-fill focuses the composer').toBeFocused()
    await expect(composer).toHaveValue(/^Explain this excerpt: "/)
    expect((await atFocus(page)).top, 'the composer took focus below the fold').toBeGreaterThan(800)
    expect(await settled(page), 'a pre-fill leaves the page at its top').toBe(0)
    expectInView(await where(page), 'once the pane settles')

    // Shift+Tab from the field reaches the last starter, on screen. With the cell held tall again, Enter asks it, and
    // the rail hands focus back to the composer, below the fold until its column brings it up, the page where it was.
    await page.keyboard.press('Shift+Tab')
    const starter = page.locator(PANE).locator(':focus')
    await expect(starter).toHaveText(/\?$/)
    await expect(starter, 'the starter is on screen').toBeInViewport()
    await holdCellUntilFocus(page)
    await page.keyboard.press('Enter')
    await expect(composer, 'the starter hands focus to the composer').toBeFocused()
    await expect(page.locator(PANE).getByText(ANSWER.answer)).toBeVisible()
    expect((await atFocus(page)).top, 'the composer took focus below the fold').toBeGreaterThan(800)
    expect(await settled(page), 'a starter leaves the page at its top').toBe(0)
    expectInView(await where(page), 'after the starter')
    expect(await pageMoves(page), 'the composer never moved the page').toEqual([])
  })

  test('the focused composer keeps to the foot of a column that settles shorter, unless the reader scrolled it away', async ({ page, baseURL }) => {
    await openFiling(page, baseURL!)
    await pressSource(page)
    await expect(composerIn(page)).toBeFocused()
    await settled(page)

    // The cell settles shorter, as the pane can at a large text size: at 320px the column (92px less, under the pane's
    // header) ends above the composer's shell, 263px into its content with its ring's margin. The column scrolls, and
    // the shell comes to its foot, the least distance.
    await holdCell(page, 320)
    await twoFrames(page)
    const settledColumn = await column(page)
    expect(settledColumn.scrollTop, 'the column brought the composer up').toBeGreaterThan(0)
    expect(settledColumn.shellFoot, "the composer's shell ends inside the column").toBeLessThanOrEqual(settledColumn.foot)
    expect(settledColumn.shellFoot, '... at its foot').toBeGreaterThan(settledColumn.foot - 8)

    // Settling further keeps it there.
    await holdCell(page, 300)
    await twoFrames(page)
    const further = await column(page)
    expect(further.scrollTop).toBeGreaterThan(settledColumn.scrollTop)
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
    expect(await pageMoves(page), 'not by a resize, not by the follow').toEqual([])
  })

  test("a pre-fill into a short column keeps the grown field's foot in view", async ({ page, baseURL }) => {
    // The column ends above the composer from the start. The pre-fill reveals the one-line field, then the field grows
    // to fit the excerpt a task later, before the column reports the reveal's own scroll: that scroll is not the
    // reader's, and the column follows the grown shell to its foot.
    await openFiling(page, baseURL!)
    await holdCell(page, 320)
    await selectLeadAndAsk(page)
    const composer = composerIn(page)
    await expect(composer).toBeFocused()
    await expect(composer).toHaveValue(/^Explain this excerpt: "/)
    expect(await settled(page), 'the page never moved').toBe(0)
    const grown = await composer.evaluate((field) => field.getBoundingClientRect().height)
    expect(grown, 'the field grew past one line').toBeGreaterThan(40)
    const settledColumn = await column(page)
    expect(settledColumn.shellFoot, 'the grown shell ends inside the column').toBeLessThanOrEqual(settledColumn.foot)
    expect(settledColumn.shellFoot, '... at its foot').toBeGreaterThan(settledColumn.foot - 8)
    expect(await pageMoves(page)).toEqual([])
  })
})

/** The page's foot, the page still. */
async function toTheFoot(page: Page) {
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await settled(page)
}

test.describe('a press whose composer is still out of view once the pane settles moves the page once (E252) / a Pro reader on /filing/3', () => {
  test.use({ reducedMotion: 'reduce', serviceWorkers: 'block', colorScheme: 'light' })

  for (const { width, height } of [{ width: 1100, height: 800 }, { width: 1280, height: 600 }]) {
    for (const press of ['Source', '⌘K'] as const) {
      const label = `at the foot, ${width}x${height} under 200% text, ${press}`
      test(`${label}: the pane opens above the screen, and the page moves up once to bring the composer below the site header`, async ({ page, baseURL }) => {
        await page.setViewportSize({ width, height })
        await openFiling(page, baseURL!, { doubled: true })
        await toTheFoot(page)
        if (press === 'Source') await pressSource(page)
        else await page.keyboard.press('ControlOrMeta+k')
        await expect(composerIn(page), `${label}: the composer takes focus`).toBeFocused()
        await settled(page)
        const moves = await pageMoves(page)
        expect(moves, `${label}: one page move`).toHaveLength(1)
        const [move] = moves
        const at = await where(page)
        // As the move was made, the pane had settled above the screen: no part of the shell showed below the header.
        expect(move.shell!.bottom, `${label}: the shell, ${r(move.shell!.top)} to ${r(move.shell!.bottom)}px, sat above the ${r(at.bandTop)}px header's foot`).toBeLessThanOrEqual(at.bandTop)
        expect(move.options.top, `${label}: the move is up`).toBeLessThan(0)
        expectNear(move.after - move.before, move.options.top, `${label}: the page moved by the distance asked`)
        // The least distance: the shell, its top margin covering the ring, lands at the header's foot.
        expectNear(at.shell.top - at.shell.marginTop, at.bandTop, `${label}: the shell lands at the header's foot, the least distance`)
        expectInView(at, label)
        expect(await settled(page), `${label}: the page stays where the move left it`).toBe(at.scrollY)
        expect(await pageMoves(page), `${label}: once`).toHaveLength(1)
      })
    }
  }

  for (const { width, height } of [{ width: 1100, height: 800 }, { width: 1280, height: 600 }]) {
    const label = `at the foot, ${width}x${height} at the default text size`
    test(`${label}: the composer shows, and the page holds`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height })
      await openFiling(page, baseURL!)
      await toTheFoot(page)
      await pressSource(page)
      await expect(composerIn(page), `${label}: the composer takes focus`).toBeFocused()
      await settled(page)
      const at = await where(page)
      expectInView(at, `${label} (the pane's top at ${r(at.paneTop)}px)`)
      expect(await pageMoves(page), `${label}: the page holds`).toEqual([])
    })
  }

  // The 38px column at 1100x800, and #1847's short windows, where the pane opens below the fold or shorter than its tabs.
  for (const height of [800, 600, 500]) {
    const label = `at the top, 1100x${height} under 200% text`
    test(`${label}: the composer is short of the window's foot, and the page moves down once to bring it there`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width: 1100, height })
      await openFiling(page, baseURL!, { doubled: true })
      await pressSource(page)
      await expect(composerIn(page), `${label}: the composer takes focus`).toBeFocused()
      await settled(page)
      const moves = await pageMoves(page)
      expect(moves, `${label}: one page move`).toHaveLength(1)
      const [move] = moves
      const at = await where(page)
      expect(move.shell!.bottom, `${label}: the shell, ${r(move.shell!.top)} to ${r(move.shell!.bottom)}px, ran past the ${height}px window's foot`).toBeGreaterThan(at.bandBottom)
      expect(move.options.top, `${label}: the move is down`).toBeGreaterThan(0)
      expectNear(move.after - move.before, move.options.top, `${label}: the page moved by the distance asked`)
      // The least distance: the shell, its bottom margin covering the ring, lands at the window's foot.
      expectNear(at.shell.bottom + at.shell.marginBottom, at.bandBottom, `${label}: the shell lands at the window's foot, the least distance`)
      expectInView(at, label)
      expect(await settled(page), `${label}: the page stays where the move left it`).toBe(at.scrollY)
      expect(await pageMoves(page), `${label}: once`).toHaveLength(1)
    })
  }

  // #1847's sheet cases: below lg the pane is a fixed sheet, and its column scrolls under 200% text.
  for (const { width, height } of [{ width: 390, height: 844 }, { width: 320, height: 568 }]) {
    const label = `the sheet at ${width}x${height} under 200% text`
    test(`${label}: its column alone shows the composer, its ring inside, and the page stays at its top`, async ({ page, baseURL }) => {
      await page.setViewportSize({ width, height })
      await openFiling(page, baseURL!, { doubled: true })
      await pressSource(page)
      await expect(composerIn(page), `${label}: the composer takes focus`).toBeFocused()
      expect(await settled(page), `${label}: the page stays at its top`).toBe(0)
      const at = await where(page)
      expectInView(at, label, { fixedLayer: true })
      expect(at.column.bottom, `${label}: the column ends inside the ${height}px window`).toBeLessThanOrEqual(height + 0.5)
      expect(await pageMoves(page), `${label}: no page move`).toEqual([])
    })
  }
})
