import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import type { NotificationPreferences } from '@/features/notifications/api/notifications-api'
import type { SubscriptionStatus } from '@/features/subscriptions/api/subscriptions-api'
import ProfileForm from '@/features/settings/components/ProfileForm'
import ChangePasswordForm from '@/features/settings/components/ChangePasswordForm'
import ConnectedAccounts from '@/features/settings/components/ConnectedAccounts'
import BillingPanel from '@/features/settings/components/BillingPanel'
import NotificationPreferencesForm from '@/features/settings/components/NotificationPreferencesForm'

/**
 * Settings controls keep keyboard focus while their own request is in flight and through the state
 * that request leaves behind ("Saved", cleared fields). They are aria-disabled + aria-busy with an
 * early return, never natively `disabled`: Chromium blurs a focused control that turns `disabled` to
 * <body>. jsdom does not blur disabled elements, so these specs pin the attributes, that focus is
 * never moved off the control, and that a second activation (click, Enter-submit) sends no request.
 */

const api = vi.hoisted(() => ({
  getCurrentUserSafe: vi.fn(),
  updateProfile: vi.fn(),
  changePassword: vi.fn(),
  getConnections: vi.fn(),
  unlinkProvider: vi.fn(),
  logoutAllSessions: vi.fn(),
  getSubscriptionStatus: vi.fn(),
  getUsage: vi.fn(),
  createPortalSession: vi.fn(),
  getNotificationPreferences: vi.fn(),
  updateNotificationPreferences: vi.fn(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: api.getCurrentUserSafe,
  updateProfile: api.updateProfile,
  changePassword: api.changePassword,
  getConnections: api.getConnections,
  unlinkProvider: api.unlinkProvider,
  logoutAllSessions: api.logoutAllSessions,
}))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: api.getSubscriptionStatus,
  getUsage: api.getUsage,
  createPortalSession: api.createPortalSession,
}))
vi.mock('@/features/notifications/api/notifications-api', () => ({
  getNotificationPreferences: api.getNotificationPreferences,
  updateNotificationPreferences: api.updateNotificationPreferences,
}))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

const user = (fullName: string | null): CurrentUser => ({
  id: 1, email: 'a@example.test', full_name: fullName, is_pro: true, is_beta: false, is_admin: false, email_verified: true,
})

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

/** TanStack calls mutationFn a few microtasks after mutate(), so a request count is only
    meaningful once pending work has flushed — otherwise a second request would not be seen yet. */
const settle = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })

/** In flight: announced busy + unavailable, still focusable, and still the focused element. */
function expectBusyAndFocused(control: HTMLElement) {
  expect(control).toHaveAttribute('aria-busy', 'true')
  expect(control).toHaveAttribute('aria-disabled', 'true')
  expect(control).not.toBeDisabled()
  expect(document.activeElement).toBe(control)
}

afterEach(() => {
  cleanup()
  Object.values(api).forEach((mock) => mock.mockReset())
})

describe('ProfileForm Save', () => {
  it('keeps focus through its request and the clean "Saved" state after it, and ignores repeat clicks', async () => {
    api.getCurrentUserSafe.mockResolvedValueOnce(user('Old')).mockResolvedValue(user('New'))
    const patch = deferred<unknown>()
    api.updateProfile.mockReturnValue(patch.promise)
    renderWithClient(<ProfileForm />)

    const field = screen.getByLabelText('Display name')
    await waitFor(() => expect(field).toHaveValue('Old'))
    const save = screen.getByRole('button', { name: 'Save changes' })
    // Nothing to save: unavailable, but focusable — the state a save lands back in.
    expect(save).toHaveAttribute('aria-disabled', 'true')
    expect(save).not.toBeDisabled()
    fireEvent.click(save)
    await settle()
    expect(api.updateProfile).not.toHaveBeenCalled()

    fireEvent.change(field, { target: { value: 'New' } })
    expect(save).not.toHaveAttribute('aria-disabled')
    save.focus()
    fireEvent.click(save)
    await waitFor(() => expect(save).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(save)
    fireEvent.click(save)
    await settle()
    expect(api.updateProfile).toHaveBeenCalledTimes(1)

    await act(async () => patch.resolve(user('New')))
    // The refetched name now matches the field, so the form is clean: Save turns unavailable
    // while it still holds focus — the flip native `disabled` would blur.
    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(save).toHaveAttribute('aria-disabled', 'true')
    expect(save).not.toHaveAttribute('aria-busy')
    expect(save).not.toBeDisabled()
    expect(document.activeElement).toBe(save)
    fireEvent.click(save)
    await settle()
    expect(api.updateProfile).toHaveBeenCalledTimes(1)
  })

  it('stays busy after the PATCH until the refetched name lands, so a click in that window sends no second save', async () => {
    const me = deferred<CurrentUser>()
    api.getCurrentUserSafe.mockResolvedValueOnce(user('Old')).mockReturnValueOnce(me.promise)
    api.updateProfile.mockResolvedValue(user('New'))
    renderWithClient(<ProfileForm />)

    const field = screen.getByLabelText('Display name')
    await waitFor(() => expect(field).toHaveValue('Old'))
    fireEvent.change(field, { target: { value: 'New' } })
    const save = screen.getByRole('button', { name: 'Save changes' })
    save.focus()
    fireEvent.click(save)
    await waitFor(() => expect(api.getCurrentUserSafe).toHaveBeenCalledTimes(2))
    // The PATCH has resolved but /me still holds the old name, so the field is still dirty.
    expectBusyAndFocused(save)
    fireEvent.click(save)
    await settle()
    expect(api.updateProfile).toHaveBeenCalledTimes(1)

    await act(async () => me.resolve(user('New')))
    expect(await screen.findByText('Saved')).toBeInTheDocument()
    expect(save).toHaveAttribute('aria-disabled', 'true')
    expect(save).not.toHaveAttribute('aria-busy')
    expect(document.activeElement).toBe(save)
  })
})

describe('ChangePasswordForm submit', () => {
  it('keeps focus through its request and the cleared form, and refuses a repeat click or Enter-submit', async () => {
    api.getConnections.mockResolvedValue({ has_password: true, providers: [] })
    const post = deferred<unknown>()
    api.changePassword.mockReturnValue(post.promise)
    renderWithClient(<ChangePasswordForm />)

    const current = await screen.findByLabelText('Current password')
    const submit = screen.getByRole('button', { name: 'Update password' })
    const form = submit.closest('form')!
    // Incomplete: unavailable but focusable, and Enter in a field submits nothing (as `disabled` did).
    expect(submit).toHaveAttribute('aria-disabled', 'true')
    expect(submit).not.toBeDisabled()
    fireEvent.submit(form)
    await settle()
    expect(api.changePassword).not.toHaveBeenCalled()
    expect(screen.queryByText(/at least 12 characters/)).not.toBeInTheDocument()

    fireEvent.change(current, { target: { value: 'old-password-1' } })
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'new-password-12' } })
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'new-password-12' } })
    expect(submit).not.toHaveAttribute('aria-disabled')
    submit.focus()
    fireEvent.click(submit)
    await waitFor(() => expect(submit).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(submit)
    fireEvent.click(submit)
    fireEvent.submit(form) // Enter in a field while the request is in flight
    await settle()
    expect(api.changePassword).toHaveBeenCalledTimes(1)

    await act(async () => post.resolve({}))
    // Success clears the fields, so the button turns unavailable while it still holds focus.
    expect(await screen.findByText('Password saved')).toBeInTheDocument()
    expect(submit).toHaveAttribute('aria-disabled', 'true')
    expect(submit).not.toHaveAttribute('aria-busy')
    expect(submit).not.toBeDisabled()
    expect(document.activeElement).toBe(submit)
    fireEvent.click(submit)
    fireEvent.submit(form)
    await settle()
    expect(api.changePassword).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/at least 12 characters/)).not.toBeInTheDocument()
  })
})

describe('ConnectedAccounts', () => {
  const google = { provider: 'google', provider_email: 'a@gmail.test', linked_at: null }

  it('Unlink keeps focus while its own request is in flight and ignores a second click', async () => {
    api.getConnections.mockResolvedValue({ has_password: true, providers: [google] })
    const del = deferred<unknown>()
    api.unlinkProvider.mockReturnValue(del.promise)
    renderWithClient(<ConnectedAccounts />)

    const unlink = await screen.findByRole('button', { name: 'Unlink' })
    unlink.focus()
    fireEvent.click(unlink)
    await waitFor(() => expect(unlink).toHaveTextContent('Unlinking…'))
    expectBusyAndFocused(unlink)
    fireEvent.click(unlink)
    await settle()
    expect(api.unlinkProvider).toHaveBeenCalledTimes(1)

    await act(async () => del.reject(new Error('Unlink refused')))
    expect(await screen.findByText('Unlink refused')).toBeInTheDocument()
    expect(unlink).toHaveTextContent('Unlink')
    expect(unlink).not.toHaveAttribute('aria-disabled')
    expect(unlink).not.toBeDisabled()
    expect(document.activeElement).toBe(unlink)
  })

  it('Unlink stays busy until the refetch drops its row, so a second activation sends no second DELETE', async () => {
    const refetch = deferred<unknown>()
    api.getConnections
      .mockResolvedValueOnce({ has_password: true, providers: [google] })
      .mockReturnValueOnce(refetch.promise)
    api.unlinkProvider.mockResolvedValue({})
    renderWithClient(<ConnectedAccounts />)

    const unlink = await screen.findByRole('button', { name: 'Unlink' })
    unlink.focus()
    fireEvent.click(unlink)
    await waitFor(() => expect(api.getConnections).toHaveBeenCalledTimes(2))
    // The DELETE has resolved; the refetch that removes this row has not.
    expectBusyAndFocused(unlink)
    fireEvent.click(unlink)
    await settle()
    expect(api.unlinkProvider).toHaveBeenCalledTimes(1)

    await act(async () => refetch.resolve({ has_password: true, providers: [] }))
    expect(await screen.findByText('No social sign-ins linked.')).toBeInTheDocument()
    expect(screen.queryByText(/Could not unlink/)).not.toBeInTheDocument()
  })

  it('the last sign-in method is unavailable but focusable, and a click sends nothing', async () => {
    api.getConnections.mockResolvedValue({ has_password: false, providers: [google] })
    renderWithClient(<ConnectedAccounts />)
    const unlink = await screen.findByRole('button', { name: 'Unlink' })
    expect(unlink).toHaveAttribute('aria-disabled', 'true')
    expect(unlink).not.toHaveAttribute('aria-busy')
    expect(unlink).not.toBeDisabled()
    unlink.focus()
    fireEvent.click(unlink)
    await settle()
    expect(api.unlinkProvider).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(unlink)
  })

  it("a sibling's unlink that leaves this row the last sign-in method keeps focus on this row's Unlink", async () => {
    const apple = { provider: 'apple', provider_email: 'a@icloud.test', linked_at: null }
    api.getConnections
      .mockResolvedValueOnce({ has_password: false, providers: [google, apple] })
      .mockResolvedValue({ has_password: false, providers: [apple] })
    const del = deferred<unknown>()
    api.unlinkProvider.mockReturnValue(del.promise)
    renderWithClient(<ConnectedAccounts />)

    await screen.findAllByRole('button', { name: 'Unlink' })
    const [googleUnlink, appleUnlink] = screen.getAllByRole('button', { name: 'Unlink' })
    expect(appleUnlink).not.toHaveAttribute('aria-disabled')
    googleUnlink.focus()
    fireEvent.click(googleUnlink)
    await waitFor(() => expect(googleUnlink).toHaveTextContent('Unlinking…'))
    appleUnlink.focus() // Tab to the next row while Google's unlink is in flight

    await act(async () => del.resolve({}))
    await waitFor(() => expect(screen.queryByText('Google')).not.toBeInTheDocument())
    // Apple is now the only sign-in method: unavailable while it still holds focus.
    expect(appleUnlink).toBeInTheDocument()
    expect(appleUnlink).toHaveAttribute('aria-disabled', 'true')
    expect(appleUnlink).not.toBeDisabled()
    expect(document.activeElement).toBe(appleUnlink)
    fireEvent.click(appleUnlink)
    await settle()
    expect(api.unlinkProvider).toHaveBeenCalledTimes(1)
  })

  it('Sign out of all devices keeps focus while in flight and ignores a second click', async () => {
    api.getConnections.mockResolvedValue({ has_password: true, providers: [] })
    const post = deferred<unknown>()
    api.logoutAllSessions.mockReturnValue(post.promise)
    renderWithClient(<ConnectedAccounts />)

    const signOut = await screen.findByRole('button', { name: 'Sign out of all devices' })
    signOut.focus()
    fireEvent.click(signOut)
    await waitFor(() => expect(signOut).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(signOut)
    fireEvent.click(signOut)
    await settle()
    expect(api.logoutAllSessions).toHaveBeenCalledTimes(1)

    await act(async () => post.reject(new Error('Sign-out failed')))
    expect(await screen.findByText('Sign-out failed')).toBeInTheDocument()
    expect(signOut).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(signOut)
  })
})

describe('BillingPanel Manage billing', () => {
  it('keeps focus while the portal session is requested and ignores a second click', async () => {
    const sub: SubscriptionStatus = {
      is_pro: true, stripe_customer_id: 'cus_123', stripe_subscription_id: null, subscription_status: 'active',
      plan: 'pro', status: 'active', trial_end: null, current_period_end: '2027-06-18T00:00:00Z', cancel_at_period_end: false,
    }
    api.getCurrentUserSafe.mockResolvedValue(user(null))
    api.getSubscriptionStatus.mockResolvedValue(sub)
    api.getUsage.mockResolvedValue({ summaries_used: 0, summaries_limit: null, is_pro: true, month: '2026-10' })
    const portal = deferred<{ url: string }>()
    api.createPortalSession.mockReturnValue(portal.promise)
    renderWithClient(<BillingPanel />)

    const manage = await screen.findByRole('button', { name: 'Manage billing' })
    manage.focus()
    fireEvent.click(manage)
    await waitFor(() => expect(manage).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(manage)
    fireEvent.click(manage)
    await settle()
    expect(api.createPortalSession).toHaveBeenCalledTimes(1)

    await act(async () => portal.reject(new Error('stripe down')))
    expect(await screen.findByText('Could not open the billing portal. Please try again.')).toBeInTheDocument()
    expect(manage).not.toHaveAttribute('aria-disabled')
    expect(document.activeElement).toBe(manage)
  })
})

describe('NotificationPreferencesForm', () => {
  const prefs: NotificationPreferences = {
    notify_10k: false, notify_10q: true, notify_8k: false, notify_20f: false, notify_6k: false,
    channel: 'email', digest: 'daily', realtime: false, realtime_available: true, eightk_available: false,
  }

  it('a flipped switch keeps focus through the save, and no control starts a second save meanwhile', async () => {
    api.getNotificationPreferences.mockResolvedValue(prefs)
    const put = deferred<NotificationPreferences>()
    api.updateNotificationPreferences.mockReturnValue(put.promise)
    renderWithClient(<NotificationPreferencesForm />)

    const tenK = await screen.findByRole('switch', { name: 'Annual reports (10-K)' })
    // Plan availability stays native `disabled` — server-set, never flipped by the switch itself.
    expect(screen.getByRole('switch', { name: 'Material events (8-K)' })).toBeDisabled()
    tenK.focus()
    fireEvent.click(tenK)
    await waitFor(() => expect(tenK).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(tenK)
    fireEvent.click(tenK)
    fireEvent.click(screen.getByRole('switch', { name: 'Quarterly reports (10-Q)' }))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'weekly' } })
    await settle()
    expect(api.updateNotificationPreferences).toHaveBeenCalledTimes(1)
    expect(api.updateNotificationPreferences.mock.calls[0][0]).toEqual({ notify_10k: true })
    expect(screen.getByRole('combobox')).toHaveValue('daily')

    await act(async () => put.resolve({ ...prefs, notify_10k: true }))
    await waitFor(() => expect(tenK).toHaveAttribute('aria-checked', 'true'))
    expect(tenK).not.toHaveAttribute('aria-disabled')
    expect(tenK).not.toBeDisabled()
    expect(document.activeElement).toBe(tenK)
  })

  it('the digest select keeps focus through its save and ignores a second change meanwhile', async () => {
    api.getNotificationPreferences.mockResolvedValue(prefs)
    const put = deferred<NotificationPreferences>()
    api.updateNotificationPreferences.mockReturnValue(put.promise)
    renderWithClient(<NotificationPreferencesForm />)

    const digest = await screen.findByRole('combobox')
    digest.focus()
    fireEvent.change(digest, { target: { value: 'weekly' } })
    await waitFor(() => expect(digest).toHaveAttribute('aria-busy', 'true'))
    expectBusyAndFocused(digest)
    fireEvent.change(digest, { target: { value: 'immediate' } })
    await settle()
    expect(api.updateNotificationPreferences).toHaveBeenCalledTimes(1)
    expect(api.updateNotificationPreferences.mock.calls[0][0]).toEqual({ digest: 'weekly' })

    await act(async () => put.resolve({ ...prefs, digest: 'weekly' }))
    await waitFor(() => expect(digest).toHaveValue('weekly'))
    expect(digest).not.toHaveAttribute('aria-disabled')
    expect(digest).not.toBeDisabled()
    expect(document.activeElement).toBe(digest)
  })
})
