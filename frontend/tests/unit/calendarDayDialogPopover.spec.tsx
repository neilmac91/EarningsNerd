import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import EarningsCalendarPage from '@/features/calendar/components/EarningsCalendarPage'
import type { CalendarEvent } from '@/features/calendar/api/calendar-api'
import type { SignupConfig } from '@/lib/serverApi'

/**
 * The bell's popover portals into the open day dialog (DayDetailDialog, a native <dialog>), so it must
 * never outlive a change of that dialog. Closing the day from its X (a keyboard click fires no
 * `cancel`) would otherwise orphan the popover in the detached dialog, still swallowing Escape; opening
 * a day over a page popover would leave it inert beneath the top layer.
 * lessons/frontend-native-modal-dialog-makes-body-portals-inert.md
 */

// The viewer: a guest (null) unless a case signs one in.
const mockUser = vi.fn<() => Promise<{ id: number; email: string } | null>>(async () => null)
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: () => mockUser() }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getUsage: async () => ({ is_pro: false }) }))
// The registration mode the signed-out prompt's account action follows (null: no answer, the invite).
const mockRegistration = vi.fn<() => Promise<SignupConfig | null>>(async () => null)
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: () => mockRegistration() }))
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
  // The page takes its week from the clock; a holiday Monday renders "Market closed" in place of the
  // reports this spec opens, so the week is pinned to one with no market holiday.
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-03-10T15:00:00Z'))
})
afterAll(() => {
  delete dialogProto.showModal
  vi.useRealTimers()
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

describe("the signed-out prompt's account action follows the registration mode", () => {
  beforeEach(() => {
    // Each case counts its own calls: a wait on an earlier case's call would pass without a fetch.
    mockRegistration.mockReset()
    mockUser.mockReset()
    mockUser.mockResolvedValue(null)
  })

  const openPrompt = () => fireEvent.click(screen.getAllByRole('button', { name: /^Sign in to get earnings alerts/ })[0])

  it.each([
    ['before an answer', () => new Promise<SignupConfig | null>(() => {})], // never answers
    ['on an empty answer', async () => null],
  ] as const)('%s, it offers the invite (the default)', async (_name, answer) => {
    mockRegistration.mockImplementation(answer)
    await renderPage()
    await waitFor(() => expect(mockRegistration).toHaveBeenCalledTimes(1))
    openPrompt()
    expect(screen.getByRole('link', { name: 'Request an invite' })).toHaveAttribute('href', '/waitlist')
  })

  it.each([
    // The same label as the default: the fetch is what tells them apart, so the case asserts it.
    ['invite-only', { mode: 'invite_only', beta_promo_enabled: false }, 'Request an invite', '/waitlist'],
    ['public', { mode: 'public', beta_promo_enabled: false }, 'Create a free account', '/register'],
  ] as const)('%s: the page asks, and the action follows the answer', async (_name, config, label, href) => {
    mockRegistration.mockResolvedValue(config)
    await renderPage()
    await waitFor(() => expect(mockRegistration).toHaveBeenCalledTimes(1))
    openPrompt()
    await waitFor(() => expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href))
    expect(screen.queryByRole('link', { name: label === 'Create a free account' ? 'Request an invite' : 'Create a free account' })).toBeNull()
  })

  it('a failed answer fails closed to the invite', async () => {
    mockRegistration.mockRejectedValue(new Error('registration config unavailable'))
    await renderPage()
    await waitFor(() => expect(mockRegistration).toHaveBeenCalledTimes(1))
    openPrompt()
    // Let the rejection settle before reading the action, so a fail-open would have rendered by now.
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.getByRole('link', { name: 'Request an invite' })).toHaveAttribute('href', '/waitlist')
    expect(screen.queryByRole('link', { name: 'Create a free account' })).toBeNull()
  })

  it('a signed-in viewer never asks', async () => {
    mockUser.mockResolvedValue({ id: 1, email: 'reader@example.com' })
    mockRegistration.mockResolvedValue({ mode: 'public', beta_promo_enabled: false })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <EarningsCalendarPage />
      </QueryClientProvider>,
    )
    // Identity resolved to a reader: the free plan's alert count shows, and no bell offers sign-in.
    expect(await screen.findByText(/^0 of \d+$/)).toBeInTheDocument()
    await waitFor(() => expect(mockUser).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryAllByRole('button', { name: /^Sign in to get earnings alerts/ })).toHaveLength(0)
    expect(mockRegistration).not.toHaveBeenCalled()
  })
})
