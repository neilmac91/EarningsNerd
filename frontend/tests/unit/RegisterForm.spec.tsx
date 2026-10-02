import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import RegisterForm from '@/features/auth/components/RegisterForm'

/**
 * The signup page offers social sign-up only where the backend would accept it: never to an
 * uninvited visitor in invite-only mode (the callback refuses with error=invite_required), and with
 * the invite threaded onto the backend start URLs for an invited one (the callback redeems it).
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

  it('threads an invite onto the social start URLs and opens the email form', () => {
    const invite = 'tok en+/=1'
    searchParams.set('invite', invite)
    render(<RegisterForm inviteOnly />)
    const query = `?invite=${encodeURIComponent(invite)}`
    expect(socialLink('Google')).toHaveAttribute('href', `/api/auth/google${query}`)
    expect(socialLink('Apple')).toHaveAttribute('href', `/api/auth/apple${query}`)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Request an invite' })).toBeNull()
  })
})
