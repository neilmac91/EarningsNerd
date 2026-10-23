import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import RegisterForm from '@/features/auth/components/RegisterForm'
import RegisterPage from '@/app/register/page'
import type { SignupConfig } from '@/lib/serverApi'
import { PASSWORD_MIN_LENGTH, PASSWORD_RULE } from '@/lib/passwordRules'

/**
 * The signup page offers social sign-up only where the backend would accept it: never to an
 * uninvited visitor in invite-only mode (the callback refuses with error=invite_required), and for an
 * invited one through the POST start that carries the invite in its body (the callback redeems it):
 * the raw token never appears in a URL.
 */
const searchParams = new URLSearchParams()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => searchParams,
}))
vi.mock('@/lib/analytics', () => ({ default: { signupStarted: vi.fn(), signupSubmitted: vi.fn() } }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_ENABLED: false,
  ENABLE_APPLE_SIGNIN: true,
}))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('@/features/auth/components/TurnstileWidget', () => ({ default: () => null }))
// A register call that never settles, so the form can be observed while its request is in flight.
const { startOAuthWithInvite } = vi.hoisted(() => ({ startOAuthWithInvite: vi.fn(() => new Promise<string>(() => {})) }))
vi.mock('@/features/auth/api/auth-api', () => ({
  register: vi.fn(() => new Promise(() => {})),
  startOAuthWithInvite,
}))

// The register page's one read of the server's config: what the promo and invite gate say comes from here.
const { fetchSignupConfig } = vi.hoisted(() => ({ fetchSignupConfig: vi.fn<() => Promise<SignupConfig | null>>() }))
vi.mock('@/lib/serverApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/serverApi')>()),
  fetchSignupConfig,
}))

const socialLink = (provider: 'Google' | 'Apple') =>
  screen.queryByRole('link', { name: `Continue with ${provider}` })

describe('RegisterForm social sign-up follows the invite gate', () => {
  beforeEach(() => {
    Array.from(searchParams.keys()).forEach((key) => searchParams.delete(key))
    window.history.replaceState({}, '', '/register')
  })

  it('offers no social sign-up to an uninvited visitor in invite-only mode', () => {
    render(<RegisterForm inviteOnly betaPromoActive={false} />)
    expect(socialLink('Google')).toBeNull()
    expect(socialLink('Apple')).toBeNull()
    expect(screen.getByRole('link', { name: 'Request an invite' })).toHaveAttribute('href', '/waitlist')
    expect(screen.getByRole('button', { name: /sign up with email/i })).toBeInTheDocument()
  })

  it('offers plain social sign-up in public mode', () => {
    render(<RegisterForm inviteOnly={false} betaPromoActive={false} />)
    expect(socialLink('Google')).toHaveAttribute('href', '/api/auth/google')
    expect(socialLink('Apple')).toHaveAttribute('href', '/api/auth/apple')
    expect(screen.queryByRole('link', { name: 'Request an invite' })).toBeNull()
  })

  it('starts an invited social sign-up with the invite in the request body, never in a URL', () => {
    const invite = 'tok en+/=1'
    searchParams.set('invite', invite)
    render(<RegisterForm inviteOnly betaPromoActive={false} />)
    // No link carries the token: the controls are buttons that POST it.
    expect(socialLink('Google')).toBeNull()
    expect(socialLink('Apple')).toBeNull()
    for (const anchor of Array.from(document.querySelectorAll('a'))) {
      expect(anchor.getAttribute('href') ?? '').not.toMatch(/invite/)
    }
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
    expect(startOAuthWithInvite).toHaveBeenCalledWith('google', invite)
    fireEvent.click(screen.getByRole('button', { name: 'Continue with Apple' }))
    expect(startOAuthWithInvite).toHaveBeenCalledWith('apple', invite)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Request an invite' })).toBeNull()
  })

  it('a refused invited start names, under its own button, the provider it could not continue with', async () => {
    searchParams.set('invite', 'tok')
    render(<RegisterForm inviteOnly betaPromoActive={false} />)
    for (const provider of ['Google', 'Apple'] as const) {
      startOAuthWithInvite.mockRejectedValueOnce(new Error('start refused'))
      const button = screen.getByRole('button', { name: `Continue with ${provider}` })
      fireEvent.click(button)
      const status = await within(button.parentElement as HTMLElement).findByRole('status')
      expect(status).toHaveTextContent(`Couldn't continue with ${provider}. Please try again.`)
    }
  })

  it('keeps the submit focusable while the request is in flight (aria-disabled, never native disabled)', async () => {
    render(<RegisterForm inviteOnly={false} betaPromoActive={false} />)
    fireEvent.click(screen.getByRole('button', { name: /sign up with email/i }))
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'person@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-long-enough-passphrase' } })
    const submit = screen.getByRole('button', { name: 'Create account' })
    expect(submit).not.toBeDisabled()

    fireEvent.submit(submit.closest('form') as HTMLFormElement)

    await waitFor(() => expect(submit).toHaveAttribute('aria-busy', 'true'))
    expect(submit).toHaveAttribute('aria-disabled', 'true')
    expect(submit).not.toBeDisabled()
    expect(submit).toHaveTextContent('Creating account…')
  })
})

describe('RegisterForm promises Pro only while the beta promo is configured', () => {
  const PRO_SUBHEAD = 'Finish setting up to get full Pro. No credit card required.'
  const PRO_CARD = 'Your invite includes full Pro access. Create your account below.'
  const INVITE_SUBHEAD = 'Your invite opens an account during the private beta.'

  beforeEach(() => {
    Array.from(searchParams.keys()).forEach((key) => searchParams.delete(key))
    window.history.replaceState({}, '', '/register')
  })

  it('an invited visitor with the promo off is told what the invite opens, and no Pro', () => {
    searchParams.set('invite', 'tok')
    render(<RegisterForm inviteOnly betaPromoActive={false} />)
    expect(screen.getByText(INVITE_SUBHEAD)).toBeInTheDocument()
    expect(screen.getByText('Create your account below.')).toBeInTheDocument()
    expect(screen.queryByText(/\bPro\b/)).toBeNull()
  })

  it('an invited visitor with the promo on reads the Pro sentences', () => {
    searchParams.set('invite', 'tok')
    render(<RegisterForm inviteOnly betaPromoActive />)
    expect(screen.getByText(PRO_SUBHEAD)).toBeInTheDocument()
    expect(screen.getByText(PRO_CARD)).toBeInTheDocument()
    expect(screen.queryByText(INVITE_SUBHEAD)).toBeNull()
  })

  it('an uninvited visitor under the invite gate gets no subhead: the private-beta notice says it', () => {
    render(<RegisterForm inviteOnly betaPromoActive />)
    const heading = screen.getByRole('heading', { level: 1, name: 'Create your account' })
    expect(heading.nextElementSibling?.tagName).not.toBe('P')
    expect(screen.queryByText(/free AI summaries a month/)).toBeNull()
    expect(screen.queryByText(PRO_SUBHEAD)).toBeNull()
    expect(screen.getByText('EarningsNerd is in private beta')).toBeInTheDocument()
  })

  it('open registration keeps the free-plan subhead', () => {
    render(<RegisterForm inviteOnly={false} betaPromoActive={false} />)
    expect(screen.getByText(/free AI summaries a month\. No credit card required\./)).toBeInTheDocument()
  })

  describe('the register page passes the server config through', () => {
    beforeEach(() => searchParams.set('invite', 'tok'))

    it('invite-only with the promo off: no Pro', async () => {
      fetchSignupConfig.mockResolvedValue({ mode: 'invite_only', beta_promo_enabled: false })
      render(await RegisterPage())
      expect(screen.getByText(INVITE_SUBHEAD)).toBeInTheDocument()
      expect(screen.queryByText(/\bPro\b/)).toBeNull()
    })

    it('invite-only with the promo on: the Pro sentences', async () => {
      fetchSignupConfig.mockResolvedValue({ mode: 'invite_only', beta_promo_enabled: true })
      render(await RegisterPage())
      expect(screen.getByText(PRO_SUBHEAD)).toBeInTheDocument()
    })

    it('an unreachable backend fails closed: the invite gate, no Pro', async () => {
      fetchSignupConfig.mockResolvedValue(null)
      render(await RegisterPage())
      expect(screen.getByText(INVITE_SUBHEAD)).toBeInTheDocument()
      expect(screen.queryByText(/\bPro\b/)).toBeNull()
    })

    it('open registration with the promo configured: the free-plan line, no Pro, invited or not', async () => {
      // /api/auth/registration reports the promo whatever the mode (backend/app/routers/auth.py), and
      // the promo applies only under the invite gate, so the page reads it through betaPricingActive.
      fetchSignupConfig.mockResolvedValue({ mode: 'public', beta_promo_enabled: true })
      render(await RegisterPage())
      expect(screen.getByText(/free AI summaries a month\. No credit card required\./)).toBeInTheDocument()
      expect(screen.queryByText(/\bPro\b/)).toBeNull()
    })
  })
})

describe('RegisterForm password field: the rule and the meter', () => {
  beforeEach(() => Array.from(searchParams.keys()).forEach((key) => searchParams.delete(key)))

  it("states the server's rule from the shared constant, with the field's minimum", () => {
    // The hint is the one sentence passwordRulesLockstep holds to the server, so a hand-typed hint
    // fails here whatever its wording.
    render(<RegisterForm inviteOnly={false} betaPromoActive={false} />)
    fireEvent.click(screen.getByRole('button', { name: /sign up with email/i }))
    expect(screen.getByText(PASSWORD_RULE)).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAttribute('minLength', String(PASSWORD_MIN_LENGTH))
  })

  it('reads "Weak" for the first password past the floor, and "Too short" one character under it', () => {
    render(<RegisterForm inviteOnly={false} betaPromoActive={false} />)
    fireEvent.click(screen.getByRole('button', { name: /sign up with email/i }))
    const password = screen.getByLabelText('Password')
    fireEvent.change(password, { target: { value: 'a'.repeat(PASSWORD_MIN_LENGTH - 1) } })
    expect(screen.getByText('Too short')).toBeInTheDocument()
    fireEvent.change(password, { target: { value: 'a'.repeat(PASSWORD_MIN_LENGTH) } })
    expect(screen.getByText('Weak')).toBeInTheDocument()
  })
})
