import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import type { CurrentUser } from '@/features/auth/api/auth-api'
import SettingsPage from '@/app/dashboard/settings/page'
import ChangePasswordForm, {
  ACCOUNT_UNCONFIRMED_MESSAGE,
  PASSWORD_NOT_CHANGED_OTHER_ACCOUNT_MESSAGE,
} from '@/features/settings/components/ChangePasswordForm'
import { STEP_TOAST_DURATION_MS } from '@/features/auth/lib/accountQueryState'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'

/**
 * E29 (6): a tab left showing one account by another tab's sign-in posts its password change with the cookies of the
 * account the browser holds now, and for an account without a password the route asks for no current one. So the form
 * names the account its tab shows (the identity read's cached account, as "Log out of all devices" names it, E157 (2)),
 * posts nothing while that read holds no account to name, and on the route's 409 for another account it keeps nothing
 * typed for the account it showed, says why in a toast,
 * which outlives the form a read of /me replaces, and reads /me again. The settings page keys the form by the account
 * it shows, so a read of /me that moves the tab to another account remounts it empty: nothing typed for one account is
 * posted under another. The cross-tab ordering and the route's refusal are pinned in sessionCookiesAcrossTabs.spec.ts
 * and backend/tests/unit/test_password_and_profile.py.
 */

const api = vi.hoisted(() => ({ changePassword: vi.fn(), getConnections: vi.fn(), getCurrentUserSafe: vi.fn() }))
vi.mock('@/features/auth/api/auth-api', () => ({
  changePassword: api.changePassword,
  getConnections: api.getConnections,
  getCurrentUserSafe: api.getCurrentUserSafe,
  logoutAllSessions: vi.fn(),
  LogoutAllSuperseded: class LogoutAllSuperseded extends Error {},
  updateProfile: vi.fn(),
  unlinkProvider: vi.fn(),
  exportUserData: vi.fn(),
  deleteUserAccount: vi.fn(),
}))
// The settings page's other sections, which load and stay loading here.
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => new Promise(() => {}),
  getUsage: () => new Promise(() => {}),
  createPortalSession: vi.fn(),
}))
vi.mock('@/features/notifications/api/notifications-api', () => ({
  getNotificationPreferences: () => new Promise(() => {}),
  updateNotificationPreferences: vi.fn(),
}))
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
const toasts = vi.hoisted(() => ({ error: vi.fn(), success: vi.fn() }))
vi.mock('sonner', () => ({ toast: toasts }))

const shown: CurrentUser = {
  id: 7, email: 'shown@example.test', full_name: null, is_pro: false, is_beta: false, is_admin: false, email_verified: true,
}
const OTHER_ACCOUNT_DETAIL =
  'This browser is logged in to a different account from the one this page shows, so the password was not changed.'

function renderForm(account: CurrentUser | null = shown) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  if (account) client.setQueryData(queryKeys.currentUser(), account)
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  render(<QueryClientProvider client={client}><ChangePasswordForm /></QueryClientProvider>)
  return { client, invalidate }
}

async function fillAndSubmit(hasPassword: boolean) {
  if (hasPassword) fireEvent.change(await screen.findByLabelText('Current password'), { target: { value: 'old-password-1' } })
  fireEvent.change(await screen.findByLabelText('New password'), { target: { value: 'new-password-12' } })
  fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'new-password-12' } })
  fireEvent.click(screen.getByRole('button', { name: hasPassword ? 'Update password' : 'Set password' }))
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ChangePasswordForm names the account its tab shows (E29 (6))', () => {
  it.each([
    ['with a password', true, 'old-password-1'],
    ['without one', false, null],
  ] as const)('posts the shown account with the change, for an account %s', async (_label, hasPassword, current) => {
    api.getConnections.mockResolvedValue({ has_password: hasPassword, providers: [] })
    api.changePassword.mockResolvedValue({ message: 'Password updated.' })
    renderForm()
    await fillAndSubmit(hasPassword)
    await waitFor(() => expect(api.changePassword).toHaveBeenCalledWith(current, 'new-password-12', shown.id))
    expect(await screen.findByText('Password saved')).toBeInTheDocument()
  })

  it("on the route's refusal for another account, keeps nothing typed, says why in a toast and reads /me again", async () => {
    api.getConnections.mockResolvedValue({ has_password: true, providers: [] })
    api.changePassword.mockRejectedValue(new ApiError(409, OTHER_ACCOUNT_DETAIL))
    const { invalidate } = renderForm()
    await fillAndSubmit(true)

    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(
      PASSWORD_NOT_CHANGED_OTHER_ACCOUNT_MESSAGE, { duration: STEP_TOAST_DURATION_MS },
    ))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.currentUser() })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.authConnections() })
    for (const label of ['Current password', 'New password', 'Confirm new password']) {
      expect(screen.getByLabelText(label)).toHaveValue('')
    }
    // The toast gave the step; no error line repeats it under the form the read of /me puts in its place.
    expect(screen.queryByText(OTHER_ACCOUNT_DETAIL)).not.toBeInTheDocument()
    expect(screen.queryByText('Password saved')).not.toBeInTheDocument()
  })

  it('posts nothing while the identity read holds no account to name, and says why', async () => {
    // The settings page still renders its sections when its first /me read failed: an unnamed change would change
    // whichever account the browser holds.
    api.getConnections.mockResolvedValue({ has_password: false, providers: [] })
    renderForm(null)
    await fillAndSubmit(false)

    expect(await screen.findByText(ACCOUNT_UNCONFIRMED_MESSAGE)).toBeInTheDocument()
    expect(api.changePassword).not.toHaveBeenCalled()
  })

  it('shows any other refusal on its line, as before, and keeps what was typed', async () => {
    api.getConnections.mockResolvedValue({ has_password: true, providers: [] })
    api.changePassword.mockRejectedValue(Object.assign(new ApiError(400, 'Current password is incorrect.'), {
      backendDetail: 'Current password is incorrect.',
    }))
    renderForm()
    await fillAndSubmit(true)

    expect(await screen.findByText('Current password is incorrect.')).toBeInTheDocument()
    expect(toasts.error).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Current password')).toHaveValue('old-password-1')
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
  })
})

describe("the settings page's password form never posts what was typed for another account (E29 (6))", () => {
  const other: CurrentUser = { ...shown, id: 8, email: 'other@example.test' }
  const FIELDS = ['Current password', 'New password', 'Confirm new password']

  it("empties every field when a read of /me moves the tab to another account, and posts only what is typed after, naming that account", async () => {
    api.getConnections.mockResolvedValue({ has_password: true, providers: [] })
    api.getCurrentUserSafe.mockReturnValue(new Promise(() => {})) // the page's own /me read stays out: the cache speaks
    api.changePassword.mockResolvedValue({ message: 'Password updated.' })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    client.setQueryData(queryKeys.currentUser(), shown)
    render(<QueryClientProvider client={client}><SettingsPage /></QueryClientProvider>)

    for (const label of FIELDS) fireEvent.change(await screen.findByLabelText(label), { target: { value: `typed for ${shown.id}` } })
    for (const label of FIELDS) expect(screen.getByLabelText(label)).toHaveValue(`typed for ${shown.id}`)

    // Another tab signs the browser in to another account; this tab's read of /me replaces the cached account.
    await act(async () => { client.setQueryData(queryKeys.currentUser(), other) })

    // React Query tells the page on its own tick, so the remount lands after the cache write.
    await waitFor(() => { for (const label of FIELDS) expect(screen.getByLabelText(label)).toHaveValue('') })
    fireEvent.change(screen.getByLabelText('Current password'), { target: { value: 'others-password-1' } })
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'others-new-password-12' } })
    fireEvent.change(screen.getByLabelText('Confirm new password'), { target: { value: 'others-new-password-12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))

    await waitFor(() => expect(api.changePassword).toHaveBeenCalledTimes(1))
    expect(api.changePassword).toHaveBeenCalledWith('others-password-1', 'others-new-password-12', other.id)
    expect(await screen.findByText('Password saved')).toBeInTheDocument()
  })
})
