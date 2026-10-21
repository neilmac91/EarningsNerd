import { expect, type Page } from '@playwright/test'

/**
 * /calendar in CI's e2e build. The job runs no backend, so the build sets NEXT_PUBLIC_CALENDAR_FIXTURES and the page
 * reads features/calendar/api/calendar-fixtures.ts, which builds each week around the reader's today. The clock is
 * pinned so every run reads the same week, whatever the date: Thursday, July 30, 2026, noon in New York, in the
 * fixtures' busiest week. Monday and Tuesday have no reports, Wednesday's eight companies have reported, and
 * Thursday's six and Friday's two are still ahead, so the page paints every row kind and both "+N more" controls.
 * Shared by text-floors.spec.ts and reflow-200.spec.ts.
 *
 * The page is prerendered at build time, so its HTML holds the build day's week and the browser renders the pinned
 * week over it.
 */
export const CALENDAR_TODAY = new Date('2026-07-30T16:00:00Z')

export async function pinCalendarWeek(page: Page) {
  await page.clock.setFixedTime(CALENDAR_TODAY)
}

/** What only the loaded, pinned week shows: its range heading, so a run in a real week that also lists Microsoft (one
    week in thirteen, as the fixtures repeat) cannot pass on the wrong week, and Wednesday's highest-ranked reporter,
    Microsoft, in the sheet or the day list, whichever the width shows. */
export const calendarWeekReady = async (page: Page) => {
  await expect(page.getByRole('heading', { level: 2, name: /Jul 27\s–\sJul 31, 2026/ })).toBeVisible()
  await expect(page.locator('a[href="/company/MSFT"]').filter({ visible: true })).toBeVisible()
}
