import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import RegisterForm from '@/features/auth/components/RegisterForm'

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

const socialLink = (provider: 'Google' | 'Apple') =>
  screen.queryByRole('link', { name: `Sign up with ${provider}` })

describe('RegisterForm social sign-up follows the invite gate', () => {
  beforeEach(() => {
    Array.from(searchParams.keys()).forEach((key) => searchParams.delete(key))
    window.history.replaceState({}, '', '/register')
  })

  it('offers no social sign-up to an uninvited visitor in invite-only mode', () => {
    render(<RegisterForm inviteOnly />)
    expect(socialLink('Google')).toBeNull()
    expect(socialLink('Apple')).toBeNull()
    expect(screen.getByRole('link', { name: 'Request an invite' })).toHaveAttribute('href', '/waitlist')
    expect(screen.getByRole('button', { name: /sign up with email/i })).toBeInTheDocument()
  })

  it('offers plain social sign-up in public mode', () => {
    render(<RegisterForm inviteOnly={false} />)
    expect(socialLink('Google')).toHaveAttribute('href', '/api/auth/google')
    expect(socialLink('Apple')).toHaveAttribute('href', '/api/auth/apple')
    expect(screen.queryByRole('link', { name: 'Request an invite' })).toBeNull()
  })

  it('starts an invited social sign-up with the invite in the request body, never in a URL', () => {
    const invite = 'tok en+/=1'
    searchParams.set('invite', invite)
    render(<RegisterForm inviteOnly />)
    // No link carries the token: the controls are buttons that POST it.
    expect(socialLink('Google')).toBeNull()
    expect(socialLink('Apple')).toBeNull()
    for (const anchor of Array.from(document.querySelectorAll('a'))) {
      expect(anchor.getAttribute('href') ?? '').not.toMatch(/invite/)
    }
    fireEvent.click(screen.getByRole('button', { name: 'Sign up with Google' }))
    expect(startOAuthWithInvite).toHaveBeenCalledWith('google', invite)
    fireEvent.click(screen.getByRole('button', { name: 'Sign up with Apple' }))
    expect(startOAuthWithInvite).toHaveBeenCalledWith('apple', invite)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Request an invite' })).toBeNull()
  })

  it('keeps the submit focusable while the request is in flight (aria-disabled, never native disabled)', async () => {
    render(<RegisterForm inviteOnly={false} />)
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
