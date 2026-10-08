import { test, expect, type Locator, type Page } from '@playwright/test'
import { PANE, answerApi, type Who } from './fixtures/filing3Api'

/**
 * EN-05a: closing the research pane returns keyboard focus to a visible control, for every route that
 * opens it, in a real Chromium.
 *
 *  - At 1440x900 (lg+, a side pane, no trap) each route is closed by Escape and by ×. Focus lands on
 *    the opener when it is still on the page outside the pane (an in-page Ask button or starter, the
 *    control a Ctrl+K or "/" was pressed on), else on the launcher, which remounts on close. The next
 *    Tab continues from there, and Shift+Tab comes back. On main focus fell to <body> on every one of
 *    these routes (EN-01 fixed only the summary chip's).
 *  - A visitor who cannot ask (anonymous here) has no composer to take focus: a keyboard press on the
 *    launcher or the coachmark's Try, which leave with the open, hands focus to the selected tab.
 *  - At 390x844 the pane is the bottom sheet, whose trap already returned focus; it stays as it was.
 *
 * CI runs e2e with no backend (lessons/test-e2e-runs-without-backend.md): fixtures/filing3Api.ts answers
 * the API in the browser, for a Pro visitor (who can ask, so the composer takes focus on open) or an
 * anonymous one. DOM and keyboard probes only: this is not a screen-reader test.
 */

const LAUNCHER = 'button[aria-haspopup="dialog"][aria-label="Ask this Filing"]'
const CALLOUT = 'section[aria-labelledby="ask-filing-callout-heading"]'

async function openFiling(page: Page, baseURL: string, who: Who, coachmark = false) {
  await answerApi(page, baseURL, who)
  // Consent answered; the first-run coachmark seen unless the route under test is its Try.
  await page.addInitScript((showCoachmark) => {
    try {
      localStorage.setItem('theme', 'light')
      if (!showCoachmark) localStorage.setItem('en:copilot-coachmark-v1', '1')
      localStorage.setItem('cookie_consent', JSON.stringify({ essential: true, analytics: false, sessionRecording: false, timestamp: new Date().toISOString() }))
    } catch {}
  }, coachmark)
  await page.goto('/filing/3')
  await expect(page.locator(LAUNCHER)).toBeVisible()
  await expect(page.locator(CALLOUT)).toBeVisible()
  // Keep the pointer off the summary so no hover card competes with the keyboard.
  await page.mouse.move(5, 5)
}

const paneOpen = (page: Page) => page.locator(PANE).evaluate((el) => getComputedStyle(el).display !== 'none')
// The page header's "← Back" (its arrow glyph is part of the accessible name).
const back = (page: Page) => page.getByRole('button', { name: '← Back', exact: true })
const calloutAsk = (page: Page) => page.locator(CALLOUT).getByRole('button', { name: 'Ask this filing', exact: true })
const calloutStarter = (page: Page) => page.locator(CALLOUT).getByRole('button').first()

/** The focused element's description, for a readable failure. */
const focused = (page: Page) =>
  page.evaluate(() => {
    const el = document.activeElement
    if (!el || el === document.body) return 'BODY'
    return `${el.tagName} ${el.getAttribute('aria-label') ?? el.textContent?.trim().slice(0, 40) ?? ''}`
  })

/** The next Tab continues from `target` (a stop after it in the document), and Shift+Tab comes back. */
async function tabContinuesFrom(page: Page, target: Locator) {
  await page.keyboard.press('Tab')
  const after = await target.evaluate((t) => {
    const next = document.activeElement
    if (!next || next === document.body) return 'BODY'
    return t.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING ? 'after' : `before: ${next.tagName} ${next.textContent?.trim().slice(0, 30)}`
  })
  expect(after).toBe('after')
  await page.keyboard.press('Shift+Tab')
  await expect(target).toBeFocused()
}

type Route = {
  name: string
  who: Who
  coachmark?: boolean
  /** Opens the pane; returns the control focus must land on after the close. */
  open: (page: Page) => Promise<Locator>
  /** Where focus is right after the open settles (checked before closing). */
  inPane?: (page: Page) => Locator
}

const ROUTES: Route[] = [
  {
    name: 'the launcher, clicked',
    who: 'pro',
    open: async (page) => {
      await page.locator(LAUNCHER).click()
      return page.locator(LAUNCHER)
    },
  },
  {
    name: 'the launcher, by keyboard',
    who: 'pro',
    open: async (page) => {
      await page.locator(LAUNCHER).focus()
      await page.keyboard.press('Enter')
      return page.locator(LAUNCHER)
    },
    inPane: (page) => page.locator(PANE).getByPlaceholder('Ask about this filing…'),
  },
  {
    name: 'Ctrl+K on the page header’s Back',
    who: 'pro',
    open: async (page) => {
      await back(page).focus()
      await page.keyboard.press('Control+k')
      return back(page)
    },
    inPane: (page) => page.locator(PANE).getByPlaceholder('Ask about this filing…'),
  },
  {
    name: '"/" on the page header’s Back',
    who: 'pro',
    open: async (page) => {
      await back(page).focus()
      await page.keyboard.press('/')
      return back(page)
    },
    inPane: (page) => page.locator(PANE).getByPlaceholder('Ask about this filing…'),
  },
  {
    name: 'Ctrl+K with nothing focused',
    who: 'pro',
    open: async (page) => {
      await page.keyboard.press('Control+k')
      return page.locator(LAUNCHER)
    },
  },
  {
    name: 'the summary’s "Ask this filing" button',
    who: 'pro',
    open: async (page) => {
      await calloutAsk(page).focus()
      await page.keyboard.press('Enter')
      return calloutAsk(page)
    },
    inPane: (page) => page.locator(PANE).getByPlaceholder('Ask about this filing…'),
  },
  {
    name: 'a summary starter question',
    who: 'pro',
    open: async (page) => {
      await calloutStarter(page).focus()
      await page.keyboard.press('Enter')
      return calloutStarter(page)
    },
    inPane: (page) => page.locator(PANE).getByPlaceholder('Ask about this filing…'),
  },
  {
    name: 'the coachmark’s Try, by keyboard',
    who: 'pro',
    coachmark: true,
    open: async (page) => {
      await page.getByRole('button', { name: 'Try it' }).focus()
      await page.keyboard.press('Enter')
      return page.locator(LAUNCHER)
    },
    inPane: (page) => page.locator(PANE).getByPlaceholder('Ask about this filing…'),
  },
  {
    name: 'the launcher, by keyboard, for a visitor who cannot ask',
    who: 'anon',
    open: async (page) => {
      await page.locator(LAUNCHER).focus()
      await page.keyboard.press('Enter')
      return page.locator(LAUNCHER)
    },
    inPane: (page) => page.locator(PANE).getByRole('tab', { name: 'Answer' }),
  },
  {
    name: 'the coachmark’s Try, by keyboard, for a visitor who cannot ask',
    who: 'anon',
    coachmark: true,
    open: async (page) => {
      await page.getByRole('button', { name: 'Try it' }).focus()
      await page.keyboard.press('Enter')
      return page.locator(LAUNCHER)
    },
    inPane: (page) => page.locator(PANE).getByRole('tab', { name: 'Answer' }),
  },
]

const CLOSES = {
  Escape: async (page: Page) => page.keyboard.press('Escape'),
  '×': async (page: Page) => {
    await page.locator(PANE).getByRole('button', { name: 'Close' }).focus()
    await page.keyboard.press('Enter')
  },
}

test.describe('closing the research pane returns focus, desktop 1440x900', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  for (const route of ROUTES) {
    for (const [closeName, close] of Object.entries(CLOSES)) {
      test(`${route.name}, closed by ${closeName}`, async ({ page, baseURL }) => {
        await openFiling(page, baseURL!, route.who, route.coachmark)
        const target = await route.open(page)
        await expect.poll(() => paneOpen(page)).toBe(true)
        if (route.inPane) await expect(route.inPane(page), `after open: ${await focused(page)}`).toBeFocused()

        await close(page)
        await expect.poll(() => paneOpen(page)).toBe(false)
        await expect(target, `after close: ${await focused(page)}`).toBeFocused()
        await tabContinuesFrom(page, target)
      })
    }
  }
})

test.describe('the bottom sheet is unchanged, 390x844', () => {
  test.use({ viewport: { width: 390, height: 844 } })

  for (const route of [ROUTES[1], ROUTES[5]]) {
    for (const [closeName, close] of Object.entries(CLOSES)) {
      test(`${route.name}, closed by ${closeName}, returns to the launcher`, async ({ page, baseURL }) => {
        await openFiling(page, baseURL!, route.who)
        await route.open(page)
        await expect.poll(() => paneOpen(page)).toBe(true)
        // The trap moved focus into the sheet.
        expect(await page.locator(PANE).evaluate((el) => el.contains(document.activeElement))).toBe(true)
        await close(page)
        await expect.poll(() => paneOpen(page)).toBe(false)
        await expect(page.locator(LAUNCHER), `after close: ${await focused(page)}`).toBeFocused()
      })
    }
  }
})
