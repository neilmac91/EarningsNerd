import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import ContactForm from '@/features/contact/components/ContactForm'
import FeedbackWidget from '@/features/feedback/components/FeedbackWidget'
import WaitlistForm from '@/features/waitlist/components/WaitlistForm'
import PricingPage from '@/app/pricing/page'
import { queryKeys } from '@/lib/queryKeys'
import type { SubscriptionStatus, Usage } from '@/features/subscriptions/api/subscriptions-api'

/**
 * Public/app forms keep keyboard focus while their own submit is in flight. The submit Button is
 * `loading` (aria-busy + aria-disabled + click guard) and the contact fields are readOnly — never
 * natively `disabled`: Chromium blurs a focused control that turns `disabled` to <body>, including
 * the field a user pressed Enter in. jsdom does not blur disabled elements, so these specs pin the
 * attributes, that focus is never moved off the control, and that a second activation (click,
 * Enter in a field, a direct submit) sends no second request.
 */

const api = vi.hoisted(() => ({
  submitContactForm: vi.fn(),
  submitFeedback: vi.fn(),
  joinWaitlist: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  getSubscriptionStatus: vi.fn(),
  getUsage: vi.fn(),
  createCheckoutSession: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: api.submitContactForm }))
vi.mock('@/features/feedback/api/feedback-api', () => ({ submitFeedback: api.submitFeedback }))
vi.mock('@/features/waitlist/api/waitlist-api', () => ({ joinWaitlist: api.joinWaitlist }))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: api.getCurrentUserSafe }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: api.getSubscriptionStatus,
  getUsage: api.getUsage,
  createCheckoutSession: api.createCheckoutSession,
}))
const nav = vi.hoisted(() => ({ router: { push: () => {}, refresh: () => {} }, searchParams: new URLSearchParams() }))
vi.mock('next/navigation', () => ({ useRouter: () => nav.router, useSearchParams: () => nav.searchParams }))
vi.mock('posthog-js/react', () => ({ useFeatureFlagVariantKey: () => undefined }))
vi.mock('posthog-js', () => ({ default: { capture: () => {} } }))
vi.mock('@/lib/analytics', () => ({
  default: { pricingViewed: () => {}, billingCycleToggled: () => {}, checkoutStarted: () => {} },
}))
vi.mock('sonner', () => ({ toast: { success: api.toastSuccess, error: api.toastError } }))
vi.mock('@/lib/api/session', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/api/session')>()),
  hasActiveSession: () => true,
}))
// Deterministic flags: no Turnstile gate (its native `disabled` is a kept availability state), and
// the feedback launcher on.
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  TURNSTILE_ENABLED: false,
  ENABLE_FEEDBACK_WIDGET: true,
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

/** Let any re-entrant submit reach its request before counting requests. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

/** In flight: announced busy + unavailable, still focusable, and still the focused element. */
/** Busy is announced (aria-busy + aria-disabled) and the control keeps focus. That a busy flag
    never turns it natively disabled is the rule-12 gate's job (busyControlsStayFocusable.spec.ts). */
function expectBusyAndFocused(control: HTMLElement) {
  expect(control).toHaveAttribute('aria-busy', 'true')
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(document.activeElement).toBe(control)
}

afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
})

describe('ContactForm', () => {
  function fill() {
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.test' } })
    fireEvent.change(screen.getByLabelText('Subject'), { target: { value: 'Hello' } })
    fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: 'A message long enough.' } })
  }

  it('Send keeps focus through its request and settle, and refuses a repeat click or submit', async () => {
    const post = deferred<unknown>()
    api.submitContactForm.mockReturnValue(post.promise)
    render(<ContactForm />)
    fill()

    const send = screen.getByRole('button', { name: 'Send Message' })
    const form = send.closest('form')!
    send.focus()
    fireEvent.click(send)
    await waitFor(() => expect(send).toHaveTextContent('Sending...'))
    expectBusyAndFocused(send)
    fireEvent.click(send)
    fireEvent.submit(form) // Enter in a field while the request is in flight
    await settle()
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(send)

    await act(async () => post.reject(new Error('Server unavailable')))
    expect(await screen.findByText('Server unavailable')).toBeInTheDocument()
    expect(send).toHaveTextContent('Send Message')
    expect(send).not.toHaveAttribute('aria-disabled')
    expect(send).not.toHaveAttribute('aria-busy')
    expect(send).not.toBeDisabled()
    expect(document.activeElement).toBe(send)
  })

  it('a successful send hands focus to "Message sent", and "Send another message" hands it to Name', async () => {
    api.submitContactForm.mockResolvedValue({})
    render(<ContactForm />)
    fill()

    // The success panel replaces the form, and the focused Send with it: focus must not stay on <body>.
    const send = screen.getByRole('button', { name: 'Send Message' })
    send.focus()
    fireEvent.click(send)
    const heading = await screen.findByRole('heading', { name: 'Message sent' })
    expect(send.isConnected).toBe(false)
    expect(document.activeElement).toBe(heading)

    // 'Send another message' unmounts itself as the form comes back.
    const again = screen.getByRole('button', { name: 'Send another message' })
    again.focus()
    fireEvent.click(again)
    await waitFor(() => expect(again.isConnected).toBe(false))
    expect(document.activeElement).toBe(screen.getByLabelText(/^Name/))
  })

  it('a field submitted with Enter stays focused and readOnly (not disabled), and a second Enter sends nothing', async () => {
    const post = deferred<unknown>()
    api.submitContactForm.mockReturnValue(post.promise)
    const user = userEvent.setup()
    render(<ContactForm />)
    fill()

    const name = screen.getByLabelText(/^Name/)
    const send = screen.getByRole('button', { name: 'Send Message' })
    const form = send.closest('form')!
    name.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(send).toHaveAttribute('aria-busy', 'true'))
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)

    // Every field holds its value read-only while the form sends (that a busy flag never disables it
    // is the rule-12 gate's job).
    for (const field of [name, screen.getByLabelText(/^Email/), screen.getByLabelText('Subject'), screen.getByLabelText(/^Message/)]) {
      expect(field).toHaveAttribute('readonly')
    }
    expect(document.activeElement).toBe(name)
    await user.type(name, 'x', { skipClick: true })
    expect(name).toHaveValue('Ada Lovelace')

    await user.keyboard('{Enter}')
    fireEvent.submit(form)
    await settle()
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(name)

    await act(async () => post.reject(new Error('Server unavailable')))
    expect(await screen.findByText('Server unavailable')).toBeInTheDocument()
    expect(name).not.toHaveAttribute('readonly')
    expect(document.activeElement).toBe(name)
  })
})

describe('FeedbackWidget', () => {
  it('Send keeps focus through its request and settle, and refuses a repeat click or submit', async () => {
    const post = deferred<unknown>()
    api.submitFeedback.mockReturnValue(post.promise)
    render(<FeedbackWidget />)

    fireEvent.click(await screen.findByRole('button', { name: 'Send feedback' }))
    const message = await screen.findByLabelText('Feedback message')
    const send = screen.getByRole('button', { name: 'Send feedback' })
    // Too short is a kept availability state: set by the textarea, never by Send's own activation.
    expect(send).toBeDisabled()
    fireEvent.change(message, { target: { value: 'The chart is off by one.' } })
    expect(send).not.toBeDisabled()

    const form = send.closest('form')!
    send.focus()
    fireEvent.click(send)
    await waitFor(() => expect(send).toHaveTextContent('Sending…'))
    expectBusyAndFocused(send)
    fireEvent.click(send)
    fireEvent.submit(form)
    await settle()
    expect(api.submitFeedback).toHaveBeenCalledTimes(1)
    expect(document.activeElement).toBe(send)

    await act(async () => post.reject(new Error('offline')))
    await waitFor(() => expect(api.toastError).toHaveBeenCalledTimes(1))
    expect(send).toHaveTextContent('Send feedback')
    expect(send).not.toHaveAttribute('aria-disabled')
    expect(send).not.toHaveAttribute('aria-busy')
    expect(send).not.toBeDisabled()
    expect(document.activeElement).toBe(send)
    expect(message).toHaveValue('The chart is off by one.')
  })
})

describe('WaitlistForm (already `loading` + submit guard — pinned so it cannot regress)', () => {
  it('Join keeps focus through its request and settle, and refuses a repeat click or submit', async () => {
    const post = deferred<unknown>()
    api.joinWaitlist.mockReturnValue(post.promise)
    render(<WaitlistForm />)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'ada@example.test' } })

    const join = screen.getByRole('button', { name: 'Join the waitlist' })
    const form = join.closest('form')!
    join.focus()
    fireEvent.click(join)
    await waitFor(() => expect(join).toHaveTextContent('Joining waitlist...'))
    expectBusyAndFocused(join)
    fireEvent.click(join)
    fireEvent.submit(form)
    await settle()
    expect(api.joinWaitlist).toHaveBeenCalledTimes(1)

    await act(async () => post.reject(new Error('offline')))
    expect(await screen.findByText('Network error. Please try again in a moment.')).toBeInTheDocument()
    expect(join).not.toHaveAttribute('aria-disabled')
    expect(join).not.toBeDisabled()
    expect(document.activeElement).toBe(join)
  })
})

describe('Pricing page Retry buttons (a failure keeps its Notice through any refetch until data replaces it)', () => {
  afterEach(() => onlineManager.setOnline(true))
  const user1 = { id: 1, email: 'ada@example.test' }
  const freeSub: SubscriptionStatus = {
    is_pro: false,
    stripe_customer_id: null,
    stripe_subscription_id: null,
    subscription_status: null,
    plan: 'free',
    status: null,
    trial_end: null,
    current_period_end: null,
    cancel_at_period_end: false,
  }
  const usage = { summaries_used: 1, summaries_limit: 5, is_pro: false, month: '2026-10' } as Usage

  function renderPricing() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <PricingPage />
      </QueryClientProvider>,
    )
    return client
  }

  const intro = () => screen.getByText(/Choose the plan that works for you/)

  const cases = [
    {
      name: 'Retry account check',
      request: api.getCurrentUserSafe,
      key: queryKeys.currentUser(),
      message: 'network down',
      // Identity failed with no data; subscription and usage never ran.
      arrange: () => {
        api.getCurrentUserSafe.mockRejectedValueOnce(new Error('network down'))
        api.getSubscriptionStatus.mockResolvedValue(freeSub)
        api.getUsage.mockResolvedValue(usage)
      },
      success: user1 as unknown,
    },
    {
      name: 'Retry subscription',
      request: api.getSubscriptionStatus,
      key: queryKeys.subscription.byUser(1),
      message: 'subscription unavailable',
      // Initial subscription read failed with no data; usage is fine.
      arrange: () => {
        api.getCurrentUserSafe.mockResolvedValue(user1)
        api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
        api.getUsage.mockResolvedValue(usage)
      },
      success: freeSub as unknown,
    },
    {
      name: 'Retry usage',
      request: api.getUsage,
      key: queryKeys.usage.byUser(1),
      message: 'usage unavailable',
      // Initial usage read failed with no data; the subscription is fine.
      arrange: () => {
        api.getCurrentUserSafe.mockResolvedValue(user1)
        api.getSubscriptionStatus.mockResolvedValue(freeSub)
        api.getUsage.mockRejectedValueOnce(new Error('usage unavailable'))
      },
      success: usage as unknown,
    },
  ]

  // React Query puts a query with no data back to `pending` (error: null) the moment it refetches.
  // The Notice must not read that as "no longer failed": unmounting it removes the focused Retry
  // button before its `loading` renders, and focus falls to <body>.
  it.each(cases)('$name keeps focus through its retry and a failed settle, and lands on the intro once it succeeds', async ({ name, request, message, arrange, success }) => {
    const user = userEvent.setup()
    arrange()
    renderPricing()

    const retry = await screen.findByRole('button', { name })
    expect(screen.getByText(message)).toBeInTheDocument()
    const first = deferred<unknown>()
    request.mockReturnValueOnce(first.promise)
    retry.focus()
    await user.keyboard('{Enter}')
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2))

    // In flight: the same button, still in the document, busy and focused; the Notice keeps its copy.
    expect(retry.isConnected).toBe(true)
    expectBusyAndFocused(retry)
    expect(screen.getByText(message)).toBeInTheDocument()
    await user.keyboard('{Enter}')
    fireEvent.click(retry)
    await settle()
    expect(request).toHaveBeenCalledTimes(2)

    // A failed retry settles with the Notice and the focused button in place.
    await act(async () => first.reject(new Error('still down')))
    expect(await screen.findByText('still down')).toBeInTheDocument()
    expect(retry.isConnected).toBe(true)
    expect(retry).not.toHaveAttribute('aria-busy')
    expect(retry).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(retry)

    // A successful retry removes the Notice; focus lands on the intro line above it, not <body>.
    request.mockResolvedValue(success)
    await user.keyboard('{Enter}')
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(request).toHaveBeenCalledTimes(3)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(intro())
  })

  it('a retry that succeeds while focus has moved on leaves focus where the user put it', async () => {
    api.getCurrentUserSafe.mockResolvedValue(user1)
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
    api.getUsage.mockResolvedValue(usage)
    renderPricing()

    const retry = await screen.findByRole('button', { name: 'Retry subscription' })
    const pending = deferred<unknown>()
    api.getSubscriptionStatus.mockReturnValueOnce(pending.promise)
    fireEvent.click(retry)
    await waitFor(() => expect(retry).toHaveAttribute('aria-busy', 'true'))
    const toggle = screen.getByRole('switch', { name: /billing cycle/i })
    toggle.focus()

    await act(async () => pending.resolve(freeSub))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(document.activeElement).toBe(toggle)
  })

  it('a refetch nobody pressed keeps the Notice and a focused Retry, busy, then hands focus to the intro when it lands', async () => {
    api.getCurrentUserSafe.mockResolvedValue(user1)
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
    api.getUsage.mockResolvedValue(usage)
    const client = renderPricing()
    const retry = await screen.findByRole('button', { name: 'Retry subscription' })
    retry.focus()

    // A refetch nobody pressed (reconnect, window focus, an invalidation) puts the data-less query back
    // to pending. The failure stays shown until data replaces it, so the focused Retry is not unmounted.
    const background = deferred<unknown>()
    api.getSubscriptionStatus.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: queryKeys.subscription.all() }) })
    await waitFor(() => expect(api.getSubscriptionStatus).toHaveBeenCalledTimes(2))
    expect(retry).toHaveAttribute('aria-busy', 'true')
    expect(document.activeElement).toBe(retry)
    expect(screen.getByText('subscription unavailable')).toBeInTheDocument()

    await act(async () => background.resolve(freeSub))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(document.activeElement).toBe(intro())
  })

  it('a Notice that clears while its Retry does not hold focus moves no focus', async () => {
    api.getCurrentUserSafe.mockResolvedValue(user1)
    api.getSubscriptionStatus.mockRejectedValueOnce(new Error('subscription unavailable'))
    api.getSubscriptionStatus.mockResolvedValue(freeSub)
    api.getUsage.mockResolvedValue(usage)
    const client = renderPricing()
    await screen.findByRole('button', { name: 'Retry subscription' })
    expect(document.activeElement).toBe(document.body)

    // A background refetch (window focus, reconnect) recovers the subscription on its own.
    await act(async () => { await client.refetchQueries() })
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(document.activeElement).toBe(document.body)
  })

  it.each(cases)('$name pressed offline waits paused, busy and focused, and a second press sends nothing', async ({ name, request, arrange }) => {
    arrange()
    renderPricing()
    const retry = await screen.findByRole('button', { name })
    retry.focus()
    onlineManager.setOnline(false)
    fireEvent.click(retry)
    await settle()
    expectBusyAndFocused(retry)
    expect(retry).toHaveAccessibleName('Retrying…')
    fireEvent.click(retry)
    await settle()
    expect(request).toHaveBeenCalledTimes(1)
  })

  it.each(cases)('$name: after a press fails again and the user moves off, a recovery nobody pressed moves no focus', async ({ name, request, arrange, key, success }) => {
    arrange()
    const client = renderPricing()
    const retry = await screen.findByRole('button', { name })
    retry.focus()
    request.mockRejectedValueOnce(new Error('still down'))
    fireEvent.click(retry)
    expect(await screen.findByText('still down')).toBeInTheDocument()
    await waitFor(() => expect(retry).not.toHaveAttribute('aria-busy'))
    retry.blur()
    const background = deferred<unknown>()
    request.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: key }) })
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3))
    await settle()
    expect(document.activeElement).toBe(document.body)
    await act(async () => background.resolve(success))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(document.body)
  })

  it.each(cases)('$name: a refetch nobody pressed keeps it focused and busy under its own label; its success hands focus to the intro', async ({ name, request, arrange, key, success }) => {
    arrange()
    const client = renderPricing()
    const retry = await screen.findByRole('button', { name })
    retry.focus()
    const background = deferred<unknown>()
    request.mockReturnValueOnce(background.promise)
    act(() => { void client.refetchQueries({ queryKey: key }) })
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
    await settle()
    expectBusyAndFocused(retry)
    expect(retry).toHaveAccessibleName(name)
    await act(async () => background.resolve(success))
    await waitFor(() => expect(retry.isConnected).toBe(false))
    await settle()
    expect(document.activeElement).toBe(intro())
  })

  it('a Retry never outlives its Notice: when the account Notice gives way to the details Notice, its focused Retry goes too', async () => {
    // The plan check of user 1 failed earlier with data on screen (a stale failure), and is still cached.
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(queryKeys.subscription.byUser(1), freeSub)
    client.setQueryData(queryKeys.usage.byUser(1), usage)
    await client
      .fetchQuery({ queryKey: queryKeys.subscription.byUser(1), queryFn: () => Promise.reject(new Error('plan refresh failed')) })
      .catch(() => {})
    expect(client.getQueryState(queryKeys.subscription.byUser(1))?.status).toBe('error')
    api.getCurrentUserSafe.mockRejectedValueOnce(new Error('network down'))
    const planRefresh = deferred<SubscriptionStatus>()
    api.getSubscriptionStatus.mockReturnValue(planRefresh.promise)
    api.getUsage.mockResolvedValue(usage)
    render(<QueryClientProvider client={client}><PricingPage /></QueryClientProvider>)

    const accountRetry = await screen.findByRole('button', { name: 'Retry account check' })
    accountRetry.focus()
    api.getCurrentUserSafe.mockResolvedValueOnce(user1)
    fireEvent.click(accountRetry, { detail: 0 })
    // The account resolves, and in the same render the cached plan failure shows the details Notice. Unkeyed,
    // React reused the account Retry as "Retry subscription": the same focused node under another label.
    const planRetry = await screen.findByRole('button', { name: 'Retry subscription' })
    expect(planRetry).not.toBe(accountRetry)
    expect(accountRetry.isConnected).toBe(false)
    await settle()
    expect(document.activeElement).toBe(intro())
    await act(async () => planRefresh.resolve(freeSub))
  })
})
