import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { Mock } from 'vitest'
import LoginPage from '@/app/login/page'
import RegisterForm from '@/features/auth/components/RegisterForm'
import ContactForm from '@/features/contact/components/ContactForm'
import { ApiError } from '@/lib/api/client'

/**
 * E117: Cloudflare verifies a Turnstile token once (siteverify answers timeout-or-duplicate after), and the login,
 * register and contact routes check it right after the rate limit, so a submit that does not land may have spent its
 * token (a 429, which the limit answers first, spends none): once Turnstile is on, a retry after a wrong password
 * would answer 403. Each form renews the token after every submit it sends, as WaitlistForm does since #1386 (its
 * cases are in waitlistSuccessCard.spec.tsx): a new key mounts a new widget, and the submit waits for the new token
 * aria-disabled behind its handler's guard, never natively disabled. Chromium moves focus to <body> from a focused
 * button that turns disabled and never gives it back; jsdom moves no focus, so the cases hold the attributes as well
 * as the focus.
 */

// Turnstile, off unless a case turns it on. On, each mount of the widget yields a new token, as a new Cloudflare
// widget does: at once, or, while a case holds tokens, when the case issues it (issueToken).
const turnstile = vi.hoisted(() => ({ on: false, mounts: 0, hold: false, waiting: new Set<() => void>() }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  get TURNSTILE_ENABLED() {
    return turnstile.on
  },
}))
vi.mock('@/features/auth/components/TurnstileWidget', async () => {
  const { useEffect, useRef } = await import('react')
  return {
    // As the real widget is built: the latest onToken through a ref, and one effect for each mount, so only a new key
    // (a new widget) yields a new token, never a new callback.
    default: function TurnstileWidget({ onToken }: { onToken: (token: string) => void }) {
      const onTokenRef = useRef(onToken)
      useEffect(() => {
        onTokenRef.current = onToken
      })
      useEffect(() => {
        if (!turnstile.on) return
        const token = `token-${++turnstile.mounts}`
        if (!turnstile.hold) {
          onTokenRef.current(token)
          return
        }
        const issue = () => {
          turnstile.waiting.delete(issue)
          onTokenRef.current(token)
        }
        turnstile.waiting.add(issue)
        // An unmounted widget's token never comes (TurnstileWidget removes its widget).
        return () => {
          turnstile.waiting.delete(issue)
        }
      }, [])
      return null
    },
  }
})
/** Hands the mounted widget's held token to the form, as Cloudflare does once its check passes. */
const issueToken = () => act(() => turnstile.waiting.forEach((issue) => issue()))

const api = vi.hoisted(() => ({ login: vi.fn(), register: vi.fn(), submitContactForm: vi.fn() }))
vi.mock('@/features/auth/api/auth-api', () => ({
  login: api.login,
  register: api.register,
  getCurrentUserSafe: async () => ({ id: 1, email: 'reader@example.com' }),
  startOAuthWithInvite: vi.fn(),
}))
vi.mock('@/features/contact/api/contact-api', () => ({ submitContactForm: api.submitContactForm }))
const searchParams = new URLSearchParams()
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => searchParams,
}))
vi.mock('@/lib/analytics', () => ({
  default: { loginCompleted: vi.fn(), signupStarted: vi.fn(), signupSubmitted: vi.fn() },
}))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}))
vi.mock('@/features/auth/components/SocialAuthButtons', () => ({ default: () => null }))
// The login page's registration read (its link for a visitor without an account) is answered here, never by the network.
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: async () => null }))

afterEach(() => {
  turnstile.on = false
  turnstile.mounts = 0
  turnstile.hold = false
  turnstile.waiting.clear()
  api.login.mockReset()
  api.register.mockReset()
  api.submitContactForm.mockReset()
})

interface FormUnderTest {
  /** Renders the form with its fields filled. */
  open: () => void
  submit: string
  call: Mock
  /** The Turnstile token each call sent. */
  tokens: () => unknown[]
  refusal: ApiError
}

const FORMS: Array<[string, FormUnderTest]> = [
  ['the sign-in form', {
    open: () => {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      render(<QueryClientProvider client={client}><LoginPage /></QueryClientProvider>)
      fireEvent.click(screen.getByRole('button', { name: 'Continue with email' }))
      fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader@example.com' } })
      fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } })
    },
    submit: 'Log in',
    call: api.login,
    tokens: () => api.login.mock.calls.map(([, , token]) => token),
    refusal: new ApiError(401, 'Incorrect email or password'),
  }],
  ['the register form', {
    open: () => {
      render(<RegisterForm inviteOnly={false} betaPromoActive={false} />)
      fireEvent.click(screen.getByRole('button', { name: /sign up with email/i }))
      fireEvent.click(screen.getByRole('checkbox', { name: /at least 18/i }))
      fireEvent.click(screen.getByRole('checkbox', { name: /agree to the/i }))
      fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'person@example.com' } })
      fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'a-long-enough-passphrase' } })
    },
    submit: 'Create account',
    call: api.register,
    tokens: () => api.register.mock.calls.map(([, , , token]) => token),
    refusal: new ApiError(400, 'Registration failed'),
  }],
  ['the contact form', {
    open: () => {
      render(<ContactForm />)
      fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
      fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.com' } })
      fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: 'A message long enough.' } })
    },
    submit: 'Send message',
    call: api.submitContactForm,
    tokens: () => api.submitContactForm.mock.calls.map(([, token]) => token),
    refusal: new ApiError(500, 'Failed to save contact form submission'),
  }],
]

describe.each(FORMS)('%s with Turnstile on', (_, form) => {
  beforeEach(() => {
    turnstile.on = true
  })

  it('holds the submit busy and aria-disabled, never natively disabled, while its request is in flight', async () => {
    form.call.mockReturnValueOnce(new Promise(() => {}))
    form.open()
    const button = screen.getByRole('button', { name: form.submit })
    fireEvent.click(button)
    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).not.toBeDisabled()
  })

  it('sends a new token on the retry after a refused submit', async () => {
    form.call.mockRejectedValueOnce(form.refusal).mockRejectedValueOnce(form.refusal)
    form.open()
    fireEvent.click(screen.getByRole('button', { name: form.submit }))
    await screen.findByRole('alert')
    fireEvent.click(screen.getByRole('button', { name: form.submit }))
    await waitFor(() => expect(form.call).toHaveBeenCalledTimes(2))
    expect(form.tokens()).toEqual(['token-1', 'token-2'])
  })

  describe('while a token comes', () => {
    beforeEach(() => {
      turnstile.hold = true
    })

    async function refusedFromTheButton() {
      form.open()
      issueToken()
      const button = screen.getByRole('button', { name: form.submit })
      button.focus()
      form.call.mockRejectedValueOnce(form.refusal)
      await userEvent.keyboard('{Enter}')
      await screen.findByRole('alert')
      return button
    }

    it('keeps focus on the button through the renewal, unable to act until the new token', async () => {
      const button = await refusedFromTheButton()
      expect(document.activeElement).toBe(button)
      expect(button).not.toBeDisabled()
      expect(button).toHaveAttribute('aria-disabled', 'true')
      issueToken()
      expect(document.activeElement).toBe(button)
      expect(button).not.toHaveAttribute('aria-disabled')
    })

    it('sends nothing on a press or Enter while the token renews, and the new token on the next press', async () => {
      const button = await refusedFromTheButton()
      await userEvent.keyboard('{Enter}')
      await userEvent.click(button)
      fireEvent.submit(button.closest('form')!)
      await act(async () => {})
      expect(form.call).toHaveBeenCalledTimes(1)

      issueToken()
      form.call.mockRejectedValueOnce(form.refusal)
      await userEvent.keyboard('{Enter}')
      await waitFor(() => expect(form.call).toHaveBeenCalledTimes(2))
      expect(form.tokens()).toEqual(['token-1', 'token-2'])
    })

    it("refuses a press's default while the token comes, so the browser's own validation never starts", async () => {
      form.open()
      const button = screen.getByRole('button', { name: form.submit })
      // A required field left empty, as by a reader who presses before typing it.
      const field = button.closest('form')!.querySelector<HTMLInputElement>('input[required]')!
      fireEvent.change(field, { target: { value: '' } })
      const invalid = vi.fn()
      field.addEventListener('invalid', invalid)
      fireEvent.click(button)
      field.focus()
      await userEvent.keyboard('{Enter}')
      expect(invalid).not.toHaveBeenCalled()
      expect(document.activeElement).toBe(field)

      // With the token, a press is the browser's again: it validates, finds the empty field and sends nothing.
      issueToken()
      fireEvent.click(button)
      expect(invalid).toHaveBeenCalledTimes(1)
      expect(form.call).not.toHaveBeenCalled()
    })

    it('waits for the first token the same way: focusable, and the first press after it sends token-1', async () => {
      form.open()
      const button = screen.getByRole('button', { name: form.submit })
      button.focus()
      expect(button).not.toBeDisabled()
      expect(button).toHaveAttribute('aria-disabled', 'true')
      await userEvent.keyboard('{Enter}')
      expect(form.call).not.toHaveBeenCalled()

      issueToken()
      expect(document.activeElement).toBe(button)
      form.call.mockRejectedValueOnce(form.refusal)
      await userEvent.keyboard('{Enter}')
      await waitFor(() => expect(form.call).toHaveBeenCalledTimes(1))
      expect(form.tokens()).toEqual(['token-1'])
    })
  })
})

describe('the contact form after a sent message', () => {
  it("waits for a new token on 'Send another message' and sends it", async () => {
    turnstile.on = true
    turnstile.hold = true
    api.submitContactForm.mockResolvedValueOnce(undefined).mockResolvedValueOnce(undefined)
    FORMS[2][1].open()
    issueToken()
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Send another message' }))

    // The form comes back waiting: the spent token is gone, and the new widget's token has not come.
    const button = screen.getByRole('button', { name: 'Send message' })
    expect(button).toHaveAttribute('aria-disabled', 'true')
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: 'Ada Lovelace' } })
    fireEvent.change(screen.getByLabelText(/^Email/), { target: { value: 'ada@example.com' } })
    fireEvent.change(screen.getByLabelText(/^Message/), { target: { value: 'A second message, long enough.' } })
    fireEvent.click(button)
    await act(async () => {})
    expect(api.submitContactForm).toHaveBeenCalledTimes(1)

    issueToken()
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
    await waitFor(() => expect(api.submitContactForm).toHaveBeenCalledTimes(2))
    expect(api.submitContactForm.mock.calls.map(([, token]) => token)).toEqual(['token-1', 'token-2'])
  })
})

// These cases exercise the form after release; legalReadiness.spec.tsx holds the closed and stale gates.
vi.mock('@/features/legal/hooks/useLegalReadiness', async () => {
  const { readyLegalHook } = await import('./fixtures/legalReady')
  return { useLegalReadiness: () => readyLegalHook }
})
