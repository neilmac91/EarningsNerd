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
// The login page's registration read, answered here: no answer (the default) fails closed to the invite.
const { getRegistrationConfig } = vi.hoisted(() => ({
  getRegistrationConfig: vi.fn<() => Promise<{ mode: 'public' | 'invite_only'; beta_promo_enabled: boolean } | null>>(async () => null),
}))
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig }))

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
import { pythonTokens, type Token } from './pythonTokens'

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

/** Every `.py` file under backend/app, relative to backend/. */
function backendFiles(): string[] {
  const files = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const full = path.join(dir, entry.name)
      if (entry.isDirectory()) return entry.name === '__pycache__' ? [] : files(full)
      return entry.name.endsWith('.py') ? [full] : []
    })
  return files(path.join(BACKEND, 'app')).map((file) => path.relative(BACKEND, file).split(path.sep).join('/'))
}

/**
 * Each match of `match` (a global pattern) in `source`, as `file::function`: the nearest `def` at or above
 * the line the match starts on. The whole file is read, so a match may run across lines.
 */
function sites(rel: string, source: string, match: RegExp): string[] {
  if (!match.global) throw new Error('sites() reads every match: give the pattern the g flag')
  const lines = source.split('\n')
  return [...source.matchAll(match)].map((found) => {
    const line = source.slice(0, found.index).split('\n').length - 1
    const def = lines.slice(0, line + 1).reverse().find((l) => /^\s*(?:async\s+)?def\s+\w+/.test(l))
    return `${rel}::${def?.match(/def\s+(\w+)/)?.[1] ?? '<module>'}`
  })
}

/**
 * Every backend line that says "verify your email" (the words lib/api/client.ts reads off a 403 to open
 * the verification dialog), as `file::function`. The mail bodies (`app/services/email_service.py`) are
 * copy sent to an inbox and are left out: that service cannot raise a 403, since
 * `backend/tests/unit/test_services_http_free_allowlist.py` keeps it free of fastapi.
 */
function verifyEmailRefusals(): string[] {
  return backendFiles()
    .filter((rel) => rel !== 'app/services/email_service.py')
    .flatMap((rel) => sites(rel, backend(rel), /verify your email/gi))
}

/**
 * Each read of an account's verification state in Python `source`, as `file::function` (the nearest `def` at or
 * above the line it starts on), read on the source's tokens (`pythonTokens.ts`), so a comment, a docstring or
 * any other string that names the field is never a read:
 * - an attribute `.email_verified` that is not assigned (`==` and `!=` are reads);
 * - a `getattr` whose second argument is the literal "email_verified";
 * - a `filter_by` keyword of that name.
 * Tokens carry no line breaks, so a read split across lines or continued with a backslash is the same read. A
 * provider's claim (`claims["email_verified"]`), a parameter and a constructor keyword of that name are not the
 * account's state. An f-string is one string token, so a read inside its braces is not seen: no gate lives there.
 */
function emailVerifiedSites(rel: string, source: string): string[] {
  const lines = source.split('\n')
  const site = (line: number) => {
    const def = lines.slice(0, line).reverse().find((l) => /^\s*(?:async\s+)?def\s+\w+/.test(l))
    return `${rel}::${def?.match(/def\s+(\w+)/)?.[1] ?? '<module>'}`
  }
  const toks = pythonTokens(source).filter((t) => !(t.kind === 'op' && t.text === '\\'))
  const is = (t: Token | undefined, kind: Token['kind'], text: string) => t?.kind === kind && t.text === text
  const opens = (t: Token | undefined) => t?.kind === 'op' && '([{'.includes(t.text)
  const closes = (t: Token | undefined) => t?.kind === 'op' && ')]}'.includes(t.text)
  /** In the call whose `(` is at `k`, whether `found` holds at any token directly inside it. */
  const inCall = (k: number, found: (j: number) => boolean) => {
    for (let j = k + 1, depth = 1; j < toks.length && depth > 0; j++) {
      if (opens(toks[j])) depth++
      else if (closes(toks[j])) depth--
      else if (depth === 1 && found(j)) return true
    }
    return false
  }
  return toks.flatMap((t, k) => {
    if (is(t, 'name', 'email_verified') && is(toks[k - 1], 'op', '.')) {
      const assigned = is(toks[k + 1], 'op', '=') && !is(toks[k + 2], 'op', '=')
      return assigned ? [] : [site(t.line)]
    }
    if (is(t, 'name', 'getattr') && is(toks[k + 1], 'op', '(')) {
      let second = false
      inCall(k + 1, (j) => {
        if (!is(toks[j], 'op', ',')) return false
        second = is(toks[j + 1], 'str', 'email_verified')
        return true
      })
      return second ? [site(t.line)] : []
    }
    if (is(t, 'name', 'filter_by') && is(toks[k + 1], 'op', '(')) {
      const keyword = (j: number) => is(toks[j], 'name', 'email_verified') && is(toks[j + 1], 'op', '=') && !is(toks[j + 2], 'op', '=')
      return inCall(k + 1, keyword) ? [site(t.line)] : []
    }
    return []
  })
}

/**
 * Every backend read of an account's `email_verified`, with what it does. The banner and the dialog name
 * subscribing alone because checkout is the one read that gates a feature. The "verify your email" scan
 * above finds a gate by its words; this list finds it by the field, so a gate worded any other way
 * ("Confirm your address first.") fails here until the banner and the dialog name what it gates.
 */
const EMAIL_VERIFIED_READS: [site: string, what: string][] = [
  ['app/routers/subscriptions.py::create_checkout_session', 'the gate: its 403 says "verify your email", and the banner and the dialog name subscribing'],
  ['app/services/oauth_account_service.py::resolve_google_user', "links Google to an existing account only once both sides have verified the email (the login page's conflict sentence)"],
  ['app/services/oauth_account_service.py::resolve_apple_user', 'the same for Apple'],
  ['app/routers/auth.py::resend_verification', 'sends no link to a verified address; the answer reads the same either way'],
  ['app/routers/auth.py::get_current_user_info', 'reports the state (/me), which shows or hides the banner'],
  ['app/services/admin_account_service.py::_provision_account', "reports a new account's state to the admin who created it"],
]

function emailVerifiedReads(): string[] {
  return backendFiles().flatMap((rel) => emailVerifiedSites(rel, backend(rel)))
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
    // An address has no break opportunity: at 200% text a long one ran past the column to the screen's
    // edge, so its line may break inside it (overflow-wrap: break-word; the column's width is definite).
    expect(screen.getByText('new@example.com')).toHaveClass('break-words')
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
        `This email already has an EarningsNerd account, and the two could not be linked. Log in the way you created that account and verify your email. Once the email is verified on EarningsNerd and ${provider}, try ${provider} again.`,
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/password instead/i)).toBeNull()
    expect(screen.queryByText(/will link/i)).toBeNull()
  })
})

describe('login: the way in for a visitor without an account (D-046, F44)', () => {
  // The link under the form follows the one access decision (features/marketing/lib/access.ts), as RegisterForm's
  // notice and the header do: while registration is by invite, and until the registration payload answers or when
  // it cannot, it asks for an invite on /waitlist; open registration offers the free account on /register.
  it.each([
    ['no answer', 'Request an invite', '/waitlist', null],
    ['invite_only', 'Request an invite', '/waitlist', { mode: 'invite_only', beta_promo_enabled: false }],
    ['public', 'Create a free account', '/register', { mode: 'public', beta_promo_enabled: false }],
  ] as const)('under %s it reads "%s" and goes to %s', async (_mode, label, href, config) => {
    useSearchParams.mockReturnValue(new URLSearchParams())
    getRegistrationConfig.mockClear()
    getRegistrationConfig.mockResolvedValueOnce(config)
    withQueryClient(<LoginPage />)
    await waitFor(() => expect(getRegistrationConfig).toHaveBeenCalledTimes(1))
    expect(await screen.findByRole('link', { name: label })).toHaveAttribute('href', href)
    expect(screen.queryByRole('link', { name: /^sign up$/i })).toBeNull()
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

  it('every backend read of email_verified is listed with what it does, so a gate worded any way fails until the banner and the dialog name it', () => {
    expect(
      emailVerifiedReads().sort(),
      'a new read of email_verified: if it gates a feature, name that feature in the banner and the dialog; then list the read in EMAIL_VERIFIED_READS with what it does',
    ).toEqual(EMAIL_VERIFIED_READS.map(([site]) => site).sort())
  })

  it('the read scan sees a gate whatever its refusal says and however its lines break, and not a write, a provider claim or prose', () => {
    const planted = [
      'async def export_filing(current_user):',
      '    if not current_user.email_verified:',
      '        raise HTTPException(status_code=403, detail="Confirm your address first.")',
      'def unverified(db):',
      '    return db.query(User).filter(User.email_verified == False).all()',
      'def unverified_by_keyword(db):',
      '    return db.query(User).filter_by(email_verified=False).all()',
      'def flag(user):',
      '    return getattr(user, "email_verified", False)',
      'async def export_wrapped(current_user):',
      '    if not getattr(',
      '        current_user, "email_verified", False',
      '    ):',
      '        raise HTTPException(status_code=403, detail="Confirm your address first.")',
      'def continued(user):',
      '    return user.\\',
      '        email_verified',
      'def bracketed(user):',
      '    return (user.',
      '        email_verified)',
      'def unverified_wrapped(db):',
      '    return db.query(User).filter_by(',
      '        email_verified=False,',
      '    ).all()',
      'def writes(user, claims, email_verified):',
      '    user.email_verified = True',
      '    user.email_verified = (',
      '        email_verified',
      '    )',
      '    by_google = bool(claims.get("email_verified", False))',
      '    return User(email_verified=email_verified and by_google)',
      'def prose(current_user):',
      '    """Once refused a checkout unless current_user.email_verified held."""',
      '    # was: if not current_user.email_verified: raise HTTPException(status_code=403)',
      '    logger.info("current_user.email_verified was read here; getattr(user, \'email_verified\')")',
      '    return render(f"{current_user.email_verified}")',
    ].join('\n')
    // `prose` names the field in a docstring, a comment, a log string and an f-string, and reads it nowhere else:
    // the f-string's braces are the scan's one named gap (see emailVerifiedSites).
    expect(emailVerifiedSites('app/routers/probe.py', planted)).toEqual([
      'app/routers/probe.py::export_filing',
      'app/routers/probe.py::unverified',
      'app/routers/probe.py::unverified_by_keyword',
      'app/routers/probe.py::flag',
      'app/routers/probe.py::export_wrapped',
      'app/routers/probe.py::continued',
      'app/routers/probe.py::bracketed',
      'app/routers/probe.py::unverified_wrapped',
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
