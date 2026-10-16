import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import EarningsCalendarPage from '@/features/calendar/components/EarningsCalendarPage'
import { MonthView } from '@/features/calendar/components/MonthView'
import { WeekView, type DayBucket } from '@/features/calendar/components/WeekView'
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import type { EarningsAlertsApi } from '@/features/calendar/hooks/useCalendar'

/**
 * The calendar at enlarged text (the 2026-10-14 capture review of #1301, at 390px under a 32px root):
 * the month grid cut every ticker to one letter at 390px, and at 200% its weekday heads ran together,
 * its day numbers were cut at the cell edge, its tickers vanished and "+2 more" ran into the next
 * column; the range label truncated to "O…". A view now shows only what fits whole, chosen by its own
 * width in em (its text size) through container queries, and the range label wraps between whole
 * dates. jsdom has no layout, so these hold the contract; the capture harness measures the layout.
 */

const ALERTS: EarningsAlertsApi = {
  identityPending: false,
  isOn: (ticker) => ticker === 'AAA',
  isPending: () => false,
  toggle: () => {},
  blocked: null,
  clearBlocked: () => {},
}

const event = (ticker: string, event_date: string, anticipation_score: number): CalendarEvent => ({
  ticker,
  company_name: `${ticker} Corp`,
  event_date,
  event_time: 'bmo',
  status: 'confirmed',
  confidence: 'high',
  eps_estimate: 1,
  eps_actual: null,
  anticipation_score,
})

describe('the month sheet shows a day only what fits whole', () => {
  // January 2026: five reports on the 13th; the 19th is a market holiday (Martin Luther King Jr. Day).
  const busy = ['AAA', 'BBB', 'CCC', 'DDD', 'EEE'].map((t, i) => event(t, '2026-01-13', 90 - i))
  const renderMonth = () =>
    render(
      <MonthView anchorIso="2026-01-15" todayIso="2026-01-14" eventsByDate={new Map([['2026-01-13', busy]])} alerts={ALERTS} onOpenDay={() => {}} />,
    ).container.firstElementChild as HTMLElement
  const NARROW = '[@container(width<21em)]'
  const MID = '[@container(width<42em)]'

  it('is an inline-size container whose cells give their padding way as it narrows', () => {
    const sheet = renderMonth()
    expect(sheet).toHaveClass('[container-type:inline-size]')
    const day = screen.getByRole('button', { name: /^Tuesday, January 13, 5 companies report/ })
    expect(day).toHaveClass('[@container(width>=42em)]:px-2.5', '[@container(21em<=width<42em)]:px-1', `${NARROW}:items-center`)
    // Padding only from 21em up, so below it nothing has to reset the padding to zero (button-icon-size-gate
    // bans that reset app-wide) and no unconditioned padding is left on the cell.
    expect(day.className.split(/\s+/).filter((c) => /^p[xlr]?-/.test(c))).toEqual([])
  })

  it("sizes today's marker in rem, never px, so it holds its digits at any text size, and caps its width at its day's", () => {
    // The design review of #1369: a fixed 22px pill held 24px digits in a 32px line box at 200% text, so they ran
    // about 9px past its bottom edge, and the lower half of the white digits vanished into the light panel.
    renderMonth()
    const today = within(screen.getByRole('button', { name: /^Wednesday, January 14,/ })).getByText('14')
    expect(today).toHaveClass('rounded-full', 'h-[1.375rem]', 'min-w-[min(1.375rem,100%)]')
    expect(today.className.split(/\s+/).filter((c) => /^(min-|max-)?(h|w|size)-\[[^\]]*px[^\]]*\]$/.test(c))).toEqual([])
  })

  it('narrow, a day shows the count of companies reporting in place of tickers, and the caption says so', () => {
    renderMonth()
    const day = screen.getByRole('button', { name: /^Tuesday, January 13, 5 companies report/ })
    for (const ticker of ['AAA', 'BBB', 'CCC']) expect(within(day).getByText(ticker).parentElement).toHaveClass(`${NARROW}:hidden`)
    expect(within(day).getByText('+2 more')).toHaveClass(`${NARROW}:hidden`)
    const count = within(day).getByText('5')
    expect(count).toHaveClass('hidden', `${NARROW}:block`)
    // The caption shows exactly when the count does: the same container condition.
    expect(screen.getByText('Each day shows how many companies report. Open a day to see them.')).toHaveClass('hidden', `${NARROW}:block`)
  })

  it('below six em a day, the tickers drop their session glyph and follow bell before anything clips', () => {
    renderMonth()
    const day = screen.getByRole('button', { name: /^Tuesday, January 13, 5 companies report/ })
    const followed = within(day).getByText('AAA').parentElement as HTMLElement
    const [glyph, , bell] = Array.from(followed.children)
    expect(glyph).toHaveClass(`${MID}:hidden`)
    expect(bell).toHaveClass(`${MID}:hidden`)
  })

  it('narrow, the weekday heads are one letter and a holiday drops its "Closed", its date in the weekend\'s ink', () => {
    renderMonth()
    expect(screen.getByText('Mon')).toHaveClass(`${NARROW}:hidden`)
    expect(screen.getAllByText('M')[0]).toHaveClass('hidden', `${NARROW}:inline`)
    const holiday = screen.getByRole('button', { name: /^Monday, January 19, market holiday/ })
    expect(within(holiday).getByText('Closed')).toHaveClass(`${NARROW}:hidden`)
    // With "Closed" gone, a primary-ink date would read as a trading day with no reports (the design review of
    // #1369): the holiday's date takes the weekend's tertiary ink there, and a trading day keeps the primary ink.
    expect(within(holiday).getByText('19')).toHaveClass(`${NARROW}:text-text-tertiary-light`, `dark:${NARROW}:text-text-secondary-dark`)
    const tradingDay = within(screen.getByRole('button', { name: /^Tuesday, January 20,/ })).getByText('20')
    expect(tradingDay).toHaveClass('text-text-primary-light', 'dark:text-text-primary-dark')
    expect(tradingDay.className).not.toMatch(/text-text-tertiary/)
    // On a holiday that is today, the marker keeps its own ink.
    cleanup()
    render(<MonthView anchorIso="2026-01-15" todayIso="2026-01-19" eventsByDate={new Map()} alerts={ALERTS} onOpenDay={() => {}} />)
    const today = within(screen.getByRole('button', { name: /^Monday, January 19, market holiday/ })).getByText('19')
    expect(today).toHaveClass('text-white')
    expect(today.className).not.toMatch(/text-text-tertiary/)
  })
})

describe('the week view picks the sheet or the list by its own width in em', () => {
  it('shows the five-column sheet from 42.5em and the day list below it, not at a viewport breakpoint', () => {
    const days: DayBucket[] = ['2026-03-09', '2026-03-10', '2026-03-11', '2026-03-12', '2026-03-13'].map((iso) => ({
      iso,
      isToday: false,
      holidayName: null,
      events: [event('AAA', iso, 90)],
    }))
    const { container } = render(<WeekView days={days} alerts={ALERTS} signedIn={false} onShowMore={() => {}} />)
    const view = container.firstElementChild as HTMLElement
    expect(view).toHaveClass('[container-type:inline-size]')
    const [sheet, list] = Array.from(view.children)
    expect(sheet).toHaveClass('hidden', '[@container(width>=42.5em)]:block')
    expect(list).toHaveClass('[@container(width>=42.5em)]:hidden')
    expect(`${sheet.className} ${list.className}`).not.toMatch(/\bmd:(block|hidden)\b/)
  })
})

/** The calendar range's answer: `pending` holds it in flight, so the page shows its loading skeleton. */
const calendarRange = vi.hoisted(() => ({ pending: false }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => null }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getUsage: async () => ({ is_pro: false }) }))
vi.mock('@/features/calendar/api/calendar-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/calendar/api/calendar-api')>()
  return {
    ...actual,
    getCalendar: (from: string) =>
      calendarRange.pending
        ? new Promise<never>(() => {})
        : Promise.resolve({ events: [event('AAA', from, 90)], universe: 'all' as const }),
    getEarningsAlertTickers: async () => [],
  }
})

describe('the loading skeleton switches where the week view does', () => {
  afterAll(() => {
    calendarRange.pending = false
  })

  // The review of #1369: the skeleton switched at the md viewport while the week view switches at 42.5em of its own
  // width, so the layout jumped when the week landed (at 200% text on a desktop, and from a 680px view to md).
  it('is the five-column sheet from 42.5em of the same width and one column below it, never at a viewport breakpoint', async () => {
    calendarRange.pending = true
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <EarningsCalendarPage />
      </QueryClientProvider>,
    )
    const skeleton = await screen.findByRole('status', { name: 'Loading calendar' })
    // The container is a wrapper with no border, as WeekView's root is, so both read the same width.
    expect(skeleton.parentElement).toHaveClass('[container-type:inline-size]')
    const grid = skeleton.firstElementChild as HTMLElement
    expect(grid).toHaveClass('grid-cols-1', '[@container(width>=42.5em)]:grid-cols-5')
    const [first, ...rest] = Array.from(grid.children)
    expect(first).not.toHaveClass('hidden')
    expect(rest).toHaveLength(4)
    for (const column of rest) expect(column).toHaveClass('hidden', '[@container(width>=42.5em)]:block', '[@container(width>=42.5em)]:border-l')
    expect(skeleton.parentElement?.outerHTML).not.toMatch(/\bmd:/)
  })
})

describe("the toolbar's range label", () => {
  // The page takes its week from the clock: the week of Monday, March 9, 2026.
  beforeAll(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-03-10T15:00:00Z'))
  })
  afterAll(() => {
    vi.useRealTimers()
  })

  it('wraps between whole dates, the dash kept to the first, and never truncates', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <EarningsCalendarPage />
      </QueryClientProvider>,
    )
    const label = await screen.findByRole('heading', { level: 2, name: /^Mar 9/ })
    expect(label).not.toHaveClass('truncate')
    expect(label.parentElement).toHaveClass('flex-wrap')
    const [first, second] = Array.from(label.children)
    expect(first).toHaveClass('whitespace-nowrap')
    expect(first.textContent).toBe('Mar 9 –')
    expect(second).toHaveClass('whitespace-nowrap')
    expect(second.textContent).toBe('Mar 13, 2026')

    fireEvent.click(screen.getByRole('button', { name: 'Month' }))
    await waitFor(() => expect(screen.getByRole('heading', { level: 2, name: 'March 2026' }).firstElementChild).toHaveClass('whitespace-nowrap'))
  })
})
