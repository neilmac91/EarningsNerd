import React from 'react'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * What the auth-adjacent pages say (docs/brand/07-voice.md; 2026-10 audit, UA-29 to UA-47). Each claim
 * is the one the code enforces: verifying confirms the address (reading and a password sign-in never
 * waited on it; checkout is the one action that refuses an unverified email, with a 403, and a Google or
 * Apple sign-in links to an existing account only once both sides have verified the email), the
 * password rule is the server's, and a failure says what the reader can do. Where a sentence carries a
 * server value or names a server gate, the case reads the backend source for it.
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
import EmailVerificationModal from '@/features/auth/components/EmailVerificationModal'
import { getCurrentUserSafe, resendVerification, verifyEmail } from '@/features/auth/api/auth-api'
import { ApiError, EMAIL_VERIFICATION_REQUIRED_EVENT } from '@/lib/api/client'
import { VERIFY_EMAIL_REASONS, VERIFY_LINK_FALLBACK, VERIFY_RETRY_FALLBACK } from '@/features/auth/lib/verifyEmailFailure'
import { readdirSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PASSWORD_MIN_LENGTH, PASSWORD_RULE } from '@/lib/passwordRules'

function withQueryClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const BACKEND = path.resolve(FRONTEND, '../backend')
const backend = (rel: string) => readFileSync(path.join(BACKEND, rel), 'utf8')

/** The link's lifetime as the server sets it (`issue_email_verification_token`), so check-email's sentence follows it. */
function verifyLinkHours(): number {
  const service = backend('app/services/auth_account_service.py')
  const hours = service.match(/^EMAIL_VERIFY_EXPIRY_HOURS\s*=\s*(\d+)\s*$/m)?.[1]
  if (!hours || !service.includes('timedelta(hours=EMAIL_VERIFY_EXPIRY_HOURS)')) {
    throw new Error('the verification link expiry is no longer EMAIL_VERIFY_EXPIRY_HOURS in backend/app/services/auth_account_service.py')
  }
  return Number(hours)
}

/**
 * Every backend line that says "verify your email" (the words lib/api/client.ts reads off a 403 to open
 * the verification dialog), as `file::function`. The mail bodies (`app/services/email_service.py`) are
 * copy sent to an inbox and are left out: that service cannot raise a 403, since
 * `backend/tests/unit/test_services_http_free_allowlist.py` keeps it free of fastapi.
 */
function verifyEmailRefusals(): string[] {
  const files = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) return entry.name === '__pycache__' ? [] : files(full)
      return entry.name.endsWith('.py') ? [full] : []
    })
  return files(path.join(BACKEND, 'app'))
    .map((file) => path.relative(BACKEND, file).split(path.sep).join('/'))
    .filter((rel) => rel !== 'app/services/email_service.py')
    .flatMap((rel) => {
      const lines = backend(rel).split('\n')
      return lines.flatMap((line, index) => {
        if (!/verify your email/i.test(line)) return []
        const def = lines.slice(0, index).reverse().find((l) => /^\s*(?:async\s+)?def\s+\w+/.test(l))
        return [`${rel}::${def?.match(/def\s+(\w+)/)?.[1] ?? '<module>'}`]
      })
    })
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
    expect(
      screen.getByText(`Open the newest one to verify your email address. Each link expires ${verifyLinkHours()} hours after we send it.`),
    ).toBeInTheDocument()
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
    // /check-email without an address offers no Resend, so the link promises a new link, not a send.
    expect(screen.getByRole('link', { name: 'Get a new link' })).toHaveAttribute('href', '/check-email')
    expect(screen.queryByText(/resend/i)).toBeNull()
  })

  it("lists exactly the endpoint's reasons (backend/app/routers/auth.py::verify_email)", () => {
    const router = backend('app/routers/auth.py')
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
  // no password, so the sentence never sends the reader to one. Verifying links nothing by itself: the
  // provider links on a later sign-in through it (resolve_google_user, resolve_apple_user), so the
  // sentence ends on that next step.
  it.each([
    ['google_account_conflict', 'Google'],
    ['apple_account_conflict', 'Apple'],
  ])('%s names the provider tried, the way back, and the sign-in that links it', (code, provider) => {
    useSearchParams.mockReturnValue(new URLSearchParams(`error=${code}`))
    withQueryClient(<LoginPage />)
    expect(
      screen.getByText(
        `This email already has an EarningsNerd account, and the two could not be linked. Sign in the way you created that account and verify your email. Once the email is verified on EarningsNerd and ${provider}, try ${provider} again.`,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/password instead/i)).toBeNull()
    expect(screen.queryByText(/will link/i)).toBeNull()
  })
})

describe('verification banner and dialog', () => {
  it("the 403 that opens the dialog is checkout's alone (backend/app/routers/subscriptions.py)", () => {
    // The client opens the dialog on a 403 whose detail reads "verify your email"; both lines below name
    // subscribing because checkout is the only route that answers an unverified email that way.
    expect(readFileSync(path.join(FRONTEND, 'lib/api/client.ts'), 'utf8')).toContain('/verify your email/i.test(backendDetail)')
    expect(verifyEmailRefusals(), 'a new "verify your email" refusal: name what it gates in the banner and the dialog, then list it here').toEqual([
      'app/routers/subscriptions.py::create_checkout_session',
    ])
  })

  it('the banner says verifying unlocks subscribing: checkout is the one feature gated on it (linking Google or Apple also waits on it)', async () => {
    sessionStorage.clear()
    vi.mocked(getCurrentUserSafe).mockResolvedValue({ id: 1, email: 'a@example.com', email_verified: false } as never)
    withQueryClient(<VerificationBanner />)
    expect(await screen.findByText('Verify your email to subscribe.')).toBeInTheDocument()
    expect(screen.queryByText(/generate/i)).toBeNull()
  })

  it('the dialog checkout opens names subscribing alone, and says where links go, not that one was sent', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue({ id: 1, email: 'a@example.com', email_verified: false } as never)
    withQueryClient(<EmailVerificationModal />)
    act(() => {
      window.dispatchEvent(new Event(EMAIL_VERIFICATION_REQUIRED_EVENT))
    })
    const address = await screen.findByText('a@example.com')
    // The same words as /check-email's: opening the dialog sends nothing, Resend does.
    expect(address.closest('p')?.textContent).toBe('Subscribing requires a verified email. We send verification links to a@example.com.')
    expect(screen.queryByText(/generat/i)).toBeNull()
    expect(screen.queryByText(/we sent/i)).toBeNull()
    expect(resendVerification).not.toHaveBeenCalled()
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
