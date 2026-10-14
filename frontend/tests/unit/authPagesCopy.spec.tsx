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
import { VERIFY_EMAIL_REASONS, VERIFY_LINK_FALLBACK, VERIFY_RETRY_FALLBACK } from '@/features/auth/lib/verifyEmailFailure'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
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
  it('says what the link does, not that it activates the account, and never that one was just sent', () => {
    // The account menu's "Verify your email" lands here with the address and sends nothing.
    useSearchParams.mockReturnValue(new URLSearchParams('email=new@example.com'))
    render(<CheckEmailPage />)
    expect(screen.getByText('We send verification links to')).toBeInTheDocument()
    expect(screen.getByText('new@example.com')).toBeInTheDocument()
    expect(screen.getByText('Open the newest one to verify your email address. Each link expires 24 hours after we send it.')).toBeInTheDocument()
    expect(screen.queryByText(/activate/i)).toBeNull()
    expect(screen.queryByText(/we sent a verification link/i)).toBeNull()
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

  it("lists exactly the endpoint's reasons (backend/app/routers/auth.py::verify_email)", () => {
    const router = readFileSync(
      path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../backend/app/routers/auth.py'),
      'utf8',
    )
    const body = router.match(/^async def verify_email\b[\s\S]*?(?=^@|^(?:async )?def )/m)?.[0] ?? ''
    expect([...body.matchAll(/detail="([^"]+)"/g)].map((m) => m[1]).sort()).toEqual([...VERIFY_EMAIL_REASONS].sort())
  })

  // What lib/api/client.ts's interceptor actually throws when the answer carries no reason of the server's.
  it.each([
    ['a bodiless 400 (axios)', new ApiError(400, 'Request failed with status code 400'), VERIFY_LINK_FALLBACK],
    ['a lost connection', new ApiError(0, 'Unable to connect to the server. Please ensure the backend API is running on http://localhost:8000'), VERIFY_RETRY_FALLBACK],
    ['a timeout', new ApiError(0, 'The request timed out. Please try again.'), VERIFY_RETRY_FALLBACK],
    ['a server error', new ApiError(500, 'A server error occurred. Please try again later.'), VERIFY_RETRY_FALLBACK],
    ["the backend's production 500", new ApiError(500, 'An unexpected error occurred'), VERIFY_RETRY_FALLBACK],
  ])('on %s, says its own sentence, never the client text', async (_case, rejection, expected) => {
    useSearchParams.mockReturnValue(new URLSearchParams('token=t'))
    vi.mocked(verifyEmail).mockRejectedValue(rejection)
    withQueryClient(<VerifyEmailPage />)
    expect(await screen.findByText(expected)).toBeInTheDocument()
    expect(screen.queryByText(rejection.detail)).toBeNull()
  })

  it('confirms the address and says where it goes next', async () => {
    useSearchParams.mockReturnValue(new URLSearchParams('token=t'))
    vi.mocked(verifyEmail).mockResolvedValue({})
    withQueryClient(<VerifyEmailPage />)
    expect(await screen.findByText('Your email address is confirmed. Taking you to the home page…')).toBeInTheDocument()
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
  // One sentence for the three paths behind both codes (backend/app/services/oauth_account_service.py): an
  // unverified email on the account or at the provider, and a lost first-sign-in race. The account may have
  // no password, so the sentence never sends the reader to one.
  it.each([
    ['google_account_conflict', 'Google'],
    ['apple_account_conflict', 'Apple'],
  ])('%s names the provider tried and the way back', (code, provider) => {
    useSearchParams.mockReturnValue(new URLSearchParams(`error=${code}`))
    withQueryClient(<LoginPage />)
    expect(
      screen.getByText(
        `This email already has an EarningsNerd account, and the two could not be linked. Sign in the way you created that account, verify your email, and ${provider} will link once both sides have verified it.`,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/password instead/i)).toBeNull()
  })
})

describe('verification banner', () => {
  it('says verifying unlocks subscribing, the one action the server gates on it', async () => {
    sessionStorage.clear()
    vi.mocked(getCurrentUserSafe).mockResolvedValue({ id: 1, email: 'a@example.com', email_verified: false } as never)
    withQueryClient(<VerificationBanner />)
    expect(await screen.findByText('Verify your email to subscribe.')).toBeInTheDocument()
    expect(screen.queryByText(/generate/i)).toBeNull()
  })

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
