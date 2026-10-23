import { expect, type Page } from '@playwright/test'

/**
 * /calendar in CI's e2e build. The job runs no backend, so the build sets NEXT_PUBLIC_CALENDAR_FIXTURES and the page
 * reads features/calendar/api/calendar-fixtures.ts, which builds each week around the reader's today. The clock is
 * pinned so every run reads the same week, whatever the date: Thursday, July 30, 2026, noon in New York, in the
 * fixtures' busiest week. Monday and Tuesday have no reports, Wednesday's eight companies have reported, and
 * Thursday's six and Friday's two are still ahead, so the page paints every row kind and both "+N more" controls.
 * Shared by text-floors.spec.ts and reflow-200.spec.ts.
 *
 * The page is prerendered at build time, and the clock is pinned in the browser alone, so every pinned load meets
 * what a reader meets once the New York week turns over before the page renders again: the server's hour and the
 * browser's in different weeks. The page names no week until the browser has read today (useTodayEasternIso), so
 * the browser's first render matches the build's markup and the pinned week renders over it. Until E136 the markup
 * held the build day's week, and every pinned load logged React error 418 and rendered the page again on the client;
 * calendarWeekReady fails on that error, and on a heading that kept the build's week, as suppressHydrationWarning
 * would leave it (React keeps the server's text).
 */
export const CALENDAR_TODAY = new Date('2026-07-30T16:00:00Z')

/** React's hydration errors as a production build reports them (#418: the server's markup and the browser's first
    render disagree; #423 and #425 are React 18's forms of it), or as a development build words them. */
const HYDRATION_ERROR = /Minified React error #(418|423|425)\b|Hydration failed|did not match/

/** What each pinned page has logged as an error or thrown since it was pinned. */
const logged = new WeakMap<Page, string[]>()

export async function pinCalendarWeek(page: Page) {
  const errors: string[] = []
  logged.set(page, errors)
  // React reports a hydration mismatch through reportError, which the page throws as an uncaught error.
  page.on('pageerror', (error) => errors.push(error.message))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text())
  })
  await page.clock.setFixedTime(CALENDAR_TODAY)
}

/** What only the loaded, pinned week shows: its range heading, so a run in a real week that also lists Microsoft (one
    week in thirteen, as the fixtures repeat) cannot pass on the wrong week, and Wednesday's highest-ranked reporter,
    Microsoft, in the sheet or the day list, whichever the width shows. By then the page has hydrated, with no
    hydration error logged (E136). */
export const calendarWeekReady = async (page: Page) => {
  await expect(page.getByRole('heading', { level: 2, name: /Jul 27\s–\sJul 31, 2026/ })).toBeVisible()
  await expect(page.locator('a[href="/company/MSFT"]').filter({ visible: true })).toBeVisible()
  const errors = logged.get(page)
  expect(errors, 'pin the week with pinCalendarWeek before the page loads').toBeDefined()
  expect(errors?.filter((error) => HYDRATION_ERROR.test(error)), 'the pinned load logs no hydration error (React #418)').toEqual([])
}
