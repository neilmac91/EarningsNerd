import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import EarningsCalendarPage from '@/features/calendar/components/EarningsCalendarPage'
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'

/**
 * The bell's popover portals into the open day dialog (DayDetailDialog, a native <dialog>), so it must
 * never outlive a change of that dialog. Closing the day from its X (a keyboard click fires no
 * `cancel`) would otherwise orphan the popover in the detached dialog, still swallowing Escape; opening
 * a day over a page popover would leave it inert beneath the top layer.
 * lessons/frontend-native-modal-dialog-makes-body-portals-inert.md
 */

vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => null }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getUsage: async () => ({ is_pro: false }) }))
vi.mock('@/features/calendar/api/calendar-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/calendar/api/calendar-api')>()
  const day = (from: string): CalendarEvent[] =>
    Array.from({ length: 7 }, (_, i) => ({
      ticker: `T${i}X`,
      company_name: `Company ${i}`,
      event_date: from, // the range's Monday: seven reports, so the week view shows "+2 more"
      event_time: i % 2 ? 'amc' : 'bmo',
      status: 'estimated',
      confidence: 'high',
      eps_estimate: 1,
      eps_actual: null,
      anticipation_score: 100 - i,
    }))
  return {
    ...actual,
    getCalendar: async (from: string) => ({ events: day(from), universe: 'all' as const }),
    getEarningsAlertTickers: async () => [],
  }
})

// jsdom has no showModal(); the real one also puts the dialog in the top layer, which jsdom cannot model.
const dialogProto = HTMLElement.prototype as HTMLElement & { showModal?: () => void }
beforeAll(() => {
  dialogProto.showModal = function (this: HTMLElement) {
    this.setAttribute('open', '')
  }
})
afterAll(() => {
  delete dialogProto.showModal
})

async function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <EarningsCalendarPage />
    </QueryClientProvider>,
  )
  // Identity resolves to a guest: every bell offers sign-in.
  await waitFor(() => expect(screen.getAllByRole('button', { name: /^Sign in to get earnings alerts/ }).length).toBeGreaterThan(0))
}

/** The desktop "+N more" opens the day dialog (the mobile one expands in place). */
function openDay(): HTMLElement {
  for (const more of screen.getAllByRole('button', { name: /^\+\d+ more$/ })) {
    fireEvent.click(more)
    const dialog = document.querySelector('dialog[open]')
    if (dialog) return dialog as HTMLElement
  }
  throw new Error('no "+N more" opened the day dialog')
}

describe('the bell popover never outlives a change of the day dialog', () => {
  it('closing the day (its X, from the keyboard) closes the popover inside it; Escape is not swallowed', async () => {
    await renderPage()
    const dialog = openDay()
    fireEvent.click(within(dialog).getAllByRole('button', { name: /^Sign in to get earnings alerts/ })[0])
    expect(dialog).toContainElement(screen.getByRole('group', { name: 'Sign in to set earnings alerts' }))

    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(document.querySelector('dialog')).toBeNull()
    expect(fireEvent.keyDown(document.body, { key: 'Escape' })).toBe(true) // nobody is holding it
  })

  it('opening a day over a page popover closes the popover first', async () => {
    await renderPage()
    fireEvent.click(screen.getAllByRole('button', { name: /^Sign in to get earnings alerts/ })[0])
    expect(screen.getByRole('group', { name: 'Sign in to set earnings alerts' })).toBeInTheDocument()

    openDay()
    expect(screen.queryByRole('group', { name: 'Sign in to set earnings alerts' })).not.toBeInTheDocument()
  })
})
