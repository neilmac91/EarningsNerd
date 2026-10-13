import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * What the auth-adjacent pages say (docs/brand/07-voice.md; 2026-10 audit, UA-29 to UA-47). Each claim
 * is the one the code enforces: verifying confirms the address (signing in and reading never waited on
 * it), the password rule is the server's, and a failure says what the reader can do.
 */
const { useSearchParams, push, refresh } = vi.hoisted(() => ({
  useSearchParams: vi.fn<() => URLSearchParams>(),
  push: vi.fn(),
  refresh: vi.fn(),
}))
vi.mock('next/navigation', () => ({ useSearchParams, useRouter: () => ({ push, refresh }), usePathname: () => '/dashboard' }))
vi.mock('@/features/auth/api/auth-api', () => ({
  verifyEmail: vi.fn(),
  resendVerification: vi.fn(),
  resetPassword: vi.fn(),
  getCurrentUserSafe: vi.fn(),
  login: vi.fn(),
}))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('@/features/auth/components/TurnstileWidget', () => ({ default: () => null }))

import CheckEmailPage from '@/app/check-email/page'
import VerifyEmailPage from '@/app/verify-email/page'
import ResetPasswordPage from '@/app/reset-password/page'
import LoginPage from '@/app/login/page'
import VerificationBanner from '@/features/auth/components/VerificationBanner'
import { getCurrentUserSafe, resendVerification, verifyEmail } from '@/features/auth/api/auth-api'
import { ApiError } from '@/lib/api/client'
import { PASSWORD_MIN_LENGTH, PASSWORD_RULE } from '@/lib/passwordRules'

function withQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  vi.mocked(verifyEmail).mockReset()
  vi.mocked(resendVerification).mockReset()
  push.mockReset()
})

describe('check email', () => {
  it('says what the link does, not that it activates the account', () => {
    useSearchParams.mockReturnValue(new URLSearchParams('email=new@example.com'))
    render(<CheckEmailPage />)
    expect(screen.getByText('new@example.com')).toBeInTheDocument()
    expect(screen.getByText('Open the link to verify your email address. It expires in 24 hours.')).toBeInTheDocument()
    expect(screen.queryByText(/activate/i)).toBeNull()
    expect(screen.getByRole('button', { name: 'Resend email' })).toBeInTheDocument()
  })
})

describe('verify email', () => {
  it('shows the server reason for a refused link', async () => {
    useSearchParams.mockReturnValue(new URLSearchParams('token=t'))
    vi.mocked(verifyEmail).mockRejectedValue(new ApiError(400, 'Verification link has expired. Request a new one.'))
    withQueryClient(<VerifyEmailPage />)
    expect(await screen.findByText('Verification link has expired. Request a new one.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Resend verification email' })).toHaveAttribute('href', '/check-email')
  })

  it('falls back to the likely reason when the failure carries none', async () => {
    useSearchParams.mockReturnValue(new URLSearchParams('token=t'))
    vi.mocked(verifyEmail).mockRejectedValue('offline')
    withQueryClient(<VerifyEmailPage />)
    expect(await screen.findByText('The link has expired, or a newer one replaced it.')).toBeInTheDocument()
  })

  it('confirms the address and says where it goes next', async () => {
    useSearchParams.mockReturnValue(new URLSearchParams('token=t'))
    vi.mocked(verifyEmail).mockResolvedValue({})
    withQueryClient(<VerifyEmailPage />)
    expect(await screen.findByText('Your email address is confirmed. Taking you to EarningsNerd…')).toBeInTheDocument()
    expect(screen.queryByText(/account is active/i)).toBeNull()
  })
})

describe('reset password', () => {
  it("states the server's rule from the shared constant", () => {
    useSearchParams.mockReturnValue(new URLSearchParams('token=t'))
    render(<ResetPasswordPage />)
    expect(screen.getByText(PASSWORD_RULE)).toBeInTheDocument()
    expect(screen.queryByText(/upper- and lowercase/i)).toBeNull()
    expect(screen.getByLabelText('New password')).toHaveAttribute('minLength', String(PASSWORD_MIN_LENGTH))
  })
})

describe('login: an OAuth account conflict', () => {
  it.each(['google_account_conflict', 'apple_account_conflict'])('%s says what happened and what to do', (code) => {
    useSearchParams.mockReturnValue(new URLSearchParams(`error=${code}`))
    withQueryClient(<LoginPage />)
    expect(
      screen.getByText(
        "This email already has an EarningsNerd account we couldn't link. Sign in with your email and password instead.",
      ),
    ).toBeInTheDocument()
  })
})

describe('verification banner', () => {
  it('says a failed resend failed, and when to try again', async () => {
    sessionStorage.clear()
    vi.mocked(getCurrentUserSafe).mockResolvedValue({ id: 1, email: 'a@example.com', email_verified: false } as never)
    vi.mocked(resendVerification).mockRejectedValue(new ApiError(503, 'Service temporarily unavailable.'))
    const user = userEvent.setup()
    withQueryClient(<VerificationBanner />)
    await user.click(await screen.findByRole('button', { name: 'Resend link' }))
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent("Couldn't send a new link. Try again in a few minutes."),
    )
  })
})
